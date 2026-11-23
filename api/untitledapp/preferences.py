"""
A player's own settings, which belong to the player and not to a kingdom: the colour theme, the kinds of
notification they have turned off (``muted``, the kinds in push.py), whether the advisors give advice, the advice
they have hidden (advisors.py), their answer to the guided tour (``tour``), and whether actions play their short
animations (``effects``, src/components/flourish.js).

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

# (value, label), in the order the Settings page shows them. The first is the default, except for the theme, whose
# default is DEFAULT_THEME (the same as DEFAULT_THEME in src/theme.js).
THEMES = [
    ("gray", "Gray"),
    ("dark", "Dark"),
    ("light", "Light"),
    ("eclipse", "Eclipse"),
    ("nebula", "Nebula"),
    ("planet", "Planet"),
    ("twilight", "Twilight"),
]
DEFAULT_THEME = "twilight"
# Whether the Status page's advisors give advice (advisors.py).
ADVISORS = [("on", "On"), ("off", "Off")]
# The guided tour (src/components/tour.js): offered on the player's first visit until they answer. "later" (Not now, or
# left before the end) keeps a card on the Status page that starts it; after "declined" (No thanks) or "done" (finished)
# only the Settings page starts it.
TOUR = [("offer", "Not answered"), ("later", "Later"), ("declined", "No thanks"), ("done", "Taken")]
# Whether attacks, spy operations, missile launches and election results play a short animation
# (src/components/flourish.js). A device set to reduce motion never plays them.
EFFECTS = [("on", "On"), ("off", "Off")]
OPTIONS = {"theme": THEMES, "advisors": ADVISORS, "tour": TOUR, "effects": EFFECTS}
DEFAULTS = {**{key: options[0][0] for key, options in OPTIONS.items()}, "theme": DEFAULT_THEME}
# Each advice the player hid is its own key, ``hide_advice_<id>: true``, so two hides at once (two tabs) can not undo
# each other through the shallow merge; showing it again writes false. Read back as the list ``hidden_advice``.
HIDDEN_ADVICE_PREFIX = "hide_advice_"


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
    values["hidden_advice"] = sorted(
        key[len(HIDDEN_ADVICE_PREFIX):] for key, value in stored.items()
        if key.startswith(HIDDEN_ADVICE_PREFIX) and value is True
    )
    options ={key: [{"value": v, "label": label} for v, label in choices] for key, choices in OPTIONS.items()}
    options["muted"] = [{"value": kind, "label": label, "group": group} for kind, label, group in KINDS]
    return {**values, "options": options}


def read(user_id):
    """The user's preferences with the defaults filled in (one read; every default if it fails)."""
    response = REQUESTS_SESSION.get(_path(user_id), headers=_headers())
    return _answer(json.loads(response.text) if response.status_code == 200 else {})


def set_advice_hidden(user_id, advice_id, hidden):
    """Hide one advice for good, or show it again. A merge of one key of its own, so nothing to race. True if saved."""
    response = REQUESTS_SESSION.patch(
        _path(user_id), headers=_headers(), data=json.dumps({HIDDEN_ADVICE_PREFIX + advice_id: bool(hidden)})
    )
    return response.status_code < 300


@bp.route("/api/preferences")
@flask_praetorian.auth_required
def get_preferences():
    """The preferences, and the player's username for the user menu (from the login token, so no extra read)."""
    user = flask_praetorian.current_user()
    return flask.jsonify({**read(user.id), "username": user.username}), 200


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
