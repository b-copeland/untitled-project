"""
Empire targets (api/untitledapp/targets.py): marking targets, participation points, the spoils fund and its payouts.

Empire "e1" is galaxies "1:1" (kingdom 1, ``jwt1``, the emperor) and "1:2" (kingdom 2, ``jwt2``). The target, 5, is in
galaxy "1:3", outside the empire.
"""
import datetime

import pytest

import untitledapp.conquer as uac
import untitledapp.shared as uas
import untitledapp.targets as uat

from tests.test_concurrency import KD_ID, _create_item, _get, _run_together, _set_up_kingdom  # noqa: F401
from tests.test_politics import _empire_politics, _galaxy_politics

NOW = datetime.datetime(2026, 11, 20, 12, 0, tzinfo=datetime.timezone.utc)
MEMBER = "2"
TARGET = "5"
UNITS = {"attack": 0, "defense": 0, "flex": 0, "recruits": 0, "engineers": 0, "big_flex": 0}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _entry(**fields):
    return {**uat.new_target(TARGET, {"successful_attacks": 1.0}, 0.1, KD_ID, NOW), **fields}


# --- the rules, on plain documents ---------------------------------------------------------------------------------

def test_points_scale_with_the_damage_done_and_the_multiplier():
    assert uat.points_for("kidnap", {"population": 1000}) == pytest.approx(2 * uat.points_for("kidnap", {"population": 500}))
    assert uat.points_for("kidnap", {"population": 1000}, 2.0) == pytest.approx(2 * uat.points_for("kidnap", {"population": 1000}))
    assert uat.points_for("kidnap", {"population": 0}) == 0
    # Missiles count each kind of damage they do.
    rates = uas.TARGET_ACTIONS["missiles"]["points"]
    assert uat.points_for("missiles", {"stars": 2, "population": 100, "fuel": 1000}) == pytest.approx(
        2 * rates["stars"] + 100 * rates["population"] + 1000 * rates["fuel"])


def test_the_fund_takes_its_share_of_stars_and_money_and_leaves_the_rest():
    spoils = {"stars": 101, "population": 50, "money": 1000, "fuel": 30, "funding": {"settle": 55, "military": 0}}
    attacker, fund = uat.fund_split(spoils, 0.1)
    assert fund == {"stars": 10, "money": 100 + 5}
    assert attacker == {"stars": 91, "population": 50, "money": 900, "fuel": 30, "funding": {"settle": 50, "military": 0}}
    assert uat.fund_split(spoils, 0) == (spoils, {"stars": 0, "money": 0})


def test_payouts_are_in_proportion_to_points_and_round_down():
    shares = uat.payout_shares({"1": 30, "2": 10, "3": 0}, {"stars": 101, "money": 1001})
    assert shares == {"1": {"stars": 75, "money": 750}, "2": {"stars": 25, "money": 250}}
    assert uat.payout_shares({}, {"stars": 10, "money": 10}) == {}


