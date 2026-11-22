
import collections
import datetime
import itertools
import json
import math
import os
import random

import flask
import flask_praetorian

import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.getters as uag
import untitledapp.galaxypolicies as uagp
import untitledapp.universepolicies as uaup
import untitledapp.shared as uas
import untitledapp.targets as uat
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


def empire_size_problem(empire_galaxies, galaxy, galaxy_members, galaxy_networth):
    """
    Why ``galaxy`` may not join an empire of ``empire_galaxies``, or None if it may: the empire would then hold more
    than ``EMPIRE_MAX_KINGDOMS_SHARE`` of the universe's kingdoms or ``EMPIRE_MAX_NETWORTH_SHARE`` of its networth.
    An empire of ``EMPIRE_ALWAYS_ALLOWED_GALAXIES`` galaxies is always allowed. ``galaxy_members`` is
    ``{galaxy: [kingdoms]}`` and ``galaxy_networth`` ``{galaxy: networth}``, as the scores have it. The bots ask the
    same question before they invite or ask.
    """
    together = set(empire_galaxies) | {galaxy}
    if len(together) <= uas.GAME_CONFIG["EMPIRE_ALWAYS_ALLOWED_GALAXIES"]:
        return None
    kingdoms = sum(len(galaxy_members.get(g, [])) for g in together)
    all_kingdoms = max(sum(len(members) for members in galaxy_members.values()), 1)
    if kingdoms / all_kingdoms > uas.GAME_CONFIG["EMPIRE_MAX_KINGDOMS_SHARE"]:
        return (f"The Empire would have {kingdoms / all_kingdoms:.0%} of the universe's kingdoms; "
                f"the most an Empire can have is {uas.GAME_CONFIG['EMPIRE_MAX_KINGDOMS_SHARE']:.0%}")
    networth = sum(galaxy_networth.get(g, 0) for g in together)
    all_networth = max(sum(galaxy_networth.values()), 1)
    if networth / all_networth > uas.GAME_CONFIG["EMPIRE_MAX_NETWORTH_SHARE"]:
        return (f"The Empire would have {networth / all_networth:.0%} of the universe's networth; "
                f"the most an Empire can have is {uas.GAME_CONFIG['EMPIRE_MAX_NETWORTH_SHARE']:.0%}")
    return None


def _size_check(galaxy):
    """
    A check for ``_change_empire_galaxies``: refuses ``galaxy`` if it would make the empire too large. The galaxies
    and the scores are read only when the empire would be larger than the size that is always allowed, and once.
    """
    read = {}

    def check(empire_galaxies):
        if len(set(empire_galaxies) | {galaxy}) <= uas.GAME_CONFIG["EMPIRE_ALWAYS_ALLOWED_GALAXIES"]:
            return
        if not read:
            read["members"] = uag._get_galaxies_inverted()[1]
            read["networth"] = uag._get_scores().get("galaxy_networth", {})
        problem = empire_size_problem(empire_galaxies, galaxy, read["members"], read["networth"])
        if problem:
            raise occ.Rejected(problem)
    return check


