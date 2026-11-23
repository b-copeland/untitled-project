"""Unread counts as a sequence and a read cursor (funcapp/notifs.py), and the notifs PATCH that applies them."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import notifs  # noqa: E402


def test_an_old_count_reads_as_that_many_unread():
    assert notifs.counter({"news_kingdom": 3}, "news_kingdom") == (3, 0)
    assert notifs.counter({}, "galaxy_board") == (0, 0)


def test_adding_keeps_the_count_the_pages_read():
    doc = {"news_kingdom": 2}
    notifs.add(doc, "news_kingdom")
    assert doc == {"news_kingdom": 3, "news_kingdom_total": 3, "news_kingdom_read": 0}


def test_marking_read_up_to_what_was_seen_leaves_newer_items_unread():
    doc = {}
    for _ in range(5):
        notifs.add(doc, "messages")
    notifs.mark_read(doc, "messages", 3)  # the page loaded when there were 3; 2 more came in since
    assert doc["messages"] == 2


def test_marking_read_is_safe_to_repeat_and_never_goes_back_or_past_the_total():
    doc = {"messages_total": 5, "messages_read": 3, "messages": 2}
    notifs.mark_read(doc, "messages", 3)
    notifs.mark_read(doc, "messages", 3)
    assert doc["messages"] == 2
    notifs.mark_read(doc, "messages", 1)
    assert doc["messages_read"] == 3
    notifs.mark_read(doc, "messages", 99)
    assert doc["messages_read"] == 5 and doc["messages"] == 0


def test_marking_all_read():
    doc = {"shared": 4}
    notifs.mark_read(doc, "shared")
    assert doc == {"shared": 0, "shared_total": 4, "shared_read": 4}


# --- the handler, on the in-memory container --------------------------------------------------------------------

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


@pytest.fixture
def session():
    pytest.importorskip("azure.cosmos")
    pytest.importorskip("azure.functions")
    from tests import fake_backend
    container = fake_backend.FakeContainer()
    container.create_item({"id": "notifs_1", "news_kingdom": 0, "news_galaxy": 1})
    return fake_backend.FakeSession(fake_backend.load_function_app(container))


def _patch(session, body):
    return session.request("PATCH", "http://funcapp/api/kingdom/1/notifs", data=json.dumps(body))


def _get(session):
    return json.loads(session.request("GET", "http://funcapp/api/kingdom/1/notifs").text)


def test_read_wins_over_clear_for_the_same_category(session):
    for _ in range(3):
        _patch(session, {"add_categories": ["news_kingdom"]})

    _patch(session, {"clear_categories": ["news_kingdom", "news_galaxy"], "read": {"news_kingdom": 2}})

    stored = _get(session)
    assert stored["news_kingdom"] == 1   # the third came in after the page loaded
    assert stored["news_galaxy"] == 0    # no cursor sent: cleared outright, as before