def test_a_fund_is_paid_out_at_most_once_per_cooldown():
    entry = _entry(points={"1": 5}, fund={"stars": 10, "money": 0})
    assert uat.payout_problem(entry, NOW) is None
    shares = uat.pay_out(entry, NOW)
    assert shares == {"1": {"stars": 10, "money": 0}}
    assert entry["fund"] == {"stars": 0, "money": 0} and entry["paid"] == {"1": {"stars": 10, "money": 0}}
    entry["fund"] = {"stars": 10, "money": 0}
    assert "again in" in uat.payout_problem(entry, NOW + datetime.timedelta(seconds=1))
    later = NOW + datetime.timedelta(seconds=uas.GAME_CONFIG["TARGET_PAYOUT_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] + 1)
    assert uat.payout_problem(entry, later) is None


def test_an_empty_fund_or_no_participants_can_not_be_paid_out():
    assert "empty" in uat.payout_problem(_entry(points={"1": 5}), NOW)
    assert "Nobody" in uat.payout_problem(_entry(fund={"stars": 10, "money": 0}), NOW)


def test_only_intel_the_empire_did_not_have_earns_points():
    entry = _entry(actions={"intel": 1.0})
    until = NOW + datetime.timedelta(hours=4)
    earned, new = uat.record_intel(entry, ["military"], until, "1", NOW)
    assert new == ["military"] and earned == pytest.approx(uas.TARGET_ACTIONS["intel"]["points"]["categories"])
    earned, new = uat.record_intel(entry, ["military", "shields"], until + datetime.timedelta(hours=1), "2", NOW)
    assert new == ["shields"]
    assert entry["points"] == {"1": pytest.approx(earned), "2": pytest.approx(earned)}
    assert entry["intel"]["military"] == (until + datetime.timedelta(hours=1)).isoformat()  # the later expiry is kept
    # Once the empire's intel has run out, it counts as new again.
    _, new = uat.record_intel(entry, ["military"], until + datetime.timedelta(hours=8), "1", until + datetime.timedelta(hours=2))
    assert new == ["military"]


def test_only_marked_actions_earn_points_but_the_fund_always_fills():
    entry = _entry()
    assert uat.record_damage(entry, "kidnap", {"population": 1000}, {"stars": 3, "money": 0}, "1") == 0
    assert entry["points"] == {} and entry["fund"] == {"stars": 3, "money": 0}


def test_ending_a_target_pays_everything_out_and_keeps_it_in_the_history():
    document = uat.normalize({"targets": {TARGET: _entry(points={"1": 1, "2": 3}, fund={"stars": 10, "money": 100})}})
    shares = uat.end(document, TARGET, "removed", KD_ID, NOW, extra_fund={"stars": 2, "money": 0})
    assert shares == {"1": {"stars": 3, "money": 25}, "2": {"stars": 9, "money": 75}}
    assert document["targets"] == {}
    record = document["history"][0]
    assert record["reason"] == "removed" and record["lost"] == {"stars": 0, "money": 0}
    # With nobody to pay, the fund is lost.
    document = uat.normalize({"targets": {TARGET: _entry(fund={"stars": 10, "money": 100})}})
    assert uat.end(document, TARGET, "killed", None, NOW) == {}
    assert document["history"][0]["lost"] == {"stars": 10, "money": 100}


def test_bad_actions_and_fund_shares_are_refused():
    for value in (None, {}, {"dance": 1}, {"kidnap": -1}, {"kidnap": uas.GAME_CONFIG["TARGET_MAX_POINTS_MULTIPLIER"] + 1},
                  {"kidnap": "lots"}, {"kidnap": False}):
        with pytest.raises(ValueError):
            uat.parse_actions(value)
    assert uat.parse_actions({"kidnap": True, "intel": 2, "missiles": None}) == {"kidnap": 1.0, "intel": 2.0}
    assert uat.parse_fund_share(None) == uas.GAME_CONFIG["TARGET_DEFAULT_FUND_SHARE"]
    assert uat.parse_fund_share("25") == pytest.approx(0.25)
    with pytest.raises(ValueError):
        uat.parse_fund_share(str(uas.GAME_CONFIG["TARGET_MAX_FUND_SHARE"] * 100 + 1))


# --- the routes ------------------------------------------------------------------------------------------------------

def _set_up_empire(target_overrides=None, attacker_overrides=None, galaxies=2):
    _set_up_kingdom(money=1_000_000, units={**UNITS, "attack": 1000}, **(attacker_overrides or {}))
    _set_up_kingdom(money=1_000_000, kd_id=MEMBER)
    target = {"money": 1_000_000, "units": {**UNITS, "defense": 10}}
    target.update(target_overrides or {})
    _set_up_kingdom(kd_id=TARGET, **target)
    empire_galaxies = ["1:1", "1:2", "1:4"][:galaxies]
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": [MEMBER], "1:3": [TARGET], "1:4": []}})
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Emperor", MEMBER: "Member", TARGET: "Target"}})
    for galaxy, leader in (("1:1", KD_ID), ("1:2", MEMBER), ("1:3", TARGET), ("1:4", "")):
        _create_item(f"galaxy_votes_{galaxy}", _galaxy_politics(leader=leader))
        _create_item(f"galaxy_news_{galaxy}", {"news": []})
    empire = {"name": "One", "galaxies": empire_galaxies, "war": [], "peace": {}, "denounced": "", "aggression": {},
              "aggression_max": 100, "surprise_war_penalty": False}
    _create_item("empires", {"empires": {"e1": empire}})
    _create_item("empire_politics_e1", _empire_politics("1:1"))


def _add(client, token=None, target=TARGET, actions=None, fund_share=10, jwt=None):
    return client.post("/api/empiretargets/add", headers=_auth(jwt),
                       json={"target": target, "actions": actions or {"successful_attacks": 1, "failed_attacks": 1,
                                                                      "missiles": 1, "kidnap": 1, "intel": 1},
                             "fund_share": fund_share})


def _targets():
    return uat.normalize(_get("/empire/e1/targets"))


def test_the_emperor_marks_a_target_and_the_empire_sees_it(app, client, jwt1, jwt2):
    _set_up_empire()
    response = _add(client, jwt=jwt1)
    assert response.status_code == 200, response.get_json()
    assert TARGET in _targets()["targets"]
    assert _get("/empires")["empires"]["e1"]["targets"] == [TARGET]

    view = client.get("/api/empiretargets", headers=_auth(jwt2)).get_json()
    assert view["can_manage"] is False and view["is_emperor"] is False
    assert [target["target"] for target in view["targets"]] == [TARGET]
    assert view["targets"][0]["name"] == "Target"
    assert client.get("/api/empiretargets", headers=_auth(jwt1)).get_json()["is_emperor"] is True
    # Nobody learns the empire's targets from the empires list.
    assert "targets" not in client.get("/api/empires", headers=_auth(jwt2)).get_json()["e1"]


def test_only_leadership_manages_targets_and_only_the_emperor_names_delegates(app, client, jwt1, jwt2):
    _set_up_empire()
    response = _add(client, jwt=jwt2)
    assert response.status_code == 400 and "emperor" in response.get_json()["message"]
    assert _get("/empires")["empires"]["e1"].get("targets", []) == []  # refused before the hint was touched

    assert client.post("/api/empiretargets/delegates", headers=_auth(jwt2), json={"delegates": [MEMBER]}).status_code == 400
    assert client.post("/api/empiretargets/delegates", headers=_auth(jwt1), json={"delegates": [TARGET]}).status_code == 400
    response = client.post("/api/empiretargets/delegates", headers=_auth(jwt1), json={"delegates": [MEMBER]})
    assert response.status_code == 200, response.get_json()
    assert _add(client, jwt=jwt2).status_code == 200
    assert client.post(f"/api/empiretargets/{TARGET}/update", headers=_auth(jwt2),
                       json={"actions": {"kidnap": 2}, "fund_share": 20}).status_code == 200
    entry = _targets()["targets"][TARGET]
    assert entry["actions"] == {"kidnap": 2.0} and entry["fund_share"] == pytest.approx(0.2)


def test_an_empire_has_at_most_one_target_per_galaxy_and_never_its_own_kingdoms(app, client, jwt1):
    _set_up_empire(galaxies=1)
    assert "own empire" in _add(client, jwt=jwt1, target=KD_ID).get_json()["message"]
    assert _add(client, jwt=jwt1).status_code == 200
    assert "already" in _add(client, jwt=jwt1).get_json()["message"]
    assert "at most 1" in _add(client, jwt=jwt1, target=MEMBER).get_json()["message"]
    assert "no such" in _add(client, jwt=jwt1, target="99").get_json()["message"].lower()


def test_a_dead_kingdom_can_not_be_targeted(app, client, jwt1):
    _set_up_empire(target_overrides={"status": "Dead"})
    assert "dead" in _add(client, jwt=jwt1).get_json()["message"]


def _attack(client, jwt, units=1000):
    return client.post(f"/api/attack/{TARGET}", json={"attackerValues": {"attack": units, "generals": 1}},
                       headers=_auth(jwt))


def test_an_attack_on_a_target_fills_the_fund_earns_points_and_pays_no_intel_cut(app, client, jwt1):
    _set_up_empire()
    _add(client, jwt=jwt1)
    # Intel bought from a galaxymate would earn its sharer a cut anywhere else.
    _create_item("galaxy_intel_1:1", {"accepted": {KD_ID: {TARGET: {"military": {
        "sharer": "3", "cut": 0.2, "time": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)).isoformat(),
        "source": "market", "accepted_at": NOW.isoformat()}}}}})
    attacker0, target0 = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET}")

    response = _attack(client, jwt1)

    assert response.status_code == 200 and response.get_json()["status"] == "success", response.get_json()
    assert "spoils fund" in response.get_json()["message"]
    attacker, target = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET}")
    taken = target0["stars"] - target["stars"]
    entry = _targets()["targets"][TARGET]
    assert entry["fund"]["stars"] == taken // 10 and entry["fund"]["money"] > 0
    assert attacker["stars"] - attacker0["stars"] == taken - entry["fund"]["stars"]  # no cut for kingdom 3
    assert entry["points"] == {KD_ID: pytest.approx(taken * uas.TARGET_ACTIONS["successful_attacks"]["points"]["stars"])}


