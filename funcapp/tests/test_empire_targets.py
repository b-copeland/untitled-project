"""
Tests for the empire targets document (``empire_targets_<empire>``).

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


def test_reading_creates_an_empty_document(backend):
    container, session = backend
    response = _call(session, "GET", "/empire/2/targets")
    assert response.status_code == 200
    assert response.json()["id"] == "empire_targets_2"
    assert "_etag" in response.json()
    assert container.docs["empire_targets_2"]["id"] == "empire_targets_2"


def test_first_reads_at_the_same_moment_make_one_document(backend):
    container, session = backend
    responses = _in_threads(6, lambda _: _call(session, "GET", "/empire/2/targets"))
    assert all(response.status_code == 200 for response in responses)
    assert [doc_id for doc_id in container.docs if doc_id.startswith("empire_targets_")] == ["empire_targets_2"]


def test_update_is_a_shallow_merge_and_keeps_the_id(backend):
    container, session = backend
    _call(session, "GET", "/empire/2/targets")
    _call(session, "PATCH", "/empire/2/targets", json={"votes": {"2:1": "a"}, "levels": {"a": 0.1}})
    _call(session, "PATCH", "/empire/2/targets", json={"votes": {"2:2": "b"}, "id": "something_else"})
    stored = container.docs["empire_targets_2"]
    assert stored["id"] == "empire_targets_2"
    assert stored["votes"] == {"2:2": "b"}
    assert stored["levels"] == {"a": 0.1}


def test_update_of_a_missing_document_is_404(backend):
    _, session = backend
    assert _call(session, "PATCH", "/empire/9/targets", json={"votes": {}}).status_code == 404


def test_update_rejects_a_body_that_is_not_an_object(backend):
    _, session = backend
    _call(session, "GET", "/empire/2/targets")
    assert _call(session, "PATCH", "/empire/2/targets", json=[1, 2]).status_code == 400


def test_update_honours_if_match(backend):
    container, session = backend
    etag = _call(session, "GET", "/empire/2/targets").json()["_etag"]
    first = _call(session, "PATCH", "/empire/2/targets", json={"votes": {"x": 1}}, headers={"If-Match": etag})
    stale = _call(session, "PATCH", "/empire/2/targets", json={"votes": {"y": 1}}, headers={"If-Match": etag})
    assert (first.status_code, stale.status_code) == (200, 412)
    assert container.docs["empire_targets_2"]["votes"] == {"x": 1}
