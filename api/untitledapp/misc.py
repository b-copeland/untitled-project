import collections
import datetime
import json
import os
import time
import random
import uuid

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.account as uaa
import untitledapp.shared as uas
import untitledapp.getters as uag
import untitledapp.occ as occ
from untitledapp import User, Locks, REQUESTS_SESSION, SOCK_HANDLERS, before_start_required, alive_required

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

def _create_kingdom_documents(user_id, name):
    """
    Make a kingdom's documents in the function app, in the galaxy with the fewest kingdoms, and record its id on the
    user. Returns ``(kd_id, message)``: the message is empty when it worked. If the user turns out to have a kingdom
    already (a double click got here first), that kingdom's id is returned and nothing is made.
    """
    app = flask.current_app
    db = flask.current_app.extensions["sqlalchemy"]

    request_id = str(uuid.uuid4())
    if not acquire_locks(["/kingdoms", "/galaxies"], request_id=request_id):
        return None, "Server is busy"

    try:
        # The checks at the top of the route happened before the lock, so a double click could pass them twice. Look
        # again, at the user as stored now.
        stored_user = db.session.query(User).filter_by(id=user_id).populate_existing().one()
        if stored_user.kd_id != "" and stored_user.kd_id is not None:
            return stored_user.kd_id, ""

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

        db.session.expunge_all()
        user = flask_praetorian.current_user()
        user.kd_id = kd_id
        db.session.commit()
        uaa._update_accounts()
    finally:
        release_locks_by_id(request_id)
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


def _finish_kingdom(kd_id, plan):
    """Set a freshly made kingdom up as the plan says, once. Returns the response."""
    db = flask.current_app.extensions["sqlalchemy"]

    if not acquire_lock(f"/kingdom/{kd_id}"):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    def decide(kd_info):
        if kd_info.get("race"):
            raise occ.Rejected("This kingdom has already been created")
        payload = _kingdom_setup_payload(kd_info, plan["units"], plan["structures"], plan["race"])
        payload.update(plan["settings"])
        if plan["settings"].get("auto_spending_enabled"):
            # Same as a player switching auto spending on: it first runs after one auto-spending interval.
            payload["next_resolve"]["auto_spending"] = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"])
            ).isoformat()
        return payload, None

    try:
        # The kingdom is only ever set up once: the second of two racing requests finds the race already chosen.
        occ.update(f"/kingdom/{kd_id}", decide)

        db.session.expunge_all()
        user = flask_praetorian.current_user()
        user.kd_created = True
        db.session.commit()
        uaa._update_accounts()
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    finally:
        release_lock(f"/kingdom/{kd_id}")

    return (flask.jsonify({"message": ""}), 200)


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
    user = flask_praetorian.current_user()
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

    return _finish_kingdom(kd_id, plan)


