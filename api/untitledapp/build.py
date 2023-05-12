import collections
import datetime
import json
import math
import os

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.getters as uag
import untitledapp.shared as uas
from untitledapp import app, alive_required, REQUESTS_SESSION, SOCK_HANDLERS

def _make_time_splits(min_time, max_time, num_splits):
    assert num_splits % 2 == 0, "num_splits must be even"

    splits = []
    step = (min_time + max_time) / num_splits
    for i in range(num_splits):
        splits.append(min_time + step * i)

    n_half = int(num_splits / 2)
    middle_out_low_end = splits[(n_half - 1)::-1]
    middle_out_high_end = splits[n_half:]

    splits_middle_out = []
    for i in range(n_half):
        splits_middle_out.append(middle_out_high_end[i])
        splits_middle_out.append(middle_out_low_end[i])
    return splits_middle_out

def _divide_across_splits(splits, amount):
    len_splits = len(splits)
    remainder = amount % len_splits
    whole_splits = int(amount / len_splits)

    remainder_splits = splits[:remainder]
    if whole_splits:
        map_splits = {
            split: whole_splits + int(split in remainder_splits)
            for split in splits
        }
    else:
        map_splits = {
            split: 1
            for split in remainder_splits
        }
    return map_splits


def _validate_recruits(recruits_input, current_available_recruits):
    if recruits_input > current_available_recruits:
        return False
    if recruits_input <= 0:
        return False

    return True



def _get_new_recruits(recruits_input, is_conscription):
    time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_RECRUIT_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_RECRUIT_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_RECRUIT_TIME_SPLITS"],
    )
    input_splits = _divide_across_splits(time_splits, recruits_input)

    min_time = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(
            seconds=uag._calc_recruit_time(
                is_conscription,
                min(input_splits.keys()),
            )
        )
    ).isoformat()
    new_recruits = [
        {
            "time": (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(
                    seconds=uag._calc_recruit_time(
                        is_conscription,
                        time_multiplier,
                    )
                )
            ).isoformat(),
            "recruits": amount,
        }
        for time_multiplier, amount in input_splits.items()
    ]
    return new_recruits, min_time

@app.route('/api/recruits', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def recruits():
    req = flask.request.get_json(force=True)
    
    recruits_input = int(req["recruitsInput"])
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    mobis_info_parse = uag._get_mobis_queue(kd_id)
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_units = mobis_info_parse

    start_time = datetime.datetime.now(datetime.timezone.utc)
    units = uag._calc_units(start_time, current_units, generals_units, mobis_units)

    max_available_recruits, current_available_recruits = uag._calc_max_recruits(kd_info_parse, units)
    valid_recruits = _validate_recruits(recruits_input, current_available_recruits)
    if not valid_recruits:
        return (flask.jsonify({"message": 'Please enter valid recruits value'}), 400)

    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_conscription = "Conscription" in galaxy_policies["active_policies"]

    new_recruits, min_recruits_time = _get_new_recruits(recruits_input, is_conscription)

    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["mobis"] = min(next_resolve["mobis"], min_recruits_time)
    new_money = kd_info_parse["money"] - uas.GAME_CONFIG["BASE_RECRUIT_COST"] * recruits_input
    kd_payload = {'money': new_money, 'next_resolve': next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    recruits_payload = {
        "new_mobis": new_recruits
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(recruits_payload),
    )
    return (flask.jsonify({"message": "Successfully began recruiting", "status": "success"}), 200)

def _get_mobis_cost(mobis_request):
    state = uag._get_state()
    units_adjusted_costs = uag._get_units_adjusted_costs(state)
    mobis_cost = sum([
        units_adjusted_costs[k]['cost'] * units_value
        for k, units_value in mobis_request.items()
    ])
    return mobis_cost

def _validate_train_mobis(mobis_request, current_units, kd_info_parse, mobis_cost):
    if sum(mobis_request.values()) > current_units["recruits"]:
        return False
    if sum(mobis_request.values()) == 0:
        return False
    if any((value < 0 for value in mobis_request.values())):
        return False
    if mobis_cost > kd_info_parse["money"]:
        return False
    if mobis_request.get("big_flex", 0) > 0 and "big_flexers" not in kd_info_parse["completed_projects"]:
        return False
    
    return True
    
    

def _get_new_mobis(mobis_request):
    mobi_time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_SPECIALIST_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_SPECIALIST_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_SPECIALIST_TIME_SPLITS"],
    )
    mobis_request_split = collections.defaultdict(dict)
    for key_mobi, amt_mobi in mobis_request.items():
        split_amt_mobi = _divide_across_splits(
            mobi_time_splits,
            amt_mobi,
        )
        for time_multiplier, amt_split in split_amt_mobi.items():
            mobis_request_split[time_multiplier][key_mobi] = amt_split
    
    min_mobi_time = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * min(mobis_request_split.keys()))
    ).isoformat()

    new_mobis = [
        {
            "time": (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier)
            ).isoformat(),
            **time_mobis,
        }
        for time_multiplier, time_mobis in mobis_request_split.items()
    ]
    return new_mobis, min_mobi_time

