"""
Tests for ``universe_stats``, the advisors' comparison of every kingdom: read without a document, the merge that
creates it, and that /init makes it and a new round empties it.

They run the real handlers on the in-memory container (tests/fake_backend.py). Run them from the repo root:

    conda run -n funcapp-worker python -m pytest funcapp/tests
"""
import json
import pathlib
import sys

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


def _patch(session, body):
    return session.request("PATCH", f"{ENDPOINT}/universestats", data=json.dumps(body))


def _get(session):
    return session.request("GET", f"{ENDPOINT}/universestats")


def test_missing_stats_read_empty_and_nothing_is_written(backend):
    container, session = backend
    response = _get(session)
    assert response.status_code == 200
    assert response.json() == {"id": "universe_stats"}
    assert "universe_stats" not in container.docs


def test_the_first_merge_creates_it_and_later_ones_merge(backend):
    _, session = backend
    assert _patch(session, {"peer_ranges": {"drones_per_star": {"low": 1}}}).status_code == 200
    assert _patch(session, {"last_update": "now", "id": "other"}).status_code == 200
    document = _get(session).json()
    assert document["id"] == "universe_stats"
    assert document["peer_ranges"] == {"drones_per_star": {"low": 1}} and document["last_update"] == "now"


def test_a_body_that_is_not_an_object_is_refused(backend):
    _, session = backend
    assert _patch(session, ["peer_ranges"]).status_code == 400


def test_init_creates_it_and_a_new_round_empties_it(backend):
    container, session = backend
    session.request("POST", f"{ENDPOINT}/init")
    assert container.docs["universe_stats"]["peer_ranges"] == {}
    _patch(session, {"peer_ranges": {"drones_per_star": {"low": 1}}})
    session.request("POST", f"{ENDPOINT}/resetstate")
    assert container.docs["universe_stats"]["peer_ranges"] == {}