@bp.route('/api/resetkingdom', methods=["POST"])
@flask_praetorian.auth_required
@before_start_required
# @flask_praetorian.roles_required('verified')
def reset_initial_kingdom():    
    app = flask.current_app
    db = flask.current_app.extensions["sqlalchemy"]
    user = flask_praetorian.current_user()
    kd_id = user.kd_id
    kd_info = uag._get_kd_info(kd_id)
    request_id = str(uuid.uuid4())
    table_states = {
        f"{table}_{kd_id}": initial_state
        for table, initial_state in uas.INITIAL_KINGDOM_STATE.items()
    }
    if not acquire_locks(table_states, request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
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
            
        db.session.expunge_all()
        user = flask_praetorian.current_user()
        user.kd_created = False
        db.session.commit()
        uaa._update_accounts()
    finally:
        release_locks_by_id(request_id)
    return (flask.jsonify("Reset kingdom"), 200)

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
    start_time_datetime = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    payload["last_income"] = max(state["state"]["game_start"], datetime.datetime.now(datetime.timezone.utc).isoformat())
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
        if v != ""
    }
    valid_shields, error_message = _validate_shields(req_values)
    if not valid_shields:
        return flask.jsonify({"message": error_message}), 400
    
    
    kd_id = flask_praetorian.current_user().kd_id

    def decide(kd_info):
        # Decided against the kingdom as it is when the write lands, not against a read taken before the lock.
        if kd_info["fuel"] <= 0:
            raise occ.Rejected("You can't set shields without fuel")
        return {"shields": {**kd_info["shields"], **req_values}}, None

    # The legacy lock stays while other routes still write the kingdom without checking its version.
    if not acquire_lock(f"/kingdom/{kd_id}"):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        occ.update(f"/kingdom/{kd_id}", decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    finally:
        release_lock(f"/kingdom/{kd_id}")
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

    request_id = str(uuid.uuid4())
    if not acquire_locks([f"/kingdom/{kd_id}/messages", f"/kingdom/{target_kd}/messages", f"/kingdom/{target_kd}/notifs"], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
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
        try:
            ws = SOCK_HANDLERS[target_kd]
            ws.send(json.dumps({
                "message": f"New message from {kingdoms[kd_id]}!",
                "status": "info",
                "category": "Message",
                "delay": 30000,
                "update": ["messages"],
            }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    finally:
        release_locks_by_id(request_id)
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

    if not acquire_lock(f"/kingdom/{kd_id}"):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
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
            if (value or 0) != 0
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
    finally:
        release_lock(f"/kingdom/{kd_id}")
    return (flask.jsonify({"message": message, "status": "success"}), 200)

@bp.route('/api/share/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def share_kd(share_to):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id


    request_id = str(uuid.uuid4())
    if not acquire_locks([f"/kingdom/{kd_id}/revealed", f"/kingdom/{share_to}/revealed"], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        galaxies_inverted, _ = uag._get_galaxies_inverted()
        if galaxies_inverted[kd_id] != galaxies_inverted[share_to]:
            return flask.jsonify("You can only share your kingdom to galaxymates"), 400

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
    finally:
        release_locks_by_id(request_id)
    return (flask.jsonify(kd_response.text)), 200

@bp.route('/api/unshare/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def unshare_kd(share_to):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    request_id = str(uuid.uuid4())
    if not acquire_locks([f"/kingdom/{kd_id}/revealed", f"/kingdom/{share_to}/revealed"], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        galaxies_inverted, _ = uag._get_galaxies_inverted()
        if galaxies_inverted[kd_id] != galaxies_inverted[share_to]:
            return flask.jsonify("You can only share your kingdom to galaxymates"), 400

        # Each list loses one entry, taken from that document's latest version, so an unshare can not undo a share
        # that landed at the same moment on the other entries.
        def stop_sharing(revealed):
            return {"revealed_to_galaxymates": [i for i in revealed["revealed_to_galaxymates"] if i != share_to]}, None

        def stop_receiving(revealed):
            return {"revealed_galaxymates": [i for i in revealed["revealed_galaxymates"] if i != kd_id]}, None

        occ.update(f'/kingdom/{kd_id}/revealed', stop_sharing)
        occ.update(f'/kingdom/{share_to}/revealed', stop_receiving)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    finally:
        release_locks_by_id(request_id)
    return (flask.jsonify("Updated"), 200)

def _add_notifs(kd_id, categories):
    app = flask.current_app
    add_notifs_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"add_categories": categories}),
    )

def _clear_notifs(kd_id, categories):
    app = flask.current_app
    clear_notifs_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"clear_categories": categories}),
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
    kd_id = flask_praetorian.current_user().kd_id
    notifs = _get_notifs(kd_id)
    return flask.jsonify(notifs), 200


@bp.route('/api/clearnotifs', methods=['POST'])
@flask_praetorian.auth_required
def clear_notifs():
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)

    categories = req.get("categories", [])
    if categories:
        _clear_notifs(kd_id, categories)
    
    return "Cleared", 200

def _mark_kingdom_death(kd_id):
    db = flask.current_app.extensions["sqlalchemy"]
    query = db.session.query(User).filter_by(kd_id=kd_id).all()
    user = query[0]
    user.kd_death_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.session.commit()
    uaa._update_accounts()
    try:
        ws = SOCK_HANDLERS[kd_id]
        ws.send(json.dumps({
            "message": f"You died!",
            "status": "warning",
            "category": "Dead",
            "delay": 999999,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    return flask.jsonify(str(user.__dict__))

def acquire_lock(lock_name, timeout=10):
    """
    Try to acquire a lock with a given name.
    
    :param lock_name: Name of the lock
    :param timeout: Expiry time for the lock in seconds
    :return: True if the lock was acquired, False otherwise
    """
    db = flask.current_app.extensions["sqlalchemy"]
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        expiration_time = (now + datetime.timedelta(seconds=timeout)).isoformat()

        # Check if the lock is available or expired
        lock = db.session.query(Locks).filter(Locks.lock_name == lock_name).one_or_none()

        if lock is None or lock.expires_at <= now.isoformat():
            # Acquire or update the lock
            db.session.merge(Locks(lock_name=lock_name, request_id=str(uuid.uuid4()), expires_at=expiration_time))
            db.session.commit()
            return True

        # Lock is already held and not expired
        return False
    except Exception as e:
        print(f"Failed to acquire lock: {e}")
        db.session.rollback()
        return False

def release_lock(lock_name):
    """
    Release a lock with a given name.
    
    :param lock_name: Name of the lock
    """
    db = flask.current_app.extensions["sqlalchemy"]
    try:
        # Delete the lock
        db.session.query(Locks).filter(Locks.lock_name == lock_name).delete()
        db.session.commit()
    except Exception as e:
        print(f"Failed to release lock: {e}")
        db.session.rollback()

def acquire_locks(lock_names, timeout=10, lock_timeout=20, request_id=None) -> bool:
    """
    Try to acquire multiple locks.
    
    :param lock_names: List of lock names to acquire.
    :param timeout: Expiry time for each lock in seconds.
    :return: True if all locks were acquired, False otherwise.
    """
    db = flask.current_app.extensions["sqlalchemy"]
    if request_id is None:
        request_id = str(uuid.uuid4())
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        lock_expiration_time = (now + datetime.timedelta(seconds=lock_timeout)).isoformat()
        timeout_time = (now + datetime.timedelta(seconds=timeout)).isoformat()

        # Check existing locks
        existing_locks = db.session.query(Locks).filter(Locks.lock_name.in_(lock_names)).all()
        print("existing_locks:", existing_locks)
        new_locks = set(lock_names) - set([lock.lock_name for lock in existing_locks])
        print("new_locks:", new_locks)
                
        # Reserve locks while trying to acquire active locks
        for lock_name in new_locks:
            db.session.add(Locks(lock_name=lock_name, request_id=request_id, expires_at=lock_expiration_time))
        if new_locks:
            db.session.commit()

        # Determine if any lock is already held and not expired
        expired_locks = []
        active_locks = []
        for lock in existing_locks:
            if lock.expires_at > str(now):
                active_locks.append(lock.lock_name)
            else:
                expired_locks.append(lock.lock_name)
        print("active_locks:", active_locks)
        print("expired_locks:", expired_locks)
        
        for lock_name in expired_locks:
            db.session.merge(Locks(lock_name=lock_name, request_id=request_id, expires_at=lock_expiration_time))
        if expired_locks:
            db.session.commit()

        db.session.expunge_all()
        before_timeout = True
        while active_locks and before_timeout:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            existing_locks = db.session.query(Locks).filter(Locks.lock_name.in_(active_locks)).all()

            new_locks = set(active_locks) - set([lock.lock_name for lock in existing_locks])
            for lock_name in new_locks:
                db.session.add(Locks(lock_name=lock_name, request_id=request_id, expires_at=lock_expiration_time))
            if new_locks:
                print("new_locks (loop):", new_locks)
                db.session.commit()
            
            expired_locks = [
                lock.lock_name
                for lock in existing_locks
                if lock.expires_at < now
            ]
            for lock_name in expired_locks:
                db.session.merge(Locks(lock_name=lock_name, request_id=request_id, expires_at=lock_expiration_time))
            if expired_locks:
                print("expired_locks (loop):", expired_locks)
                db.session.commit()

            active_locks = set(active_locks) - set(new_locks) - set(expired_locks)
            if new_locks or expired_locks:
                print("active_locks (loop):", active_locks)

            if now > timeout_time:
                before_timeout = False
                release_locks_by_id(request_id)
                return False
            time.sleep(0.01)
        
        return True
    except Exception as e:
        print(f"Failed to acquire locks: {e}")
        db.session.rollback()
        return False

def release_locks_by_name(lock_names):
    """
    Release multiple locks at the same time.

    :param lock_names: List of lock names to release.
    """
    db = flask.current_app.extensions["sqlalchemy"]
    try:
        # Delete all specified locks in a single query
        db.session.query(Locks).filter(Locks.lock_name.in_(lock_names)).delete(
            synchronize_session=False
        )
        db.session.commit()
    except Exception as e:
        print(f"Failed to release locks: {e}")
        db.session.rollback()

def release_locks_by_id(request_id):
    db = flask.current_app.extensions["sqlalchemy"]
    try:
        db.session.query(Locks).filter(Locks.request_id == request_id).delete(
            synchronize_session=False
        )
        db.session.commit()
    except Exception as e:
        print(f"Failed to release locks: {e}")
        db.session.rollback()