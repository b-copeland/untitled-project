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
from api.untitledapp import REQUESTS_SESSION

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


def _set_up_kingdom(money):
    """A freshly created kingdom 1, in a game that has started, with the given money."""
    game_start = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    _create_item("state", {"state": {"game_start": game_start, "active_policies": []}})
    for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
        state = initial_state.copy()
        if table == "kingdom":
            state["kdId"] = KD_ID
            state["name"] = "Test Kingdom"
            state["money"] = money
        _create_item(f"{table}_{KD_ID}", state)


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
