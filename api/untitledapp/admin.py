"""
The admin's tools: starting a round, changing its dates, adding bots, and watching it. See docs/admin.md.

Starting a round is one request (``POST /api/admin/newround``) so that the game is never left half set up: before it,
the old round; after it, a new round with every setting the refresh and the pages need. It works from any starting
point (an empty container, one ``/deleteall`` blanked, a running round, a finished one) and running it again after a
failure is the fix.
"""
import datetime
import json
import random

import flask
import flask_praetorian

import untitledapp.galaxypolicies as uagp
import untitledapp.migrations as uamig
import untitledapp.getters as uag
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import guard, User, REQUESTS_SESSION

bp = flask.Blueprint("admin", __name__)

MAX_GALAXIES = 100  # galaxies one new round may have: each is three documents
MAX_BOTS_PER_CALL = 200  # each bot is about twenty function app calls, all in the one request


def galaxy_ids(num_galaxies, cluster_size):
    """The ids of ``num_galaxies`` galaxies dealt in order into clusters of ``cluster_size``: ``cluster:galaxy``."""
    return [f"{i // cluster_size + 1}:{i % cluster_size + 1}" for i in range(num_galaxies)]


def _function_app(method, path, payload=None):
    app = flask.current_app
    return getattr(REQUESTS_SESSION, method)(
        app.config['AZURE_FUNCTION_ENDPOINT'] + path,
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        **({"data": json.dumps(payload)} if payload is not None else {}),
    )


# --- rules for a round's settings (plain functions, unit tested) ---------------------------------------------------

