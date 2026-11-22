"""
Tests for a player's preferences (``preferences_<user_id>``): read without a document, the merge that creates it, and
that it outlives a round like the user it belongs to.

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


@pytest.fixture
def backend():
    container = fake_backend.FakeContainer(latency=0.002)
    session = fake_backend.FakeSession(fake_backend.load_function_app(container))
    return container, session


def _patch(session, body, user_id=1):
    return session.request("PATCH", f"{ENDPOINT}/preferences/{user_id}", data=json.dumps(body))


def _get(session, user_id=1):
    return session.request("GET", f"{ENDPOINT}/preferences/{user_id}")


def test_a_user_with_no_preferences_reads_empty_and_nothing_is_written(backend):
    container, session = backend
    response = _get(session)
    assert response.status_code == 200
    assert response.json() == {"id": "preferences_1"}
    assert "preferences_1" not in container.docs


def test_the_first_merge_creates_the_document_and_later_ones_merge_into_it(backend):
    container, session = backend
    assert _patch(session, {"theme": "nebula"}).status_code == 200
    assert _patch(session, {"other": 1, "id": "preferences_9"}).status_code == 200
    document = _get(session).json()
    assert document["id"] == "preferences_1"
    assert document["theme"] == "nebula" and document["other"] == 1
    assert "preferences_9" not in container.docs


def test_a_body_that_is_not_an_object_is_refused(backend):
    _, session = backend
    assert _patch(session, ["theme"]).status_code == 400


def test_overlapping_merges_all_land(backend):
    """Several writes at once, the first of them creating the document: none is lost."""
    container, session = backend
    count = 6
    barrier = threading.Barrier(count)
    statuses = [None] * count

    def run(index):
        barrier.wait()
        statuses[index] = _patch(session, {f"key_{index}": index}).status_code

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert statuses == [200] * count
    assert {f"key_{i}" for i in range(count)} <= set(container.docs["preferences_1"])


def test_preferences_outlive_a_round_and_deleteall_removes_them(backend):
    container, session = backend
    assert session.request("POST", ENDPOINT + "/init").status_code == 201
    assert _patch(session, {"theme": "light"}).status_code == 200

    assert session.request("POST", ENDPOINT + "/resetstate").status_code == 200
    assert container.docs["preferences_1"]["theme"] == "light"

    session.request("POST", ENDPOINT + "/deleteall")
    assert "preferences_1" not in container.docs
