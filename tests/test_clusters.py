"""Cluster politics (clusters.py): the level math, the leader's vote, the read view and the refresh's alignment sync."""
import copy
import datetime
import random
import re

import pytest

import untitledapp.admin as admin
import untitledapp.clusters as clusters
import untitledapp.getters as getters
import untitledapp.refresh as refresh
import untitledapp.shared as uas
from tests import kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get, _run_together, _set_up_kingdom  # noqa: F401
from tests.test_politics import _auth, _galaxy_politics

NOW = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
EPOCH = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
RATE = uas.GAME_CONFIG["CLUSTER_VOTE_RATE"]
DECAY = uas.GAME_CONFIG["CLUSTER_DECAY_RATE"]


def _at(epochs):
    return NOW + datetime.timedelta(seconds=epochs * EPOCH)


@pytest.fixture
def config(monkeypatch):
    """The issue's example numbers, whatever the placeholders in shared.py become."""
    monkeypatch.setitem(uas.GAME_CONFIG, "CLUSTER_VOTE_RATE", 0.005)
    monkeypatch.setitem(uas.GAME_CONFIG, "CLUSTER_DECAY_RATE", 0.005)
    monkeypatch.setitem(uas.GAME_CONFIG, "CLUSTER_REF_SIZE", 5)
    monkeypatch.setattr(uas, "CLUSTER_BENEFITS", {
        "drone_production": {"name": "Drones", "desc": "", "max": 0.15, "thresholds": [(1 / 3, 0.8)],
                             "effect": "drone_production"},
        "unit_cost": {"name": "Units", "desc": "", "max": 0.05, "thresholds": [], "effect": "unit_cost"},
        "settle_cost": {"name": "Settle", "desc": "", "max": 0.10, "thresholds": [], "effect": "settle_cost"},
    })


# --- the level math -----------------------------------------------------------------------------------------------

def test_the_issues_worked_example(config):
    galaxies = [f"1:{i}" for i in range(1, 6)]
    document = {
        "votes": {"1:1": "drone_production", "1:2": "drone_production", "1:3": "drone_production",
                  "1:4": "unit_cost", "1:5": "unit_cost"},
        "levels": {"drone_production": 1 / 3, "unit_cost": 0.0, "settle_cost": 0.5},
        "last_update": NOW.isoformat(),
    }
    levels = clusters.advance(document, galaxies, _at(1))["levels"]
    assert levels["drone_production"] == pytest.approx(1 / 3 + 0.005 * 3 * 0.8 - 0.005)  # past the threshold: +0.7%
    assert levels["unit_cost"] == pytest.approx(0.005 * 2 - 0.005)  # +0.5%
    assert levels["settle_cost"] == pytest.approx(0.5 - 0.005)  # nobody voted: -0.5%


@pytest.mark.parametrize("level, gain", [(0.0, 0.02), (0.3, 0.02), (0.9, 0.0), (0.5, 0.004), (0.2, 0.0065)])
def test_splitting_the_time_gives_the_same_level(level, gain):
    thresholds = [(0.25, 0.8), (0.5, 0.5)]
    whole = clusters.advance_level(level, gain, 0.003, thresholds, 40)
    split = level
    for epochs in (0.3, 7, 0.01, 12.69, 20):
        split = clusters.advance_level(split, gain, 0.003, thresholds, epochs)
    assert split == pytest.approx(whole, abs=1e-9)


def test_no_time_changes_nothing():
    assert clusters.advance_level(0.4, 0.02, 0.003, [(0.25, 0.8)], 0) == 0.4


def test_crossing_a_threshold_is_exact():
    # From 0.2, gaining 0.01 - 0.0 per epoch up to 0.3, then 0.01 * 0.5 above it: 10 epochs, then 10 more at half.
    assert clusters.advance_level(0.2, 0.01, 0.0, [(0.3, 0.5)], 20) == pytest.approx(0.3 + 0.05)


def test_a_level_holds_at_a_threshold_votes_can_keep_but_not_pass():
    # Gains 0.01 below 0.3 and 0.004 above it, against a decay of 0.005: it climbs to 0.3 and stays.
    assert clusters.advance_level(0.1, 0.01, 0.005, [(0.3, 0.4)], 1000) == pytest.approx(0.3)
    assert clusters.advance_level(0.6, 0.01, 0.005, [(0.3, 0.4)], 1000) == pytest.approx(0.3)


