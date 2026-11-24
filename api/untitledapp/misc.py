import collections
import copy
import datetime
import json
import os
import random
import uuid

import flask
import flask_praetorian
from flask_sock import Sock

import untitledapp.shared as uas
import untitledapp.getters as uag
import untitledapp.lastknown as uala
import untitledapp.news as uan
import untitledapp.occ as occ
import untitledapp.visits as uav
from untitledapp import User, REQUESTS_SESSION, before_start_required, alive_required
from untitledapp.push import push
from untitledapp.users import issue_tokens

bp = flask.Blueprint("misc", __name__)

def _create_galaxy(galaxy_id):
    app = flask.current_app
    create_galaxy_response = REQUESTS_SESSION.post(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
    )
    return create_galaxy_response.text

def _validate_kingdom_name(
    name,    
):
    kingdoms = uag._get_kingdoms()
    if any((name.lower() == existing_name.lower() for existing_name in kingdoms.values())):
        return False, "Kingdom name already exists"
    
    if len(name) > 24:
        return False, "Kingdom name must be less than 25 characters"
    
    if len(name) == 0:
        return False, "Kingdom name must have at least one character"
    
    return True, ""

# How long a request's claim to make a user's kingdom holds off another request for the same user (see below).
KINGDOM_CLAIM_SECONDS = 120


def _create_kingdom_documents(user_id, name):
    """
    Make a kingdom's documents in the function app, in the galaxy with the fewest kingdoms, and record its id on the
    user. Returns ``(kd_id, message)``: the message is empty when it worked. If the user turns out to have a kingdom
    already (a double click got here first), that kingdom's id is returned and nothing is made.

    Two requests for one user (a double click, two tabs, two machines) are kept from both making a kingdom by a claim
    on the user document, decided with ``occ.update``: only one request can set ``kd_pending`` while the user has no
    kingdom. The claim expires after ``KINGDOM_CLAIM_SECONDS`` in case its request died half way.
    """
    app = flask.current_app
    user = User.get(user_id)
    if user is None:
        return None, "Could not find your account"

    request_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)

    def claim(document):
        if document.get("kd_id") not in ("", None):
            return None, document["kd_id"]
        pending = document.get("kd_pending")
        if pending and pending.get("request") != request_id:
            started = datetime.datetime.fromisoformat(pending["time"])
            if (now - started).total_seconds() < KINGDOM_CLAIM_SECONDS:
                raise occ.Rejected("Your kingdom is already being created")
        return {"kd_pending": {"request": request_id, "time": now.isoformat()}}, None

    try:
        existing = occ.update(f"/user/{user.id}", claim)
    except occ.Rejected as rejection:
        return None, rejection.message
    except occ.Busy:
        return None, "Server is busy"
    if existing:
        return existing, ""

    # Two different players creating kingdoms at once get different ids: the function app takes the id with a
    # conditional write on `kingdoms`.
    kd_id = None
    try:
        valid_name, message = _validate_kingdom_name(name)
        if not valid_name:
            return None, message

        galaxies = uag._get_galaxy_info()
        size_galaxies = collections.defaultdict(list)
        for galaxy_id, kingdoms in galaxies.items():
            size_galaxies[len(kingdoms)].append(galaxy_id)

        smallest_galaxy_size = min(size_galaxies.keys())
        smallest_galaxies = size_galaxies[smallest_galaxy_size]

        chosen_galaxy = random.choice(smallest_galaxies)
        create_kd_response = REQUESTS_SESSION.post(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({"kingdom_name": name, "galaxy": chosen_galaxy}),
        )
        if create_kd_response.status_code == 400:  # the name was taken at the same moment
            return None, "Kingdom name already exists"
        if create_kd_response.status_code != 201:
            return None, "Error creating kingdom"

        kd_id = create_kd_response.text

        for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
            item_id = f"{table}_{kd_id}"
            state = initial_state.copy()
            if table == "kingdom":
                state["kdId"] = kd_id
                state["name"] = name

            REQUESTS_SESSION.post(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps({
                    "item": item_id,
                    "state": state,
                }),
            )

        user.save(kd_id=kd_id, kd_pending=None)
    finally:
        if kd_id is None:
            user.save(kd_pending=None)  # nothing was made, so let the player try again straight away
    return kd_id, ""


