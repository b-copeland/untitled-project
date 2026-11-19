"""Cluster politics (clusters.py): the level math, the leader's vote, the read view and the refresh's alignment sync."""
import datetime

import pytest

import untitledapp.admin as admin
import untitledapp.clusters as clusters
import untitledapp.shared as uas
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


def test_modifiers_are_the_level_times_the_max(config):
    cluster = clusters.normalize({"levels": {"drone_production": 0.5, "unit_cost": 1.0}})
    assert clusters.modifiers(cluster) == pytest.approx(
        {"drone_production": 0.075, "unit_cost": 0.05, "settle_cost": 0.0})


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


def test_a_vote_can_be_withdrawn(app, client, jwt1):
    _cluster_of_two_galaxies()
    client.post("/api/cluster/vote", json={"benefit": "unit_cost"}, headers=_auth(jwt1))
    response = client.post("/api/cluster/vote", json={"benefit": None}, headers=_auth(jwt1))
    assert response.status_code == 200
    assert _get("/cluster/1")["votes"] == {}


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
    assert view["cluster"] == "1" and view["galaxy"] == "1:1" and view["is_leader"] is True
    assert [galaxy["id"] for galaxy in view["galaxies"]] == ["1:1", "1:2"]  # not 2:1
    assert view["galaxies"][0]["vote"] == "unit_cost"
    assert view["benefits"]["unit_cost"]["votes"] == 1
    assert set(view["benefits"]) == set(uas.CLUSTER_BENEFITS)


def test_the_view_tells_a_non_leader_they_are_not(app, client, jwt2):
    _cluster_of_two_galaxies(leader2="")
    view = client.get("/api/cluster", headers=_auth(jwt2)).get_json()
    assert view["is_leader"] is False


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