def _change_empire_galaxies(empire_id, add=None, remove=None, check=None, leave_check=None):
    """
    Add a galaxy to an empire, or take one out, on the empires document as it is right now (not the copy read at the
    start of the request, which would overwrite changes made since). ``check`` is called with the empire's galaxies as
    they are now, before ``add`` joins them, and ``leave_check`` with the empire as it is now, before ``remove`` leaves
    it; either may raise ``occ.Rejected``. Returns the empire's galaxies afterwards.
    """
    def change(empires_document):
        empire = empires_document["empires"][empire_id]
        if remove is not None and leave_check is not None:
            leave_check(empire)
        galaxies = [galaxy for galaxy in empire["galaxies"] if galaxy != remove]
        if add is not None and any(
            add in other["galaxies"] for other_id, other in empires_document["empires"].items() if other_id != empire_id
        ):
            # Two invitations accepted at the same moment: whichever lands first wins.
            raise occ.Rejected("That galaxy is already part of an Empire")
        if add is not None and check is not None and add not in galaxies:
            check(galaxies)
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


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _record_vote(galaxy_votes, kind, kd_id, choice, now):
    """
    Put ``kd_id``'s vote of ``kind`` (``leader``) as ``choice`` in ``galaxy_votes`` (the document as it is right now),
    and return the fields to write. Changing a vote that was cast starts the cooldown, and inside it raises
    ``occ.Rejected`` saying when it can change; voting what it already is changes nothing and starts nothing. The first
    vote is free. Policy votes have no cooldown: the tally weighs them by time instead (``galaxypolicies``).
    """
    fields = {}
    if galaxy_votes["votes"][kind].get(kd_id) != choice:
        unlocks = uas.galaxy_vote_unlocks_at(galaxy_votes, kind, kd_id, now)
        if unlocks:
            raise occ.Rejected(f"You changed this vote recently. You can change it again in {uas.wait_text(unlocks - now)}.")
        changed = galaxy_votes.get("vote_changed") or {}
        changed[kind] = {**(changed.get(kind) or {}), kd_id: now.isoformat()}
        galaxy_votes["vote_changed"] = changed
        fields["vote_changed"] = changed
    galaxy_votes["votes"][kind][kd_id] = choice
    fields["votes"] = galaxy_votes["votes"]
    return fields


def cast_leader_vote(kd_id, selected):
    """Vote for ``selected`` as the leader of ``kd_id``'s galaxy. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    
    galaxy_votes, galaxy_id = uag._get_galaxy_politics(kd_id)
    now = _now()

    def vote(galaxy_votes):
        # Added to the votes as they are right now, so galaxymates voting together all count.
        patch_payload = _record_vote(galaxy_votes, "leader", kd_id, selected, now)
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
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400

    return galaxy_votes, 200


@bp.route('/api/galaxypolitics/leader', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_leader():
    req = flask.request.get_json(force=True)
    payload, status = cast_leader_vote(flask_praetorian.current_user().kd_id, req["selected"])
    return flask.jsonify(payload), status

def cast_galaxy_vote(kd_id, galaxy_id, policy, option):
    """
    Record ``kd_id``'s vote for ``option`` of the galaxy ``policy`` (None withdraws it). It does not switch the policy:
    the next tally does, weighing every vote by how long it was held (``galaxypolicies``). Returns the galaxy's
    policies as they are after the vote (``galaxypolicies.advance``). Raises ``occ.Rejected`` for a policy this round
    does not play or an option it does not have, and ``occ.Busy``. The route and the bots both come through here.
    """
    state = uag._get_state()
    policies = uagp.round_policies(state.get("state"))
    problem = uagp.vote_problem(policies, policy, option)
    if problem:
        raise occ.Rejected(problem)
    round_start = uag._round_start(state)
    now = _now()

    def vote(galaxy_votes):
        galaxy = uagp.advance(galaxy_votes, policies, round_start, now)
        if not uagp.cast(galaxy, kd_id, policy, option):
            return None, galaxy  # the vote is what it was: nothing to write
        return uagp.written(galaxy), galaxy

    return occ.update(f'/galaxy/{galaxy_id}/politics', vote)


@bp.route('/api/galaxypolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def galaxy_policies():
    req = flask.request.get_json(force=True, silent=True)
    req = req if isinstance(req, dict) else {}
    kd_id = flask_praetorian.current_user().kd_id
    policy = req.get("policy")
    option = req.get("option") or None
    if not isinstance(policy, str) or (option is not None and not isinstance(option, str)):
        return (flask.jsonify({"message": "Choose a policy and one of its options"}), 400)

    _, galaxy_id = uag._get_galaxy_politics(kd_id)
    try:
        cast_galaxy_vote(kd_id, galaxy_id, policy, option)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)

    if option is None:
        message = f"Your vote on {uas.GALAXY_POLICIES[policy]['name']} is withdrawn"
    else:
        message = (f"You now vote for {uas.GALAXY_POLICIES[policy]['options'][option]['name']}. "
                   "It counts from now towards the next tally")
    return (flask.jsonify({"message": message, "status": "success"}), 200)

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


def found_empire(kd_id, empire_name):
    """Found an empire led by ``kd_id``'s galaxy. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app

    # A quick answer for the player. What stops two clicks (or a join that lands at the same moment) from putting the
    # galaxy in two empires is the function app: it takes the new empire's id with a conditional write on `empires`
    # and refuses a galaxy that is already in one (409).
    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, _, _, _ = uag._get_empires_inverted()

    valid_name, message = _validate_empire_name(empire_name, galaxy_politics, kd_id, empires_inverted)
    if not valid_name:
        return {"message": message}, 400

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
    if create_empire_response.status_code == 409:
        return {"message": "You are already part of an Empire"}, 400
    if create_empire_response.status_code != 201:
        return {"message": "The Empire could not be created"}, 500

    return {"message": "Empire created", "status": "success"}, 201