@app.route('/api/mobis', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def train_mobis():
    req = flask.request.get_json(force=True)
    
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    current_units = kd_info_parse["units"]

    mobis_request = {
        k: int(v or 0)
        for k, v in req.items()
        if int(v or 0) != 0
    }
    mobis_cost = _get_mobis_cost(mobis_request)
    valid_mobis = _validate_train_mobis(mobis_request, current_units, kd_info_parse, mobis_cost)
    if not valid_mobis:
        return (flask.jsonify({"message": 'Please enter valid training values'}), 400)

    new_money = kd_info_parse["money"] - mobis_cost
    new_recruits = kd_info_parse["units"]["recruits"] - sum(mobis_request.values())

    new_mobis, min_mobis_time = _get_new_mobis(mobis_request)
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["mobis"] = min(next_resolve["mobis"], min_mobis_time)
    kd_payload = {
        'money': new_money,
        'units': {
            **kd_info_parse["units"],
            'recruits': new_recruits,
        },
        'next_resolve': next_resolve,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    mobis_payload = {
        "new_mobis": new_mobis
    }
    mobis_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(mobis_payload),
    )
    return (flask.jsonify({"message": "Successfully began training specialists", "status": "success"}), 200)

def _validate_mobis_target(req_targets, kd_info_parse):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    if req_targets.get("big_flex", 0) > 0 and "big_flexers" not in kd_info_parse["completed_projects"]:
        return False, "You have not unlocked big_flexers"
    
    return True, ""

@app.route('/api/mobis/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_mobis():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("recruits_before_units", None) is not None:
        recruits_before_units = req["recruits_before_units"]
        payload = {'recruits_before_units': recruits_before_units}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if recruits_before_units:
            message = "Recruits will be trained before units during auto spending"
        else:
            message = "Recruits will be trained after units during auto spending"
        return (flask.jsonify({"message": message, "status": "success"}), 200)

    
    req_targets = {
        key: float(value or 0) / 100
        for key, value in req.get("targets", {}).items()
        if (value or 0) != 0
    }

    current_targets = kd_info_parse['units_target']
    new_targets = {
        **current_targets,
        **req_targets,
    }
    valid_targets, message = _validate_mobis_target(new_targets, kd_info_parse)
    if not valid_targets:
        return (flask.jsonify({"message": message}), 400)

    payload = {'units_target': new_targets}
    if req.get("max_recruits", "") != "":
        payload["max_recruits"] = int(req["max_recruits"])
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

def _validate_disband(kd_info, input):

    for key_unit, value_unit in input.items():
        if value_unit < 0 or value_unit > kd_info["units"].get(key_unit, 0):
            return False, "You do not have that many units to disband"
    
    if "engineers" in input.keys():
        "You can't disband engineers"
        
    return True, ""

@app.route('/api/mobis/disband', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def disband_mobis():
    req = flask.request.get_json(force=True)
    req_input = {
        k: int(v)
        for k, v in req["input"].items()
        if v not in ("", "0")
    } 

    kd_id = flask_praetorian.current_user().kd_id

    kd_info = uag._get_kd_info(kd_id)

    valid_disband, message = _validate_disband(kd_info, req_input)
    if not valid_disband:
        return (flask.jsonify({"message": message}), 400)
    
    new_units = {
        key_unit: value_unit - req_input.get(key_unit, 0)
        for key_unit, value_unit in kd_info["units"].items()
    }
    new_money = kd_info["money"] + sum([
        uas.UNITS[key_unit].get("cost", 0) * value_unit * uas.GAME_CONFIG["BASE_DISBAND_COST_RETURN"]
        for key_unit, value_unit in req_input.items()
    ])
    new_pop = kd_info["population"] + sum(req_input.values())

    kd_payload = {
        "units": new_units,
        "money": new_money,
        "population": new_pop,
    }
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    
    return (flask.jsonify({"message": "Disbanded units", "status": "success"}), 200)


def _validate_structures(structures_input, current_available_structures):
    """Confirm that spending request is valid"""

    values = structures_input.values()
    if any((value < 0 for value in values)):
        return False
    if sum(values) > current_available_structures:
        return False
    if sum(values) == 0:
        return False
    
    return True

def _get_new_structures(structures_request):
    structure_time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_STRUCTURE_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_STRUCTURE_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_STRUCTURE_TIME_SPLITS"],
    )
    structures_request_split = collections.defaultdict(dict)
    for key_structure, amt_structure in structures_request.items():
        split_amt_structure = _divide_across_splits(
            structure_time_splits,
            amt_structure,
        )
        for time_multiplier, amt_split in split_amt_structure.items():
            structures_request_split[time_multiplier][key_structure] = amt_split
    
    min_structure_time = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * min(structures_request_split.keys()))
    ).isoformat()

    new_structures = [
        {
            "time": (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier)
            ).isoformat(),
            **time_structures,
        }
        for time_multiplier, time_structures in structures_request_split.items()
    ]
    return new_structures, min_structure_time

