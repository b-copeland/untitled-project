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
