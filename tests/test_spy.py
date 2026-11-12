"""Spy operations through the real route, including duplicate requests racing."""
import pytest

from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, no_shared_lock, _create_item, _get, _run_together  # noqa: F401


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


def test_scheduling_beyond_the_limit_of_ten_is_refused_even_when_racing(app, client, jwt1):
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