@bp.route('/api/empire', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def create_empire():
    req = flask.request.get_json(force=True)
    payload, status = found_empire(flask_praetorian.current_user().kd_id, req.get("empireName", ""))
    return flask.jsonify(payload), status

def _validate_join_empire(galaxy_politics, kd_id, empires_inverted):    
    if galaxy_politics["leader"] != kd_id:
        return False, "You must be galaxy leader to join an Empire"
    
    if empires_inverted.get(kd_id) != None:
        return False, "You are already part of an Empire"
    
    return True, ""

def ask_to_join_empire(kd_id, target_empire):
    """Ask for ``kd_id``'s galaxy to join an empire. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()


    valid_join, message = _validate_join_empire(galaxy_politics, kd_id, empires_inverted)
    if not valid_join:
        return {"message": message}, 400
    try:
        _size_check(kd_galaxy)(empires_info["empires"].get(target_empire, {}).get("galaxies", []))
    except occ.Rejected as rejection:
        return {"message": rejection.message}, 400
        
        
    target_empire_politics = uag._get_empire_politics(target_empire)

    _change_list(f'/empire/{target_empire}/politics', "empire_join_requests", add=kd_galaxy)
    _change_list(f'/galaxy/{kd_galaxy}/politics', "empire_join_requests", add=target_empire)
    return {"message": "Join request sent", "status": "success"}, 200


@bp.route('/api/empire/<target_empire>/join', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def request_join_empire(target_empire):
    payload, status = ask_to_join_empire(flask_praetorian.current_user().kd_id, target_empire)
    return flask.jsonify(payload), status

def withdraw_join_request(kd_id, target_empire):
    """Take back ``kd_id``'s galaxy's request to join an empire. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)

    if galaxy_politics["leader"] != kd_id:
        return {"message": "You must be galaxy leader to manage Empire requests"}, 400

    _change_list(f'/empire/{target_empire}/politics', "empire_join_requests", remove=kd_galaxy)
    _change_list(f'/galaxy/{kd_galaxy}/politics', "empire_join_requests", remove=target_empire)
    return {"message": "Join request cancelled", "status": "success"}, 200


@bp.route('/api/empire/<target_empire>/canceljoin', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def cancel_join_empire(target_empire):
    payload, status = withdraw_join_request(flask_praetorian.current_user().kd_id, target_empire)
    return flask.jsonify(payload), status

def _validate_empire_invite(galaxy_politics, kd_id, empires_inverted):    
    if galaxy_politics["leader"] != kd_id:
        return False, "You must be galaxy leader to join an Empire"
    
    if empires_inverted.get(kd_id) != None:
        return False, "You are already part of an Empire"
    
    return True, ""

def join_invited_empire(kd_id, target_empire):
    """Accept an empire's invitation to ``kd_id``'s galaxy. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app

    galaxy_politics, kd_galaxy = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()


    try:
        valid_invite, message = _validate_empire_invite(galaxy_politics, kd_id, empires_inverted)
        if not valid_invite:
            return {"message": message}, 400
        
        
        _change_empire_galaxies(target_empire, add=kd_galaxy, check=_size_check(kd_galaxy))
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
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Joined Empire", "status": "success"}, 200


@bp.route('/api/empire/<target_empire>/acceptinvite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_empire_invite(target_empire):
    payload, status = join_invited_empire(flask_praetorian.current_user().kd_id, target_empire)
    return flask.jsonify(payload), status

def _validate_invite_galaxy(empire_politics, kd_id, galaxy_empires, galaxy_id, kd_galaxy_politics, kd_galaxy_id):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if galaxy_empires.get(galaxy_id) != None:
        return False, "That galaxy is already part of an Empire"
    
    return True, ""

def invite_galaxy_to_empire(kd_id, target_galaxy):
    """Invite a galaxy into the empire ``kd_id`` leads. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)

    
    empire_politics = uag._get_empire_politics(kd_empire)

    valid_invite, message = _validate_invite_galaxy(empire_politics, kd_id, galaxy_empires, target_galaxy, kd_galaxy_politics, kd_galaxy_id)
    if not valid_invite:
        return {"message": message}, 400
    try:
        _size_check(target_galaxy)(empires_info["empires"].get(kd_empire, {}).get("galaxies", []))
    except occ.Rejected as rejection:
        return {"message": rejection.message}, 400
        

    _change_list(f'/empire/{kd_empire}/politics', "empire_invitations", add=target_galaxy)
    _change_list(f'/galaxy/{target_galaxy}/politics', "empire_invitations", add=kd_empire)
    return {"message": "Invitation sent", "status": "success"}, 200


