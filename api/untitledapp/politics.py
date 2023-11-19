
import collections
import datetime
import json
import os
import random

import flask
import flask_praetorian

import untitledapp.getters as uag
import untitledapp.shared as uas
from untitledapp import app, alive_required, start_required, REQUESTS_SESSION, SOCK_HANDLERS

@app.route('/api/galaxypolitics/leader', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_leader():
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, galaxy_id = uag._get_galaxy_politics(kd_id)

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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(patch_payload)
    )

    return (flask.jsonify(galaxy_votes), 200)

@app.route('/api/galaxypolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_policies():
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, galaxy_id = uag._get_galaxy_politics(kd_id)

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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(patch_payload)
    )

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


@app.route('/api/empire', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def create_empire():
    req = flask.request.get_json(force=True)
    empire_name = req.get("empireName", "")
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, _, _, _ = uag._get_empires_inverted()

    valid_name, message = _validate_empire_name(empire_name, galaxy_politics, kd_id, empires_inverted)
    if not valid_name:
        return flask.jsonify({"message": message}), 400
    
    empire_payload = {
        "empire_name": empire_name,
        "galaxy_id": kd_galaxy,
        "leader": kd_galaxy,
    }
    create_empire_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empire_payload)
    )

    return flask.jsonify({"message": "Empire created", "status": "success"}), 201

def _validate_join_empire(galaxy_politics, kd_id, empires_inverted):    
    if galaxy_politics["leader"] != kd_id:
        return False, "You must be galaxy leader to join an Empire"
    
    if empires_inverted.get(kd_id) != None:
        return False, "You are already part of an Empire"
    
    return True, ""

@app.route('/api/empire/<target_empire>/join', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def request_join_empire(target_empire):
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, _, _, _ = uag._get_empires_inverted()

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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_empire_payload)
    )

    new_galaxy_empire_requests = set(galaxy_politics["empire_join_requests"])
    new_galaxy_empire_requests.add(target_empire)
    galaxy_payload = {
        "empire_join_requests": list(new_galaxy_empire_requests)
    }

    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{kd_galaxy}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(galaxy_payload)
    )
    return flask.jsonify({"message": "Join request sent", "status": "success"}), 200

@app.route('/api/empire/<target_empire>/canceljoin', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_join_empire(target_empire):
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)

    if galaxy_politics["leader"] != kd_id:
        return flask.jsonify({"message": "You must be galaxy leader to manage Empire requests"}), 400    
    
    target_empire_politics = uag._get_empire_politics(target_empire)

    new_empire_requests = set(target_empire_politics["empire_join_requests"])
    new_empire_requests.remove(kd_galaxy)

    target_empire_payload = {
        "empire_join_requests": list(new_empire_requests)
    }

    join_empire_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_empire_payload)
    )

    new_galaxy_empire_requests = set(galaxy_politics["empire_join_requests"])
    new_galaxy_empire_requests.remove(target_empire)
    galaxy_payload = {
        "empire_join_requests": list(new_galaxy_empire_requests)
    }

    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{kd_galaxy}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(galaxy_payload)
    )
    return flask.jsonify({"message": "Join request cancelled", "status": "success"}), 200

def _validate_empire_invite(galaxy_politics, kd_id, empires_inverted):    
    if galaxy_politics["leader"] != kd_id:
        return False, "You must be galaxy leader to join an Empire"
    
    if empires_inverted.get(kd_id) != None:
        return False, "You are already part of an Empire"
    
    return True, ""

@app.route('/api/empire/<target_empire>/acceptinvite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_empire_invite(target_empire):
    kd_id = flask_praetorian.current_user().kd_id

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()

    valid_invite, message = _validate_empire_invite(galaxy_politics, kd_id, empires_inverted)
    if not valid_invite:
        return flask.jsonify({"message": message}), 400
    
    
    empires_info[target_empire]["galaxies"].append(kd_galaxy)
    empires_payload = {
        "empires": empires_info
    }

    empires_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empires_payload)
    )

    target_empire_politics = uag._get_empire_politics(target_empire)
    new_empire_requests = set(target_empire_politics["empire_invitations"])
    new_empire_requests.remove(kd_galaxy)

    target_empire_payload = {
        "empire_invitations": list(new_empire_requests)
    }

    join_empire_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_empire_payload)
    )

    galaxy_payload = {
        "empire_invitations": [],
        "empire_join_requests": []
    }

    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{kd_galaxy}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(galaxy_payload)
    )
    return flask.jsonify({"message": "Joined Empire", "status": "success"}), 200

def _validate_invite_galaxy(empire_politics, kd_id, galaxy_empires, galaxy_id, kd_galaxy_politics, kd_galaxy_id):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if galaxy_empires.get(galaxy_id) != None:
        return False, "That galaxy is already part of an Empire"
    
    return True, ""

