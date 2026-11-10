"""
End-to-end checks that overlapping requests can not duplicate an action, through the real routes, the function app and
Cosmos (the emulator).

The legacy lock is switched off in every test here. It lives in this process's SQLite file, so a second web app
instance would not share it, and these tests are about what protects the data when it does not: the version check in
the function app (funcapp/concurrency.py) together with api/untitledapp/occ.py.

Needs the function app and Azurite running, like the rest of this directory.
"""
import datetime
import json
import threading

import pytest

import untitledapp.misc as uam
import untitledapp.shared as uas
from api.untitledapp import REQUESTS_SESSION, User

KD_ID = "1"  # user1 in the testing config owns kingdom 1
FUNCTION_URL = "http://localhost:7071/api"


@pytest.fixture(autouse=True)
def no_shared_lock(monkeypatch):
    """Behave like one of several web app instances: no lock state shared with the others."""
    monkeypatch.setattr(uam, "acquire_locks", lambda *args, **kwargs: True)
    monkeypatch.setattr(uam, "release_locks_by_id", lambda *args, **kwargs: None)
    monkeypatch.setattr(uam, "acquire_lock", lambda *args, **kwargs: True)
    monkeypatch.setattr(uam, "release_lock", lambda *args, **kwargs: None)


def _create_item(item, state):
    response = REQUESTS_SESSION.post(f"{FUNCTION_URL}/createitem", data=json.dumps({"item": item, "state": state}))
    assert response.status_code == 201, response.text


def _get(path):
    return json.loads(REQUESTS_SESSION.get(f"{FUNCTION_URL}{path}").text)


def _set_up_kingdom(money, kd_id=KD_ID, **overrides):
    """A freshly created kingdom 1, in a game that has started, with the given money and any other overrides."""
    game_start = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    _create_item("state", {"state": {"game_start": game_start, "active_policies": []}})
    _create_item("galaxies", {"galaxies": {"1": [KD_ID]}})
    _create_item("galaxy_votes_1", {"active_policies": [], "votes": {}})
    for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
        state = initial_state.copy()
        if table == "kingdom":
            state["kdId"] = kd_id
            state["name"] = "Test Kingdom"
            state["money"] = money
            state.update(overrides)
        _create_item(f"{table}_{kd_id}", state)


