"""
A player's own settings, which belong to the player and not to a kingdom: the colour theme, and the kinds of
notification they have turned off (``muted``, the kinds in push.py).

They live in ``preferences_<user_id>`` (docs/data-model.md), one document per user, which outlives a round. A user who
has set nothing has no document and gets every default. The options and their defaults are here, and the Settings page
lists them from ``GET /api/preferences``, so a new theme is one line in ``THEMES`` plus its colours in
``src/styles/themes.css``.
"""
import json

import flask
import flask_praetorian

from untitledapp import REQUESTS_SESSION
from untitledapp.push import KINDS, MUTABLE

bp = flask.Blueprint("preferences", __name__)

# (value, label), in the order the Settings page shows them. The first is the default.
THEMES = [
    ("gray", "Gray"),
    ("dark", "Dark"),
    ("light", "Light"),
    ("eclipse", "Eclipse"),
    ("nebula", "Nebula"),
    ("planet", "Planet"),
    ("twilight", "Twilight"),
]
OPTIONS = {"theme": THEMES}
DEFAULTS = {key: options[0][0] for key, options in OPTIONS.items()}


def _path(user_id):
    return flask.current_app.config["AZURE_FUNCTION_ENDPOINT"] + f"/preferences/{user_id}"


def _headers():
    return {"x-functions-key": flask.current_app.config["AZURE_FUNCTION_KEY"]}


def _answer(stored):
    """The player's preferences with the defaults filled in (a value no longer offered falls back to its default),
    and the options for each. ``muted`` keeps only the kinds that still exist, in the order of ``KINDS``."""
    values = {
        key: stored.get(key) if stored.get(key) in {value for value, _ in options} else DEFAULTS[key]
        for key, options in OPTIONS.items()
    }
    stored_muted = stored.get("muted") if isinstance(stored.get("muted"), list) else []
    values["muted"] = [kind for kind, _, _ in KINDS if kind in stored_muted]
    options = {key: [{"value": v, "label": label} for v, label in choices] for key, choices in OPTIONS.items()}
    options["muted"] = [{"value": kind, "label": label, "group": group} for kind, label, group in KINDS]
    return {**values, "options": options}


@bp.route("/api/preferences")
@flask_praetorian.auth_required
def get_preferences():
    """The preferences, and the player's username for the user menu (from the login token, so no extra read)."""
    user = flask_praetorian.current_user()
    response = REQUESTS_SESSION.get(_path(user.id), headers=_headers())
    stored = json.loads(response.text) if response.status_code == 200 else {}
    return flask.jsonify({**_answer(stored), "username": user.username}), 200


@bp.route("/api/preferences", methods=["POST"])
@flask_praetorian.auth_required
def set_preferences():
    """Body: any of the preferences, each one of its options; ``muted`` is the whole list of kinds turned off. Only the
    player's own document is written."""
    req = flask.request.get_json(force=True, silent=True)
    if not isinstance(req, dict) or not req:
        return flask.jsonify({"message": "Choose a setting to change"}), 400
    changes = {}
    for key, value in req.items():
        if key == "muted":
            if not isinstance(value, list) or not all(kind in MUTABLE for kind in value):
                return flask.jsonify({"message": "Choose notifications from the list"}), 400
            changes[key] = sorted(set(value))
            continue
        if key not in OPTIONS:
            return flask.jsonify({"message": f"There is no setting called {key}"}), 400
        if value not in {option for option, _ in OPTIONS[key]}:
            return flask.jsonify({"message": f"{value} is not one of the choices for {key}"}), 400
        changes[key] = value
    # A shallow merge of independent keys: no read is needed to decide anything, so there is nothing to race.
    response = REQUESTS_SESSION.patch(_path(flask_praetorian.current_user().id), headers=_headers(), data=json.dumps(changes))
    if response.status_code >= 300:
        return flask.jsonify({"message": "Your settings could not be saved. Try again."}), 503
    return flask.jsonify({"message": "Settings saved", "status": "success", **_answer(changes)}), 200
