"""Marking news read through /api/clearnotifs: up to what the page saw, so what came in after stays unread."""
import json

import untitledapp.misc as uam
from untitledapp import REQUESTS_SESSION
from tests.test_concurrency import FUNCTION_URL, KD_ID, _set_up_kingdom


def _notifs():
    return json.loads(REQUESTS_SESSION.get(f"{FUNCTION_URL}/kingdom/{KD_ID}/notifs").text)


def _clear(client, jwt, body):
    return client.post("/api/clearnotifs", json=body, headers={"Authorization": f"Bearer {jwt}"})


def test_an_item_that_comes_in_after_the_page_loaded_stays_unread(app, client, jwt1):
    with app.app_context():
        _set_up_kingdom(1000)
        uam._add_notifs(KD_ID, ["news_kingdom"])
        uam._add_notifs(KD_ID, ["news_kingdom"])
        seen = _notifs()["news_kingdom_total"]       # the page loads with two
        uam._add_notifs(KD_ID, ["news_kingdom"])       # a third arrives before it marks them read

    assert _clear(client, jwt1, {"categories": ["news_kingdom"], "seen": {"news_kingdom": seen}}).status_code == 200

    with app.app_context():
        assert _notifs()["news_kingdom"] == 1


def test_without_a_total_the_category_is_cleared_outright(app, client, jwt1):
    with app.app_context():
        _set_up_kingdom(1000)
        uam._add_notifs(KD_ID, ["messages"])

    _clear(client, jwt1, {"categories": ["messages"]})

    with app.app_context():
        assert _notifs()["messages"] == 0


def test_only_known_categories_can_be_cleared(app, client, jwt1):
    with app.app_context():
        _set_up_kingdom(1000)

    _clear(client, jwt1, {"categories": ["last_active", "news_kingdom"], "seen": {"news_kingdom": True}})

    with app.app_context():
        stored = _notifs()
    assert "last_active_total" not in stored and stored.get("last_active") != 0