@bp.route('/api/galaxy/<target_galaxy>/invite', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def invite_galaxy(target_galaxy):
    payload, status = invite_galaxy_to_empire(flask_praetorian.current_user().kd_id, target_galaxy)
    return flask.jsonify(payload), status

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

    
    empire_politics = uag._get_empire_politics(kd_empire)
        
    if empire_politics["leader"] != kd_galaxy_id:
        return flask.jsonify({"message": "You are not a part of the Empire's ruling galaxy"}), 400
        
    if kd_galaxy_politics["leader"] != kd_id:
        return flask.jsonify({"message": "You are not the leader of the Empire's ruling galaxy"}), 400
        

    _change_list(f'/empire/{kd_empire}/politics', "empire_invitations", remove=target_galaxy)
    _change_list(f'/galaxy/{target_galaxy}/politics', "empire_invitations", remove=kd_empire)
    return flask.jsonify({"message": "Invitation revoked", "status": "success"}), 200

def _validate_accept_galaxy_request(empire_politics, kd_id, galaxy_empires, galaxy_id, kd_galaxy_politics, kd_galaxy_id):    
    if empire_politics["leader"] != kd_galaxy_id:
        return False, "You are not a part of the Empire's ruling galaxy"
    
    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the Empire's ruling galaxy"
    
    if galaxy_empires.get(galaxy_id) != None:
        return False, "That galaxy is already part of an Empire"
    
    return True, ""

def admit_galaxy_to_empire(kd_id, target_galaxy):
    """Accept a galaxy's request to join the empire ``kd_id`` leads. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    galaxy_politics, _ = uag._get_galaxy_politics("", galaxy_id=target_galaxy)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)


    try:
        empire_politics = uag._get_empire_politics(kd_empire)

        valid_request, message = _validate_accept_galaxy_request(empire_politics, kd_id, galaxy_empires, target_galaxy, kd_galaxy_politics, kd_galaxy_id)
        if not valid_request:
            return {"message": message}, 400
        

        _change_empire_galaxies(kd_empire, add=target_galaxy, check=_size_check(target_galaxy))
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
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Galaxy added to Empire", "status": "success"}, 200


@bp.route('/api/galaxy/<target_galaxy>/accept', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def accept_galaxy_request(target_galaxy):
    payload, status = admit_galaxy_to_empire(flask_praetorian.current_user().kd_id, target_galaxy)
    return flask.jsonify(payload), status

def _leave_problem(empire):
    """Why a galaxy can not leave ``empire`` (its entry in the empires document) now, or None. A galaxy can not walk out
    of a war: it stays until the war ends, which only a surrender does."""
    if empire.get("war"):
        return "You can not leave your Empire while it is at war. A war ends when one side surrenders"
    return None


def _refuse_leaving(empire):
    problem = _leave_problem(empire)
    if problem:
        raise occ.Rejected(problem)


def _validate_leave_empire(empire_politics, kd_id, kd_galaxy_politics, empire=None):

    if kd_galaxy_politics["leader"] != kd_id:
        return False, "You are not the leader of the your galaxy"
    problem = _leave_problem(empire or {})
    if problem:
        return False, problem

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

    
    if kd_empire is None:
        return flask.jsonify({"message": "Your galaxy is not in an Empire"}), 400
    empire_politics = uag._get_empire_politics(kd_empire)

    valid_leave, message = _validate_leave_empire(empire_politics, kd_id, kd_galaxy_politics,
                                                  empires_info["empires"].get(kd_empire))
    if not valid_leave:
        return flask.jsonify({"message": message}), 400

    try:
        # Checked again on the empires document as it is when the galaxy leaves: a war declared a moment ago holds it.
        remaining_galaxies = _change_empire_galaxies(kd_empire, remove=kd_galaxy_id, leave_check=_refuse_leaving)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400

    if len(remaining_galaxies) > 0 and empire_politics["leader"] == kd_galaxy_id:
        kd_empire_payload = {
            "leader": random.choice(remaining_galaxies)
        }

        empire_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/politics',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
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

def denounce_empire(kd_id, target_empire):
    """Denounce an empire, as the leader of ``kd_id``'s empire. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)


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
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Denounced!", "status": "success"}, 200


@bp.route('/api/empire/<target_empire>/denounce', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def denounce(target_empire):
    payload, status = denounce_empire(flask_praetorian.current_user().kd_id, target_empire)
    return flask.jsonify(payload), status

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

def declare_war_on(kd_id, target_empire):
    """Declare war on an empire, as the leader of ``kd_id``'s empire. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app

    kd_galaxy_politics, kd_galaxy_id = uag._get_galaxy_politics(kd_id)
    empires_inverted, empires_info, galaxy_empires, _ = uag._get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)


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
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Declared war!", "status": "success"}, 200


@bp.route('/api/empire/<target_empire>/declare', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def declare_war(target_empire):
    payload, status = declare_war_on(flask_praetorian.current_user().kd_id, target_empire)
    return flask.jsonify(payload), status

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
    # Targets exist only in war: each side's targets in the other end now, with their final payouts.
    uat.end_war(winning_empire, losing_empire)

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

def buy_universe_votes(kd_id, votes):
    """Buy ``votes`` universe votes with ``kd_id``'s money. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    
    votes_cost = votes * uas.GAME_CONFIG["BASE_VOTES_COST"]


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
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Bought votes", "status": "success"}, 200


@bp.route('/api/votes', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def buy_votes():
    req = flask.request.get_json(force=True)
    payload, status = buy_universe_votes(flask_praetorian.current_user().kd_id, int(req["votes"]))
    return flask.jsonify(payload), status

def _validate_cast_votes(
    kd_info,
    votes,
):
    if votes <= 0:
        return False, "Votes must be greater than 0"
    if votes > kd_info["votes"]:
        return False, "Not enough votes available"
    
    return True, ""

def cast_universe_votes(kd_id, policy, option, votes):
    """
    Spend ``votes`` of ``kd_id``'s votes on ``option`` of the universe ``policy``. Returns ``(payload, status_code)``.
    The route and the bots both come through here.
    """

    state = uag._get_state().get("state", {})
    problem = uaup.vote_problem(uaup.ballot_of(state), policy, option, bool(state.get("election_end")))
    if problem:
        return {"message": problem}, 400

    def take_votes(kd_info):
        valid_votes, message = _validate_cast_votes(kd_info, votes)
        if not valid_votes:
            raise occ.Rejected(message)
        return {"votes": kd_info["votes"] - votes}, None

    def add_votes(universe_politics):
        tally = universe_politics.get("votes") or {}
        cast = tally.setdefault(policy, {}).setdefault(option, {})
        cast[kd_id] = cast.get(kd_id, 0) + votes
        return {"votes": tally}, None

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
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400

    return {"message": "Cast votes", "status": "success"}, 200


@bp.route('/api/universepolitics/policies', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def universe_policies():
    req = flask.request.get_json(force=True, silent=True)
    req = req if isinstance(req, dict) else {}
    kd_id = flask_praetorian.current_user().kd_id
    try:
        votes = int(req.get("votes"))
    except (TypeError, ValueError):
        return (flask.jsonify({"message": "Choose how many votes to cast"}), 400)

    payload, status = cast_universe_votes(kd_id, req.get("policy"), req.get("option"), votes)
    return (flask.jsonify(payload), status)