def test_levels_stay_between_zero_and_one():
    assert clusters.advance_level(0.01, 0.0, 0.005, [], 100) == 0.0
    assert clusters.advance_level(0.99, 0.1, 0.0, [], 100) == 1.0


def test_a_unanimous_cluster_gains_the_same_whatever_its_size(config):
    def unanimous(size):
        galaxies = [f"1:{i}" for i in range(1, size + 1)]
        document = {"votes": {g: "unit_cost" for g in galaxies}, "last_update": NOW.isoformat()}
        return clusters.advance(document, galaxies, _at(10))["levels"]["unit_cost"]
    assert unanimous(3) == pytest.approx(unanimous(5)) == pytest.approx(unanimous(8))


def test_votes_from_galaxies_outside_the_cluster_and_unknown_benefits_do_not_count(config):
    document = {"votes": {"2:1": "unit_cost", "1:1": "no_such_thing"}, "last_update": NOW.isoformat()}
    assert clusters.advance(document, ["1:1"], _at(10))["levels"]["unit_cost"] == 0.0


def test_an_empty_document_is_all_zero_and_starts_its_clock(config):
    cluster = clusters.advance({"id": "cluster_1"}, ["1:1"], NOW)
    assert cluster["levels"] == {key: 0.0 for key in uas.CLUSTER_BENEFITS}
    assert cluster["last_update"] == NOW.isoformat()
    assert clusters.modifiers(cluster) == {"drone_production": 0.0, "unit_cost": 0.0, "settle_cost": 0.0}


def test_modifiers_are_the_level_times_the_max_signed_the_way_that_helps(config):
    # A discount is a lower cost, so it comes out negative, as policies give it (shared.EFFECTS).
    cluster = clusters.normalize({"levels": {"drone_production": 0.5, "unit_cost": 1.0}})
    assert clusters.modifiers(cluster) == pytest.approx(
        {"drone_production": 0.075, "unit_cost": -0.05, "settle_cost": 0.0})


def test_rate_matches_what_advance_does(config):
    assert clusters.rate_of(0.5, 0.0, 0.005, []) == -0.005
    assert clusters.rate_of(0.0, 0.0, 0.005, []) == 0.0
    assert clusters.rate_of(0.3, 0.01, 0.005, [(0.3, 0.4)]) == 0.0  # holding at the threshold


def test_alignment_is_the_share_in_the_largest_empire():
    empires = {"a": {"galaxies": ["1:1", "1:2", "2:1"]}, "b": {"galaxies": ["1:3"]}}
    assert clusters.alignment(["1:1", "1:2", "1:3", "1:4"], empires) == 0.5
    assert clusters.alignment(["3:1"], empires) == 0.0
    assert clusters.alignment(["1:1"], {}) == 0.0


def test_members_and_clusters_come_from_galaxy_ids():
    galaxies = {"1:1": [], "1:10": [], "1:2": [], "2:1": []}
    assert clusters.members(galaxies, "1") == ["1:1", "1:2", "1:10"]
    assert clusters.clusters(galaxies) == ["1", "2"]
    assert clusters.cluster_of("12:3") == "12"


def test_createstate_deals_galaxies_into_clusters_in_order():
    assert admin.galaxy_ids(12, 5) == ["1:1", "1:2", "1:3", "1:4", "1:5", "2:1", "2:2", "2:3", "2:4", "2:5",
                                       "3:1", "3:2"]
    assert admin.galaxy_ids(3, 5) == ["1:1", "1:2", "1:3"]  # what a small game always got


# --- the vote and the view, through the routes ---------------------------------------------------------------------

def _cluster_of_two_galaxies(leader1=KD_ID, leader2="2"):
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2")
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"], "2:1": ["3"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=leader1))
    _create_item("galaxy_votes_1:2", _galaxy_politics(leader=leader2))
    _create_item("empires", {"empires": {}})


def test_a_leader_votes_for_their_galaxy(app, client, jwt1):
    _cluster_of_two_galaxies()
    response = client.post("/api/cluster/vote", json={"benefit": "unit_cost"}, headers=_auth(jwt1))
    assert response.status_code == 200, response.get_json()
    stored = _get("/cluster/1")
    assert stored["votes"] == {"1:1": "unit_cost"}
    assert "last_update" in stored