def test_a_failed_attack_on_a_target_earns_points_for_the_units_it_destroyed(app, client, jwt1):
    _set_up_empire(target_overrides={"units": {**UNITS, "defense": 100_000}})
    _add(client, jwt=jwt1)
    target0 = _get(f"/kingdom/{TARGET}")

    response = _attack(client, jwt1)

    assert response.get_json()["status"] == "failure"
    destroyed = target0["units"]["defense"] - _get(f"/kingdom/{TARGET}")["units"]["defense"]
    assert destroyed > 0
    assert _targets()["targets"][TARGET]["points"][KD_ID] == pytest.approx(
        destroyed * uas.TARGET_ACTIONS["failed_attacks"]["points"]["units"])
    assert _targets()["targets"][TARGET]["fund"] == {"stars": 0, "money": 0}


def test_an_attack_on_a_kingdom_that_is_not_a_target_records_nothing(app, client, jwt1):
    _set_up_empire()
    response = _attack(client, jwt1)
    assert response.get_json()["status"] == "success"
    assert _targets()["targets"] == {}


def test_missiles_put_every_star_they_destroy_into_the_fund(app, client, jwt1):
    _set_up_empire()
    kingdom = _get(f"/kingdom/{KD_ID}")
    _create_item(f"kingdom_{KD_ID}", {**kingdom, "missiles": {**kingdom["missiles"], "planet_busters": 5}})
    _add(client, jwt=jwt1)
    target0 = _get(f"/kingdom/{TARGET}")

    response = client.post(f"/api/launchmissiles/{TARGET}", json={"attackerValues": {"planet_busters": 5}},
                           headers=_auth(jwt1))

    assert response.status_code == 200, response.get_json()
    destroyed = target0["stars"] - _get(f"/kingdom/{TARGET}")["stars"]
    entry = _targets()["targets"][TARGET]
    assert destroyed > 0 and entry["fund"]["stars"] == destroyed
    assert entry["points"][KD_ID] > 0


