
import collections
import datetime
import itertools
import json
import math
import os
import random
import uuid

import flask
import flask_praetorian

import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.getters as uag
import untitledapp.shared as uas
from untitledapp import alive_required, start_required, REQUESTS_SESSION, SOCK_HANDLERS

bp = flask.Blueprint("politics", __name__)


def _replace_entries(path, field, remove_if, add=None):
    """
    Drop the entries of a list on a politics document that match ``remove_if``, and optionally add one, on the document
    as it is right now.
    """
    def change(document):
        entries = [entry for entry in document[field] if not remove_if(entry)]
        if add is not None:
            entries.append(add)
        return {field: entries}, None

    occ.update(path, change)


def _claim_entry(path, field, expected, message):
    """Remove ``expected`` from a list on a politics document, or reject if it is no longer there."""
    def claim(document):
        if expected not in document[field]:
            raise occ.Rejected(message)
        return {field: [entry for entry in document[field] if entry != expected]}, None

    occ.update(path, claim)


def _change_empire_galaxies(empire_id, add=None, remove=None):
    """
    Add a galaxy to an empire, or take one out, on the empires document as it is right now (not the copy read at the
    start of the request, which would overwrite changes made since). Returns the empire's galaxies afterwards.
    """
    def change(empires_document):
        empire = empires_document["empires"][empire_id]
        galaxies = [galaxy for galaxy in empire["galaxies"] if galaxy != remove]
        if add is not None and any(
            add in other["galaxies"] for other_id, other in empires_document["empires"].items() if other_id != empire_id
        ):
            # Two invitations accepted at the same moment: whichever lands first wins.
            raise occ.Rejected("That galaxy is already part of an Empire")
        if add is not None and add not in galaxies:
            galaxies.append(add)
        empire["galaxies"] = galaxies
        return {"empires": empires_document["empires"]}, galaxies

    return occ.update('/empires', change)



def _change_list(path, field, add=None, remove=None):
    """
    Add or remove one item of a list on a politics document, on the document as it is right now. Adding an item that
    is there, or removing one that is not, changes nothing, so this is safe to repeat and does not depend on the order
    of requests that overlap.
    """
    def change(document):
        items = [item for item in document[field] if item != remove]
        if add is not None and add not in items:
            items.append(add)
        return {field: items}, None

    occ.update(path, change)


