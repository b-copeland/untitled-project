"""
The galaxy board (#183): a place for galaxymates to coordinate, for example to share a Discord invite.

One document per galaxy, ``galaxy_board_<galaxy>``: ``posts`` (newest first, the newest ``GALAXY_BOARD_KEEP_POSTS``
kept) and ``pinned`` (a copy of one post, or None, set by the galaxy's leader so it does not scroll away). Only the
galaxy's own kingdoms read or write it: the routes take the galaxy from the caller's kingdom, never from the request.

Every change is decided on the document as it is when it lands (``occ.update``), so posts at the same moment are all
kept and a post deleted twice is deleted once.
"""
import datetime
import uuid

import flask
import flask_praetorian

import untitledapp.getters as uag
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import alive_required

bp = flask.Blueprint("board", __name__)


def normalize(document):
    """The board's fields, with defaults: the document is created as ``{"id": ...}`` the first time it is read."""
    return {"posts": list(document.get("posts") or []), "pinned": document.get("pinned")}


def text_problem(text):
    """Why ``text`` can not be posted, or None. ``text`` is already stripped."""
    if not isinstance(text, str) or not text:
        return "Write something to post"
    maximum = uas.GAME_CONFIG["GALAXY_BOARD_MAX_LENGTH"]
    if len(text) > maximum:
        return f"A post can be at most {maximum} characters"
    return None


def with_post(board, post):
    """The board with ``post`` added at the top, keeping the newest ``GALAXY_BOARD_KEEP_POSTS``."""
    keep = uas.GAME_CONFIG["GALAXY_BOARD_KEEP_POSTS"]
    return {**board, "posts": ([post] + board["posts"])[:keep]}


def without_post(board, post_id, kd_id, is_leader):
    """The board with the post taken out (and unpinned if it was pinned). Its author or the galaxy's leader may."""
    post = next((post for post in board["posts"] if post["id"] == post_id), None)
    pinned = board["pinned"] if board["pinned"] and board["pinned"]["id"] == post_id else None
    found = post or pinned
    if found is None:
        raise occ.Rejected("That post is not on the board")
    if found["from"] != kd_id and not is_leader:
        raise occ.Rejected("Only its author or the galaxy leader can delete a post")
    return {
        "posts": [post for post in board["posts"] if post["id"] != post_id],
        "pinned": None if pinned else board["pinned"],
    }


def _path(galaxy):
    return f"/galaxy/{galaxy}/board"


def _where(kd_id):
    """``(galaxy, galaxy politics)`` of the caller's kingdom."""
    politics, galaxy = uag._get_galaxy_politics(kd_id)
    return galaxy, politics


def _answer(payload, status=200):
    return flask.jsonify(payload), status


def _decide_and_answer(galaxy, change, message):
    def decide(document):
        return change(normalize(document)), None

    try:
        occ.update(_path(galaxy), decide)
    except occ.Rejected as rejection:
        return _answer({"message": rejection.message}, rejection.status)
    except occ.Busy:
        return _answer({"message": "Server is busy"}, 400)
    return _answer({"message": message, "status": "success"})


@bp.route('/api/galaxyboard', methods=['GET'])
@flask_praetorian.auth_required
def galaxy_board():
    kd_id = flask_praetorian.current_user().kd_id
    galaxy, politics = _where(kd_id)
    board = normalize(occ.read(_path(galaxy)))
    return _answer({**board, "galaxy": galaxy, "can_moderate": politics.get("leader") == kd_id})


@bp.route('/api/galaxyboard', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def post_to_board():
    kd_id = flask_praetorian.current_user().kd_id
    body = flask.request.get_json(force=True, silent=True)
    text = body.get("text") if isinstance(body, dict) else None
    text = text.strip() if isinstance(text, str) else text
    problem = text_problem(text)
    if problem:
        return _answer({"message": problem}, 400)
    galaxy, _ = _where(kd_id)
    post = {
        "id": uuid.uuid4().hex,
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "from": kd_id,
        "text": text,
    }
    answer = _decide_and_answer(galaxy, lambda board: with_post(board, post), "Posted")
    if answer[1] == 200:
        for galaxymate in uag._get_galaxy_info().get(galaxy, []):
            if galaxymate != kd_id:
                uam._add_notifs(galaxymate, ["galaxy_board"])
    return answer


@bp.route('/api/galaxyboard/<post_id>/delete', methods=['POST'])
@flask_praetorian.auth_required
def delete_from_board(post_id):
    kd_id = flask_praetorian.current_user().kd_id
    galaxy, politics = _where(kd_id)
    is_leader = politics.get("leader") == kd_id
    return _decide_and_answer(galaxy, lambda board: without_post(board, post_id, kd_id, is_leader), "Post deleted")


def _must_lead(politics, kd_id):
    if politics.get("leader") != kd_id:
        return _answer({"message": "Only the galaxy leader can pin or unpin a post"}, 400)
    return None


@bp.route('/api/galaxyboard/<post_id>/pin', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def pin_post(post_id):
    kd_id = flask_praetorian.current_user().kd_id
    galaxy, politics = _where(kd_id)
    refusal = _must_lead(politics, kd_id)
    if refusal:
        return refusal

    def pin(board):
        post = next((post for post in board["posts"] if post["id"] == post_id), None)
        if post is None:
            raise occ.Rejected("That post is not on the board")
        return {**board, "pinned": post}

    return _decide_and_answer(galaxy, pin, "Pinned")


@bp.route('/api/galaxyboard/unpin', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def unpin_post():
    kd_id = flask_praetorian.current_user().kd_id
    galaxy, politics = _where(kd_id)
    refusal = _must_lead(politics, kd_id)
    if refusal:
        return refusal
    return _decide_and_answer(galaxy, lambda board: {**board, "pinned": None}, "Unpinned")
