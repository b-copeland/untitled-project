"""
The lists that grow with play keep only their newest lines (issue #219), so no free action repeated by a script can
grow a document without end. Run from the repo root: conda run -n funcapp-worker python -m pytest funcapp/tests
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
    container = fake_backend.FakeContainer()
    module = fake_backend.load_function_app(container)
    return container, fake_backend.FakeSession(module), module


def _patch(session, path, body):
    return session.request("PATCH", ENDPOINT + path, data=json.dumps(body))


@pytest.mark.parametrize("path, item, field, body, limit", [
    ("/kingdom/1/news", "news_1", "news", lambda i: {"time": f"t{i}", "news": f"n{i}"}, "NEWS_LENGTH"),
    ("/galaxy/1:1/news", "galaxy_news_1:1", "news", lambda i: {"time": f"t{i}", "news": f"n{i}"}, "NEWS_LENGTH"),
    ("/empire/3/news", "empire_news_3", "news", lambda i: {"news": {"time": f"t{i}", "news": f"n{i}"}}, "NEWS_LENGTH"),
    ("/universenews", "universe_news", "news", lambda i: {"news": {"time": f"t{i}", "news": f"n{i}"}}, "UNIVERSE_NEWS_LENGTH"),
    ("/kingdom/1/spyhistory", "spy_history_1", "spy_history", lambda i: {"time": f"t{i}", "n": i}, "HISTORY_LENGTH"),
    ("/kingdom/1/attackhistory", "attack_history_1", "attack_history", lambda i: {"time": f"t{i}", "n": i}, "HISTORY_LENGTH"),
    ("/kingdom/1/missilehistory", "missile_history_1", "missile_history", lambda i: {"time": f"t{i}", "n": i}, "HISTORY_LENGTH"),
])
def test_a_growing_list_keeps_its_newest_lines(backend, monkeypatch, path, item, field, body, limit):
    container, session, module = backend
    monkeypatch.setattr(module, limit, 5)
    container.create_item({"id": item, field: []})

    for i in range(8):
        assert _patch(session, path, body(i)).status_code == 200

    lines = container.docs[item][field]
    assert [line["time"] for line in lines] == ["t7", "t6", "t5", "t4", "t3"]


def test_pinning_keeps_each_kingdom_once_and_the_newest_few(backend, monkeypatch):
    container, session, module = backend
    monkeypatch.setattr(module, "PINNED_LENGTH", 3)
    container.create_item({"id": "pinned_1", "pinned": []})

    for kd in ["5", "5", "6", "7", "8", "5"]:
        assert _patch(session, "/kingdom/1/pinned", {"pinned": [kd]}).status_code == 200
    assert _patch(session, "/kingdom/1/pinned", {"unpinned": ["7"]}).status_code == 200

    # 5 fell off when 8 came, and pinning it again puts it back as the newest.
    assert container.docs["pinned_1"]["pinned"] == ["8", "5"]