def parse_time(value):
    """An ISO 8601 time from the admin page as a UTC datetime, or None if it is empty or not a time."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return uas.utc(value)
    except ValueError:
        return None


def _whole_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number


def check_new_round(req, now):
    """
    The settings of a new round from the admin's request: ``(settings, errors)``. ``errors`` maps each bad field to a
    sentence and is empty when the settings are good. Times come back as UTC datetimes.
    """
    errors = {}
    start = parse_time(req.get("game_start"))
    end = parse_time(req.get("game_end"))
    election_text = req.get("election_start") or ""
    election = parse_time(election_text)
    if start is None:
        errors["game_start"] = "Choose when the round starts"
    if end is None:
        errors["game_end"] = "Choose when the round ends"
    elif end <= now:
        errors["game_end"] = "The end must be in the future"
    elif start is not None and end <= start:
        errors["game_end"] = "The end must be after the start"
    if election_text and election is None:
        errors["election_start"] = "Not a time"
    elif election is not None and start is not None and end is not None and not start <= election < end:
        errors["election_start"] = "The first election must be during the round"

    num_galaxies = _whole_number(req.get("num_galaxies"))
    if num_galaxies is None or not 1 <= num_galaxies <= MAX_GALAXIES:
        errors["num_galaxies"] = f"Between 1 and {MAX_GALAXIES} galaxies"
    cluster_size = req.get("cluster_size")
    cluster_size = uas.GAME_CONFIG["CLUSTER_SIZE"] if cluster_size in (None, "") else _whole_number(cluster_size)
    if cluster_size is None or cluster_size < 1:
        errors["cluster_size"] = "At least 1 galaxy per cluster"

    settings = {
        "game_start": start,
        "game_end": end,
        "election_start": election,
        "num_galaxies": num_galaxies,
        "cluster_size": cluster_size,
        "archive": bool(req.get("archive", True)),
    }
    return settings, errors


def round_state(settings, rounds_archived, rng=random):
    """
    The whole inner ``state`` of a round that has not run yet. Every key the refresh, the decorators and the pages read
    is here, so nothing left over from an earlier round (an open election, policies, ``game_over``) carries on. The
    galaxy policies the round plays are drawn here with ``rng``, once, and hold for the whole round.
    """
    start = settings["game_start"].isoformat()
    return {
        "galaxy_policies": uagp.draw(rng),
        "migrations_done": uamig.all_ids(),  # a new round's documents are made in the current shape
        "game_start": start,
        "game_end": settings["game_end"].isoformat(),
        "election_start": settings["election_start"].isoformat() if settings["election_start"] else "",
        "election_end": "",
        "next_history": start,
        "active_policies": [],
        "game_over": "",
        "rounds_archived": rounds_archived,
        "cluster_size": settings["cluster_size"],
    }


def check_round_change(stored, req, now):
    """
    A change to the dates of the round that is set up: ``(changes, errors)``, ``changes`` being the fields of the inner
    state to write. ``stored`` is the inner state as it is now. Only the fields in ``req`` change:

    * ``game_start``, only before the round has started (it also moves the history mark);
    * ``game_end``, to a time in the future, after the start;
    * ``election_start``, the next election (``""`` for none), only while no election is open.
    """
    errors, changes = {}, {}
    if not (stored.get("game_start") and stored.get("game_end")):
        return {}, {"round": "No round is set up: start a new one"}
    if stored.get("game_over"):
        return {}, {"round": "The round is over: start a new one"}
    start = uas.utc(stored["game_start"])
    end = uas.utc(stored["game_end"])

    if "game_start" in req:
        new_start = parse_time(req["game_start"])
        if now >= start:
            errors["game_start"] = "The round has started: its start can not move"
        elif new_start is None:
            errors["game_start"] = "Not a time"
        else:
            start = new_start
            changes["game_start"] = changes["next_history"] = new_start.isoformat()
    if "game_end" in req:
        new_end = parse_time(req["game_end"])
        if new_end is None:
            errors["game_end"] = "Not a time"
        elif new_end <= now:
            errors["game_end"] = "The end must be in the future (End the round now to stop it)"
        else:
            end = new_end
            changes["game_end"] = new_end.isoformat()
    if end <= start and "game_end" not in errors:
        errors["game_end"] = "The end must be after the start"
    if "election_start" in req:
        text = req["election_start"] or ""
        election = parse_time(text)
        if stored.get("election_end"):
            errors["election_start"] = "An election is open: wait until it closes"
        elif text and election is None:
            errors["election_start"] = "Not a time"
        elif election is not None and not (max(start, now) <= election < end):
            errors["election_start"] = "The election must be during the rest of the round"
        else:
            changes["election_start"] = election.isoformat() if election else ""
    return changes, errors


def _refused(errors, status=400):
    return flask.jsonify({"message": next(iter(errors.values())), "errors": errors}), status


# --- signing in -----------------------------------------------------------------------------------------------------

@bp.route('/api/adminlogin', methods=['POST'])
def admin_login():
    req = flask.request.get_json(force=True)
    username = req.get('username', None)
    password = req.get('password', None)
    user = guard.authenticate(username, password)
    if "admin" not in user.roles:
        return flask.jsonify({"message": "Not authorized"})
    ret = {'accessToken': guard.encode_jwt_token(user), 'refreshToken': guard.encode_jwt_token(user)}
    return (flask.jsonify(ret), 200)

@bp.route('/api/adminrefresh', methods=['POST'])
@flask_praetorian.roles_required('admin')
def admin_refresh():

    old_token = guard.read_token_from_header()
    new_token = guard.refresh_jwt_token(old_token)
    ret = {'accessToken': new_token}
    return ret, 200


# --- the round ------------------------------------------------------------------------------------------------------

def _round_summary():
    """What the admin page shows about the round: its settings and how full it is. Three cached reads."""
    state = uag._get_state()
    inner = state.get("state") or {}
    galaxies = uag._get_galaxy_info()
    kingdoms = uag._get_kingdoms()
    now = datetime.datetime.now(datetime.timezone.utc)
    set_up = bool(inner.get("game_start") and inner.get("game_end"))
    if not set_up:
        phase = "not set up"
    elif inner.get("game_over"):
        phase = "over"
    elif now < uas.utc(inner["game_start"]):
        phase = "not started"
    else:
        phase = "running"
    clusters = sorted({galaxy.split(":")[0] for galaxy in galaxies})
    bots = sum(1 for name in kingdoms.values() if str(name).startswith("bot_"))
    return {
        "phase": phase,
        "game_start": inner.get("game_start", ""),
        "game_end": inner.get("game_end", ""),
        "election_start": inner.get("election_start", ""),
        "election_end": inner.get("election_end", ""),
        "game_over": inner.get("game_over", ""),
        "rounds_archived": inner.get("rounds_archived", 0),
        "cluster_size": inner.get("cluster_size", uas.GAME_CONFIG["CLUSTER_SIZE"]),
        "galaxies": len(galaxies),
        "clusters": len(clusters),
        "kingdoms": len(kingdoms),
        "bots": bots,
        "players": len(kingdoms) - bots,
        "default_cluster_size": uas.GAME_CONFIG["CLUSTER_SIZE"],
        "max_galaxies": MAX_GALAXIES,
        "max_bots": MAX_BOTS_PER_CALL,
        "election_hours": uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_ELECTION_LENGTH_MULTIPLIER"] / 3600,
        "election_every_hours": uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * (
            uas.GAME_CONFIG["BASE_ELECTION_LENGTH_MULTIPLIER"] + uas.GAME_CONFIG["BASE_ELECTION_RESULTS_DURATION_MULTIPLIER"]) / 3600,
    }


@bp.route('/api/admin/round', methods=["GET"])
@flask_praetorian.roles_required('admin')
def get_round():
    """The round as the admin sees it."""
    _function_app("post", "/init")  # a container never set up gets its empty documents (a no-op otherwise)
    return flask.jsonify(_round_summary()), 200


@bp.route('/api/admin/round', methods=["POST"])
@flask_praetorian.roles_required('admin')
def change_round():
    """Move the dates of the round that is set up: any of ``game_start``, ``game_end``, ``election_start``."""
    req = flask.request.get_json(force=True) or {}
    now = datetime.datetime.now(datetime.timezone.utc)
    refused = {}

    def decide(document):
        changes, errors = check_round_change(document.get("state") or {}, req, now)
        refused.clear()
        refused.update(errors)
        if errors:
            raise occ.Rejected(next(iter(errors.values())))
        return changes, changes

    try:
        changes = occ.update("/state", decide, write_path="/updatestate")
    except occ.Rejected:
        return _refused(refused)
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    if "game_start" in changes:
        # Scores and empires count their time from the start of the round.
        _function_app("post", "/createitem", {"item": "scores", "state": {"last_update": changes["game_start"]}})
        _function_app("post", "/createitem", {"item": "empires", "state": {"last_update": changes["game_start"]}})
    return flask.jsonify({"message": "Round updated", "status": "success", "round": _round_summary()}), 200


def _pause(now, archive):
    """
    Stop the game engine before anything is deleted: from now on a refresh does nothing and players can not act
    (``game_over`` is set, roundend.py). A round that has started is archived first if ``archive`` and it has kingdoms.
    Returns the state document as it is now.
    """
    import untitledapp.roundend as uare

    state = uag._get_state()
    inner = state.get("state") or {}
    if inner.get("game_over"):
        return state
    started = bool(inner.get("game_start")) and now >= uas.utc(inner["game_start"])
    if archive and started and uag._get_kingdoms():
        return uare.end_round(state, now=now, reason="Ended by the admin to start a new round")

    def pause(document):
        if (document.get("state") or {}).get("game_over"):
            return None, None
        return {"game_over": now.isoformat()}, None

    occ.update("/state", pause, write_path="/updatestate")
    return uag._get_state()


@bp.route('/api/admin/newround', methods=["POST"])
@flask_praetorian.roles_required('admin')
def new_round():
    """
    Start a new round, from whatever the game holds now. Body: ``game_start``, ``game_end``, ``election_start``
    (optional, ``""`` for no elections), ``num_galaxies``, ``cluster_size`` (optional, ``CLUSTER_SIZE``), ``archive``
    (default true: archive a round that has started and not finished first). In order:

    1. the core documents exist (``/init``);
    2. the engine is paused (``game_over``), so no refresh or player changes anything while the rest happens;
    3. the function app empties the game (``/resetstate``) and every user loses their kingdom;
    4. the galaxies are made, dealt into clusters;
    5. the scores' and empires' clocks are set to the start, and the new state is written whole, which clears
       ``game_over`` and so restarts the engine last.

    Bots are added afterwards with ``POST /api/admin/bots``.
    """
    req = flask.request.get_json(force=True) or {}
    now = datetime.datetime.now(datetime.timezone.utc)
    settings, errors = check_new_round(req, now)
    if errors:
        return _refused(errors)

    if _function_app("post", "/init").status_code >= 300:
        return flask.jsonify({"message": "Could not create the game's documents. Nothing was changed."}), 500
    state = _pause(now, settings["archive"])
    rounds_archived = int((state.get("state") or {}).get("rounds_archived", 0))

    failed = "The new round failed part way, so the game is paused. Start the new round again."
    if _function_app("post", "/resetstate").status_code != 200:
        return flask.jsonify({"message": failed}), 500
    # Users outlive the round (the function app's reset keeps their documents); only their kingdoms go.
    for user in User.all():
        if user.kd_id not in (None, "") or user.kd_created or user.kd_death_date not in (None, ""):
            user.save(kd_id=None, kd_created=False, kd_death_date=None)
    for galaxy_id in galaxy_ids(settings["num_galaxies"], settings["cluster_size"]):
        if _function_app("post", f"/galaxy/{galaxy_id}").status_code != 201:
            return flask.jsonify({"message": failed}), 500

    start = settings["game_start"].isoformat()
    _function_app("post", "/createitem", {"item": "scores", "state": {"last_update": start}})
    _function_app("post", "/createitem", {"item": "empires", "state": {"last_update": start}})
    # Written whole (``createitem`` replaces the inner ``state`` object), and last: this clears ``game_over``.
    written = _function_app("post", "/createitem", {"item": "state", "state": {"state": round_state(settings, rounds_archived)}})
    if written.status_code != 201:
        return flask.jsonify({"message": failed}), 500

    summary = _round_summary()
    return flask.jsonify({
        "message": f"New round ready: {summary['galaxies']} galaxies in {summary['clusters']} clusters",
        "status": "success",
        "round": summary,
    }), 200


# --- bots -----------------------------------------------------------------------------------------------------------

@bp.route('/api/admin/bots', methods=["POST"])
@flask_praetorian.roles_required('admin')
def create_bots():
    """
    Add bots: ``{"total": 100}`` for the default mix (``bots.mix_for``), or counts per type, e.g.
    ``{"explorer": 25, "attacker": 25, "intel": 25, "thief": 25}``. See docs/bots.md.
    """
    import untitledapp.bots as bots

    counts = flask.request.get_json(force=True) or {}
    if "total" in counts:
        total = _whole_number(counts["total"])
        if total is None or total < 1:
            return flask.jsonify({"message": "Add at least one bot"}), 400
        if total > MAX_BOTS_PER_CALL:
            return flask.jsonify({"message": f"Create at most {MAX_BOTS_PER_CALL} bots at a time"}), 400
        counts = bots.mix_for(total)
    unknown = set(counts) - set(bots.ARCHETYPES)
    if unknown:
        return flask.jsonify({"message": f"Unknown bot types {sorted(unknown)}; choose from {sorted(bots.ARCHETYPES)}"}), 400
    numbers = {kind: _whole_number(n) for kind, n in counts.items()}
    if any(n is None or n < 0 for n in numbers.values()):
        return flask.jsonify({"message": "Bot counts must be whole numbers"}), 400
    if sum(numbers.values()) > MAX_BOTS_PER_CALL:
        return flask.jsonify({"message": f"Create at most {MAX_BOTS_PER_CALL} bots at a time"}), 400
    if not (occ.read("/galaxies") or {}).get("galaxies"):  # read plainly: a blanked container has no galaxies key
        return flask.jsonify({"message": "There are no galaxies: start a new round first"}), 400
    try:
        created = bots.create_bots(numbers)
    except ValueError as error:
        return flask.jsonify({"message": str(error)}), 400
    return flask.jsonify({"message": f"Created {len(created)} bots", "status": "success", "bots": created}), 201


# --- watching a round -------------------------------------------------------------------------------------------------
# Admin only, and everything is shown: these routes are for the maintainer watching a round (bots included), not for
# players. The universe view reads four shared documents whatever the number of kingdoms; a kingdom's details are two
# reads, made when the admin opens it.


@bp.route('/api/admin/universe', methods=["GET"])
@flask_praetorian.roles_required('admin')
def admin_universe():
    """Every kingdom at a glance: name, galaxy, empire, stars, networth and points, and the round's times."""
    names = uag._get_kingdoms()
    kd_empire, empires_info, _, galaxy_members = uag._get_empires_inverted()
    galaxy_of = {kd: galaxy for galaxy, members in galaxy_members.items() for kd in members}
    scores = uag._get_scores()
    state = uag._get_state().get("state", {})
    empires = empires_info.get("empires", {})
    kingdoms = []
    for kd_id, name in names.items():
        empire = kd_empire.get(kd_id)
        kingdoms.append({
            "kd_id": kd_id,
            "name": name,
            # Bots are named bot_<playstyle>_<n> (bots.py).
            "playstyle": name.split("_")[1] if name.startswith("bot_") and name.count("_") >= 2 else "player",
            "galaxy": galaxy_of.get(kd_id),
            "empire": empires.get(empire, {}).get("name") if empire else None,
            "stars": scores.get("stars", {}).get(kd_id, 0),
            "networth": scores.get("networth", {}).get(kd_id, 0),
            "points": round(scores.get("points", {}).get(kd_id, 0), 1),
        })
    return flask.jsonify({
        "kingdoms": sorted(kingdoms, key=lambda kd: -kd["networth"]),
        "game_start": state.get("game_start"),
        "game_end": state.get("game_end"),
        "empires": {eid: {"name": e.get("name"), "galaxies": e.get("galaxies", []), "war": e.get("war", [])}
                    for eid, e in empires.items()},
    }), 200


@bp.route('/api/admin/kingdom/<kd_id>', methods=["GET"])
@flask_praetorian.roles_required('admin')
def admin_kingdom(kd_id):
    """One kingdom in full, with its bot's style, phase, memory and decisions if it is a bot, and its latest news."""
    kingdom = uag._get_kd_info(kd_id)
    if not kingdom or "kdId" not in kingdom:
        return flask.jsonify({"message": "No such kingdom"}), 400
    kingdom = {key: value for key, value in kingdom.items() if not key.startswith("_")}
    news = occ.read(f'/kingdom/{kd_id}/news').get("news", [])
    return flask.jsonify({"kingdom": kingdom, "news": news[-20:]}), 200
