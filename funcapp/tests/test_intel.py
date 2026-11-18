"""
Tests for the galaxy intel document (``galaxy_intel_<galaxy>``) and for how ``new_revealed`` merges expiries.

They run the real handlers on the in-memory container (tests/fake_backend.py), so they need no emulator or function
host. Run them from the repo root:

    conda run -n funcapp-worker python -m pytest funcapp/tests
"""
import pathlib
import sys
import threading

import pytest

pytest.importorskip("azure.cosmos")
pytest.importorskip("azure.functions")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tests import fake_backend  # noqa: E402

ENDPOINT = "http://funcapp/api"


@pytest.fixture
def backend():
    container = fake_backend.FakeContainer(latency=0.002)
    session = fake_backend.FakeSession(fake_backend.load_function_app(container))
    return container, session


def _call(session, method, path, **kwargs):
    return session.request(method, ENDPOINT + path, **kwargs)


def _in_threads(count, target):
    results = [None] * count
    barrier = threading.Barrier(count)

    def run(index):
        barrier.wait()
        results[index] = target(index)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


# --- galaxy_intel_<galaxy> ---------------------------------------------------------------------------------------

def test_reading_creates_an_empty_document(backend):
    container, session = backend
    response = _call(session, "GET", "/galaxy/1:2/intel")
    assert response.status_code == 200
    assert response.json()["id"] == "galaxy_intel_1:2"
    assert "_etag" in response.json()
    assert container.docs["galaxy_intel_1:2"]["id"] == "galaxy_intel_1:2"


def test_reading_twice_keeps_what_was_written(backend):
    _, session = backend
    _call(session, "GET", "/galaxy/1:2/intel")
    assert _call(session, "PATCH", "/galaxy/1:2/intel", json={"listings": {"a": 1}}).status_code == 200
    assert _call(session, "GET", "/galaxy/1:2/intel").json()["listings"] == {"a": 1}


def test_first_reads_at_the_same_moment_make_one_document(backend):
    container, session = backend
    responses = _in_threads(6, lambda _: _call(session, "GET", "/galaxy/1:2/intel"))
    assert all(response.status_code == 200 for response in responses)
    assert [doc_id for doc_id in container.docs if doc_id.startswith("galaxy_intel_")] == ["galaxy_intel_1:2"]


def test_update_is_a_shallow_merge_and_keeps_the_id(backend):
    container, session = backend
    _call(session, "GET", "/galaxy/1:2/intel")
    _call(session, "PATCH", "/galaxy/1:2/intel", json={"listings": {"a": 1}, "history": [1]})
    _call(session, "PATCH", "/galaxy/1:2/intel", json={"listings": {"b": 2}, "id": "something_else"})
    stored = container.docs["galaxy_intel_1:2"]
    assert stored["id"] == "galaxy_intel_1:2"
    assert stored["listings"] == {"b": 2}
    assert stored["history"] == [1]


def test_update_of_a_missing_document_is_404(backend):
    _, session = backend
    assert _call(session, "PATCH", "/galaxy/9:9/intel", json={"listings": {}}).status_code == 404


def test_update_rejects_a_body_that_is_not_an_object(backend):
    _, session = backend
    _call(session, "GET", "/galaxy/1:2/intel")
    assert _call(session, "PATCH", "/galaxy/1:2/intel", json=[1, 2]).status_code == 400


def test_update_honours_if_match(backend):
    container, session = backend
    etag = _call(session, "GET", "/galaxy/1:2/intel").json()["_etag"]
    first = _call(session, "PATCH", "/galaxy/1:2/intel", json={"bounties": {"x": 1}}, headers={"If-Match": etag})
    stale = _call(session, "PATCH", "/galaxy/1:2/intel", json={"bounties": {"y": 1}}, headers={"If-Match": etag})
    assert (first.status_code, stale.status_code) == (200, 412)
    assert container.docs["galaxy_intel_1:2"]["bounties"] == {"x": 1}


def test_concurrent_updates_of_different_fields_all_land(backend):
    container, session = backend
    _call(session, "GET", "/galaxy/1:2/intel")
    fields = [f"field_{i}" for i in range(6)]
    responses = _in_threads(len(fields), lambda i: _call(session, "PATCH", "/galaxy/1:2/intel", json={fields[i]: i}))
    assert all(response.status_code == 200 for response in responses)
    stored = container.docs["galaxy_intel_1:2"]
    assert all(stored[field] == i for i, field in enumerate(fields))


# --- revealed: new_revealed keeps the later expiry -----------------------------------------------------------------

def _revealed(container, revealed):
    container.create_item({
        "id": "revealed_1", "revealed": revealed, "galaxies": {}, "revealed_galaxymates": [], "revealed_to_galaxymates": [],
    })


def test_new_revealed_never_shortens_a_reveal(backend):
    container, session = backend
    _revealed(container, {"5": {"military": "2026-11-18T12:00:00+00:00"}})
    _call(session, "PATCH", "/kingdom/1/revealed", json={"new_revealed": {"5": {"military": "2026-11-18T09:00:00+00:00"}}})
    assert container.docs["revealed_1"]["revealed"]["5"]["military"] == "2026-11-18T12:00:00+00:00"


def test_new_revealed_extends_a_reveal_and_adds_new_stats_and_targets(backend):
    container, session = backend
    _revealed(container, {"5": {"military": "2026-11-18T12:00:00+00:00", "drones": "2026-11-18T10:00:00+00:00"}})
    _call(session, "PATCH", "/kingdom/1/revealed", json={"new_revealed": {
        "5": {"military": "2026-11-18T15:00:00+00:00", "shields": "2026-11-18T11:00:00+00:00"},
        "6": {"kingdom": "2026-11-18T13:00:00+00:00"},
    }})
    stored = container.docs["revealed_1"]["revealed"]
    assert stored["5"] == {
        "military": "2026-11-18T15:00:00+00:00",
        "drones": "2026-11-18T10:00:00+00:00",
        "shields": "2026-11-18T11:00:00+00:00",
    }
    assert stored["6"] == {"kingdom": "2026-11-18T13:00:00+00:00"}


def test_new_revealed_compares_times_not_strings(backend):
    container, session = backend
    # 11:30 at -01:00 is 12:30 UTC: later than the stored 12:00, though it sorts lower as a string.
    _revealed(container, {"5": {"military": "2026-11-18T12:00:00+00:00"}})
    _call(session, "PATCH", "/kingdom/1/revealed", json={"new_revealed": {"5": {"military": "2026-11-18T11:30:00-01:00"}}})
    assert container.docs["revealed_1"]["revealed"]["5"]["military"] == "2026-11-18T11:30:00-01:00"


def test_replacing_revealed_can_still_remove_entries(backend):
    container, session = backend
    _revealed(container, {"5": {"military": "2026-11-18T12:00:00+00:00"}})
    _call(session, "PATCH", "/kingdom/1/revealed", json={"revealed": {}})
    assert container.docs["revealed_1"]["revealed"] == {}