def _plan_from_request(req):
    """
    What the player asked their kingdom to start as, checked: ``({units, structures, race, settings}, "")``, or
    ``(None, reason)``. Either a quick start (``preset``: one of the bot archetypes, with ``autoBuilder`` saying whether
    its auto builder is switched on) or the player's own ``unitsChoices``, ``structuresChoices`` and ``race``.
    """
    # The bots module imports this one, so it can only be imported once this one is loaded.
    import untitledapp.bots as bots

    settings = {}
    preset = req.get("preset")
    if preset:
        archetype = bots.ARCHETYPES.get(preset)
        if archetype is None:
            return None, "Unknown quick start"
        unit_choices = dict(archetype.unit_choices)
        structures_choices = dict(archetype.structures_choices)
        race = archetype.race
        settings = bots.player_settings(archetype, bool(req.get("autoBuilder", False)))
    else:
        try:
            unit_choices = {unit: 0 for unit in uas.KINGDOM_CREATOR_POINTS}
            unit_choices.update({k: int(v or 0) for k, v in (req.get("unitsChoices") or {}).items()})
            structures_choices = {k: int(v or 0) for k, v in (req.get("structuresChoices") or {}).items()}
        except (AttributeError, TypeError, ValueError):
            return None, "Unit and structure amounts must be whole numbers"
        race = req.get("race") or ""

    valid_kd, message = _validate_kingdom_choices(unit_choices, structures_choices, race)
    if not valid_kd:
        return None, message
    return {"units": unit_choices, "structures": structures_choices, "race": race, "settings": settings}, ""


def _new_tokens(user_id):
    """Fresh login tokens for a player whose kingdom just changed (decision 0005); the front end swaps them in."""
    return issue_tokens(User.get(user_id))


def _galaxy_news_for_all(galaxy_id, message, time_now=None, kind="", from_kd="", to_kd=""):
    """A line in a galaxy's news, unread for every kingdom in it."""
    galaxies = occ.read('/galaxies')["galaxies"]  # fresh: the request may have just changed the galaxy
    uan.galaxy(galaxy_id, message, time_now, kind=kind, from_kd=from_kd, to_kd=to_kd)
    for galaxymate in galaxies.get(galaxy_id, []):
        _add_notifs(galaxymate, ["news_galaxy"])


def _galaxy_of(kd_id):
    galaxies = occ.read('/galaxies')["galaxies"]
    return next((galaxy for galaxy, members in galaxies.items() if str(kd_id) in members), None)


@uan.best_effort
def announce_new_kingdom(kd_id, name):
    """A kingdom was set up: its galaxy's news says so. Players and bots both come through here."""
    galaxy = _galaxy_of(kd_id)
    if galaxy is not None:
        _galaxy_news_for_all(galaxy, f"{name or 'A new kingdom'} joined the galaxy", kind="galaxy", from_kd=str(kd_id))


@uan.best_effort
def _death_news(kd_id, killer=None):
    """A kingdom died: its galaxy's news says so, and who killed it if anyone did."""
    galaxy = _galaxy_of(kd_id)
    if galaxy is None:
        return
    names = uag._get_kingdoms()
    name = names.get(str(kd_id), f"Kingdom {kd_id}")
    message = f"{name} has died" + (f", killed by {names.get(str(killer), killer)}" if killer is not None else "")
    _galaxy_news_for_all(galaxy, message, kind="death", from_kd="" if killer is None else str(killer),
                         to_kd=str(kd_id))