@app.route('/api/structures', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def build_structures():
    req = flask.request.get_json(force=True)
    
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    
    structures_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    structures_info_parse = json.loads(structures_info.text)

    current_price = uag._get_structure_price(kd_info_parse)
    current_structures = kd_info_parse["structures"]
    building_structures = structures_info_parse["structures"]

    start_time = datetime.datetime.now(datetime.timezone.utc)
    structures = uag._calc_structures(start_time, current_structures, building_structures)

    max_available_structures, current_available_structures = uag._calc_available_structures(current_price, kd_info_parse, structures)

    structures_request = {
        k: int(v or 0)
        for k, v in req.items()
        if int(v or 0) != 0
    }
    valid_structures = _validate_structures(structures_request, current_available_structures)
    if not valid_structures:
        return (flask.jsonify({"message": 'Please enter valid structures values'}), 400)

    new_structures, min_structures_time = _get_new_structures(structures_request)
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["structures"] = min(next_resolve["structures"], min_structures_time)
    new_money = kd_info_parse["money"] - sum(structures_request.values()) * current_price
    kd_payload = {'money': new_money, 'next_resolve': next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    structures_payload = {
        "new_structures": new_structures
    }
    structures_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(structures_payload),
    )
    return (flask.jsonify({"message": "Successfully began building structures", "status": "success"}), 200)

def _validate_structures_target(req_targets):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    
    return True, ""

@app.route('/api/structures/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_structures():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    
    req_targets = {
        key: float(value or 0) / 100
        for key, value in req.items()
        if (value or 0) != 0
    }

    current_targets = kd_info_parse['structures_target']
    new_targets = {
        **current_targets,
        **req_targets,
    }
    valid_targets, message = _validate_structures_target(new_targets)
    if not valid_targets:
        return (flask.jsonify({"message": message}), 400)

    payload = {'structures_target': new_targets}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

def _validate_raze(kd_info, input):

    for key_structure, value_structure in input.items():
        if value_structure < 0 or value_structure > kd_info["structures"].get(key_structure, 0):
            return False, "You do not have that many structures to raze"
        
    return True, ""

@app.route('/api/structures/raze', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def raze_structures():
    req = flask.request.get_json(force=True)
    req_input = {
        k: int(v)
        for k, v in req["input"].items()
        if v not in ("", "0")
    } 

    kd_id = flask_praetorian.current_user().kd_id

    kd_info = uag._get_kd_info(kd_id)

    valid_raze, message = _validate_raze(kd_info, req_input)
    if not valid_raze:
        return (flask.jsonify({"message": message}), 400)
    
    structures_price = uag._get_structure_price(kd_info)

    new_structures = {
        key_structure: math.floor(value_structure - req_input.get(key_structure, 0))
        for key_structure, value_structure in kd_info["structures"].items()
    }
    new_money = kd_info["money"] + sum([
        structures_price * value_structures * uas.GAME_CONFIG["BASE_STRUCTURES_RAZE_RETURN"]
        for value_structures in req_input.values()
    ])

    kd_payload = {
        "structures": new_structures,
        "money": new_money,
    }
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    
    return (flask.jsonify({"message": "Razed structures", "status": "success"}), 200)


def _validate_settles(settle_input, kd_info, settle_info, is_expansionist):
    max_settle, available_settle = uag._get_available_settle(kd_info, settle_info, is_expansionist)
    if settle_input <= 0:
        return False
    if settle_input > available_settle:
        return False

    return True

def _get_new_settles(kd_info_parse, settle_input):
    settle_time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_SETTLE_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_SETTLE_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_SETTLE_TIME_SPLITS"],
    )
    settle_splits = _divide_across_splits(settle_time_splits, settle_input)

    min_settle_time = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(
            seconds=uag._get_settle_time(
                kd_info_parse,
                min(settle_splits.keys()),
            )
        )
    ).isoformat()
    new_settles = [
        {
            "time": (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(
                    seconds=uag._get_settle_time(
                        kd_info_parse,
                        time_multiplier,
                    )
                )
            ).isoformat(),
            "amount": amount,
        }
        for time_multiplier, amount in settle_splits.items()
    ]
    return new_settles, min_settle_time

@app.route('/api/settle', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def settle():
    req = flask.request.get_json(force=True)
    
    settle_input = int(req["settleInput"])
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    settle_info = uag._get_settle_queue(kd_id)
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_expansionist = "Expansionist" in galaxy_policies["active_policies"]
    valid_settle = _validate_settles(settle_input, kd_info_parse, settle_info, is_expansionist)
    if not valid_settle:
        return (flask.jsonify({"message": 'Please enter valid settle value'}), 400)


    new_settles, min_settle_time = _get_new_settles(kd_info_parse, settle_input)

    settle_price = uag._get_settle_price(kd_info_parse, is_expansionist)
    new_money = kd_info_parse["money"] - settle_price * settle_input
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["settles"] = min(next_resolve["settles"], min_settle_time)
    kd_payload = {'money': new_money, "next_resolve": next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    settle_payload = {
        "new_settles": new_settles,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(settle_payload),
    )
    return (flask.jsonify({"message": "Successfully began settling", "status": "success"}), 200)


def _validate_missiles(missiles_request, kd_info_parse, missiles_building, max_available_missiles):
    current_missiles = kd_info_parse["missiles"]
    missiles = {k: current_missiles.get(k, 0) + missiles_building.get(k, 0) for k in uas.MISSILES}

    missiles_available = {k: max_available_missiles - missiles.get(k, 0) for k in missiles}
    costs = sum([uas.MISSILES[key_missile]["cost"] * value_missile for key_missile, value_missile in missiles_request.items()])
    fuel_costs = sum([uas.MISSILES[key_missile]["fuel_cost"] * value_missile for key_missile, value_missile in missiles_request.items()])

    if any((value < 0 for value in missiles_request.values())):
        return False
    if any((value_missile > missiles_available.get(key_missile, 0) for key_missile, value_missile in missiles_request.items())):
        return False
    if sum(missiles_request.values()) == 0:
        return False
    if costs > kd_info_parse["money"]:
        return False
    if fuel_costs > kd_info_parse["fuel"]:
        return False
    if missiles_request["star_busters"] > 0 and "star_busters" not in kd_info_parse["completed_projects"]:
        return False
    if missiles_request["galaxy_busters"] > 0 and "galaxy_busters" not in kd_info_parse["completed_projects"]:
        return False
    
    return True


@app.route('/api/missiles', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def build_missiles():
    req = flask.request.get_json(force=True)
    
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    
    missiles_info = uag._get_missiles_info(kd_id)
    missiles_building = uag._get_missiles_building(missiles_info)

    max_available_missiles = math.floor(kd_info_parse["structures"]["missile_silos"]) * math.floor(
        uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"]
        * (
            1
            + int(kd_info_parse["race"] == "Fuzi") * uas.GAME_CONFIG["FUZI_MISSILE_SILO_CAPACITY_INCREASE"]
        )
    )

    missiles_request = {
        k: int(v or 0)
        for k, v in req.items()
    }
    valid_missiles = _validate_missiles(missiles_request, kd_info_parse, missiles_building, max_available_missiles)
    if not valid_missiles:
        return (flask.jsonify({"message": 'Please enter valid missiles values'}), 400)

    cost_multiplier = (
        1
        - int(kd_info_parse["race"] == "Fuzi") * uas.GAME_CONFIG["FUZI_MISSILE_COST_REDUCTION"]
    )
    costs = sum([uas.MISSILES[key_missile]["cost"] * value_missile * cost_multiplier for key_missile, value_missile in missiles_request.items()])
    fuel_costs = sum([uas.MISSILES[key_missile]["fuel_cost"] * value_missile * cost_multiplier for key_missile, value_missile in missiles_request.items()])
    new_money = kd_info_parse["money"] - costs
    new_fuel = kd_info_parse["fuel"] - fuel_costs
    missiles_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_MISSILE_TIME_MULTIPLER"])).isoformat()
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["missiles"] = min(next_resolve["missiles"], missiles_time)
    kd_payload = {
        'money': new_money,
        'fuel': new_fuel,
        'next_resolve': next_resolve,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    missiles_payload = {
        "new_missiles": [
            {
                "time": missiles_time,
                **missiles_request,
            }
        ]
    }
    missiles_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(missiles_payload),
    )
    return (flask.jsonify({"message": "Successfully began building missiles", "status": "success"}), 200)


def _validate_engineers(engineers_input, current_available_engineers):
    if engineers_input > current_available_engineers:
        return False
    if engineers_input <= 0:
        return False

    return True


def _get_new_engineers(engineers_input):
    time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_ENGINEER_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_ENGINEER_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_ENGINEER_TIME_SPLITS"],
    )
    input_splits = _divide_across_splits(time_splits, engineers_input)

    min_time = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * min(input_splits.keys()))
    ).isoformat()
    new_engineers = [
        {
            "time": (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(
                    seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier,
                )
            ).isoformat(),
            "amount": amount,
        }
        for time_multiplier, amount in input_splits.items()
    ]
    return new_engineers, min_time

@app.route('/api/engineers', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def train_engineers():
    req = flask.request.get_json(force=True)
    
    engineers_input = int(req["engineersInput"])
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    engineers_info = uag._get_engineers_queue(kd_id)
    engineers_building = sum([training["amount"] for training in engineers_info])
    max_workshop_capacity, current_workshop_capacity = uag._calc_workshop_capacity(kd_info_parse, engineers_building)
    max_available_engineers, current_available_engineers = uag._calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity)

    valid_engineers = _validate_engineers(engineers_input, current_available_engineers)
    if not valid_engineers:
        return (flask.jsonify({"message": 'Please enter valid recruits value'}), 400)

    new_engineers, min_engineers_time = _get_new_engineers(engineers_input)
    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["engineers"] = min(next_resolve["engineers"], min_engineers_time)
    new_money = kd_info_parse["money"] - uas.GAME_CONFIG["BASE_ENGINEER_COST"] * engineers_input
    kd_payload = {'money': new_money, 'next_resolve': next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    engineers_payload = {
        "new_engineers": new_engineers
    }
    engineers_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(engineers_payload),
    )
    return (flask.jsonify({"message": "Successfully began training engineers", "status": "success"}), 200)


def _validate_projects_target(req_targets, kd_info_parse):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    if req_targets.get("spy_bonus", 0) > 0 and "drone_gadgets" not in kd_info_parse["completed_projects"]:
        return False
    
    return True, ""

@app.route('/api/projects/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_projects():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("enabled", None) is not None:
        payload = {'auto_assign_projects': req["enabled"]}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if req["enabled"]:
            message = "Auto assigning engineers enabled"
        else:
            message = "Auto assigning engineers disabled"
        return (flask.jsonify({"message": message, "status": "success"}), 200)

    
    req_targets = {
        key: float(value or 0) / 100
        for key, value in req.get("targets", {}).items()
        if (value or 0) != 0
    }

    current_targets = kd_info_parse['projects_target']
    new_targets = {
        **current_targets,
        **req_targets,
    }
    valid_targets, message = _validate_projects_target(new_targets, kd_info_parse)
    if not valid_targets:
        return (flask.jsonify({"message": message}), 400)

    payload = {'projects_target': new_targets}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

def _validate_assign_projects(req, kd_info_parse):
    engineers_assigned = sum(req["assign"].values())
    if engineers_assigned > kd_info_parse["units"]["engineers"]:
        return False
    if any(value < 0 for value in req["assign"].values()):
        return False
    if req.get("spy_bonus", 0) > 0 and "drone_gadgets" not in kd_info_parse["completed_projects"]:
        return False
    return True

def _validate_add_projects(req, available_engineers, kd_info_parse):
    engineers_added = sum(req["add"].values())
    if engineers_added > available_engineers:
        return False
    if any(value < 0 for value in req["add"].values()):
        return False
    if req.get("spy_bonus", 0) > 0 and "drone_gadgets" not in kd_info_parse["completed_projects"]:
        return False
    return True

@app.route('/api/projects', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def manage_projects():
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    new_projects_assigned = kd_info_parse["projects_assigned"].copy()
    if "clear" in req.keys():
        projects_to_clear = req["clear"]
        for project_to_clear in projects_to_clear:
            new_projects_assigned[project_to_clear] = 0

    elif "assign" in req.keys():
        req["assign"] = {k: int(v) for k, v in req["assign"].items()}
        valid_assign = _validate_assign_projects(req, kd_info_parse)
        if not valid_assign:
            return (flask.jsonify({"message": 'Please enter valid assign engineers value'}), 400)
        
        new_projects_assigned = {
            key: req["assign"].get(key, 0)
            for key in kd_info_parse["projects_assigned"]
        }
        
    elif "add" in req.keys():
        req["add"] = {k: int(v) for k, v in req["add"].items()}
        available_engineers = kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values())
        valid_add = _validate_add_projects(req, available_engineers, kd_info_parse)
        if not valid_add:
            return (flask.jsonify({"message": 'Please enter valid add engineers value'}), 400)
        
        new_projects_assigned = {
            key: value + req["add"].get(key, 0)
            for key, value in kd_info_parse["projects_assigned"].items()
        }

    kd_payload = {"projects_assigned": new_projects_assigned}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )
    return (flask.jsonify({"message": "Successfully updated project assignment", "status": "success"}), 200)