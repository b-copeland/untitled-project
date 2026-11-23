"""
Tests for ``PATCH /empire/<id>/news``, which appends to ``empire_news_<id>`` (made when the empire is founded).

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
    container.create_item({"id": "empire_news_3", "news": [{"time": "t0", "news": "old"}]})
    return container, session


def _patch(session, empire, body):
    return session.request("PATCH", f"{ENDPOINT}/empire/{empire}/news", json=body)


def _lines(container):
    return [line["news"] for line in container.docs["empire_news_3"]["news"]]


def test_a_line_or_a_list_of_lines_goes_in_front(backend):
    container, session = backend
    assert _patch(session, 3, {"news": {"time": "t1", "news": "one"}}).status_code == 200
    assert _patch(session, 3, {"news": [{"time": "t3", "news": "three"}, {"time": "t2", "news": "two"}]}).status_code == 200
    assert _lines(container) == ["three", "two", "one", "old"]
    assert "empire_3" not in container.docs  # the old handler wrote here


def test_a_missing_empire_or_a_bad_body_is_refused(backend):
    container, session = backend
    assert _patch(session, 9, {"news": {"time": "t", "news": "x"}}).status_code == 404
    assert _patch(session, 3, {"line": "x"}).status_code == 400
    assert _patch(session, 3, ["x"]).status_code == 400
    assert _lines(container) == ["old"]


def test_appends_at_the_same_moment_are_all_kept(backend):
    container, session = backend
    responses = _in_threads(6, lambda i: _patch(session, 3, {"news": {"time": f"t{i}", "news": f"n{i}"}}))
    assert all(response.status_code == 200 for response in responses)
    assert sorted(_lines(container)) == sorted([f"n{i}" for i in range(6)] + ["old"])