@app.route('/api/galaxy/<target_galaxy>/invite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def invite_galaxy(target_galaxy):
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, _, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_empire_payload)
    )

    new_galaxy_empire_invitations = set(galaxy_politics["empire_invitations"])
    new_galaxy_empire_invitations.add(kd_empire)
    galaxy_payload = {
        "empire_invitations": list(new_galaxy_empire_invitations)
    }

    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{target_galaxy}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(galaxy_payload)
    )
    return flask.jsonify({"message": "Invitation sent", "status": "success"}), 200

@app.route('/api/galaxy/<target_galaxy>/cancelinvite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_invite_galaxy(target_galaxy):
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, _, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_empire_payload)
    )

    new_galaxy_empire_invitations = set(galaxy_politics["empire_invitations"])
    new_galaxy_empire_invitations.remove(kd_empire)
    galaxy_payload = {
        "empire_invitations": list(new_galaxy_empire_invitations)
    }

    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{target_galaxy}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(galaxy_payload)
    )
    return flask.jsonify({"message": "Invitation revoked", "status": "success"}), 200

def _validate_accept_galaxy_request(empire_politics, kd_id, galaxy_empires, galaxy_id, kd_galaxy_politics, kd_galaxy_id):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if galaxy_empires.get(galaxy_id) != None:
        return False, "That galaxy is already part of an Empire"
    
    return True, ""

@app.route('/api/galaxy/<target_galaxy>/accept', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_galaxy_request(target_galaxy):
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
    empire_politics = uag._get_empire_politics(kd_empire)

    valid_request, message = _validate_accept_galaxy_request(empire_politics, kd_id, galaxy_empires, target_galaxy, kd_galaxy_politics, kd_galaxy_id)
    if not valid_request:
        return flask.jsonify({"message": message}), 400
    

    empires_info[kd_empire]["galaxies"].append(target_galaxy)
    empires_payload = {
        "empires": empires_info
    }

    empires_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empires_payload)
    )

    new_empire_requests = set(empire_politics["empire_join_requests"])
    new_empire_requests.remove(target_galaxy)

    kd_empire_payload = {
        "empire_join_requests": list(new_empire_requests)
    }

    join_empire_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_empire_payload)
    )

    galaxy_payload = {
        "empire_invitations": [],
        "empire_join_requests": []
    }

    galaxy_politics_info = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{target_galaxy}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(galaxy_payload)
    )
    return flask.jsonify({"message": "Galaxy added to Empire", "status": "success"}), 200

def _validate_leave_empire(empire_politics, kd_id, kd_galaxy_politics):
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the your galaxy"
    
    return True, ""

@app.route('/api/leaveempire', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def leave_empire():
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empires_payload)
    )

    if len(empires_info[kd_empire]["galaxies"]) > 0 and empire_politics["leader"] == kd_galaxy_id:
        kd_empire_payload = {
            "leader": random.choice(empires_info[kd_empire]["galaxies"])
        }

        empire_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(kd_empire_payload)
        )
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

@app.route('/api/empire/<target_empire>/denounce', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def denounce(target_empire):
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(news_payload)
    )

    empires_payload = {
        "empires": empires_info["empires"],
    }
    update_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empires_payload)
    )
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

    return True, ""

@app.route('/api/empire/<target_empire>/declare', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def declare_war(target_empire):
    kd_id = flask_praetorian.current_user().kd_id

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(news_payload)
    )

    empires_payload = {
        "empires": empires_info["empires"],
    }
    update_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empires_payload)
    )
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

@app.route('/api/empire/<target_empire>/surrenderrequest', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def request_surrender(target_empire):
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_empire_payload)
    )
    empire_payload = {
        "surrender_requests_sent": new_empire_requests_sender
    }

    surrender_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empire_payload)
    )

    return flask.jsonify({"message": "Surrender request sent", "status": "success"}), 200

@app.route('/api/empire/<target_empire>/cancelsurrenderrequest', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_request_surrender(target_empire):
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_empire_payload)
    )
    empire_payload = {
        "surrender_requests_sent": new_empire_requests_sender
    }

    surrender_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empire_payload)
    )

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

@app.route('/api/empire/<target_empire>/surrenderoffer', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def offer_surrender(target_empire):
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_empire_payload)
    )
    empire_payload = {
        "surrender_offers_sent": new_empire_offers_sender
    }

    surrender_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empire_payload)
    )

    return flask.jsonify({"message": "Surrender offer sent", "status": "success"}), 200

@app.route('/api/empire/<target_empire>/cancelsurrenderoffer', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_offer_surrender(target_empire):
    kd_id = flask_praetorian.current_user().kd_id
    req = flask.request.get_json(force=True)
    surrender_type = req.get("type")
    surrender_value = req.get("value")

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{target_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_empire_payload)
    )
    empire_payload = {
        "surrender_offers_sent": new_empire_offers_sender
    }

    surrender_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(empire_payload)
    )

    return flask.jsonify({"message": "Surrender offer cancelled", "status": "success"}), 200


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

@app.route('/api/votes', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def buy_votes():
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload)
    )

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

@app.route('/api/universepolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def universe_policies():
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
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
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload)
    )

    universe_politics_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universepolitics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(universe_politics)
    )

    return (flask.jsonify({"message": "Cast votes", "status": "success"}), 200)