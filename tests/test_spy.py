"""Spy operations through the real route, including duplicate requests racing."""
import pytest

import untitledapp.shared as uas

from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get, _run_together, _set_up_kingdom  # noqa: F401

FUTURE = "2999-01-01T00:00:00+00:00"
PAST = "2000-01-01T00:00:00+00:00"


def _spy(client, jwt, operation="suicidedrones", drones=100):
    return client.post(
        f"/api/spy/{TARGET_ID}",
        json={"drones": drones, "shielded": False, "operation": operation},
        headers={"Authorization": f"Bearer {jwt}"},
    )


def test_suicide_drones_burn_the_targets_fuel_and_cost_the_drones(app, client, jwt1):
    _set_up_two_kingdoms()
    attacker0, target0 = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")

    response = _spy(client, jwt1)

    assert response.status_code == 200, response.get_json()
    attacker, target = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")
    assert attacker["drones"] == attacker0["drones"] - 100
    assert attacker["spy_attempts"] == attacker0["spy_attempts"] - 1
    assert target["fuel"] < target0["fuel"]
    assert len(_get(f"/kingdom/{KD_ID}/spyhistory")["spy_history"]) == 1


def test_a_spy_request_without_enough_drones_is_refused(app, client, jwt1):
    _set_up_two_kingdoms()
    before = _get(f"/kingdom/{KD_ID}")
    assert _spy(client, jwt1, drones=10**6).status_code == 400
    after = _get(f"/kingdom/{KD_ID}")
    assert (after["drones"], after["spy_attempts"]) == (before["drones"], before["spy_attempts"])


@pytest.mark.parametrize("repeat", range(3))
def test_racing_duplicate_spy_operations_use_the_attempt_and_drones_once(app, client, jwt1, repeat):
    _set_up_two_kingdoms()
    attacker0 = _get(f"/kingdom/{KD_ID}")
    _create_item(f"kingdom_{KD_ID}", {**attacker0, "spy_attempts": 1})

    responses = _run_together(app, 8, lambda c, i: _spy(c, jwt1))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    attacker = _get(f"/kingdom/{KD_ID}")
    assert attacker["spy_attempts"] == 0
    assert attacker["drones"] == attacker0["drones"] - 100
    assert len(_get(f"/kingdom/{KD_ID}/spyhistory")["spy_history"]) == 1


def test_racing_robs_of_primitives_use_the_attempt_and_drones_once(app, client, jwt1):
    _set_up_two_kingdoms()
    attacker0 = _get(f"/kingdom/{KD_ID}")
    _create_item(f"kingdom_{KD_ID}", {**attacker0, "spy_attempts": 1})

    responses = _run_together(app, 8, lambda c, i: c.post(
        "/api/robprimitives", json={"drones": 100, "shielded": False}, headers={"Authorization": f"Bearer {jwt1}"}))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    attacker = _get(f"/kingdom/{KD_ID}")
    assert attacker["spy_attempts"] == 0 and attacker["drones"] < attacker0["drones"]
    assert attacker["money"] > attacker0["money"]
    assert len(_get(f"/kingdom/{KD_ID}/spyhistory")["spy_history"]) == 1


def test_scheduling_beyond_the_limit_is_refused_even_when_racing(app, client, jwt1, monkeypatch):
    # The real limit is only a guard against bloat (BASE_MAX_SCHEDULE_ENTRIES); a small one keeps the race short.
    monkeypatch.setitem(uas.GAME_CONFIG, "BASE_MAX_SCHEDULE_ENTRIES", 10)
    _set_up_two_kingdoms()
    body = {"type": "attackprimitives", "time": _in_game_time(),
            "options": {"generals": 1, "pure_offense": 50, "flex_offense": 50}}

    responses = _run_together(app, 16, lambda c, i: c.post(
        "/api/schedule", json=body, headers={"Authorization": f"Bearer {jwt1}"}))

    assert sorted(r.status_code for r in responses).count(200) == 10, [r.get_json() for r in responses]
    assert len(_get(f"/kingdom/{KD_ID}")["schedule"]) == 10


def test_scheduled_actions_added_at_the_same_time_are_all_kept_and_one_can_be_cancelled(app, client, jwt1):
    _set_up_two_kingdoms()
    body = {"type": "attackprimitives", "time": _in_game_time(),
            "options": {"generals": 1, "pure_offense": 50, "flex_offense": 50}}
    headers = {"Authorization": f"Bearer {jwt1}"}

    responses = _run_together(app, 5, lambda c, i: c.post("/api/schedule", json=body, headers=headers))

    assert [r.status_code for r in responses] == [200] * 5
    schedule = _get(f"/kingdom/{KD_ID}")["schedule"]
    assert len(schedule) == 5
    assert schedule[0]["options"]["pure_offense"] == 0.5  # rescaled once, not once per retry
    assert client.post("/api/schedule/cancel", json={"id": schedule[0]["id"]}, headers=headers).status_code == 200
    assert len(_get(f"/kingdom/{KD_ID}")["schedule"]) == 4


