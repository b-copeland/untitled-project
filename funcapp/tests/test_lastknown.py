"""
Tests for a kingdom's last-known intel (``lastknown_<kd_id>``): read without a document, and the merge that keeps the
entry that ended later.

They run the real handlers on the in-memory container (tests/fake_backend.py). Run them from the repo root:

    conda run -n funcapp-worker python -m pytest funcapp/tests
"""
import json
import pathlib
import sys
import threading

import pytest

pytest.importorskip("azure.cosmos")
pytest.importorskip("azure.functions")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tests import fake_backend  # noqa: E402

ENDPOINT = "http://funcapp/api"
EARLY = "2026-11-20T10:00:00+00:00"
LATE = "2026-11-20T12:00:00+00:00"


@pytest.fixture
def backend():
    container = fake_backend.FakeContainer(latency=0.002)
    session = fake_backend.FakeSession(fake_backend.load_function_app(container))
    return container, session


def _patch(session, body, kd_id=1):
    return session.request("PATCH", f"{ENDPOINT}/kingdom/{kd_id}/lastknown", data=json.dumps(body))


def _get(session, kd_id=1):
    return session.request("GET", f"{ENDPOINT}/kingdom/{kd_id}/lastknown")


def test_a_kingdom_with_no_document_reads_empty_and_nothing_is_written(backend):
    container, session = backend
    response = _get(session)
    assert response.status_code == 200
    assert response.json()["known"] == {}
    assert "lastknown_1" not in container.docs


def test_the_first_merge_creates_the_document(backend):
    container, session = backend
    entry = {"ended": EARLY, "values": {"drones": 10}}
    assert _patch(session, {"new_known": {"2": {"drones": entry}}}).status_code == 200
    assert container.docs["lastknown_1"]["known"] == {"2": {"drones": entry}}
    assert _get(session).json()["known"] == {"2": {"drones": entry}}


def test_each_category_keeps_the_entry_that_ended_later(backend):
    container, session = backend
    late = {"ended": LATE, "values": {"drones": 20}}
    early = {"ended": EARLY, "values": {"drones": 10}}
    structures = {"ended": EARLY, "values": {"structures": {"homes": 5}}}
    _patch(session, {"new_known": {"2": {"drones": late}}})
    _patch(session, {"new_known": {"2": {"drones": early, "structures": structures}, "3": {"drones": early}}})
    known = container.docs["lastknown_1"]["known"]
    assert known["2"] == {"drones": late, "structures": structures}  # the older drones did not replace the newer
    assert known["3"] == {"drones": early}
    newer = {"ended": "2026-11-21T00:00:00+00:00", "values": {"drones": 30}}
    _patch(session, {"new_known": {"2": {"drones": newer}}})
    assert container.docs["lastknown_1"]["known"]["2"]["drones"] == newer


@pytest.mark.parametrize("body", [
    {},
    {"new_known": []},
    {"new_known": {"2": []}},
    {"new_known": {"2": {"drones": {"values": {}}}}},
])
def test_a_bad_body_is_refused(backend, body):
    container, session = backend
    assert _patch(session, body).status_code == 400
    assert "lastknown_1" not in container.docs


def test_overlapping_merges_all_land(backend):
    """Several writes at once, the first of them creating the document: none is lost."""
    container, session = backend
    count = 6
    barrier = threading.Barrier(count)
    statuses = [None] * count

    def run(index):
        barrier.wait()
        statuses[index] = _patch(
            session, {"new_known": {str(index + 2): {"drones": {"ended": EARLY, "values": {"drones": index}}}}},
        ).status_code

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert statuses == [200] * count
    assert sorted(container.docs["lastknown_1"]["known"]) == sorted(str(i + 2) for i in range(count))