def test_only_the_leader_can_vote(app, client, jwt1):
    _cluster_of_two_galaxies(leader1="")
    response = client.post("/api/cluster/vote", json={"benefit": "unit_cost"}, headers=_auth(jwt1))
    assert response.status_code == 400
    assert "leader" in response.get_json()["message"]
    assert _get("/cluster/1").get("votes") is None


def test_an_unknown_benefit_is_refused(app, client, jwt1):
    _cluster_of_two_galaxies()
    response = client.post("/api/cluster/vote", json={"benefit": "free_money"}, headers=_auth(jwt1))
    assert response.status_code == 400


def _vote(client, jwt, benefit):
    return client.post("/api/cluster/vote", json={"benefit": benefit}, headers=_auth(jwt))


def _clock(monkeypatch, hours_from_now=0.0):
    """Moves the vote routes' clock forward, so a cooldown can pass without waiting."""
    start = datetime.datetime.now(datetime.timezone.utc)
    monkeypatch.setattr(clusters, "_now", lambda: start + datetime.timedelta(hours=hours_from_now))


def test_a_vote_can_be_withdrawn(app, client, jwt1, monkeypatch):
    _cluster_of_two_galaxies()
    _vote(client, jwt1, "unit_cost")
    _clock(monkeypatch, 4)  # past the cooldown
    response = _vote(client, jwt1, None)
    assert response.status_code == 200
    assert _get("/cluster/1")["votes"] == {}


def test_a_changed_vote_is_locked_for_the_cooldown(app, client, jwt1, monkeypatch):
    _cluster_of_two_galaxies()
    cooldown_hours = uas.GAME_CONFIG["CLUSTER_VOTE_COOLDOWN_EPOCHS"] * EPOCH / 3600
    assert _vote(client, jwt1, "unit_cost").status_code == 200  # the first vote is free
    _clock(monkeypatch, 1)
    for benefit in ("settle_cost", None):  # switching and withdrawing are changes too
        refused = _vote(client, jwt1, benefit)
        assert refused.status_code == 400, refused.get_json()
        message = refused.get_json()["message"]
        assert re.search(r"can change again in (2 hours|1 hour 59 minutes)\.", message), message
        assert "epoch" not in message.lower()
    assert _get("/cluster/1")["votes"] == {"1:1": "unit_cost"}
    view = client.get("/api/cluster", headers=_auth(jwt1)).get_json()
    assert view["vote_unlocks_at"] is not None
    assert view["vote_cooldown_hours"] == cooldown_hours

    _clock(monkeypatch, cooldown_hours + 0.01)
    assert _vote(client, jwt1, "settle_cost").status_code == 200
    assert _get("/cluster/1")["votes"] == {"1:1": "settle_cost"}
    _clock(monkeypatch, cooldown_hours + 0.02)  # and that change starts the cooldown again
    assert _vote(client, jwt1, "unit_cost").status_code == 400


def test_the_same_vote_again_changes_nothing_and_starts_no_cooldown(app, client, jwt1, monkeypatch):
    _cluster_of_two_galaxies()
    assert _vote(client, jwt1, None).status_code == 200  # no vote to withdraw
    assert "vote_changed" not in _get("/cluster/1") or _get("/cluster/1")["vote_changed"] == {}
    assert _vote(client, jwt1, "unit_cost").status_code == 200
    stamp = _get("/cluster/1")["vote_changed"]["1:1"]
    _clock(monkeypatch, 1)
    assert _vote(client, jwt1, "unit_cost").status_code == 200  # still unit_cost: allowed, and not a new change
    assert _get("/cluster/1")["vote_changed"]["1:1"] == stamp


def test_each_galaxy_has_its_own_cooldown(app, client, jwt1, jwt2):
    _cluster_of_two_galaxies()
    assert _vote(client, jwt1, "unit_cost").status_code == 200
    assert _vote(client, jwt2, "settle_cost").status_code == 200
    assert _vote(client, jwt1, "settle_cost").status_code == 400
    view = client.get("/api/cluster", headers=_auth(jwt2)).get_json()
    assert view["galaxy"] == "1:2" and view["vote_unlocks_at"] is not None


def test_two_leaders_voting_at_the_same_moment_are_both_counted(app, client, jwt1, jwt2):
    _cluster_of_two_galaxies()
    responses = _run_together(app, 2, lambda c, i: c.post(
        "/api/cluster/vote", json={"benefit": ["unit_cost", "settle_cost"][i]}, headers=_auth([jwt1, jwt2][i])))
    assert [r.status_code for r in responses] == [200, 200]
    assert _get("/cluster/1")["votes"] == {"1:1": "unit_cost", "1:2": "settle_cost"}