def _run_together(app, count, request):
    """Start ``count`` requests at the same moment, each with its own client, and collect the responses."""
    gate = threading.Barrier(count)
    responses = [None] * count

    def worker(i):
        client = app.test_client()
        gate.wait()
        responses[i] = request(client, i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return responses


def test_duplicate_build_requests_charge_and_queue_once(app, client, jwt1):
    price = uas.GAME_FUNCS["BASE_STRUCTURE_COST"](int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"]))
    count = 100
    _set_up_kingdom(money=price * count + 10)  # affords exactly one build of 100, with a little left over

    responses = _run_together(
        app,
        6,
        lambda c, i: c.post("/api/structures", json={"homes": count}, headers={"Authorization": f"Bearer {jwt1}"}),
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] + [400] * 5, [response.get_json() for response in responses]

    assert _get(f"/kingdom/{KD_ID}")["money"] == 10  # charged once

    queue = _get(f"/kingdom/{KD_ID}/structures")["structures"]
    queued = sum(amount for batch in queue for name, amount in batch.items() if name != "time")
    assert queued == count  # queued once


def test_shield_changes_made_at_the_same_time_are_all_kept(app, client, jwt1):
    _set_up_kingdom(money=1000)
    _create_item(f"kingdom_{KD_ID}", {"fuel": 1000})
    wanted = {"military": 5, "spy": 10, "spy_radar": 15, "missiles": 40}  # all within the game maximums
    names = list(wanted)

    responses = _run_together(
        app,
        len(names),
        lambda c, i: c.post(
            "/api/shields", json={names[i]: wanted[names[i]]}, headers={"Authorization": f"Bearer {jwt1}"}
        ),
    )

    assert [response.status_code for response in responses] == [200] * len(names)
    shields = _get(f"/kingdom/{KD_ID}")["shields"]
    assert {name: round(shields[name] * 100) for name in names} == wanted


def _post(app, jwt, path, body):
    return lambda c, i: c.post(path, json=body, headers={"Authorization": f"Bearer {jwt}"})


def _queue_length(table):
    return len(next(v for k, v in _get(f"/kingdom/{KD_ID}/{table}").items() if isinstance(v, list)))


# route, request body, queue table the request appends to (or None), kingdom fields that start non-default.
SPENDING_ROUTES = [
    ("/api/recruits", {"recruitsInput": 10}, "mobis", {}),
    ("/api/mobis", {"attack": 5}, "mobis", {"units": {"attack": 0, "defense": 0, "flex": 0, "recruits": 50,
                                                         "engineers": 0, "big_flex": 0}}),
    ("/api/engineers", {"engineersInput": 5}, "engineers", {"structures": {"homes": 0, "mines": 0, "fuel_plants": 0,
                                                                            "hangars": 0, "drone_factories": 0,
                                                                            "missile_silos": 0, "workshops": 10}}),
    ("/api/settle", {"settleInput": 5}, "settles", {}),
    ("/api/missiles", {"planet_busters": 1}, "missiles", {"structures": {"homes": 0, "mines": 0, "fuel_plants": 0,
                                                                          "hangars": 0, "drone_factories": 0,
                                                                          "missile_silos": 10, "workshops": 0}}),
]


@pytest.mark.parametrize("path,body,queue,overrides", SPENDING_ROUTES, ids=[r[0] for r in SPENDING_ROUTES])
def test_racing_duplicates_of_a_spending_route_charge_and_queue_once(app, client, jwt1, path, body, queue, overrides):
    """Money for one request, many arrive together. Compared with what a single request does on its own."""
    rich = 10**7
    _set_up_kingdom(money=rich, **overrides)
    single = client.post(path, json=body, headers={"Authorization": f"Bearer {jwt1}"})
    assert single.status_code == 200, single.get_json()
    cost = rich - _get(f"/kingdom/{KD_ID}")["money"]
    assert cost > 0
    queued_by_one = _queue_length(queue)

    start = cost + 0.5
    _set_up_kingdom(money=start, **overrides)
    responses = _run_together(app, 8, _post(app, jwt1, path, body))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] + [400] * 7, [response.get_json() for response in responses]
    assert _get(f"/kingdom/{KD_ID}")["money"] == pytest.approx(0.5)  # charged once
    assert _queue_length(queue) == queued_by_one  # queued once


def test_racing_disbands_return_the_units_once(app, client, jwt1):
    units = {"attack": 10, "defense": 0, "flex": 0, "recruits": 0, "engineers": 0, "big_flex": 0}
    _set_up_kingdom(money=0, units=units)
    responses = _run_together(app, 8, _post(app, jwt1, "/api/mobis/disband", {"input": {"attack": "10"}}))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["units"]["attack"] == 0
    assert kingdom["money"] == pytest.approx(10 * uas.UNITS["attack"]["cost"] * uas.GAME_CONFIG["BASE_DISBAND_COST_RETURN"])


def test_racing_razes_return_the_money_once(app, client, jwt1):
    structures = {"homes": 10, "mines": 0, "fuel_plants": 0, "hangars": 0, "drone_factories": 0,
                  "missile_silos": 0, "workshops": 0}
    _set_up_kingdom(money=0, structures=structures)
    responses = _run_together(app, 8, _post(app, jwt1, "/api/structures/raze", {"input": {"homes": "10"}}))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["structures"]["homes"] == 0
    assert kingdom["money"] > 0


def test_spending_target_changes_made_at_the_same_time_are_all_kept(app, client, jwt1):
    _set_up_kingdom(money=0)
    kinds = ["homes", "mines", "fuel_plants", "hangars", "drone_factories"]
    responses = _run_together(app, len(kinds), lambda c, i: c.post(
        "/api/structures/target", json={kinds[i]: 10}, headers={"Authorization": f"Bearer {jwt1}"}))

    assert [r.status_code for r in responses] == [200] * len(kinds)
    targets = _get(f"/kingdom/{KD_ID}")["structures_target"]
    assert {k: round(targets[k] * 100) for k in kinds} == {k: 10 for k in kinds}


def test_racing_requests_to_disable_auto_spending_release_the_funding_once(app, client, jwt1):
    funding = {"settle": 100, "structures": 0, "military": 0, "engineers": 0}
    _set_up_kingdom(money=0, funding=funding, auto_spending_enabled=True)
    responses = _run_together(app, 8, _post(app, jwt1, "/api/spending", {"enabled": False}))

    assert [r.status_code for r in responses] == [200] * 8
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["money"] == 100  # released once, not once per request
    assert kingdom["funding"]["settle"] == 0


def test_racing_kingdom_setups_apply_the_choices_once(app, client, jwt1):
    _set_up_kingdom(money=0)
    with app.app_context():
        db = app.extensions["sqlalchemy"]
        user = db.session.query(User).filter_by(username="user1").one()
        user.kd_created = False
        db.session.commit()

    body = {
        "race": "Gaian",
        "unitsChoices": {"drones": 20000, "recruits": 0, "attack": 0, "defense": 0, "flex": 0, "engineers": 0},
        "structuresChoices": {"homes": int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"])},
    }
    responses = _run_together(app, 6, _post(app, jwt1, "/api/createkingdomchoices", body))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 5, [r.get_json() for r in responses]
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["structures"]["homes"] == int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"])


def test_racing_vote_purchases_charge_and_grant_once(app, client, jwt1):
    price = uas.GAME_CONFIG["BASE_VOTES_COST"]
    _set_up_kingdom(money=price * 3 + 5)
    responses = _run_together(app, 8, _post(app, jwt1, "/api/votes", {"votes": 3}))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["money"] == 5
    assert kingdom["votes"] == 3


def test_racing_vote_casts_spend_the_votes_once_and_tally_them_once(app, client, jwt1):
    _set_up_kingdom(money=0, votes=5)
    _create_item("universe_votes", {"votes": {"policy_1": {"1": {}, "2": {}}}})
    body = {"votes": 5, "policy": "policy_1", "option": "1"}
    responses = _run_together(app, 8, _post(app, jwt1, "/api/universepolitics/policies", body))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    assert _get(f"/kingdom/{KD_ID}")["votes"] == 0
    assert _get("/universevotes")["votes"]["policy_1"]["1"][KD_ID] == 5
