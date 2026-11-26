"""Moving money between money and the auto spender's funding categories (/api/funding/move)."""
import pytest

from tests.test_concurrency import KD_ID, _get, _run_together, _set_up_kingdom

FUNDING = {"settle": 100, "structures": 200, "military": 300, "engineers": 0}


def _move(client, jwt, source, destination, amount):
    return client.post("/api/funding/move", json={"from": source, "to": destination, "amount": amount},
                       headers={"Authorization": f"Bearer {jwt}"})


def _kingdom(**overrides):
    _set_up_kingdom(money=1_000, **{"auto_spending_enabled": True, "funding": dict(FUNDING), **overrides})


def test_funding_goes_back_to_money(app, client, jwt1):
    _kingdom()
    response = _move(client, jwt1, "military", "money", 120)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["message"] == "Moved 120 from military funding to money"
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["money"] == 1_120 and kingdom["funding"] == {**FUNDING, "military": 180}


def test_funding_moves_between_categories_and_keeps_the_others(app, client, jwt1):
    _kingdom()
    assert _move(client, jwt1, "structures", "engineers", "all").status_code == 200
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["money"] == 1_000 and kingdom["funding"] == {**FUNDING, "structures": 0, "engineers": 200}


def test_money_goes_into_funding_only_while_auto_spending_is_on(app, client, jwt1):
    _kingdom()
    assert _move(client, jwt1, "money", "settle", 400).status_code == 200
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["money"] == 600 and kingdom["funding"]["settle"] == 500

    _kingdom(auto_spending_enabled=False)
    refused = _move(client, jwt1, "money", "settle", 400)
    assert refused.status_code == 400 and "Turn auto spending on" in refused.get_json()["message"]
    # Back to money works with it off.
    assert _move(client, jwt1, "settle", "money", 100).status_code == 200


@pytest.mark.parametrize("source, destination, amount, problem", [
    ("military", "money", 301, "There is only 300 to move"),
    ("money", "money", 1, "Choose two different places"),
    ("engineers", "money", "all", "There is nothing to move"),
])
def test_a_bad_move_is_refused_and_changes_nothing(app, client, jwt1, source, destination, amount, problem):
    _kingdom()
    response = _move(client, jwt1, source, destination, amount)
    assert response.status_code == 400 and response.get_json()["message"] == problem
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["money"] == 1_000 and kingdom["funding"] == FUNDING


@pytest.mark.parametrize("body", [
    {"from": "gold", "to": "money", "amount": 1},
    {"from": "settle", "to": "money", "amount": "nan"},
    {"from": "settle", "to": "money", "amount": 1.5},
    {"from": "settle", "to": "money", "amount": -5},
])
def test_bad_input_is_refused(app, client, jwt1, body):
    _kingdom()
    assert client.post("/api/funding/move", json=body, headers={"Authorization": f"Bearer {jwt1}"}).status_code == 400


def test_two_moves_at_once_can_not_spend_the_same_funding_twice(app, jwt1):
    _kingdom()
    responses = _run_together(app, 4, lambda client, i: _move(client, jwt1, "military", "money", 300))
    assert sorted(r.status_code for r in responses) == [200, 400, 400, 400]
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["money"] == 1_300 and kingdom["funding"]["military"] == 0