def test_the_view_shows_only_the_callers_own_cluster(app, client, jwt1):
    _cluster_of_two_galaxies()
    client.post("/api/cluster/vote", json={"benefit": "unit_cost"}, headers=_auth(jwt1))
    view = client.get("/api/cluster", headers=_auth(jwt1)).get_json()
    assert view["cluster"] == "1" and view["galaxy"] == "1:1"
    assert [galaxy["id"] for galaxy in view["galaxies"]] == ["1:1", "1:2"]  # not 2:1
    assert view["galaxies"][0]["vote"] == "unit_cost"
    assert view["benefits"]["unit_cost"]["votes"] == 1
    # A round made before the draw plays the first benefits.
    assert set(view["benefits"]) == set(list(uas.CLUSTER_BENEFITS)[:uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]])


def test_the_view_shows_the_benefits_in_the_games_order_and_their_forecast(app, client, jwt2):
    _cluster_of_two_galaxies()
    view = client.get("/api/cluster", headers=_auth(jwt2)).get_json()
    assert view["order"] == list(uas.CLUSTER_BENEFITS)[:uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]]
    assert view["benefits"]["unit_cost"]["rate_per_epoch"] == 0  # nothing to lose yet
    assert view["benefits"]["unit_cost"]["effect_text"] == "Military units cost 5% less"  # at its max
    assert view["galaxy"] == "1:2"


def test_state_lists_the_cluster_benefits(app, client):
    _set_up_kingdom(money=0)
    state = client.get("/api/state").get_json()
    assert state["order"]["cluster_benefits"] == list(uas.CLUSTER_BENEFITS)
    assert set(state["cluster_benefits"]) == set(uas.CLUSTER_BENEFITS)


# --- what the benefits do --------------------------------------------------------------------------------------------

def test_the_unit_discount_lowers_every_unit_cost():
    state = {"state": {"active_policies": []}}
    plain = getters._get_units_adjusted_costs(state)
    cheaper = getters._get_units_adjusted_costs(state, {"unit_cost": -0.05})
    for unit, desc in plain.items():
        if "cost" in desc:
            assert cheaper[unit]["cost"] == pytest.approx(desc["cost"] * 0.95)


def test_the_settle_discount_lowers_the_settle_price():
    kd = kingdoms.kingdom()
    base = uas.GAME_FUNCS["BASE_SETTLE_COST"](int(kd["stars"]))
    assert (getters._get_settle_price(kd) - getters._get_settle_price(kd, {"settle_cost": -0.1})) == pytest.approx(base * 0.1)


def test_the_drone_bonus_raises_drone_production(app):
    kd = kingdoms.kingdom(structures={"drone_factories": 100})
    later = kingdoms.START + datetime.timedelta(seconds=EPOCH)
    with app.app_context():
        _set_up_kingdom(0)
        plain = refresh._kingdom_with_income(copy.deepcopy(kd), uas.project_bonuses(kd), {"state": {"active_policies": []}},
                                             later, None, [])
        more = refresh._kingdom_with_income(copy.deepcopy(kd), uas.project_bonuses(kd), {"state": {"active_policies": []}},
                                            later, None, [], {"drone_production": 0.1})
    base = 100 * uas.GAME_CONFIG["BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH"]
    assert more["income"]["drones"] - plain["income"]["drones"] == pytest.approx(base * 0.1)


def _a_cluster_at_full(**levels):
    _create_item("cluster_1", {"levels": levels, "alignment": 0.0,
                               "last_update": datetime.datetime.now(datetime.timezone.utc).isoformat()})


def test_the_settle_page_and_settling_use_the_clusters_discount(app, client, jwt1):
    _set_up_kingdom(money=10**9)
    plain = client.get("/api/settle", headers=_auth(jwt1)).get_json()["settle_price"]
    _a_cluster_at_full(settle_cost=1.0)
    cheaper = client.get("/api/settle", headers=_auth(jwt1)).get_json()["settle_price"]
    stars = int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"])
    max_ = uas.CLUSTER_BENEFITS["settle_cost"]["max"]
    assert plain - cheaper == pytest.approx(uas.GAME_FUNCS["BASE_SETTLE_COST"](stars) * max_, rel=1e-3)

    response = client.post("/api/settle", json={"settleInput": 1}, headers=_auth(jwt1))
    assert response.status_code == 200, response.get_json()
    assert 10**9 - _get("/kingdom/1")["money"] == pytest.approx(cheaper, rel=1e-3)


