
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
import untitledapp.getters as uag
import untitledapp.shared as uas
from untitledapp import alive_required, start_required, REQUESTS_SESSION, SOCK_HANDLERS

bp = flask.Blueprint("politics", __name__)

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
    
    try:
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
        
        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(patch_payload)
        )
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

    try:
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

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(patch_payload)
        )
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

        new_empire_requests = set(target_empire_politics["empire_join_requests"])
        new_empire_requests.add(kd_galaxy)

        target_empire_payload = {
            "empire_join_requests": list(new_empire_requests)
        }

        join_empire_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_empire_payload)
        )

        new_galaxy_empire_requests = set(galaxy_politics["empire_join_requests"])
        new_galaxy_empire_requests.add(target_empire)
        galaxy_payload = {
            "empire_join_requests": list(new_galaxy_empire_requests)
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{kd_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
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

        new_empire_requests = set(target_empire_politics["empire_join_requests"])
        new_empire_requests.remove(kd_galaxy)

        target_empire_payload = {
            "empire_join_requests": list(new_empire_requests)
        }

        join_empire_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_empire_payload)
        )

        new_galaxy_empire_requests = set(galaxy_politics["empire_join_requests"])
        new_galaxy_empire_requests.remove(target_empire)
        galaxy_payload = {
            "empire_join_requests": list(new_galaxy_empire_requests)
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{kd_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
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
        
        
        empires_info["empires"][target_empire]["galaxies"].append(kd_galaxy)
        empires_payload = {
            "empires": empires_info["empires"]
        }

        empires_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empires_payload)
        )

        target_empire_politics = uag._get_empire_politics(target_empire)
        new_empire_requests = set(target_empire_politics["empire_invitations"])
        new_empire_requests.remove(kd_galaxy)

        target_empire_payload = {
            "empire_invitations": list(new_empire_requests)
        }

        join_empire_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_empire_payload)
        )

        galaxy_payload = {
            "empire_invitations": [],
            "empire_join_requests": []
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{kd_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
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
        

        new_empire_requests = set(empire_politics["empire_invitations"])
        new_empire_requests.add(target_galaxy)

        kd_empire_payload = {
            "empire_invitations": list(new_empire_requests)
        }

        join_empire_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_empire_payload)
        )

        new_galaxy_empire_invitations = set(galaxy_politics["empire_invitations"])
        new_galaxy_empire_invitations.add(kd_empire)
        galaxy_payload = {
            "empire_invitations": list(new_galaxy_empire_invitations)
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{target_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
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
        

        new_empire_requests = set(empire_politics["empire_invitations"])
        new_empire_requests.remove(target_galaxy)

        kd_empire_payload = {
            "empire_invitations": list(new_empire_requests)
        }

        join_empire_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_empire_payload)
        )

        new_galaxy_empire_invitations = set(galaxy_politics["empire_invitations"])
        new_galaxy_empire_invitations.remove(kd_empire)
        galaxy_payload = {
            "empire_invitations": list(new_galaxy_empire_invitations)
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{target_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
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
        

        empires_info[kd_empire]["galaxies"].append(target_galaxy)
        empires_payload = {
            "empires": empires_info
        }

        empires_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empires_payload)
        )

        new_empire_requests = set(empire_politics["empire_join_requests"])
        new_empire_requests.remove(target_galaxy)

        kd_empire_payload = {
            "empire_join_requests": list(new_empire_requests)
        }

        join_empire_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_empire_payload)
        )

        galaxy_payload = {
            "empire_invitations": [],
            "empire_join_requests": []
        }

        galaxy_politics_info = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{target_galaxy}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(galaxy_payload)
        )
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
        
        empires_info[kd_empire]["galaxies"] = [
            galaxy_id
            for galaxy_id in empires_info[kd_empire]["galaxies"]
            if galaxy_id != kd_galaxy_id
        ]
        empires_payload = {
            "empires": empires_info
        }

        empires_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empires_payload)
        )

        if len(empires_info[kd_empire]["galaxies"]) > 0 and empire_politics["leader"] == kd_galaxy_id:
            kd_empire_payload = {
                "leader": random.choice(empires_info[kd_empire]["galaxies"])
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

        valid_declare, message = _validate_denounce(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_info, target_empire, kd_empire)
        if not valid_declare:
            return flask.jsonify({"message": message}), 400
        
        empires_info["empires"][kd_empire]["denounced"] = target_empire

        time_now = datetime.datetime.now(datetime.timezone.utc)
        time_denounce_expires = time_now + datetime.timedelta(
            seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["DENOUNCE_DURATION_MULTIPLIER"]
        )
        empires_info["empires"][kd_empire]["denounced_expires"] = time_denounce_expires.isoformat()

        aggression_increase = empires_info["empires"][kd_empire]["aggression_max"] * uas.GAME_CONFIG["DENOUNCE_AGGRO_METER_INCREASE"]
        try:
            empires_info["empires"][kd_empire]["aggression"][target_empire] += aggression_increase
        except KeyError:
            empires_info["empires"][kd_empire]["aggression"][target_empire] = aggression_increase

        news_payload = {
            "news": {
                "time": time_now.isoformat(),
                "news": f"{empires_info['empires'][kd_empire]['name']} has denounced {empires_info['empires'][target_empire]['name']}",
            }
        }
        universe_news_update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(news_payload)
        )

        empires_payload = {
            "empires": empires_info["empires"],
        }
        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empires_payload)
        )
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

        valid_declare, message = _validate_declare_war(empire_politics, kd_id, kd_galaxy_politics, kd_galaxy_id, empires_info, target_empire, kd_empire)
        if not valid_declare:
            return flask.jsonify({"message": message}), 400
        
        empires_info["empires"][kd_empire]["war"].append(target_empire)
        empires_info["empires"][target_empire]["war"].append(kd_empire)

        time_now = datetime.datetime.now(datetime.timezone.utc)
        time_surprise_war_expires = time_now + datetime.timedelta(
            seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["SURPRISE_WAR_PENALTY_MULTIPLIER"]
        )
        empires_info["empires"][kd_empire]["surprise_war_penalty"] = True
        empires_info["empires"][kd_empire]["surprise_war_penalty_expires"] = time_surprise_war_expires.isoformat()

        news_payload = {
            "news": {
                "time": time_now.isoformat(),
                "news": f"{empires_info['empires'][kd_empire]['name']} declared a surprise war on {empires_info['empires'][target_empire]['name']}",
            }
        }
        universe_news_update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(news_payload)
        )

        empires_payload = {
            "empires": empires_info["empires"],
        }
        update_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empires_payload)
        )
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
        
        
        new_surrender_sender = {
            "type": surrender_type,
            "value": surrender_value,
            "empire": target_empire
        }
        new_surrender_receiver = {
            "type": surrender_type,
            "value": surrender_value,
            "empire": kd_empire,
        }
        new_empire_requests_receiver = [
            item
            for item in target_empire_politics["surrender_requests_received"]
            if item["empire"] != kd_empire
        ]
        new_empire_requests_receiver.append(new_surrender_receiver)
        new_empire_requests_sender = [
            item
            for item in empire_politics["surrender_requests_sent"]
            if item["empire"] != target_empire
        ]
        new_empire_requests_sender.append(new_surrender_sender)

        target_empire_payload = {
            "surrender_requests_received": new_empire_requests_receiver
        }

        surrender_target_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_empire_payload)
        )
        empire_payload = {
            "surrender_requests_sent": new_empire_requests_sender
        }

        surrender_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empire_payload)
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
        

        new_empire_requests_receiver = [
            item
            for item in target_empire_politics["surrender_requests_received"]
            if (
                item["empire"] != kd_empire
                and item["type"] != surrender_type
                and item["value"] != surrender_value
            )
        ]
        new_empire_requests_sender = [
            item
            for item in empire_politics["surrender_requests_sent"]
            if (
                item["empire"] != target_empire
                and item["type"] != surrender_type
                and item["value"] != surrender_value
            )
        ]

        target_empire_payload = {
            "surrender_requests_received": new_empire_requests_receiver
        }

        surrender_target_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_empire_payload)
        )
        empire_payload = {
            "surrender_requests_sent": new_empire_requests_sender
        }

        surrender_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empire_payload)
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
        
        
        new_surrender_sender = {
            "type": surrender_type,
            "value": surrender_value,
            "empire": target_empire
        }
        new_surrender_receiver = {
            "type": surrender_type,
            "value": surrender_value,
            "empire": kd_empire,
        }
        new_empire_offers_receiver = [
            item
            for item in target_empire_politics["surrender_offers_received"]
            if item["empire"] != kd_empire
        ]
        new_empire_offers_receiver.append(new_surrender_receiver)
        new_empire_offers_sender = [
            item
            for item in empire_politics["surrender_offers_sent"]
            if item["empire"] != target_empire
        ]
        new_empire_offers_sender.append(new_surrender_sender)

        target_empire_payload = {
            "surrender_offers_received": new_empire_offers_receiver
        }

        surrender_target_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_empire_payload)
        )
        empire_payload = {
            "surrender_offers_sent": new_empire_offers_sender
        }

        surrender_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empire_payload)
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
        

        new_empire_offers_receiver = [
            item
            for item in target_empire_politics["surrender_offers_received"]
            if (
                item["empire"] != kd_empire
                and item["type"] != surrender_type
                and item["value"] != surrender_value
            )
        ]
        new_empire_offers_sender = [
            item
            for item in empire_politics["surrender_offers_sent"]
            if (
                item["empire"] != target_empire
                and item["type"] != surrender_type
                and item["value"] != surrender_value
            )
        ]

        target_empire_payload = {
            "surrender_offers_received": new_empire_offers_receiver
        }

        surrender_target_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_empire_payload)
        )
        empire_payload = {
            "surrender_offers_sent": new_empire_offers_sender
        }

        surrender_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(empire_payload)
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
    app = flask.current_app
    losing_empire_politics = uag._get_empire_politics(losing_empire)
    winning_empire_politics = uag._get_empire_politics(winning_empire)
    if surrender_type == "stars":
        if surrender_value == 0:
            pass
        else:
            stars_pool = 0
            for losing_kd in losing_kds:
                losing_kd_info = uag._get_kd_info(losing_kd)
                stars_lost = math.floor(surrender_value * losing_kd_info["stars"])
                new_stars = losing_kd_info["stars"] - stars_lost
                stars_pool += stars_lost
                patch_payload = {"stars": new_stars}
                kd_patch_response = REQUESTS_SESSION.patch(
                    app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{losing_kd}',
                    headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                    data=json.dumps(patch_payload)
                )
            stars_per_kd = math.floor(stars_pool / len(winning_kds))
            for winning_kd in winning_kds:
                winning_kd_info = uag._get_kd_info(winning_kd)
                new_stars = winning_kd_info["stars"] + stars_per_kd
                patch_payload = {"stars": new_stars}
                kd_patch_response = REQUESTS_SESSION.patch(
                    app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{winning_kd}',
                    headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                    data=json.dumps(patch_payload)
                )

    winning_empire_politics_payload = {
        "surrender_offers_sent": [
            offer for offer in winning_empire_politics["surrender_offers_sent"]
            if offer["empire"] != losing_empire
        ],
        "surrender_offers_received": [
            offer for offer in winning_empire_politics["surrender_offers_received"]
            if offer["empire"] != losing_empire
        ],
        "surrender_requests_sent": [
            offer for offer in winning_empire_politics["surrender_requests_sent"]
            if offer["empire"] != losing_empire
        ],
        "surrender_requests_received": [
            offer for offer in winning_empire_politics["surrender_requests_received"]
            if offer["empire"] != losing_empire
        ],
    }
    winning_empire_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{winning_empire}/politics',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(winning_empire_politics_payload)
    )
    losing_empire_politics_payload = {
        "surrender_offers_sent": [
            offer for offer in losing_empire_politics["surrender_offers_sent"]
            if offer["empire"] != winning_empire
        ],
        "surrender_offers_received": [
            offer for offer in losing_empire_politics["surrender_offers_received"]
            if offer["empire"] != winning_empire
        ],
        "surrender_requests_sent": [
            offer for offer in losing_empire_politics["surrender_requests_sent"]
            if offer["empire"] != winning_empire
        ],
        "surrender_requests_received": [
            offer for offer in losing_empire_politics["surrender_requests_received"]
            if offer["empire"] != winning_empire
        ],
    }
    losing_empire_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{losing_empire}/politics',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(losing_empire_politics_payload)
    )


    empires_info["empires"][winning_empire]["aggression"][losing_empire] = 0
    empires_info["empires"][losing_empire]["aggression"][winning_empire] = 0

    empires_info["empires"][winning_empire]["war"] = [
        empire_id for empire_id in empires_info["empires"][winning_empire]["war"]
        if empire_id != losing_empire
    ]
    empires_info["empires"][losing_empire]["war"] = [
        empire_id for empire_id in empires_info["empires"][losing_empire]["war"]
        if empire_id != winning_empire
    ]

    time_now = datetime.datetime.now(datetime.timezone.utc)
    time_peace_expires = time_now + datetime.timedelta(
        seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["PEACE_DURATION_MULTIPLIER"]
    )
    empires_info["empires"][winning_empire]["peace"][losing_empire] = time_peace_expires.isoformat()
    empires_info["empires"][losing_empire]["peace"][winning_empire] = time_peace_expires.isoformat()
    empires_payload = {
        "empires": empires_info["empires"]
    }
    empires_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(empires_info)
    )

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
        if expected_surrender_offer not in empire_politics["surrender_offers_received"]:
            return flask.jsonify({"message": "Could not find surrender offer"}), 400
        
        _surrender(
            empires_info,
            losing_empire,
            winning_empire,
            losing_kds,
            winning_kds,
            surrender_type,
            surrender_value,
        )
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
        if expected_surrender_request not in empire_politics["surrender_requests_received"]:
            return flask.jsonify({"message": "Could not find surrender request"}), 400

        _surrender(
            empires_info,
            losing_empire,
            winning_empire,
            losing_kds,
            winning_kds,
            surrender_type,
            surrender_value,
        )
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
    
    if not uam.acquire_lock(f'/kingdom/{kd_id}'):
        return (flask.jsonify({"message": "Server is busy"}), 400)
    try:
        kd_info = uag._get_kd_info(kd_id)
        
        votes = int(req["votes"])
        votes_cost = votes * uas.GAME_CONFIG["BASE_VOTES_COST"]

        valid_votes, message = _validate_buy_votes(kd_info, votes)
        if not valid_votes:
            return flask.jsonify({"message": message}), 400
        
        kd_patch_payload = {
            "money": kd_info["money"] - votes_cost,
            "votes": kd_info["votes"] + votes,
        }
        kd_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_patch_payload)
        )
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
    
    try:
        kd_info = uag._get_kd_info(kd_id)
        
        votes = int(req["votes"])
        policy = req["policy"]
        option = req["option"]

        valid_votes, message = _validate_cast_votes(kd_info, votes)
        if not valid_votes:
            return flask.jsonify({"message": message}), 400
        
        universe_politics = uag._get_universe_politics()

        kd_patch_payload = {
            "votes": kd_info["votes"] - votes,
        }

        try:
            universe_politics["votes"][policy][option][kd_id] += votes
        except KeyError:
            universe_politics["votes"][policy][option][kd_id] = votes

        kd_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_patch_payload)
        )

        universe_politics_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universepolitics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(universe_politics)
        )
    finally:
        uam.release_locks_by_id(request_id)

    return (flask.jsonify({"message": "Cast votes", "status": "success"}), 200)