def _finish_kingdom(kd_id, plan, user_id):
    """Set a freshly made kingdom up as the plan says, once. Returns the response."""

    def decide(kd_info):
        if kd_info.get("race"):
            raise occ.Rejected("This kingdom has already been created")
        payload = _kingdom_setup_payload(kd_info, plan["units"], plan["structures"], plan["race"])
        payload.update(plan["settings"])
        payload["income"] = _starting_income({**kd_info, **payload})
        if plan["settings"].get("auto_spending_enabled"):
            # Same as a player switching auto spending on: it first runs after one auto-spending interval.
            payload["next_resolve"]["auto_spending"] = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"])
            ).isoformat()
        return payload, kd_info.get("name", "")

    try:
        # The kingdom is only ever set up once: the second of two racing requests finds the race already chosen.
        name = occ.update(f"/kingdom/{kd_id}", decide)
        announce_new_kingdom(kd_id, name)

        User.get(user_id).save(kd_created=True)
    except occ.Rejected as rejection:
        # The player's token may be out of date (the kingdom exists but their token says otherwise): renew it.
        return (flask.jsonify({"message": rejection.message, **_new_tokens(user_id)}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)

    return (flask.jsonify({"message": "", **_new_tokens(user_id)}), 200)


@bp.route('/api/createkingdom', methods=["POST"])
@bp.route('/api/createkingdomchoices', methods=["POST"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_kingdom():
    """
    Make the player's kingdom and set it up, in one request: ``kdName`` plus either a quick start (``preset``,
    ``autoBuilder``) or ``unitsChoices``, ``structuresChoices`` and ``race``. Everything is checked before anything is
    made. A player who already has a kingdom that was never set up (the old two-step flow, or Reset Kingdom) leaves
    ``kdName`` out and only sets it up.
    """
    req = flask.request.get_json(force=True)
    # Rare, and it decides what the player has: use the document, not the token's copy of it.
    user = User.get(flask_praetorian.current_user().id)
    user_id = user.id

    if user.kd_created:
        return (flask.jsonify({"message": "This kingdom has already been created"}), 400)

    plan, message = _plan_from_request(req)
    if plan is None:
        return (flask.jsonify({"message": message}), 400)

    kd_id = user.kd_id
    if kd_id == "" or kd_id is None:
        name = str(req.get("kdName") or "").strip()
        valid_name, message = _validate_kingdom_name(name)
        if not valid_name:
            return (flask.jsonify({"message": message, "field": "name"}), 400)
        kd_id, message = _create_kingdom_documents(user_id, name)
        if kd_id is None:
            return (flask.jsonify({"message": message}), 400)

    return _finish_kingdom(kd_id, plan, user_id)


@bp.route('/api/resetkingdom', methods=["POST"])
@flask_praetorian.auth_required
@before_start_required
# @flask_praetorian.roles_required('verified')
def reset_initial_kingdom():    
    app = flask.current_app
    user = User.get(flask_praetorian.current_user().id)
    kd_id = user.kd_id
    kd_info = uag._get_kd_info(kd_id)
    table_states = {
        f"{table}_{kd_id}": initial_state
        for table, initial_state in uas.INITIAL_KINGDOM_STATE.items()
    }

    for item_id, initial_state in table_states.items():
        state = initial_state.copy()
        if item_id.split("_")[0] == "kingdom":
            state["kdId"] = kd_id
            state["name"] = kd_info["name"]

        create_response = REQUESTS_SESSION.post(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({
                "item": item_id,
                "state": state,
            }),
        )

    user.save(kd_created=False)
    return (flask.jsonify({"message": "Reset kingdom", **_new_tokens(user.id)}), 200)

@bp.route('/api/createkingdomdata')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_kingdom_data():
    """
    Return information to inform kingdom creator page
    """

    import untitledapp.bots as bots  # imports this module, so only once it is loaded

    payload = {
        "total_points": uas.KINGDOM_CREATOR_STARTING_POINTS,
        "selection_points": uas.KINGDOM_CREATOR_POINTS,
        "total_stars": uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"],
        "presets": [bots.preset_view(archetype) for archetype in bots.ARCHETYPES.values()],
    }
    return (flask.jsonify(payload), 200)

def _validate_kingdom_choices(
    unit_choices,
    structures_choices,
    race,
):
    if any((key_unit not in uas.KINGDOM_CREATOR_POINTS for key_unit in unit_choices)):
        return False, "Unknown unit"
    if any((key_structure not in uas.INITIAL_KINGDOM_STATE["kingdom"]["structures"] for key_structure in structures_choices)):
        return False, "Unknown structure"

    sum_units_points = sum([
        value_unit * uas.KINGDOM_CREATOR_POINTS[key_unit]
        for key_unit, value_unit in unit_choices.items()
    ])
    sum_structures = sum(structures_choices.values())
    if any((value_unit < 0 for value_unit in unit_choices.values())):
        return False, "Unit values must be non-negative"
    if any((value_structure < 0 for value_structure in structures_choices.values())):
        return False, "Structures values must be non-negative"
    
    if uas.KINGDOM_CREATOR_STARTING_POINTS - sum_units_points < 0:
        return False, "You do not have that many unit points available"

    if sum_units_points != uas.KINGDOM_CREATOR_STARTING_POINTS:
        return False, "You must use all units points"
    
    if uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"] - sum_structures < 0:
        return False, "You do not have that many stars available for structures"

    if sum_structures != uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"]:
        return False, "You must use all stars for structures"
    
    if race not in uas.RACES:
        return False, "You must select a valid race"
    
    return True, ""

def _starting_income(kd_info):
    """
    The income a freshly set-up kingdom will earn, worked out the way the refresh works it out, so the Status and
    Shields pages show its money, fuel and power before the first tick (or the round's start) has run. The refresh
    replaces it on every tick. Nothing is credited and the refresh's effects are dropped.
    """
    import untitledapp.refresh as uar  # imports this module, so only once it is loaded

    kd = copy.deepcopy(kd_info)
    one_epoch_on = uas.utc(kd["last_income"]) + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])
    return uar._kingdom_with_income(kd, uas.project_bonuses(kd), uag._get_state(), one_epoch_on,
                                    effects=[], mobis_queue=[])["income"]


def _kingdom_setup_payload(kd_info, unit_choices, structures_choices, race):
    """The fields that turn a freshly created kingdom into a playable one: the chosen units, structures and race."""
    payload = {}
    payload["drones"] = unit_choices["drones"]
    payload["units"] = {
        k: v + unit_choices.get(k, 0)
        for k, v in kd_info["units"].items()
    }
    payload["structures"] = {
        k: v + structures_choices.get(k, 0)
        for k, v in kd_info["structures"].items()
    }
    state = uag._get_state()
    start_time_datetime = uas.utc(state["state"]["game_start"])
    # A kingdom made before the start earns nothing until the start.
    payload["last_income"] = max(start_time_datetime, datetime.datetime.now(datetime.timezone.utc)).isoformat()
    payload["next_resolve"] = kd_info["next_resolve"]
    payload["next_resolve"]["spy_attempt"] = (
        max(datetime.datetime.now(datetime.timezone.utc), start_time_datetime)
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_SPY_ATTEMPT_TIME_MULTIPLIER"])
    ).isoformat()
    payload["coordinate"] = random.randint(0, 99)
    payload["race"] = race
    return payload


def _validate_shields(req_values):

    if req_values.get("military", 0) > uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"]:
        return False, "Military shields must be at or below max shields value"
    if req_values.get("spy", 0) > uas.GAME_CONFIG["BASE_SPY_SHIELDS_MAX"]:
        return False, "Spy shields must be at or below max shields value"
    if req_values.get("spy_radar", 0) > uas.GAME_CONFIG["BASE_SPY_RADAR_MAX"]:
        return False, "Spy radar must be at or below max value"
    if req_values.get("missiles", 0) > uas.GAME_CONFIG["BASE_MISSILES_SHIELDS_MAX"]:
        return False, "Missiles shields must be at or below max shields value"
    if any((value < 0 for value in req_values.values())):
        return False, "Shields value must be non-negative"

    return True, ""

@bp.route('/api/shields', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def set_shields():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    req_values = {
        k: float(v or 0) / 100
        for k, v in req.items()
        if v != "" and k in uas.SHIELD_KINDS
    }
    valid_shields, error_message = _validate_shields(req_values)
    if not valid_shields:
        return flask.jsonify({"message": error_message}), 400
    
    
    kd_id = flask_praetorian.current_user().kd_id

    def decide(kd_info):
        # Decided against the kingdom as it is when the write lands, not against a read taken before the lock.
        if kd_info["fuel"] <= 0:
            raise occ.Rejected("You can't set shields without fuel")
        # A raise climbs to its level over BASE_SHIELDS_CLIMB_EPOCHS; a cut is at once.
        shields, climbs = uas.change_shields(kd_info, req_values)
        return {"shields": shields, "shields_climb": climbs}, None

    # The legacy lock stays while other routes still write the kingdom without checking its version.

    try:
        occ.update(f"/kingdom/{kd_id}", decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    return flask.jsonify({"message": "Successfully updated shields", "status": "success"}), 200


@bp.route('/api/messages/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def send_message(target_kd):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)

    kingdoms = uag._get_kingdoms()

    if len(req.get("message", "")) > 1024:
        return flask.jsonify({"message": "Messages must be less than 1024 characters"}), 400

    
    payload_from = {
        "time": req.get("time", ""),
        "with": target_kd,
        "from": True,
        "message": req.get("message", " "),
    }

    payload_to = {
        "time": req.get("time", ""),
        "with": kd_id,
        "from": False,
        "message": req.get("message", " "),
    }
        
    message_response_from = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/messages',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(payload_from)
    )
    message_response_to = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/messages',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(payload_to)
    )
    _add_notifs(target_kd, ["messages"])
    push(target_kd, "messages", f"New message from {kingdoms[kd_id]}!", delay=30000, update=["messages"])
    return (flask.jsonify({"message": "Message sent!", "status": "success"}), 200)



def _validate_spending(spending_input):
    """Confirm that spending request is valid"""

    values = spending_input.values()
    if any((value < 0 for value in values)):
        return False, "Spending values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Spending values must be less than 100%"
    if sum(values) > 1:
        return False, "Spending values must be less than 100%"
    
    return True, ""


@bp.route('/api/spending', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def spending():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id

    
    def decide(kd_info_parse):
        if req.get("enabled", None) != None:
            enabled = req["enabled"]
            payload = {'auto_spending_enabled': enabled}

            if enabled:
                next_resolve = kd_info_parse["next_resolve"]
                next_resolve["auto_spending"] = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"])).isoformat()
                payload["next_resolve"] = next_resolve
                message = "Enabled auto spending and released funding"
            else:
                # Funding goes back to money exactly once: a second request sees funding already at zero.
                total_funding = sum(kd_info_parse["funding"].values())
                next_resolve = kd_info_parse["next_resolve"]
                next_resolve["auto_spending"] = uas.DATE_SENTINEL
                payload["next_resolve"] = next_resolve
                payload["money"] = kd_info_parse["money"] + total_funding
                payload["funding"] = {
                    k: 0
                    for k in kd_info_parse["funding"]
                }
                message = "Disabled auto spending"
            return payload, message

        req_spending = {
            key: float(value or 0) / 100
            for key, value in req.items()
            # A share of 0 is a share like any other; an empty box keeps the current share. Only known categories.
            if key in kd_info_parse['auto_spending'] and value not in ("", None)
        }

        current_spending = kd_info_parse['auto_spending']
        new_spending = {
            **current_spending,
            **req_spending,
        }
        valid_spending, message = _validate_spending(new_spending)
        if not valid_spending:
            raise occ.Rejected(message)

        return {'auto_spending': new_spending}, "Updated spending"

    try:
        message = occ.update(f"/kingdom/{kd_id}", decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    return (flask.jsonify({"message": message, "status": "success"}), 200)

@bp.route('/api/share/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def share_kd(share_to):
    kd_id = flask_praetorian.current_user().kd_id
    payload, status = share_with(kd_id, share_to)
    return flask.jsonify(payload), status


def share_with(kd_id, share_to):
    """
    Show ``share_to`` (a galaxymate) everything about ``kd_id`` until it stops sharing. Two appends, one to each
    kingdom's revealed document. Returns ``(payload, status)``; the route and the bots both come through here.
    """
    app = flask.current_app
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    if share_to == kd_id or galaxies_inverted.get(kd_id) != galaxies_inverted.get(share_to):
        return "You can only share your kingdom to galaxymates", 400

    kd_payload = {
        "new_revealed_to_galaxymates": [share_to]
    }
    share_to_payload = {
        "new_revealed_galaxymates": [kd_id]
    }
    kd_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(kd_payload),
    )
    share_to_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{share_to}/revealed',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(share_to_payload),
    )
    return kd_response.text, 200

@bp.route('/api/unshare/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def unshare_kd(share_to):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    try:
        galaxies_inverted, _ = uag._get_galaxies_inverted()
        if galaxies_inverted[kd_id] != galaxies_inverted[share_to]:
            return flask.jsonify("You can only share your kingdom to galaxymates"), 400

        # Each list loses one entry, taken from that document's latest version, so an unshare can not undo a share
        # that landed at the same moment on the other entries.
        def stop_sharing(revealed):
            return {"revealed_to_galaxymates": [i for i in revealed["revealed_to_galaxymates"] if i != share_to]}, None

        def stop_receiving(revealed):
            was_receiving = kd_id in revealed["revealed_galaxymates"]
            return {"revealed_galaxymates": [i for i in revealed["revealed_galaxymates"] if i != kd_id]}, was_receiving

        occ.update(f'/kingdom/{kd_id}/revealed', stop_sharing)
        if occ.update(f'/kingdom/{share_to}/revealed', stop_receiving):
            # They saw everything about this kingdom until now: that is what they last knew of it.
            ended = datetime.datetime.now(datetime.timezone.utc).isoformat()
            uala.record(share_to, {str(kd_id): uala.snapshot(uag._get_kd_info(kd_id), list(uas.REVEAL_FIELDS), ended)})
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    return (flask.jsonify("Updated"), 200)

def _add_notifs(kd_id, categories):
    app = flask.current_app
    add_notifs_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"add_categories": categories}),
    )

def _clear_notifs(kd_id, categories, seen=None):
    """
    Mark ``categories`` read: up to the total in ``seen`` (``{category: <category>_total the page saw}``) where it has
    one, so items that came in after the page loaded stay unread, and all of them otherwise. ``clear_categories``
    goes too, for a function app from before the read cursor (funcapp/notifs.py).
    """
    app = flask.current_app
    read = {category: int(seen[category]) for category in categories
            if isinstance((seen or {}).get(category), int) and not isinstance(seen[category], bool)}
    REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"clear_categories": categories, **({"read": read} if read else {})}),
    )

