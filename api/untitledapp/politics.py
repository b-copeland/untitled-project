
import collections
import json
import os

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