"""
The end of a round (issue #17).

When ``game_end`` passes (an admin can also end a round early), the refresh finishes one last tick and then
``end_round`` runs, once:

* the round is archived: final scores, every kingdom and every galaxy, as one document ``archive_<n>`` that survives a
  reset (``GET /api/archive`` and ``GET /api/archive/<n>`` read it);
* ``game_over`` is set in the state document;
* from then on the refresh does nothing (the game engine is stopped, which includes the bots), every write to the game is
  refused (``frozen_response`` in a ``before_request``), and everything about every kingdom is public.

Nothing here is meant to be undone: ``/api/resetstate`` clears ``game_over`` when the admin starts the next round.
"""
import datetime
import json

import flask
import flask_praetorian

import untitledapp.getters as uag
from untitledapp import REQUESTS_SESSION

bp = flask.Blueprint("roundend", __name__)

# Paths that still work when the round is over: signing in and out, the account, and the admin's own tools.
_STILL_OPEN = (
    "/api/login", "/api/refresh", "/api/signup", "/api/register", "/api/finalize", "/api/account",
    "/api/adminlogin", "/api/adminrefresh", "/api/admin", "/api/updatestate", "/api/createstate", "/api/resetstate",
    "/api/clearnotifs",
)
_WRITES = ("POST", "PUT", "PATCH", "DELETE")
OVER_MESSAGE = "The round is over: the game is read only now."


def is_over(state):
    return bool(state["state"].get("game_over"))


def round_is_over():
    """Whether the round has ended (one read of the state document)."""
    return is_over(uag._get_state())


def is_due(state, now):
    """Whether ``game_end`` has passed and the round has not been closed yet."""
    game_end = state["state"].get("game_end")
    if not game_end or is_over(state):
        return False
    return now >= datetime.datetime.fromisoformat(game_end).astimezone(datetime.timezone.utc)


def frozen_response():
    """For ``before_request``: a refusal for a write once the round is over, else None."""
    request = flask.request
    if request.method not in _WRITES or not request.path.startswith("/api/"):
        return None
    if any(request.path == prefix or request.path.startswith(prefix + "/") for prefix in _STILL_OPEN):
        return None
    if round_is_over():
        return flask.jsonify({"message": OVER_MESSAGE}), 400
    return None


def _post(path, payload, method="post"):
    app = flask.current_app
    return getattr(REQUESTS_SESSION, method)(
        app.config["AZURE_FUNCTION_ENDPOINT"] + path,
        headers={"x-functions-key": app.config["AZURE_FUNCTION_KEY"]},
        data=json.dumps(payload),
    )


def _archive_number(state):
    return int(state["state"].get("rounds_archived", 0)) + 1


def build_archive(state, now, reason):
    """Everything worth keeping about the round: who ended where, with each kingdom's final numbers."""
    scores = uag._get_scores()
    galaxies = uag._get_galaxy_info()
    names = uag._get_kingdoms()
    galaxy_of = {kd_id: galaxy for galaxy, members in galaxies.items() for kd_id in members}
    kingdoms = {}
    for kd_id, name in names.items():
        info = uag._get_kd_info(kd_id)
        kingdoms[kd_id] = {
            "name": name,
            "galaxy": galaxy_of.get(kd_id, ""),
            "race": info.get("race"),
            "status": info.get("status"),
            "stars": info.get("stars"),
            "networth": info.get("networth"),
            "bot": (info.get("bot") or {}).get("type"),
        }
    final = sorted(kingdoms.items(), key=lambda item: -(scores.get("points", {}).get(item[0]) or 0))
    return {
        "ended_at": now.isoformat(),
        "reason": reason,
        "game_start": state["state"].get("game_start"),
        "game_end": state["state"].get("game_end"),
        "scores": {key: scores.get(key, {}) for key in ("stars", "networth", "points", "galaxy_networth")},
        "galaxies": galaxies,
        "kingdoms": kingdoms,
        "ranking": [kd_id for kd_id, _ in final],
    }


def end_round(state, now=None, reason="The round ended"):
    """Archive the round and close it. Safe to call twice: it does nothing if the round is already over."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if is_over(state):
        return state
    number = _archive_number(state)
    archive = build_archive(state, now, reason)
    _post("/createitem", {"item": f"archive_{number}", "state": {"number": number, **archive}})
    _post("/updatestate", {"game_over": now.isoformat(), "rounds_archived": number}, method="patch")
    flask.current_app.logger.info("Round %s ended (%s) and archived", number, reason)
    return uag._get_state()


def _get_archive(number):
    app = flask.current_app
    response = REQUESTS_SESSION.get(
        app.config["AZURE_FUNCTION_ENDPOINT"] + "/item",
        headers={"x-functions-key": app.config["AZURE_FUNCTION_KEY"]},
        data=json.dumps({"item": f"archive_{number}"}),
    )
    if response.status_code >= 300:
        return None
    return json.loads(response.text)


@bp.route("/api/archive")
@flask_praetorian.auth_required
def archive_latest():
    """The most recent finished round."""
    state = uag._get_state()
    number = int(state["state"].get("rounds_archived", 0))
    archive = _get_archive(number) if number else None
    if not archive:
        return flask.jsonify({"message": "No round has finished yet"}), 404
    return flask.jsonify(archive), 200


@bp.route("/api/archive/<int:number>")
@flask_praetorian.auth_required
def archive_number(number):
    archive = _get_archive(number)
    if not archive:
        return flask.jsonify({"message": "No such round"}), 404
    return flask.jsonify(archive), 200


@bp.route("/api/admin/endround", methods=["POST"])
@flask_praetorian.roles_required("admin")
def admin_end_round():
    """End the round now (for a win condition to call, or by hand)."""
    state = uag._get_state()
    if is_over(state):
        return flask.jsonify({"message": "The round is already over"}), 400
    end_round(state, reason="Ended by the admin")
    return flask.jsonify({"message": "The round is over and archived", "status": "success"}), 200