def _get_notifs(kd_id):
    app = flask.current_app
    get_notifs_response = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
    )
    get_notifs_response_json = json.loads(get_notifs_response.text)
    return get_notifs_response_json


@bp.route('/api/notifs', methods=['GET'])
@flask_praetorian.auth_required
def get_notifs():
    """The unread counters. The page polls this while it is shown, so it also records that the player is here."""
    kd_id = flask_praetorian.current_user().kd_id
    notifs = _get_notifs(kd_id)
    if isinstance(notifs, dict) and "_etag" in notifs:
        notifs = uav.record(kd_id, notifs)
    return flask.jsonify(notifs), 200


@bp.route('/api/clearnotifs', methods=['POST'])
@flask_praetorian.auth_required
def clear_notifs():
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)

    categories = [category for category in req.get("categories", []) if category in uas.INITIAL_KINGDOM_STATE["notifs"]]
    seen = req.get("seen") if isinstance(req.get("seen"), dict) else None
    if categories:
        _clear_notifs(kd_id, categories, seen)
    
    return "Cleared", 200

def _mark_kingdom_death(kd_id, killer=None):
    """
    Record the death on the kingdom's user (one query: deaths are rare) and tell their open socket, if any. If an empire
    targets the kingdom, its remains go into the target's spoils fund (``killer``, if known, decides whose).
    """
    import untitledapp.targets as uat  # targets reaches misc through conquer

    uat.on_kingdom_death(kd_id, killer=killer)
    death_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _death_news(kd_id, killer)
    for user in User.by_kd_id(kd_id):
        user.save(kd_death_date=death_date)
    push(kd_id, "dead", "You died!", status="warning", delay=999999)