def _spy(client, jwt, operation, drones=1000):
    return client.post(f"/api/spy/{TARGET}", json={"drones": drones, "shielded": False, "operation": operation},
                       headers=_auth(jwt))


def test_a_kidnap_on_a_target_earns_points_for_the_civilians_taken(app, client, jwt1, monkeypatch):
    _set_up_empire(attacker_overrides={"drones": 100_000})
    _add(client, jwt=jwt1)
    monkeypatch.setattr(uac.random, "uniform", lambda a, b: a)  # every operation succeeds
    target0 = _get(f"/kingdom/{TARGET}")

    response = _spy(client, jwt1, "kidnappopulation", drones=50_000)

    assert response.get_json()["status"] == "success", response.get_json()
    kidnapped = target0["population"] - _get(f"/kingdom/{TARGET}")["population"]
    assert kidnapped > 0
    assert _targets()["targets"][TARGET]["points"][KD_ID] == pytest.approx(
        kidnapped * uas.TARGET_ACTIONS["kidnap"]["points"]["population"])


def test_intel_on_a_target_is_shared_with_the_empire_and_earns_points_once(app, client, jwt1, monkeypatch):
    _set_up_empire(attacker_overrides={"drones": 100_000})
    _add(client, jwt=jwt1)
    monkeypatch.setattr(uac.random, "uniform", lambda a, b: a)

    assert _spy(client, jwt1, "spymilitary").get_json()["status"] == "success"

    assert "military" in _get(f"/kingdom/{MEMBER}/revealed")["revealed"][TARGET]
    entry = _targets()["targets"][TARGET]
    first = entry["points"][KD_ID]
    assert first == pytest.approx(uas.TARGET_ACTIONS["intel"]["points"]["categories"])
    assert "military" in entry["intel"]
    # Spying for the same intel again earns nothing.
    assert _spy(client, jwt1, "spymilitary").get_json()["status"] == "success"
    assert _targets()["targets"][TARGET]["points"][KD_ID] == pytest.approx(first)


def _with_fund(points, fund, last_payout=None):
    entry = uat.new_target(TARGET, {"successful_attacks": 1.0}, 0.1, KD_ID, NOW)
    entry.update(points=points, fund=fund, last_payout=last_payout)
    _create_item("empire_targets_e1", {"targets": {TARGET: entry}})
    empires = _get("/empires")
    empires["empires"]["e1"]["targets"] = [TARGET]
    _create_item("empires", {"empires": empires["empires"]})


