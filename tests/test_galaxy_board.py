"""The galaxy board (#183): galaxymates post, read, delete and pin; nobody else sees it."""
import pytest

import untitledapp.board as board
import untitledapp.occ as occ
import untitledapp.shared as uas
from tests.test_concurrency import KD_ID, _create_item, _get, _run_together, _set_up_kingdom
from tests.test_politics import _auth, _galaxy_politics


def _galaxy(leader=KD_ID):
    """Kingdoms 1 and 2 share galaxy 1:1 (``leader`` leads it); kingdom 3 is alone in 1:2."""
    for kd_id in (KD_ID, "2", "3"):
        _set_up_kingdom(money=0, kd_id=kd_id)
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID, "2"], "1:2": ["3"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics(leader=leader))
    _create_item("galaxy_votes_1:2", _galaxy_politics(leader="3"))


def _post(client, token, text):
    return client.post("/api/galaxyboard", json={"text": text}, headers=_auth(token))


def _board(client, token):
    return client.get("/api/galaxyboard", headers=_auth(token)).get_json()


def test_a_post_is_read_by_galaxymates_and_not_by_another_galaxy(app, client, jwt1, jwt2):
    _galaxy()
    response = _post(client, jwt1, "  Discord: https://discord.gg/abc  ")

    assert response.status_code == 200, response.get_json()
    seen = _board(client, jwt2)
    assert [(post["from"], post["text"]) for post in seen["posts"]] == [(KD_ID, "Discord: https://discord.gg/abc")]
    assert seen["galaxy"] == "1:1" and seen["can_moderate"] is False
    assert _board(client, jwt1)["can_moderate"] is True
    # Kingdom 3's galaxy has its own, empty board.
    with app.test_request_context():
        assert board.normalize(occ.read("/galaxy/1:2/board"))["posts"] == []


def test_a_post_notifies_the_other_galaxymates_only(app, client, jwt1):
    _galaxy()
    _post(client, jwt1, "hello")
    assert _get("/kingdom/2/notifs")["galaxy_board"] == 1
    assert _get(f"/kingdom/{KD_ID}/notifs").get("galaxy_board", 0) == 0
    assert _get("/kingdom/3/notifs").get("galaxy_board", 0) == 0


def test_a_kingdom_made_before_the_board_gets_its_counter_on_the_first_post(app, client, jwt1, backend):
    if backend is None:
        pytest.skip("needs the in-memory container to take a field out of a document")
    _galaxy()
    backend.docs["notifs_2"].pop("galaxy_board")
    _post(client, jwt1, "hello")
    assert _get("/kingdom/2/notifs")["galaxy_board"] == 1


@pytest.mark.parametrize("text, message", [
    ("", "Write something to post"),
    ("   ", "Write something to post"),
    (None, "Write something to post"),
    (12, "Write something to post"),
    ("x" * (uas.GAME_CONFIG["GALAXY_BOARD_MAX_LENGTH"] + 1), "at most"),
])
def test_empty_or_long_posts_are_refused(app, client, jwt1, text, message):
    _galaxy()
    response = _post(client, jwt1, text)
    assert response.status_code == 400 and message in response.get_json()["message"]
    assert _board(client, jwt1)["posts"] == []


def test_the_board_keeps_the_newest_posts():
    posts = {"posts": [{"id": str(i)} for i in range(uas.GAME_CONFIG["GALAXY_BOARD_KEEP_POSTS"])], "pinned": None}
    kept = board.with_post(posts, {"id": "new"})
    assert len(kept["posts"]) == uas.GAME_CONFIG["GALAXY_BOARD_KEEP_POSTS"]
    assert kept["posts"][0]["id"] == "new" and kept["posts"][-1]["id"] == str(len(posts["posts"]) - 2)


def test_posts_at_the_same_moment_are_all_kept(app, client, jwt1, jwt2):
    _galaxy()
    tokens = [jwt1, jwt2] * 3
    responses = _run_together(app, 6, lambda c, i: c.post("/api/galaxyboard", json={"text": f"post {i}"},
                                                          headers=_auth(tokens[i])))
    assert all(r.status_code == 200 for r in responses), [r.get_json() for r in responses]
    assert sorted(post["text"] for post in _board(client, jwt1)["posts"]) == [f"post {i}" for i in range(6)]


def test_an_author_or_the_leader_may_delete_a_post_and_nobody_else(app, client, jwt1, jwt2):
    _galaxy(leader=KD_ID)
    _post(client, jwt1, "from the leader")
    _post(client, jwt2, "from a galaxymate")
    by_text = {post["text"]: post["id"] for post in _board(client, jwt1)["posts"]}

    refused = client.post(f"/api/galaxyboard/{by_text['from the leader']}/delete", headers=_auth(jwt2))
    assert refused.status_code == 400 and "author or the galaxy leader" in refused.get_json()["message"]

    assert client.post(f"/api/galaxyboard/{by_text['from a galaxymate']}/delete", headers=_auth(jwt1)).status_code == 200
    assert [post["text"] for post in _board(client, jwt1)["posts"]] == ["from the leader"]
    gone = client.post(f"/api/galaxyboard/{by_text['from a galaxymate']}/delete", headers=_auth(jwt1))
    assert gone.status_code == 400 and gone.get_json()["message"] == "That post is not on the board"


def test_only_the_leader_pins_and_a_pinned_post_outlives_its_place_in_the_list(app, client, jwt1, jwt2):
    _galaxy(leader=KD_ID)
    _post(client, jwt2, "Discord: https://discord.gg/abc")
    post_id = _board(client, jwt1)["posts"][0]["id"]

    assert client.post(f"/api/galaxyboard/{post_id}/pin", headers=_auth(jwt2)).status_code == 400
    assert client.post(f"/api/galaxyboard/{post_id}/pin", headers=_auth(jwt1)).status_code == 200
    assert _board(client, jwt2)["pinned"]["text"] == "Discord: https://discord.gg/abc"

    trimmed = board.without_post({"posts": [], "pinned": {"id": post_id, "from": "2", "text": "x"}}, post_id, "2", False)
    assert trimmed == {"posts": [], "pinned": None}  # deleting a pinned post that has scrolled off still unpins it

    assert client.post("/api/galaxyboard/unpin", headers=_auth(jwt2)).status_code == 400
    assert client.post("/api/galaxyboard/unpin", headers=_auth(jwt1)).status_code == 200
    assert _board(client, jwt1)["pinned"] is None