def test_the_military_page_shows_the_clusters_unit_discount(app, client, jwt1):
    _set_up_kingdom(money=0)
    plain = client.get("/api/mobis", headers=_auth(jwt1)).get_json()["units_desc"]
    _a_cluster_at_full(unit_cost=1.0)
    cheaper = client.get("/api/mobis", headers=_auth(jwt1)).get_json()["units_desc"]
    max_ = uas.CLUSTER_BENEFITS["unit_cost"]["max"]
    assert cheaper["attack"]["cost"] == pytest.approx(plain["attack"]["cost"] * (1 - max_), rel=1e-3)


def test_a_kingdom_whose_cluster_has_no_document_pays_full_price(app, client, jwt1):
    _set_up_kingdom(money=0)
    base = uas.UNITS["attack"]["cost"]
    assert client.get("/api/mobis", headers=_auth(jwt1)).get_json()["units_desc"]["attack"]["cost"] == pytest.approx(base)


def test_the_refresh_context_reads_each_cluster_once(app, monkeypatch):
    reads = []
    monkeypatch.setattr(getters, "_get_galaxies_inverted",
                        lambda: ({"1": "1:1", "2": "1:2", "3": "2:1"}, {"1:1": ["1"], "1:2": ["2"], "2:1": ["3"]}))
    monkeypatch.setattr(getters, "_get_cluster_document", lambda cid: reads.append(cid) or {"levels": {"unit_cost": 1.0}})
    context = refresh._RefreshContext(state={})
    for kd_id in ("1", "2", "3", "1"):
        assert context.cluster_modifiers(kd_id, NOW)["unit_cost"] == -uas.CLUSTER_BENEFITS["unit_cost"]["max"]
    assert reads == ["1", "2"]


# --- the refresh's alignment sync ----------------------------------------------------------------------------------

def test_sync_writes_only_where_the_alignment_changed(app, config):
    _create_item("cluster_1", {"votes": {"1:1": "unit_cost"}, "levels": {}, "alignment": 0.0,
                               "last_update": NOW.isoformat()})
    _create_item("cluster_2", {"alignment": 0.0, "last_update": NOW.isoformat()})
    galaxies = {"1:1": [], "1:2": [], "2:1": []}
    empires = {"e": {"galaxies": ["1:1", "1:2"]}}
    with app.app_context():
        clusters.sync(galaxies, empires, _at(10))
    one = _get("/cluster/1")
    assert one["alignment"] == 1.0
    assert one["last_update"] == _at(10).isoformat()
    assert one["levels"]["unit_cost"] == pytest.approx((0.005 * 5 / 2 - 0.005) * 10)  # advanced at the old alignment
    assert _get("/cluster/2")["last_update"] == NOW.isoformat()  # unchanged, not written


def test_sync_twice_at_the_same_moment_changes_it_once(app, config):
    _create_item("cluster_1", {"votes": {"1:1": "unit_cost"}, "alignment": 0.0, "last_update": NOW.isoformat()})
    galaxies = {"1:1": [], "1:2": []}
    empires = {"e": {"galaxies": ["1:1"]}}
    with app.app_context():
        clusters.sync(galaxies, empires, _at(4))
        first = _get("/cluster/1")
        clusters.sync(galaxies, empires, _at(4))
    assert _get("/cluster/1")["_etag"] == first["_etag"]


# --- the round's draw ------------------------------------------------------------------------------------------------

def test_a_round_draws_its_share_of_the_benefits_in_the_listed_order():
    drawn = clusters.draw(random.Random(4))
    assert len(drawn) == len(set(drawn)) == uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]
    order = list(uas.CLUSTER_BENEFITS)
    assert drawn == sorted(drawn, key=order.index)
    assert clusters.draw(random.Random(4)) == drawn
    assert sorted(clusters.draw(random.Random(1), count=99)) == sorted(uas.CLUSTER_BENEFITS)


def test_the_rounds_benefits_come_from_the_state_and_older_rounds_play_the_first_ones():
    assert clusters.round_benefits({"cluster_benefits": ["pop_growth", "gone"]}) == ["pop_growth"]
    first = list(uas.CLUSTER_BENEFITS)[:uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]]
    assert clusters.round_benefits({}) == first and clusters.round_benefits(None) == first
    assert first[:3] == ["drone_production", "unit_cost", "settle_cost"]  # what older rounds had