def test_a_payout_credits_participants_in_proportion_to_their_points(app, client, jwt1, jwt2):
    _set_up_empire()
    _with_fund({KD_ID: 1, MEMBER: 3}, {"stars": 100, "money": 1000})
    stars1, stars2 = _get(f"/kingdom/{KD_ID}")["stars"], _get(f"/kingdom/{MEMBER}")["stars"]

    assert client.post(f"/api/empiretargets/{TARGET}/payout", headers=_auth(jwt2)).status_code == 400  # not leadership
    response = client.post(f"/api/empiretargets/{TARGET}/payout", headers=_auth(jwt1))

    assert response.status_code == 200, response.get_json()
    assert _get(f"/kingdom/{KD_ID}")["stars"] == stars1 + 25
    assert _get(f"/kingdom/{MEMBER}")["stars"] == stars2 + 75
    entry = _targets()["targets"][TARGET]
    assert entry["fund"] == {"stars": 0, "money": 0}
    assert entry["paid"][MEMBER] == {"stars": 75, "money": 750}
    assert entry["points"] == {KD_ID: 1, MEMBER: 3}  # points last for the whole target


@pytest.mark.parametrize("repeat", range(2))
def test_racing_payouts_pay_out_once(app, client, jwt1, repeat):
    _set_up_empire()
    _with_fund({KD_ID: 1, MEMBER: 1}, {"stars": 100, "money": 0})
    stars2 = _get(f"/kingdom/{MEMBER}")["stars"]

    responses = _run_together(app, 6, lambda c, i: c.post(f"/api/empiretargets/{TARGET}/payout", headers=_auth(jwt1)))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 5, [r.get_json() for r in responses]
    assert _get(f"/kingdom/{MEMBER}")["stars"] == stars2 + 50


def test_removing_a_target_pays_out_its_fund_and_keeps_it_in_the_history(app, client, jwt1):
    _set_up_empire()
    _with_fund({MEMBER: 1}, {"stars": 40, "money": 0}, last_payout=datetime.datetime.now(datetime.timezone.utc).isoformat())
    stars2 = _get(f"/kingdom/{MEMBER}")["stars"]

    response = client.post(f"/api/empiretargets/{TARGET}/remove", headers=_auth(jwt1))

    assert response.status_code == 200, response.get_json()
    assert _get(f"/kingdom/{MEMBER}")["stars"] == stars2 + 40  # the cooldown does not hold back the final payout
    document = _targets()
    assert document["targets"] == {} and document["history"][0]["reason"] == "removed"
    assert _get("/empires")["empires"]["e1"]["targets"] == []
    view = client.get("/api/empiretargets", headers=_auth(jwt1)).get_json()
    assert view["history"][0]["name"] == "Target"


def test_killing_a_target_puts_its_remains_in_the_fund_and_ends_it(app, client, jwt1):
    _set_up_empire(target_overrides={"stars": 1, "money": 5000})
    _add(client, jwt=jwt1)

    response = _attack(client, jwt1)

    assert response.get_json()["status"] == "success", response.get_json()
    target = _get(f"/kingdom/{TARGET}")
    assert target["status"] == "Dead" and target["money"] == 0  # its money went into the fund
    document = _targets()
    assert document["targets"] == {}
    record = document["history"][0]
    assert record["reason"] == "killed"
    assert record["paid"][KD_ID]["money"] > 0
    assert _get("/empires")["empires"]["e1"]["targets"] == []


def test_a_death_with_no_empire_target_takes_nothing(app, client):
    _set_up_empire(target_overrides={"status": "Dead", "money": 5000})
    with app.test_request_context():
        uat.on_kingdom_death(TARGET)
    assert _get(f"/kingdom/{TARGET}")["money"] == 5000


# --- what it costs ---------------------------------------------------------------------------------------------------

from tests.test_efficiency import calls  # noqa: E402,F401  (the fixture)


def test_the_targets_tab_reads_each_document_once(app, client, jwt1, calls):
    _set_up_empire()
    calls.clear()
    assert client.get("/api/empiretargets", headers=_auth(jwt1)).status_code == 200
    reads = [path for method, path in calls if method == "GET"]
    assert reads.count("/empire/e1/targets") == 1
    assert len(reads) == len(set(reads)) and len(calls) <= 7, calls


def test_an_attack_on_a_kingdom_no_empire_targets_reads_no_targets(app, client, jwt1, calls):
    _set_up_empire()
    calls.clear()
    assert _attack(client, jwt1).get_json()["status"] == "success"
    assert not [path for _, path in calls if path.endswith("/targets")], calls


def test_a_target_removed_just_before_it_dies_does_not_fail_the_death(app, client, jwt1):
    _set_up_empire(target_overrides={"status": "Dead", "money": 5000})
    empires = _get("/empires")
    empires["empires"]["e1"]["targets"] = [TARGET]  # a hint left behind, with no target in the document
    _create_item("empires", {"empires": empires["empires"]})
    with app.test_request_context():
        uat.on_kingdom_death(TARGET, killer=KD_ID)
    assert _targets()["targets"] == {}
