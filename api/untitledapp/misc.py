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
from untitledapp import guard, db, User, Locks, REQUESTS_SESSION, SOCK_HANDLERS, before_start_required, alive_required

bp = flask.Blueprint("misc", __name__)

def _create_galaxy(galaxy_id):
    create_galaxy_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
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

@bp.route('/api/createkingdom', methods=["POST"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_initial_kingdom():
    req = flask.request.get_json(force=True)
    user = flask_praetorian.current_user()

    if user.kd_id != "" and user.kd_id != None:
        return (flask.jsonify({"message": "You already have a kingdom ID"}), 400)

    valid_name, message = _validate_kingdom_name(req["kdName"])
    if not valid_name:
        return (flask.jsonify({"message": message}), 400)
    
    request_id = str(uuid.uuid4())
    if not acquire_locks(["/kingdoms", "/galaxies"], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        galaxies = uag._get_galaxy_info()
        size_galaxies = collections.defaultdict(list)
        for galaxy_id, kingdoms in galaxies.items():
            size_galaxies[len(kingdoms)].append(galaxy_id)

        smallest_galaxy_size = min(size_galaxies.keys())
        smallest_galaxies = size_galaxies[smallest_galaxy_size]

        chosen_galaxy = random.choice(smallest_galaxies)
        create_kd_response = REQUESTS_SESSION.post(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({"kingdom_name": req["kdName"], "galaxy": chosen_galaxy}),
        )
        if create_kd_response.status_code != 201:
            return (flask.jsonify({"message": "Error creating kingdom"}), 400)
        
        kd_id = create_kd_response.text

        for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
            item_id = f"{table}_{kd_id}"
            state = initial_state.copy()
            if table == "kingdom":
                state["kdId"] = kd_id
                state["name"] = req["kdName"]

            create_response = REQUESTS_SESSION.post(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
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
    return flask.jsonify({"message": ""}), 200


@bp.route('/api/resetkingdom', methods=["POST"])
@flask_praetorian.auth_required
@before_start_required
# @flask_praetorian.roles_required('verified')
def reset_initial_kingdom():    
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
        for item_id, initial_state in table_states:
            state = initial_state.copy()
            if item_id.split("_")[0] == "kingdom":
                state["kdId"] = kd_id
                state["name"] = kd_info["name"]

            create_response = REQUESTS_SESSION.post(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/createitem',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
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

    payload = {
        "total_points": uas.KINGDOM_CREATOR_STARTING_POINTS,
        "selection_points": uas.KINGDOM_CREATOR_POINTS,
        "total_stars": uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"],
    }
    return (flask.jsonify(payload), 200)

def _validate_kingdom_choices(
    unit_choices,
    structures_choices,
    race,
):
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

@bp.route('/api/createkingdomchoices', methods=["POST"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def create_kingdom_choices():
    req = flask.request.get_json(force=True)
    user = flask_praetorian.current_user()

    if user.kd_created:
        return (flask.jsonify({"message": "This kingdom has already been created"}), 400)

    unit_choices = {
        k: int(v or 0)
        for k, v in req["unitsChoices"].items()
    }
    structures_choices = {
        k: int(v or 0)
        for k, v in req["structuresChoices"].items()
    }
    race = req["race"]

    valid_kd, message = _validate_kingdom_choices(unit_choices, structures_choices, race)
    if not valid_kd:
        return (flask.jsonify({"message": message}), 400)
    
    kd_id = user.kd_id

    if not acquire_lock(f"/kingdom/{kd_id}"):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        kd_info = uag._get_kd_info(kd_id)
        drones = unit_choices.pop("drones")

        payload = {}
        payload["drones"] = drones
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

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )        

        db.session.expunge_all()
        user = flask_praetorian.current_user()
        user.kd_created = True
        db.session.commit()
        uaa._update_accounts()
    finally:
        release_lock(f"/kingdom/{kd_id}")

    return (flask.jsonify({"message": ""}), 200)

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
    kd_info = uag._get_kd_info(kd_id)

    if kd_info["fuel"] <= 0:
        return flask.jsonify({"message": "You can't set shields without fuel"}), 400

    if not acquire_lock(f"/kingdom/{kd_id}"):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        payload = {
            "shields": {
                **kd_info["shields"],
                **req_values,
            }
        }
        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
    finally:
        release_lock(f"/kingdom/{kd_id}")
    return flask.jsonify({"message": "Successfully updated shields", "status": "success"}), 200


@bp.route('/api/messages/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def send_message(target_kd):
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
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/messages',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload_from)
        )
        message_response_to = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/messages',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
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
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id

    if not acquire_lock(f"/kingdom/{kd_id}"):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        kd_info = REQUESTS_SESSION.get(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
        )
        
        kd_info_parse = json.loads(kd_info.text)

        if req.get("enabled", None) != None:
            enabled = req["enabled"]
            payload = {'auto_spending_enabled': enabled}

            if enabled:
                next_resolve = kd_info_parse["next_resolve"]
                next_resolve["auto_spending"] = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"])).isoformat()
                payload["next_resolve"] = next_resolve
            else:
                total_funding = sum(kd_info_parse["funding"].values())
                next_resolve = kd_info_parse["next_resolve"]
                next_resolve["auto_spending"] = uas.DATE_SENTINEL
                payload["next_resolve"] = next_resolve
                payload["money"] = kd_info_parse["money"] + total_funding
                payload["funding"] = {
                    k: 0
                    for k in kd_info_parse["funding"]
                }

            patch_response = REQUESTS_SESSION.patch(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                data=json.dumps(payload),
            )
            if enabled:
                message = "Enabled auto spending and released funding"
            else:
                message = "Disabled auto spending"
            release_lock(f"/kingdom/{kd_id}")
            return (flask.jsonify({"message": message, "status": "success"}), 200)
        
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
            return (flask.jsonify({"message": message}), 400)

        payload = {'auto_spending': new_spending}
        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
    finally:
        release_lock(f"/kingdom/{kd_id}")
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

@bp.route('/api/share/<share_to>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def share_kd(share_to):
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
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(kd_payload),
        )
        share_to_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{share_to}/revealed',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
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
    kd_id = flask_praetorian.current_user().kd_id
    request_id = str(uuid.uuid4())
    if not acquire_locks([f"/kingdom/{kd_id}/revealed", f"/kingdom/{share_to}/revealed"], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        kd_revealed = uag._get_revealed(kd_id)
        share_to_revealed = uag._get_revealed(share_to)

        galaxies_inverted, _ = uag._get_galaxies_inverted()
        if galaxies_inverted[kd_id] != galaxies_inverted[share_to]:
            return flask.jsonify("You can only share your kingdom to galaxymates"), 400

        kd_payload = {
            "revealed_to_galaxymates": [revealed_to_id for revealed_to_id in kd_revealed["revealed_to_galaxymates"] if revealed_to_id != share_to]
        }
        share_to_payload = {
            "revealed_galaxymates": [revealed_id for revealed_id in share_to_revealed["revealed_galaxymates"] if revealed_id != kd_id]
        }
        kd_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(kd_payload),
        )
        share_to_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{share_to}/revealed',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(share_to_payload),
        )
    finally:
        release_locks_by_id(request_id)
    return (flask.jsonify(kd_response.text)), 200

def _add_notifs(kd_id, categories):
    add_notifs_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps({"add_categories": categories}),
    )

def _clear_notifs(kd_id, categories):
    clear_notifs_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps({"clear_categories": categories}),
    )

def _get_notifs(kd_id):
    get_notifs_response = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/notifs',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
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
    try:
        db.session.query(Locks).filter(Locks.request_id == request_id).delete(
            synchronize_session=False
        )
        db.session.commit()
    except Exception as e:
        print(f"Failed to release locks: {e}")
        db.session.rollback()