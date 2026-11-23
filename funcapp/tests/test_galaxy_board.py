"""
Tests for ``galaxy_board_<galaxy>`` (the galaxy board) and for a notification counter added after a kingdom was made.

They run the real handlers on the in-memory container (tests/fake_backend.py). Run them from the repo root:

    conda run -n funcapp-worker python -m pytest funcapp/tests
"""
import pathlib
import sys

import pytest

pytest.importorskip("azure.cosmos")
pytest.importorskip("azure.functions")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tests import fake_backend  # noqa: E402
from funcapp.tests.test_empire_targets import _in_threads  # noqa: E402

ENDPOINT = "http://funcapp/api"


@pytest.fixture
def backend():
    container = fake_backend.FakeContainer(latency=0.002)
    session = fake_backend.FakeSession(fake_backend.load_function_app(container))
    return container, session


def _call(session, method, path, **kwargs):
    return session.request(method, ENDPOINT + path, **kwargs)


def test_reading_creates_the_board_once(backend):
    container, session = backend
    responses = _in_threads(6, lambda _: _call(session, "GET", "/galaxy/1:2/board"))
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json()["id"] == "galaxy_board_1:2"
    assert [doc for doc in container.docs if doc.startswith("galaxy_board_")] == ["galaxy_board_1:2"]


def test_update_is_a_shallow_merge_that_keeps_the_id(backend):
    container, session = backend
    _call(session, "GET", "/galaxy/1:2/board")
    response = _call(session, "PATCH", "/galaxy/1:2/board", json={"id": "other", "posts": [{"id": "a"}], "pinned": None})
    assert response.status_code == 200
    stored = container.docs["galaxy_board_1:2"]
    assert stored["id"] == "galaxy_board_1:2" and stored["posts"] == [{"id": "a"}] and stored["pinned"] is None


def test_an_unread_board_or_a_bad_body_is_refused(backend):
    _, session = backend
    assert _call(session, "PATCH", "/galaxy/9:9/board", json={"posts": []}).status_code == 404
    _call(session, "GET", "/galaxy/1:2/board")
    assert _call(session, "PATCH", "/galaxy/1:2/board", json=["x"]).status_code == 400


def test_a_counter_the_notifications_do_not_have_yet_starts_at_zero(backend):
    container, session = backend
    container.create_item({"id": "notifs_7", "news_kingdom": 2})
    assert _call(session, "PATCH", "/kingdom/7/notifs", json={"add_categories": ["galaxy_board"]}).status_code == 200
    assert container.docs["notifs_7"]["galaxy_board"] == 1 and container.docs["notifs_7"]["news_kingdom"] == 2