def _in_game_time():
    import datetime
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat()


@pytest.mark.parametrize("repeat", range(4))
def test_a_blank_cut_is_the_same_as_none(app, client, jwt1, repeat):
    """The Spy page sends the cut box as typed; empty used to crash the route with a 500 whenever the spy succeeded."""
    _set_up_two_kingdoms()
    response = client.post(
        f"/api/spy/{TARGET_ID}",
        json={"drones": 1000, "shielded": False, "operation": "spymilitary", "share_to_galaxy": False, "cut": ""},
        headers={"Authorization": f"Bearer {jwt1}"},
    )
    assert response.status_code == 200, response.get_json()


def test_the_spy_forecast_carries_the_servers_own_success_chance(app, client, jwt1):
    _set_up_two_kingdoms()
    response = client.post(
        f"/api/calculatespy/{TARGET_ID}",
        json={"drones": 10, "shielded": False, "operation": "spymilitary",
              "defenderValues": {"drones": "100", "stars": "100", "shields": "0"}},
        headers={"Authorization": f"Bearer {jwt1}"},
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert 0 < body["success_chance"] <= 1
    assert f"{body['success_chance']:.2%}" in body["message"]


def test_the_missile_forecast_gives_damage_as_numbers_as_well_as_a_sentence(app, client, jwt1):
    _set_up_two_kingdoms()
    _create_item(f"kingdom_{KD_ID}", {**_get(f"/kingdom/{KD_ID}"), "missiles": {"planet_busters": 5, "star_busters": 0, "galaxy_busters": 0}})

    response = client.post(f"/api/calculatemissiles/{TARGET_ID}", json={"attackerValues": {"planet_busters": "3"}, "defenderShields": "50"},
                           headers={"Authorization": f"Bearer {jwt1}"})

    body = response.get_json()
    assert response.status_code == 200 and body["message"].startswith("The missiles will destroy")
    assert set(body["damage"]) == {"stars", "fuel", "pop"} and body["damage"]["stars"] > 0
    assert body["shields_assumed"] == 0.5


def test_a_successful_siphon_stores_what_it_will_pay_each_epoch(app, client, jwt1, monkeypatch):
    import untitledapp.conquer as conquer
    import untitledapp.shared as shared

    _set_up_two_kingdoms()
    _create_item(f"siphons_out_{TARGET_ID}", {"siphons_out": []})
    monkeypatch.setattr(conquer.random, "uniform", lambda low, high: low)  # the operation succeeds

    response = _spy(client, jwt1, operation="siphonfunds", drones=120)

    assert response.status_code == 200, response.get_json()
    (siphon,) = _get(f"/kingdom/{TARGET_ID}/siphonsout")["siphons_out"]
    total = 120 * shared.GAME_CONFIG["BASE_DRONES_SIPHON_PER_DRONE"]
    assert siphon["from"] == KD_ID and siphon["siphon"] == total
    assert siphon["rate"] == total / shared.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"]


def _siphon_forecast(client, jwt):
    return client.post(
        f"/api/calculatespy/{TARGET_ID}",
        json={"drones": 100, "shielded": False, "operation": "siphonfunds",
              "defenderValues": {"drones": "100", "stars": "100", "shields": "0"}},
        headers={"Authorization": f"Bearer {jwt}"},
    ).get_json()


@pytest.mark.parametrize("siphons, warned", [
    ([], False),
    ([{"from": KD_ID, "time": FUTURE, "siphon": 500, "rate": 50}], True),       # yours, still running
    ([{"from": int(KD_ID), "time": FUTURE, "siphon": 500, "rate": 50}], True),  # the same, with an int id
    ([{"from": KD_ID, "time": PAST, "siphon": 500, "rate": 50}], False),        # yours, ended
    ([{"from": "99", "time": FUTURE, "siphon": 500, "rate": 50}], False),       # someone else's
], ids=["none", "yours", "yours-int-id", "yours-ended", "someone-elses"])
def test_the_siphon_forecast_warns_when_you_already_siphon_that_kingdom(app, client, jwt1, siphons, warned):
    """#220: a second siphon on the same kingdom is allowed but warned about; siphons elsewhere are not a concern."""
    _set_up_two_kingdoms()
    _create_item(f"siphons_out_{TARGET_ID}", {"siphons_out": siphons})

    body = _siphon_forecast(client, jwt1)

    assert ("warning" in body) is warned, body
    if warned:
        assert body["warning"].startswith("You already have a siphon on this kingdom, with up to 500 money")


@pytest.mark.parametrize("cut, listed", [(10, True), (0, False)])
def test_a_reveal_shared_from_the_spy_page_is_listed_for_a_cut_or_given_free(app, client, jwt1, monkeypatch, cut, listed):
    import untitledapp.conquer as conquer

    _set_up_two_kingdoms()
    _set_up_kingdom(money=0, kd_id="3")
    _create_item("galaxies", {"galaxies": {"1": [KD_ID, "3"], "2": [TARGET_ID]}})
    _create_item("kingdoms", {"kingdoms": {KD_ID: "One", "3": "Three", TARGET_ID: "Target"}})
    monkeypatch.setattr(conquer.random, "uniform", lambda a, b: a)  # every roll succeeds
    response = client.post(
        f"/api/spy/{TARGET_ID}",
        json={"drones": 1000, "shielded": False, "operation": "spymilitary", "share_to_galaxy": True, "cut": cut},
        headers={"Authorization": f"Bearer {jwt1}"},
    )
    assert response.status_code == 200, response.get_json()
    market = _get("/galaxy/1/intel")
    assert bool(market.get("listings")) is listed
    assert (TARGET_ID in _get("/kingdom/3/revealed")["revealed"]) is not listed


def _revealed(kd_id, revealed=None, galaxymates=None):
    import untitledapp.shared as uas
    _create_item(f"revealed_{kd_id}", {**uas.INITIAL_KINGDOM_STATE["revealed"], "revealed": revealed or {},
                                      "revealed_galaxymates": galaxymates or []})


@pytest.mark.parametrize("operation,revealed,galaxymates", [
    ("spymilitary", {"military": FUTURE}, []),                        # spied, or received from a galaxymate
    ("spymilitary", {}, [TARGET_ID]),                                 # the target shares its whole kingdom
    ("spyall", {c: FUTURE for c in uas.REVEAL_OPERATION_STATS["spyall"]}, []),
], ids=["own-or-received", "shared-kingdom", "full-infiltration-all-known"])
def test_a_reveal_of_what_is_already_revealed_is_refused_before_anything_is_spent(app, client, jwt1, operation, revealed, galaxymates):
    """#155: nothing to see, so no drones or attempt spent, and no way to launder received intel into your own."""
    _set_up_two_kingdoms(target_overrides={"completed_projects": []})
    if operation == "spyall":
        _create_item(f"kingdom_{KD_ID}", {**_get(f"/kingdom/{KD_ID}"), "completed_projects": ["vult_evolution"]})
    _revealed(KD_ID, {TARGET_ID: revealed}, galaxymates)
    before = _get(f"/kingdom/{KD_ID}")

    response = _spy(client, jwt1, operation=operation)

    assert response.status_code == 400
    assert response.get_json()["message"].startswith("You already have their ")
    after = _get(f"/kingdom/{KD_ID}")
    assert (after["drones"], after["spy_attempts"]) == (before["drones"], before["spy_attempts"])
    assert _get(f"/kingdom/{KD_ID}/spyhistory")["spy_history"] == []


@pytest.mark.parametrize("operation,revealed", [
    ("spymilitary", {"military": PAST}),            # ended, the refresh has not cleared it yet
    ("spymilitary", {"shields": FUTURE}),           # another category
], ids=["ended", "other-category"])
def test_a_reveal_of_something_not_revealed_now_goes_ahead(app, client, jwt1, operation, revealed):
    _set_up_two_kingdoms()
    _revealed(KD_ID, {TARGET_ID: revealed})
    before = _get(f"/kingdom/{KD_ID}")

    response = _spy(client, jwt1, operation=operation)

    assert response.status_code == 200, response.get_json()
    assert _get(f"/kingdom/{KD_ID}")["spy_attempts"] == before["spy_attempts"] - 1


def test_full_infiltration_goes_ahead_while_any_of_its_categories_is_not_revealed():
    import datetime
    import untitledapp.conquer as conquer
    now = datetime.datetime.now(datetime.timezone.utc)
    some = {"revealed": {"2": {"military": FUTURE, "shields": FUTURE}}, "revealed_galaxymates": []}
    assert conquer._already_revealed_problem(some, "2", "spyall", now) is None
    assert conquer._already_revealed_problem(some, "2", "spymilitary", now) == "You already have their military revealed"
    assert conquer._already_revealed_problem(some, 2, "spymilitary", now) is not None  # an int id from a schedule
    assert conquer._already_revealed_problem(some, "2", "siphonfunds", now) is None