@bp.route('/api/galaxypolitics/leader', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_leader():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, galaxy_id = uag._get_galaxy_politics(kd_id)
    
    if not uam.acquire_lock(f'/galaxy/{galaxy_id}/politics'):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    def vote(galaxy_votes):
        # Added to the votes as they are right now, so galaxymates voting together all count.
        galaxy_votes["votes"]["leader"][kd_id] = req["selected"]
        patch_payload = {
            "votes": galaxy_votes["votes"],
        }
        leader_votes = collections.defaultdict(int)
        for leader in galaxy_votes["votes"]["leader"].values():
            leader_votes[leader] += 1

        current_leader = galaxy_votes["leader"]
        most_votes = max(leader_votes.values())
        kds_with_most_votes = [
            k
            for k, v in leader_votes.items()
            if v == most_votes
        ]
        if len(kds_with_most_votes) == 1 and (kds_with_most_votes[0] != current_leader):
            patch_payload["leader"] = kds_with_most_votes[0]
            galaxy_votes["leader"] = kds_with_most_votes[0]
        return patch_payload, galaxy_votes

    try:
        galaxy_votes = occ.update(f'/galaxy/{galaxy_id}/politics', vote)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    finally:
        uam.release_lock(f'/galaxy/{galaxy_id}/politics')

    return (flask.jsonify(galaxy_votes), 200)

@bp.route('/api/galaxypolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_policies():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, galaxy_id = uag._get_galaxy_politics(kd_id)
    
    if not uam.acquire_lock(f'/galaxy/{galaxy_id}/politics'):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    def vote(galaxy_votes):
        galaxy_votes["votes"][req["policy"]][kd_id] = req["option"].split('_')[-1]
        patch_payload = {
            "votes": galaxy_votes["votes"],
        }
        policy_votes = collections.defaultdict(int)
        for policy in galaxy_votes["votes"][req["policy"]].values():
            policy_votes[policy] += 1

        current_option_winner = galaxy_votes[f"{req['policy']}_winner"]
        most_votes = max(policy_votes.values())
        policies_with_most_votes = [
            k
            for k, v in policy_votes.items()
            if v == most_votes
        ]
        if len(policies_with_most_votes) == 1 and (policies_with_most_votes[0] != current_option_winner):
            patch_payload[f"{req['policy']}_winner"] = policies_with_most_votes[0]
            option_names = [option["name"] for option in uas.GALAXY_POLICIES[req["policy"]]["options"].values()]
            new_option_name = uas.GALAXY_POLICIES[req["policy"]]["options"][policies_with_most_votes[0]]["name"]
            new_active_policies = [policy for policy in galaxy_votes["active_policies"] if policy not in option_names] + [new_option_name]
            patch_payload["active_policies"] = new_active_policies
            galaxy_votes[f"{req['policy']}_winner"] = policies_with_most_votes[0]
            galaxy_votes["active_policies"] = new_active_policies

        return patch_payload, galaxy_votes

    try:
        galaxy_votes = occ.update(f'/galaxy/{galaxy_id}/politics', vote)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    finally:
        uam.release_lock(f'/galaxy/{galaxy_id}/politics')

    return (flask.jsonify(galaxy_votes), 200)

def _validate_empire_name(empire_name, galaxy_politics, kd_id, empires_inverted):

    if empire_name in ("", None):
        return False, "Empire name must be populated"
    
    if galaxy_politics["leader"] != kd_id:
        return False, "You must be galaxy leader to create an Empire"
    
    if empires_inverted.get(kd_id) != None:
        return False, "You are already part of an Empire"
    
    if len(empire_name) > 24:
        return False, "Empire name must be less than 25 characters"
    
    return True, ""


@bp.route('/api/empire', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def create_empire():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    empire_name = req.get("empireName", "")
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, _, _, _ = uag._get_empires_inverted()

    valid_name, message = _validate_empire_name(empire_name, galaxy_politics, kd_id, empires_inverted)
    if not valid_name:
        return flask.jsonify({"message": message}), 400
    
    if not uam.acquire_lock(f'/empires'):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        empire_payload = {
            "empire_name": empire_name,
            "galaxy_id": kd_galaxy,
            "leader": kd_galaxy,
        }
        create_empire_response = REQUESTS_SESSION.post(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empire_payload)
        )
    finally:
        uam.release_lock('/empires')

    return flask.jsonify({"message": "Empire created", "status": "success"}), 201

def _validate_join_empire(galaxy_politics, kd_id, empires_inverted):    
    if galaxy_politics["leader"] != kd_id:
        return False, "You must be galaxy leader to join an Empire"
    
    if empires_inverted.get(kd_id) != None:
        return False, "You are already part of an Empire"
    
    return True, ""

@bp.route('/api/empire/<target_empire>/join', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def request_join_empire(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, _, _, _ = uag._get_empires_inverted()

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{target_empire}/politics', f'/galaxy/{kd_galaxy}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        valid_join, message = _validate_join_empire(galaxy_politics, kd_id, empires_inverted)
        if not valid_join:
            return flask.jsonify({"message": message}), 400
        
        
        target_empire_politics = uag._get_empire_politics(target_empire)

        _change_list(f'/empire/{target_empire}/politics', "empire_join_requests", add=kd_galaxy)
        _change_list(f'/galaxy/{kd_galaxy}/politics', "empire_join_requests", add=target_empire)
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Join request sent", "status": "success"}), 200

@bp.route('/api/empire/<target_empire>/canceljoin', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_join_empire(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)

    if galaxy_politics["leader"] != kd_id:
        return flask.jsonify({"message": "You must be galaxy leader to manage Empire requests"}), 400    
    
    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{target_empire}/politics', f'/galaxy/{kd_galaxy}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        target_empire_politics = uag._get_empire_politics(target_empire)

        _change_list(f'/empire/{target_empire}/politics', "empire_join_requests", remove=kd_galaxy)
        _change_list(f'/galaxy/{kd_galaxy}/politics', "empire_join_requests", remove=target_empire)
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Join request cancelled", "status": "success"}), 200

def _validate_empire_invite(galaxy_politics, kd_id, empires_inverted):    
    if galaxy_politics["leader"] != kd_id:
        return False, "You must be galaxy leader to join an Empire"
    
    if empires_inverted.get(kd_id) != None:
        return False, "You are already part of an Empire"
    
    return True, ""

@bp.route('/api/empire/<target_empire>/acceptinvite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_empire_invite(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks(['/empires', f'/empire/{target_empire}/politics', f'/galaxy/{kd_galaxy}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        valid_invite, message = _validate_empire_invite(galaxy_politics, kd_id, empires_inverted)
        if not valid_invite:
            return flask.jsonify({"message": message}), 400
        
        
        _change_empire_galaxies(target_empire, add=kd_galaxy)
        target_empire_politics = uag._get_empire_politics(target_empire)
        _change_list(f'/empire/{target_empire}/politics', "empire_invitations", remove=kd_galaxy)
        galaxy_payload = {
            "empire_invitations": [],
            "empire_join_requests": []
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{kd_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Joined Empire", "status": "success"}), 200

def _validate_invite_galaxy(empire_politics, kd_id, galaxy_empires, galaxy_id, kd_galaxy_politics, kd_galaxy_id):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if galaxy_empires.get(galaxy_id) != None:
        return False, "That galaxy is already part of an Empire"
    
    return True, ""

@bp.route('/api/galaxy/<target_galaxy>/invite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def invite_galaxy(target_galaxy):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, _, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{kd_empire}/politics', f'/galaxy/{target_galaxy}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        valid_invite, message = _validate_invite_galaxy(empire_politics, kd_id, galaxy_empires, target_galaxy, kd_galaxy_politics, kd_galaxy_id)
        if not valid_invite:
            return flask.jsonify({"message": message}), 400
        

        _change_list(f'/empire/{kd_empire}/politics', "empire_invitations", add=target_galaxy)
        _change_list(f'/galaxy/{target_galaxy}/politics', "empire_invitations", add=kd_empire)
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Invitation sent", "status": "success"}), 200

@bp.route('/api/galaxy/<target_galaxy>/cancelinvite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_invite_galaxy(target_galaxy):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, _, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{kd_empire}/politics', f'/galaxy/{target_galaxy}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        empire_politics = uag._get_empire_politics(kd_empire)
        
        if empire_politics["leader"] != kd_galaxy_id:
            return flask.jsonify({"message": "You are not a part of the Empire's ruling galaxy"}), 400
        
        if kd_galaxy_politics["leader"] != kd_id:
            return flask.jsonify({"message": "You are not the leader of the Empire's ruling galaxy"}), 400
        

        _change_list(f'/empire/{kd_empire}/politics', "empire_invitations", remove=target_galaxy)
        _change_list(f'/galaxy/{target_galaxy}/politics', "empire_invitations", remove=kd_empire)
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Invitation revoked", "status": "success"}), 200

def _validate_accept_galaxy_request(empire_politics, kd_id, galaxy_empires, galaxy_id, kd_galaxy_politics, kd_galaxy_id):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if galaxy_empires.get(galaxy_id) != None:
        return False, "That galaxy is already part of an Empire"
    
    return True, ""

@bp.route('/api/galaxy/<target_galaxy>/accept', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_galaxy_request(target_galaxy):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{kd_empire}/politics', f'/galaxy/{target_galaxy}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        valid_request, message = _validate_accept_galaxy_request(empire_politics, kd_id, galaxy_empires, target_galaxy, kd_galaxy_politics, kd_galaxy_id)
        if not valid_request:
            return flask.jsonify({"message": message}), 400
        

        _change_empire_galaxies(kd_empire, add=target_galaxy)
        _change_list(f'/empire/{kd_empire}/politics', "empire_join_requests", remove=target_galaxy)
        galaxy_payload = {
            "empire_invitations": [],
            "empire_join_requests": []
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{target_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Galaxy added to Empire", "status": "success"}), 200

def _validate_leave_empire(empire_politics, kd_id, kd_galaxy_politics):
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the your galaxy"
    
    return True, ""

@bp.route('/api/leaveempire', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def leave_empire():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks(['/empires', f'/empire/{kd_empire}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        valid_leave, message = _validate_leave_empire(empire_politics, kd_id, kd_galaxy_politics)
        if not valid_leave:
            return flask.jsonify({"message": message}), 400
        
        remaining_galaxies = _change_empire_galaxies(kd_empire, remove=kd_galaxy_id)

        if len(remaining_galaxies) > 0 and empire_politics["leader"] == kd_galaxy_id:
            kd_empire_payload = {
                "leader": random.choice(remaining_galaxies)
            }

            empire_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps(kd_empire_payload)
            )
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Left Empire", "status": "success"}), 200

def _validate_denounce(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_info, target_empire, kd_empire):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if target_empire == kd_empire:
        return False, "You can't denounce yourself"
    
    if empires_info["empires"][kd_empire]["denounced"] != "":
        return False, "You are already denouncing an Empire"

    return True, ""

@bp.route('/api/empire/<target_empire>/denounce', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def denounce(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks(['/universenews', '/empires', f'/empire/{kd_empire}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        time_now = datetime.datetime.now(datetime.timezone.utc)

        def denounce_empire(empires_document):
            # Checked and changed on the empires document as it is right now: two leaders pressing the button together
            # can not both denounce.
            valid_declare, message = _validate_denounce(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_document, target_empire, kd_empire)
            if not valid_declare:
                raise occ.Rejected(message)
            empires = empires_document["empires"]
            empires[kd_empire]["denounced"] = target_empire
            time_denounce_expires = time_now + datetime.timedelta(
                seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["DENOUNCE_DURATION_MULTIPLIER"]
            )
            empires[kd_empire]["denounced_expires"] = time_denounce_expires.isoformat()

            aggression_increase = empires[kd_empire]["aggression_max"] * uas.GAME_CONFIG["DENOUNCE_AGGRO_METER_INCREASE"]
            aggression = empires[kd_empire].setdefault("aggression", {})
            aggression[target_empire] = aggression.get(target_empire, 0) + aggression_increase
            return {"empires": empires}, f"{empires[kd_empire]['name']} has denounced {empires[target_empire]['name']}"

        news = occ.update('/empires', denounce_empire)

        news_payload = {
            "news": {
                "time": time_now.isoformat(),
                "news": news,
            }
        }
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(news_payload)
        )
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Denounced!", "status": "success"}), 200

def _validate_declare_war(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_info, target_empire, kd_empire):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if target_empire == kd_empire:
        return False, "You can't declare war on yourself"
    
    if target_empire in empires_info["empires"][kd_empire]["war"]:
        return False, "You are already at war with that Empire"
    
    if target_empire in empires_info["empires"][kd_empire]["peace"].keys():
        return False, "You can't declare war on a kingdom you are at peace with"

    return True, ""

@bp.route('/api/empire/<target_empire>/declare', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def declare_war(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks(['/universenews', '/empires'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        time_now = datetime.datetime.now(datetime.timezone.utc)

        def declare(empires_document):
            valid_declare, message = _validate_declare_war(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_document, target_empire, kd_empire)
            if not valid_declare:
                raise occ.Rejected(message)
            empires = empires_document["empires"]
            empires[kd_empire]["war"].append(target_empire)
            empires[target_empire]["war"].append(kd_empire)

            time_surprise_war_expires = time_now + datetime.timedelta(
                seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["SURPRISE_WAR_PENALTY_MULTIPLIER"]
            )
            empires[kd_empire]["surprise_war_penalty"] = True
            empires[kd_empire]["surprise_war_penalty_expires"] = time_surprise_war_expires.isoformat()
            return {"empires": empires}, f"{empires[kd_empire]['name']} declared a surprise war on {empires[target_empire]['name']}"

        news = occ.update('/empires', declare)

        news_payload = {
            "news": {
                "time": time_now.isoformat(),
                "news": news,
            }
        }
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(news_payload)
        )
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Declared war!", "status": "success"}), 200

def _validate_request_surrender(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_info, target_empire, kd_empire, surrender_type, surrender_value):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if target_empire == kd_empire:
        return False, "You can't surrender to yourself"
    
    if target_empire not in empires_info["empires"][kd_empire]["war"]:
        return False, "You are not at war with that Empire"
    
    if surrender_value not in uas.SURRENDER_OPTIONS.get(surrender_type, []):
        return False, "That is not a valid surrender option"

    return True, ""

@bp.route('/api/empire/<target_empire>/surrenderrequest', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def request_surrender(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{target_empire}/politics', f'/empire/{kd_empire}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        empire_politics = uag._get_empire_politics(kd_empire)
        target_empire_politics = uag._get_empire_politics(target_empire)

        valid_request, message = _validate_request_surrender(
            empire_politics,
            kd_id,
            kd_galaxy_politics,
            kd_galaxy_id,
            empires_info,
            target_empire,
            kd_empire, 
            surrender_type,
            surrender_value
        )
        if not valid_request:
            return flask.jsonify({"message": message}), 400
        
        
        # Each side's list is changed on that document as it is right now. Replacing an earlier request between the
        # same two empires is the same whatever order overlapping requests arrive in.
        _replace_entries(
            f'/empire/{target_empire}/politics', "surrender_requests_received",
            lambda entry: entry["empire"] == kd_empire,
            add={"type": surrender_type, "value": surrender_value, "empire": kd_empire},
        )
        _replace_entries(
            f'/empire/{kd_empire}/politics', "surrender_requests_sent",
            lambda entry: entry["empire"] == target_empire,
            add={"type": surrender_type, "value": surrender_value, "empire": target_empire},
        )
    finally:
        uam.release_locks_by_id(request_id)

    return flask.jsonify({"message": "Surrender request sent", "status": "success"}), 200

@bp.route('/api/empire/<target_empire>/cancelsurrenderrequest', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_request_surrender(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{target_empire}/politics', f'/empire/{kd_empire}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        empire_politics = uag._get_empire_politics(kd_empire)
        target_empire_politics = uag._get_empire_politics(target_empire)    

        valid_request, message = _validate_request_surrender(
            empire_politics,
            kd_id,
            kd_galaxy_politics,
            kd_galaxy_id,
            empires_info,
            target_empire,
            kd_empire, 
            surrender_type,
            surrender_value
        )
        if not valid_request:
            return flask.jsonify({"message": message}), 400
        

        # Cancelling removes exactly the request that was made (it used to remove any request that shared the empire, the
        # type or the value with it).
        _replace_entries(
            f'/empire/{target_empire}/politics', "surrender_requests_received",
            lambda entry: entry["empire"] == kd_empire and entry["type"] == surrender_type and entry["value"] == surrender_value,
        )
        _replace_entries(
            f'/empire/{kd_empire}/politics', "surrender_requests_sent",
            lambda entry: entry["empire"] == target_empire and entry["type"] == surrender_type and entry["value"] == surrender_value,
        )
    finally:
        uam.release_locks_by_id(request_id)

    return flask.jsonify({"message": "Surrender request cancelled", "status": "success"}), 200

def _validate_offer_surrender(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_info, target_empire, kd_empire, surrender_type, surrender_value):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if target_empire == kd_empire:
        return False, "You can't surrender to yourself"
    
    if target_empire not in empires_info["empires"][kd_empire]["war"]:
        return False, "You are not at war with that Empire"
    
    if surrender_value not in uas.SURRENDER_OPTIONS.get(surrender_type, []):
        return False, "That is not a valid surrender option"

    return True, ""

@bp.route('/api/empire/<target_empire>/surrenderoffer', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def offer_surrender(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{target_empire}/politics', f'/empire/{kd_empire}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        empire_politics = uag._get_empire_politics(kd_empire)
        target_empire_politics = uag._get_empire_politics(target_empire)

        valid_request, message = _validate_offer_surrender(
            empire_politics,
            kd_id,
            kd_galaxy_politics,
            kd_galaxy_id,
            empires_info,
            target_empire,
            kd_empire, 
            surrender_type,
            surrender_value
        )
        if not valid_request:
            return flask.jsonify({"message": message}), 400
        
        
        _replace_entries(
            f'/empire/{target_empire}/politics', "surrender_offers_received",
            lambda entry: entry["empire"] == kd_empire,
            add={"type": surrender_type, "value": surrender_value, "empire": kd_empire},
        )
        _replace_entries(
            f'/empire/{kd_empire}/politics', "surrender_offers_sent",
            lambda entry: entry["empire"] == target_empire,
            add={"type": surrender_type, "value": surrender_value, "empire": target_empire},
        )
    finally:
        uam.release_locks_by_id(request_id)

    return flask.jsonify({"message": "Surrender offer sent", "status": "success"}), 200

@bp.route('/api/empire/<target_empire>/cancelsurrenderoffer', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_offer_surrender(target_empire):
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/empire/{target_empire}/politics', f'/empire/{kd_empire}/politics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        empire_politics = uag._get_empire_politics(kd_empire)
        target_empire_politics = uag._get_empire_politics(target_empire)

        valid_request, message = _validate_offer_surrender(
            empire_politics,
            kd_id,
            kd_galaxy_politics,
            kd_galaxy_id,
            empires_info,
            target_empire,
            kd_empire, 
            surrender_type,
            surrender_value
        )
        if not valid_request:
            return flask.jsonify({"message": message}), 400
        

        _replace_entries(
            f'/empire/{target_empire}/politics', "surrender_offers_received",
            lambda entry: entry["empire"] == kd_empire and entry["type"] == surrender_type and entry["value"] == surrender_value,
        )
        _replace_entries(
            f'/empire/{kd_empire}/politics', "surrender_offers_sent",
            lambda entry: entry["empire"] == target_empire and entry["type"] == surrender_type and entry["value"] == surrender_value,
        )
    finally:
        uam.release_locks_by_id(request_id)

    return flask.jsonify({"message": "Surrender offer cancelled", "status": "success"}), 200

def _surrender(
    empires_info,
    losing_empire,
    winning_empire,
    losing_kds,
    winning_kds,
    surrender_type,
    surrender_value,
):
    """
    Carry out an accepted surrender. Each change is made to the latest version of the document it concerns and does not
    depend on the others, so it can not undo anything written meanwhile (a player spending, a refresh crediting).
    """
    if surrender_type == "stars" and surrender_value != 0:
        stars_pool = 0
        for losing_kd in losing_kds:
            def lose(kd):
                lost = math.floor(surrender_value * kd["stars"])
                return {"stars": kd["stars"] - lost}, lost

            stars_pool += occ.update(f'/kingdom/{losing_kd}', lose)
        stars_per_kd = math.floor(stars_pool / len(winning_kds))
        for winning_kd in winning_kds:
            occ.update(f'/kingdom/{winning_kd}', lambda kd: ({"stars": kd["stars"] + stars_per_kd}, None))

    for empire, other in ((winning_empire, losing_empire), (losing_empire, winning_empire)):
        for field in ("surrender_offers_sent", "surrender_offers_received", "surrender_requests_sent", "surrender_requests_received"):
            _replace_entries(f'/empire/{empire}/politics', field, lambda entry, other=other: entry["empire"] == other)

    time_now = datetime.datetime.now(datetime.timezone.utc)
    time_peace_expires = (time_now + datetime.timedelta(
        seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["PEACE_DURATION_MULTIPLIER"]
    )).isoformat()

    def make_peace(empires_document):
        empires = empires_document["empires"]
        for empire, other in ((winning_empire, losing_empire), (losing_empire, winning_empire)):
            empires[empire].setdefault("aggression", {})[other] = 0
            empires[empire]["war"] = [empire_id for empire_id in empires[empire]["war"] if empire_id != other]
            empires[empire]["peace"][other] = time_peace_expires
        return {"empires": empires}, None

    occ.update('/empires', make_peace)

@bp.route('/api/empire/<target_empire>/acceptsurrenderoffer', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_offer_surrender(target_empire):
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, galaxy_info = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    winning_empire = kd_empire
    losing_empire = target_empire
    
    losing_galaxies = empires_info["empires"][losing_empire]["galaxies"]
    winning_galaxies = empires_info["empires"][winning_empire]["galaxies"]

    losing_kds = list(itertools.chain.from_iterable([galaxy_info[galaxy] for galaxy in losing_galaxies]))
    winning_kds = list(itertools.chain.from_iterable([galaxy_info[galaxy] for galaxy in winning_galaxies]))

    request_id = str(uuid.uuid4())
    base_locks = ['/empires', f'/empire/{target_empire}/politics', f'/empire/{kd_empire}/politics']
    base_locks.extend([
        f"/kingdom/{kd_id}" for kd_id in losing_kds
    ])
    base_locks.extend([
        f"/kingdom/{kd_id}" for kd_id in winning_kds
    ])
    if not uam.acquire_locks(base_locks, request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        valid_request, message = _validate_offer_surrender(
            empire_politics,
            kd_id,
            kd_galaxy_politics,
            kd_galaxy_id,
            empires_info,
            target_empire,
            kd_empire, 
            surrender_type,
            surrender_value
        )
        if not valid_request:
            return flask.jsonify({"message": message}), 400
        
        expected_surrender_offer = {
            "empire": target_empire,
            "type": surrender_type,
            "value": surrender_value
        }
        # Taking the offer out of this empire's list is what decides who gets to carry it out: of two leaders pressing
        # accept together, only one finds it there.
        _claim_entry(f'/empire/{kd_empire}/politics', "surrender_offers_received", expected_surrender_offer, "Could not find surrender offer")

        _surrender(
            empires_info,
            losing_empire,
            winning_empire,
            losing_kds,
            winning_kds,
            surrender_type,
            surrender_value,
        )
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Surrender offer has been accepted", "status": "success"}), 200

@bp.route('/api/empire/<target_empire>/acceptsurrenderrequest', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_request_surrender(target_empire):
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, galaxy_info = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
        
    winning_empire = target_empire
    losing_empire = kd_empire
    
    losing_galaxies = empires_info["empires"][losing_empire]["galaxies"]
    winning_galaxies = empires_info["empires"][winning_empire]["galaxies"]

    losing_kds = list(itertools.chain.from_iterable([galaxy_info[galaxy] for galaxy in losing_galaxies]))
    winning_kds = list(itertools.chain.from_iterable([galaxy_info[galaxy] for galaxy in winning_galaxies]))

    request_id = str(uuid.uuid4())
    base_locks = ['/empires', f'/empire/{target_empire}/politics', f'/empire/{kd_empire}/politics']
    base_locks.extend([
        f"/kingdom/{kd_id}" for kd_id in losing_kds
    ])
    base_locks.extend([
        f"/kingdom/{kd_id}" for kd_id in winning_kds
    ])
    if not uam.acquire_locks(base_locks, request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        valid_request, message = _validate_request_surrender(
            empire_politics,
            kd_id,
            kd_galaxy_politics,
            kd_galaxy_id,
            empires_info,
            target_empire,
            kd_empire, 
            surrender_type,
            surrender_value
        )
        if not valid_request:
            return flask.jsonify({"message": message}), 400
        
        expected_surrender_request = {
            "empire": target_empire,
            "type": surrender_type,
            "value": surrender_value
        }
        # Taking the request out of this empire's list is what decides who gets to carry it out: of two leaders pressing
        # accept together, only one finds it there.
        _claim_entry(f'/empire/{kd_empire}/politics', "surrender_requests_received", expected_surrender_request, "Could not find surrender request")

        _surrender(
            empires_info,
            losing_empire,
            winning_empire,
            losing_kds,
            winning_kds,
            surrender_type,
            surrender_value,
        )
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400
    finally:
        uam.release_locks_by_id(request_id)
    return flask.jsonify({"message": "Surrender request has been accepted", "status": "success"}), 200
    


def _validate_buy_votes(
    kd_info,
    votes,
):
    if votes <= 0:
        return False, "Votes must be greater than 0"
    votes_cost = votes * uas.GAME_CONFIG["BASE_VOTES_COST"]
    if votes_cost > kd_info["money"]:
        return False, "Not enough money"
    
    return True, ""

@bp.route('/api/votes', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def buy_votes():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    votes = int(req["votes"])
    votes_cost = votes * uas.GAME_CONFIG["BASE_VOTES_COST"]

    if not uam.acquire_lock(f'/kingdom/{kd_id}'):
        return (flask.jsonify({"message": "Server is busy"}), 400)

    def decide(kd_info):
        valid_votes, message = _validate_buy_votes(kd_info, votes)
        if not valid_votes:
            raise occ.Rejected(message)

        return {
            "money": kd_info["money"] - votes_cost,
            "votes": kd_info["votes"] + votes,
        }, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    finally:
        uam.release_lock(f'/kingdom/{kd_id}')
    return (flask.jsonify({"message": "Bought votes", "status": "success"}), 200)

def _validate_cast_votes(
    kd_info,
    votes,
):
    if votes <= 0:
        return False, "Votes must be greater than 0"
    if votes > kd_info["votes"]:
        return False, "Not enough votes available"
    
    return True, ""

@bp.route('/api/universepolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def universe_policies():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    request_id = str(uuid.uuid4())
    if not uam.acquire_locks([f'/kingdom/{kd_id}', f'/universepolitics'], request_id=request_id):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    votes = int(req["votes"])
    policy = req["policy"]
    option = req["option"]

    def take_votes(kd_info):
        valid_votes, message = _validate_cast_votes(kd_info, votes)
        if not valid_votes:
            raise occ.Rejected(message)
        return {"votes": kd_info["votes"] - votes}, None

    def add_votes(universe_politics):
        try:
            universe_politics["votes"][policy][option][kd_id] += votes
        except KeyError:
            universe_politics["votes"][policy][option][kd_id] = votes
        return {"votes": universe_politics["votes"]}, None

    def give_back(kd_info):
        return {"votes": kd_info["votes"] + votes}, None

    try:
        # The votes are spent first, against the kingdom as it is right now, so two racing requests can not both
        # cast the same votes. Adding to the tally is then an increment on the freshest tally. If that fails, the
        # votes are handed back.
        occ.update(f'/kingdom/{kd_id}', take_votes)
        try:
            occ.update('/universevotes', add_votes, write_path='/universepolitics')
        except Exception:
            occ.update(f'/kingdom/{kd_id}', give_back)
            raise
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    finally:
        uam.release_locks_by_id(request_id)

    return (flask.jsonify({"message": "Cast votes", "status": "success"}), 200)
