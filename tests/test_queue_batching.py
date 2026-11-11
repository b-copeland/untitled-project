"""Appending to a build queue folds entries that finish within a minute of each other (funcapp/queues.py)."""
import datetime
import json

from untitledapp import REQUESTS_SESSION
from tests.test_concurrency import KD_ID, FUNCTION_URL, _get, _set_up_kingdom, _run_together, no_shared_lock  # noqa: F401


def _now(seconds=0):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1, seconds=seconds)).isoformat()


def _append(table, key, entries):
    return REQUESTS_SESSION.patch(f"{FUNCTION_URL}/kingdom/{KD_ID}/{table}", data=json.dumps({key: entries}))


def test_entries_appended_seconds_apart_are_stored_as_one(app, client):
    _set_up_kingdom(money=0)

    _append("settles", "new_settles", [{"time": _now(0), "amount": 3}])
    _append("settles", "new_settles", [{"time": _now(5), "amount": 4}, {"time": _now(9), "amount": 1}])

    queue = _get(f"/kingdom/{KD_ID}/settles")["settles"]
    assert len(queue) == 1 and queue[0]["amount"] == 8


def test_entries_an_hour_apart_are_kept_separate(app, client):
    _set_up_kingdom(money=0)
    _append("engineers", "new_engineers", [{"time": _now(0), "amount": 3}])
    _append("engineers", "new_engineers", [{"time": _now(3600), "amount": 4}])

    assert [e["amount"] for e in _get(f"/kingdom/{KD_ID}/engineers")["engineers"]] == [3, 4]


def test_every_queue_folds_its_fields(app, client):
    _set_up_kingdom(money=0)
    _append("structures", "new_structures", [{"time": _now(0), "homes": 2}, {"time": _now(2), "homes": 3, "mines": 1}])
    _append("mobis", "new_mobis", [{"time": _now(0), "attack": 2}, {"time": _now(2), "attack": 3}])
    _append("missiles", "new_missiles", [{"time": _now(0), "planet_busters": 2}, {"time": _now(2), "planet_busters": 3}])

    (structures,) = _get(f"/kingdom/{KD_ID}/structures")["structures"]
    (mobis,) = _get(f"/kingdom/{KD_ID}/mobis")["mobis"]
    (missiles,) = _get(f"/kingdom/{KD_ID}/missiles")["missiles"]
    assert (structures["homes"], structures["mines"], mobis["attack"], missiles["planet_busters"]) == (5, 1, 5, 5)


def test_appends_racing_each_other_lose_no_counts_when_they_fold(app, client):
    _set_up_kingdom(money=0)

    _run_together(app, 12, lambda c, i: _append("settles", "new_settles", [{"time": _now(i), "amount": 1}]))

    queue = _get(f"/kingdom/{KD_ID}/settles")["settles"]
    assert sum(entry["amount"] for entry in queue) == 12
    assert len(queue) == 1