def test_only_the_rounds_benefits_are_worth_anything():
    cluster = clusters.normalize({"levels": {"pop_growth": 1.0, "unit_cost": 1.0}})
    assert clusters.modifiers(cluster, ["pop_growth"]) == pytest.approx({"pop_growth": uas.CLUSTER_BENEFITS["pop_growth"]["max"]})


def test_every_benefit_does_something_the_game_knows_and_helps():
    for key, benefit in uas.CLUSTER_BENEFITS.items():
        assert benefit["effect"] in uas.EFFECTS, key
        assert benefit["max"] > 0 and benefit["desc"] and "epoch" not in benefit["desc"].lower(), key


def test_a_vote_for_a_benefit_this_round_does_not_play_is_refused(app, client, jwt1):
    _cluster_of_two_galaxies()
    state = _get("/state")
    _create_item("state", {"state": {**state["state"], "cluster_benefits": ["pop_growth", "shield_fuel"]}})
    refused = client.post("/api/cluster/vote", json={"benefit": "unit_cost"}, headers=_auth(jwt1))
    assert refused.status_code == 400 and refused.get_json()["message"] == "Cheaper Units is not one of this round's benefits"
    unknown = client.post("/api/cluster/vote", json={"benefit": "nope"}, headers=_auth(jwt1))
    assert unknown.status_code == 400 and unknown.get_json()["message"] == "Choose one of this round's benefits"
    assert client.post("/api/cluster/vote", json={"benefit": "shield_fuel"}, headers=_auth(jwt1)).status_code == 200
    view = client.get("/api/cluster", headers=_auth(jwt1)).get_json()
    assert view["order"] == ["pop_growth", "shield_fuel"] and set(view["benefits"]) == {"pop_growth", "shield_fuel"}


def test_a_new_round_draws_the_cluster_benefits_it_plays():
    settings, _ = admin.check_new_round({"game_start": "2030-01-01T00:00:00+00:00", "game_end": "2030-02-01T00:00:00+00:00",
                                         "num_galaxies": 4}, datetime.datetime(2029, 12, 1, tzinfo=datetime.timezone.utc))
    state = admin.round_state(settings, rounds_archived=0, rng=random.Random(2))
    assert len(state["cluster_benefits"]) == uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]
    assert set(state["cluster_benefits"]) <= set(uas.CLUSTER_BENEFITS)


# --- every cluster (#242) -----------------------------------------------------------------------------------------

def test_a_summary_gives_each_benefits_value_and_level_and_their_average_but_no_votes():
    document = {"levels": {key: 0.0 for key in uas.CLUSTER_BENEFITS}, "votes": {"1:1": "unit_cost"}}
    benefits = list(uas.CLUSTER_BENEFITS)[:2]
    document["levels"][benefits[0]] = 0.5
    row = clusters.summary(clusters.normalize(document), "1", ["1:1", "1:2"], benefits)
    assert row["cluster"] == "1" and row["galaxies"] == 2
    assert row["benefits"][benefits[0]] == {"value": 0.5 * uas.CLUSTER_BENEFITS[benefits[0]]["max"], "level": 0.5}
    assert row["average_level"] == 0.25
    assert "votes" not in row and "unit_cost" not in str(row).replace(f"'{benefits[0]}'", "").replace(f"'{benefits[1]}'", "")


def test_the_clusters_route_lists_every_cluster_most_built_up_first(app, client, jwt1):
    _cluster_of_two_galaxies()
    benefit = clusters.round_benefits(_get("/state").get("state"))[0]
    levels = {key: 0.0 for key in uas.CLUSTER_BENEFITS}
    _create_item("cluster_2", {"levels": {**levels, benefit: 0.8}, "votes": {"2:1": benefit},
                               "last_update": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    answer = client.get("/api/clusters", headers=_auth(jwt1)).get_json()
    assert answer["mine"] == "1"
    assert [row["cluster"] for row in answer["clusters"]] == ["2", "1"]
    assert answer["clusters"][0]["benefits"][benefit]["level"] == pytest.approx(0.8, abs=0.01)
    assert set(answer["order"]) == set(answer["names"]) and len(answer["order"]) == uas.GAME_CONFIG["CLUSTER_BENEFITS_PER_ROUND"]
    assert all("votes" not in row for row in answer["clusters"])
