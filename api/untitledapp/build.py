import collections
import datetime
import json
import math
import os

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.misc as uam
import untitledapp.getters as uag
import untitledapp.occ as occ
import untitledapp.shared as uas
from untitledapp import alive_required, REQUESTS_SESSION, SOCK_HANDLERS

bp = flask.Blueprint("build", __name__)

def _make_time_splits(min_time, max_time, num_splits):
    assert num_splits % 2 == 0, "num_splits must be even"

    splits = []
    step = (max_time - min_time) / (num_splits - 1)
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



def _get_new_recruits(recruits_input, modifiers, start_time):
    """The queue entries for ``recruits_input`` recruits drafted from ``start_time``, after the kingdom's ``modifiers``."""
    time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_RECRUIT_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_RECRUIT_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_RECRUIT_TIME_SPLITS"],
    )
    input_splits = _divide_across_splits(time_splits, recruits_input)

    min_time = (
        start_time
        + datetime.timedelta(
            seconds=uag._calc_recruit_time(
                min(input_splits.keys()),
                modifiers,
            )
        )
    ).isoformat()
    new_recruits = [
        {
            "time": (
                start_time
                + datetime.timedelta(
                    seconds=uag._calc_recruit_time(
                        time_multiplier,
                        modifiers,
                    )
                )
            ).isoformat(),
            "recruits": amount,
        }
        for time_multiplier, amount in input_splits.items()
    ]
    return new_recruits, min_time

def _recruit(kd_id, recruits_input):
    """Start training ``recruits_input`` recruits for ``kd_id`` with its money. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    

    def decide(kd_info_parse):
        # Runs against the kingdom as it is right now and again from the top if it changed before the write lands, so
        # it must not have side effects.
        mobis_info_parse = uag._get_mobis_queue(kd_id)
        current_units = kd_info_parse["units"]
        generals_units = kd_info_parse["generals_out"]
        mobis_units = mobis_info_parse
        state = uag._get_state()

        start_time = max(
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
        )
        units = uag._calc_units(start_time, current_units, generals_units, mobis_units)

        max_available_recruits, current_available_recruits = uag._calc_max_recruits(kd_info_parse, units)
        valid_recruits = _validate_recruits(recruits_input, current_available_recruits)
        if not valid_recruits:
            raise occ.Rejected('Please enter valid recruits value')

        new_recruits, min_recruits_time = _get_new_recruits(recruits_input, uag._get_modifiers(kd_id), start_time)

        next_resolve = kd_info_parse["next_resolve"]
        next_resolve["mobis"] = min(next_resolve["mobis"], min_recruits_time)
        new_money = kd_info_parse["money"] - uag._recruit_price(kd_info_parse) * recruits_input
        return {'money': new_money, 'next_resolve': next_resolve}, new_recruits

    try:
        new_recruits = occ.update(f'/kingdom/{kd_id}', decide)
        recruits_payload = {
            "new_mobis": new_recruits
        }
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(recruits_payload),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Successfully began recruiting", "status": "success"}, 200


@bp.route('/api/recruits', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def recruits():
    req = flask.request.get_json(force=True)
    payload, status = _recruit(flask_praetorian.current_user().kd_id, int(req["recruitsInput"]))
    return flask.jsonify(payload), status

def _get_mobis_cost(mobis_request, kd_id):
    state = uag._get_state()
    units_adjusted_costs = uag._get_units_adjusted_costs(state, uag._get_modifiers(kd_id))
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
    if any(key_unit not in uas.TRAINABLE_UNITS for key_unit in mobis_request):
        return False
    if any(units_value > 0 and uas.unit_locked(kd_info_parse, key_unit) for key_unit, units_value in mobis_request.items()):
        return False
    
    return True
    
    

def _get_new_mobis(mobis_request, start_time):
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
        start_time
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * min(mobis_request_split.keys()))
    ).isoformat()

    new_mobis = [
        {
            "time": (
                start_time
                + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier)
            ).isoformat(),
            **time_mobis,
        }
        for time_multiplier, time_mobis in mobis_request_split.items()
    ]
    return new_mobis, min_mobi_time

def _train_mobis(kd_id, mobis_request):
    """Start training units (kind to count) from ``kd_id``'s recruits with its money. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    
    

    # Parsed before taking the lock, so bad input can not leave it held.


    def decide(kd_info_parse):
        current_units = kd_info_parse["units"]
        state = uag._get_state()

        start_time = max(
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
        )

        mobis_cost = _get_mobis_cost(mobis_request, kd_id)
        valid_mobis = _validate_train_mobis(mobis_request, current_units, kd_info_parse, mobis_cost)
        if not valid_mobis:
            raise occ.Rejected('Please enter valid training values')

        new_money = kd_info_parse["money"] - mobis_cost
        new_recruits = kd_info_parse["units"]["recruits"] - sum(mobis_request.values())

        new_mobis, min_mobis_time = _get_new_mobis(mobis_request, start_time)
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
        return kd_payload, new_mobis

    try:
        new_mobis = occ.update(f'/kingdom/{kd_id}', decide)
        mobis_payload = {
            "new_mobis": new_mobis
        }
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(mobis_payload),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Successfully began training specialists", "status": "success"}, 200


@bp.route('/api/mobis', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def train_mobis():
    req = flask.request.get_json(force=True)
    mobis_request = {
        k: int(v or 0)
        for k, v in req.items()
        if int(v or 0) != 0
    }
    payload, status = _train_mobis(flask_praetorian.current_user().kd_id, mobis_request)
    return flask.jsonify(payload), status

def _validate_mobis_target(req_targets, kd_info_parse):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    for key_unit, value in req_targets.items():
        if value > 0 and uas.unit_locked(kd_info_parse, key_unit):
            project = uas.PROJECTS[uas.UNITS[key_unit]["project"]]["name"]
            return False, f"Complete the {project} project to train {uas.PRETTY_NAMES.get(key_unit, key_unit)}"
    
    return True, ""

@bp.route('/api/mobis/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_mobis():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    

    def decide(kd_info_parse):
        if req.get("recruits_before_units", None) is not None:
            recruits_before_units = req["recruits_before_units"]
            if recruits_before_units:
                message = "Recruits will be trained before units during auto spending"
            else:
                message = "Recruits will be trained after units during auto spending"
            return {'recruits_before_units': recruits_before_units}, message

        # A box left empty keeps its target; one set to 0 takes it out of the allocation (it used to be skipped, so a
        # target could never be lowered to 0).
        req_targets = {
            key: float(value or 0) / 100
            for key, value in req.get("targets", {}).items()
            if value not in ("", None)
        }

        current_targets = kd_info_parse['units_target']
        new_targets = {
            **current_targets,
            **req_targets,
        }
        valid_targets, message = _validate_mobis_target(new_targets, kd_info_parse)
        if not valid_targets:
            raise occ.Rejected(message)

        payload = {'units_target': new_targets}
        if req.get("max_recruits", "") != "":
            payload["max_recruits"] = int(req["max_recruits"])
        return payload, "Updated spending"

    try:
        message = occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    return (flask.jsonify({"message": message, "status": "success"}), 200)

def _validate_disband(kd_info, input):

    if "engineers" in input.keys():
        return False, "You can't disband engineers"

    for key_unit, value_unit in input.items():
        if value_unit < 0 or value_unit > kd_info["units"].get(key_unit, 0):
            return False, "You do not have that many units to disband"

    return True, ""

def _disband(kd_id, req_input):
    """Disband units (kind to count) of ``kd_id``: they return to the population and a share of their cost comes back. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    def decide(kd_info):
        valid_disband, message = _validate_disband(kd_info, req_input)
        if not valid_disband:
            raise occ.Rejected(message)

        new_units = {
            key_unit: value_unit - req_input.get(key_unit, 0)
            for key_unit, value_unit in kd_info["units"].items()
        }
        new_money = kd_info["money"] + sum([
            uas.UNITS[key_unit].get("cost", 0) * value_unit * uas.GAME_CONFIG["BASE_DISBAND_COST_RETURN"]
            for key_unit, value_unit in req_input.items()
        ])
        new_pop = kd_info["population"] + sum(req_input.values())

        return {
            "units": new_units,
            "money": new_money,
            "population": new_pop,
        }, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400

    return {"message": "Disbanded units", "status": "success"}, 200


@bp.route('/api/mobis/disband', methods=['POST'])
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
    payload, status = _disband(flask_praetorian.current_user().kd_id, req_input)
    return flask.jsonify(payload), status


def _upgrade_problem(upgrade_request, kd_info, units_desc, modifiers=None):
    """Why this upgrade (unit to make: count) can not start, or None. ``units_desc`` has the prices the kingdom pays.
    Several units can come from the same one (Solar and Self-Destructing Attackers both from Elite Attackers), so what
    each source gives up is added before it is compared with what is at home."""
    if not upgrade_request or sum(upgrade_request.values()) == 0:
        return "Choose some units to upgrade"
    if any(count < 0 for count in upgrade_request.values()):
        return "Upgrade counts can not be negative"
    for unit in upgrade_request:
        if unit not in uas.UPGRADABLE_UNITS:
            return f"{uas.PRETTY_NAMES.get(unit, unit)} can not be upgraded to"
        if upgrade_request[unit] > 0 and uas.unit_locked(kd_info, unit):
            project = uas.PROJECTS[uas.UNITS[unit]["project"]]["name"]
            return f"Complete the {project} project to upgrade to {uas.PRETTY_NAMES.get(unit, unit)}"
    needed = collections.Counter()
    for unit, count in upgrade_request.items():
        needed[uas.UNITS[unit]["upgrades_from"]] += count
    for source, count in needed.items():
        if count > kd_info["units"].get(source, 0):
            return f"You have {math.floor(kd_info['units'].get(source, 0)):,} {uas.PRETTY_NAMES.get(source, source)} at home"
    cost = _upgrade_cost(upgrade_request, units_desc, modifiers)
    if cost > kd_info["money"]:
        return f"Upgrading costs {math.ceil(cost):,}, you have {math.floor(kd_info['money']):,}"
    return None


def _upgrade_cost(upgrade_request, units_desc, modifiers=None):
    return sum(uas.upgrade_cost(units_desc, unit, modifiers) * count for unit, count in upgrade_request.items())


def _upgrade(kd_id, upgrade_request):
    """Upgrade units of ``kd_id`` at home one tier (unit to make: count). The units it is made from leave at once, the
    difference in price is paid, and the new units arrive through the mobis queue like trained ones, so they do not
    fight while upgrading. Returns ``(payload, status_code)``."""
    app = flask.current_app
    state = uag._get_state()
    modifiers = uag._get_modifiers(kd_id)
    units_desc = uag._get_units_adjusted_costs(state, modifiers)
    upgrade_request = {unit: count for unit, count in upgrade_request.items() if count != 0}

    def decide(kd_info):
        problem = _upgrade_problem(upgrade_request, kd_info, units_desc, modifiers)
        if problem:
            raise occ.Rejected(problem)
        start_time = max(
            datetime.datetime.now(datetime.timezone.utc),
            uas.utc(state["state"]["game_start"]),
        )
        new_units = dict(kd_info["units"])
        for unit, count in upgrade_request.items():
            source = uas.UNITS[unit]["upgrades_from"]
            new_units[source] = new_units.get(source, 0) - count
        new_mobis, min_mobis_time = _get_new_mobis(upgrade_request, start_time)
        next_resolve = kd_info["next_resolve"]
        next_resolve["mobis"] = min(next_resolve["mobis"], min_mobis_time)
        return {
            "money": kd_info["money"] - _upgrade_cost(upgrade_request, units_desc, modifiers),
            "units": new_units,
            "next_resolve": next_resolve,
        }, new_mobis

    try:
        new_mobis = occ.update(f'/kingdom/{kd_id}', decide)
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({"new_mobis": new_mobis}),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Began upgrading units", "status": "success"}, 200


@bp.route('/api/mobis/upgrade', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
def upgrade_mobis():
    req = flask.request.get_json(force=True)
    try:
        upgrade_request = {
            str(unit): int(str(count).replace(",", ""))
            for unit, count in (req.get("input") or {}).items()
            if str(count).strip() not in ("", "0")
        }
    except (AttributeError, TypeError, ValueError):
        return flask.jsonify({"message": "Please enter whole numbers of units to upgrade"}), 400
    payload, status = _upgrade(flask_praetorian.current_user().kd_id, upgrade_request)
    return flask.jsonify(payload), status


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

def _structure_time_multiplier(kd_info, modifiers=None):
    """How much of the base construction time this kingdom's structures take, after its projects and ``modifiers``."""
    multiplier = max(1 + uas.modifier(modifiers, "structure_time"), 0)
    if kd_info is not None and uas.has_project(kd_info, "gaian_capstone"):
        multiplier *= 1 - uas.GAME_CONFIG["GAIAN_CAPSTONE_STRUCTURE_TIME_REDUCTION"]
    return multiplier


def _get_new_structures(structures_request, start_time, kd_info=None, modifiers=None):
    """The queue entries for building ``structures_request``, spread over the construction times of ``kd_info``."""
    speed = _structure_time_multiplier(kd_info, modifiers)
    structure_time_splits = [
        split * speed
        for split in _make_time_splits(
            uas.GAME_CONFIG["BASE_STRUCTURE_TIME_MIN_MULTIPLIER"],
            uas.GAME_CONFIG["BASE_STRUCTURE_TIME_MAX_MUTLIPLIER"],
            uas.GAME_CONFIG["BASE_STRUCTURE_TIME_SPLITS"],
        )
    ]
    structures_request_split = collections.defaultdict(dict)
    for key_structure, amt_structure in structures_request.items():
        split_amt_structure = _divide_across_splits(
            structure_time_splits,
            amt_structure,
        )
        for time_multiplier, amt_split in split_amt_structure.items():
            structures_request_split[time_multiplier][key_structure] = amt_split
    
    min_structure_time = (
        start_time
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * min(structures_request_split.keys()))
    ).isoformat()

    new_structures = [
        {
            "time": (
                start_time
                + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier)
            ).isoformat(),
            **time_structures,
        }
        for time_multiplier, time_structures in structures_request_split.items()
    ]
    return new_structures, min_structure_time

def _build_structures(kd_id, structures_request):
    """Start building structures (kind to count) for ``kd_id`` with its money. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    
    
    
    modifiers = uag._get_modifiers(kd_id)

    def decide(kd_info_parse):
        # The money is taken from the kingdom document, so that is where the check happens: this runs against the
        # kingdom as it is right now, and the write below only lands if it is still that way. Runs again from the top
        # if something else changed the kingdom first, so it must not have side effects.
        structures_info_parse = occ.read(f'/kingdom/{kd_id}/structures')

        current_price = uag._get_structure_price(kd_info_parse, modifiers)
        current_structures = kd_info_parse["structures"]
        building_structures = structures_info_parse["structures"]

        state = uag._get_state()

        start_time = max(
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
        )
        structures = uag._calc_structures(start_time, current_structures, building_structures)

        max_available_structures, current_available_structures = uag._calc_available_structures(current_price, kd_info_parse, structures)

        valid_structures = _validate_structures(structures_request, current_available_structures)
        if not valid_structures:
            raise occ.Rejected('Please enter valid structures values')

        new_structures, min_structures_time = _get_new_structures(structures_request, start_time, kd_info_parse, modifiers)
        next_resolve = kd_info_parse["next_resolve"]
        next_resolve["structures"] = min(next_resolve["structures"], min_structures_time)
        new_money = kd_info_parse["money"] - sum(structures_request.values()) * current_price
        return {'money': new_money, 'next_resolve': next_resolve}, new_structures

    # The legacy lock stays for now: other routes still write these documents without checking the version, and the
    # lock is what keeps them from interleaving with this one on a single instance. See docs/concurrency.md.
    try:
        new_structures = occ.update(f'/kingdom/{kd_id}', decide)
        # Appending to the queue is safe to retry on its own: the function app merges it into the newest version.
        structures_payload = {
            "new_structures": new_structures
        }
        structures_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(structures_payload),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Successfully began building structures", "status": "success"}, 200


@bp.route('/api/structures', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def build_structures():
    req = flask.request.get_json(force=True)
    structures_request = {
        k: int(v or 0)
        for k, v in req.items()
        if int(v or 0) != 0
    }
    payload, status = _build_structures(flask_praetorian.current_user().kd_id, structures_request)
    return flask.jsonify(payload), status

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

@bp.route('/api/structures/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_structures():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    def decide(kd_info_parse):
        # A box left empty keeps its target; one set to 0 takes it out of the allocation (it used to be skipped, so a
        # target could never be lowered to 0).
        req_targets = {
            key: float(value or 0) / 100
            for key, value in req.items()
            if value not in ("", None)
        }

        current_targets = kd_info_parse['structures_target']
        new_targets = {
            **current_targets,
            **req_targets,
        }
        valid_targets, message = _validate_structures_target(new_targets)
        if not valid_targets:
            raise occ.Rejected(message)

        return {'structures_target': new_targets}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    return (flask.jsonify({"message": "Updated spending", "status": "success"}), 200)

def _validate_raze(kd_info, input):

    for key_structure, value_structure in input.items():
        if value_structure < 0 or value_structure > kd_info["structures"].get(key_structure, 0):
            return False, "You do not have that many structures to raze"
        
    return True, ""

@bp.route('/api/structures/raze', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def raze_structures():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    req_input = {
        k: int(v)
        for k, v in req["input"].items()
        if v not in ("", "0")
    } 

    kd_id = flask_praetorian.current_user().kd_id
    modifiers = uag._get_modifiers(kd_id)
    raze_return = uag._raze_return(modifiers)

    def decide(kd_info):
        valid_raze, message = _validate_raze(kd_info, req_input)
        if not valid_raze:
            raise occ.Rejected(message)

        # The refund is a share of what a structure costs this kingdom today.
        structures_price = uag._get_structure_price(kd_info, modifiers)

        new_structures = {
            key_structure: math.floor(value_structure - req_input.get(key_structure, 0))
            for key_structure, value_structure in kd_info["structures"].items()
        }
        new_money = kd_info["money"] + sum([
            structures_price * value_structures * raze_return
            for value_structures in req_input.values()
        ])

        return {
            "structures": new_structures,
            "money": new_money,
        }, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    
    return (flask.jsonify({"message": "Razed structures", "status": "success"}), 200)


def _validate_settles(settle_input, kd_info, settle_info, modifiers=None):
    max_settle, available_settle = uag._get_available_settle(kd_info, settle_info, modifiers)
    if settle_input <= 0:
        return False
    if settle_input > available_settle:
        return False

    return True

def _get_new_settles(kd_info_parse, settle_input, start_time):
    settle_time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_SETTLE_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_SETTLE_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_SETTLE_TIME_SPLITS"],
    )
    settle_splits = _divide_across_splits(settle_time_splits, settle_input)

    min_settle_time = (
        start_time
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
                start_time
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

def _settle(kd_id, settle_input):
    """Start settling ``settle_input`` stars for ``kd_id`` with its money. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    
    
    
    modifiers = uag._get_modifiers(kd_id)

    def decide(kd_info_parse):
        settle_info = uag._get_settle_queue(kd_id)
        valid_settle = _validate_settles(settle_input, kd_info_parse, settle_info, modifiers)
        if not valid_settle:
            raise occ.Rejected('Please enter valid settle value')

        state = uag._get_state()

        start_time = max(
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
        )
        new_settles, min_settle_time = _get_new_settles(kd_info_parse, settle_input, start_time)

        settle_price = uag._get_settle_price(kd_info_parse, modifiers)
        new_money = kd_info_parse["money"] - settle_price * settle_input
        next_resolve = kd_info_parse["next_resolve"]
        next_resolve["settles"] = min(next_resolve["settles"], min_settle_time)
        return {'money': new_money, "next_resolve": next_resolve}, new_settles

    try:
        new_settles = occ.update(f'/kingdom/{kd_id}', decide)
        settle_payload = {
            "new_settles": new_settles,
        }
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(settle_payload),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Successfully began settling", "status": "success"}, 200


@bp.route('/api/settle', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def settle():
    req = flask.request.get_json(force=True)
    payload, status = _settle(flask_praetorian.current_user().kd_id, int(req["settleInput"]))
    return flask.jsonify(payload), status

def _validate_missiles(missiles_request, kd_info_parse, missiles_building, max_available_missiles, modifiers=None):
    current_missiles = kd_info_parse["missiles"]
    missiles = {k: current_missiles.get(k, 0) + missiles_building.get(k, 0) for k in uas.MISSILES}

    missiles_available = {k: max_available_missiles - missiles.get(k, 0) for k in missiles}
    cost_multiplier = uag._missile_cost_modifier(kd_info_parse, modifiers)
    costs = sum([uas.MISSILES[key_missile]["cost"] * value_missile * cost_multiplier for key_missile, value_missile in missiles_request.items()])
    fuel_costs = sum([uas.MISSILES[key_missile]["fuel_cost"] * value_missile * cost_multiplier for key_missile, value_missile in missiles_request.items()])

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
    if any(
        value_missile > 0
        and uas.MISSILES[key_missile].get("project")
        and not uas.has_project(kd_info_parse, uas.MISSILES[key_missile]["project"])
        for key_missile, value_missile in missiles_request.items()
    ):
        return False
    
    return True


def _build_missiles(kd_id, missiles_request):
    """Start building missiles (kind to count) for ``kd_id``. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    modifiers = uag._get_modifiers(kd_id)
    
    
    

    def decide(kd_info_parse):
        missiles_info = uag._get_missiles_info(kd_id)
        missiles_building = uag._get_missiles_building(missiles_info)

        max_available_missiles = uag._calc_missile_capacity(kd_info_parse)

        valid_missiles = _validate_missiles(missiles_request, kd_info_parse, missiles_building, max_available_missiles, modifiers)
        if not valid_missiles:
            raise occ.Rejected('Please enter valid missiles values')

        cost_multiplier = uag._missile_cost_modifier(kd_info_parse, modifiers)
        costs = sum([uas.MISSILES[key_missile]["cost"] * value_missile * cost_multiplier for key_missile, value_missile in missiles_request.items()])
        fuel_costs = sum([uas.MISSILES[key_missile]["fuel_cost"] * value_missile * cost_multiplier for key_missile, value_missile in missiles_request.items()])
        new_money = kd_info_parse["money"] - costs
        new_fuel = kd_info_parse["fuel"] - fuel_costs

        state = uag._get_state()

        start_time = max(
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
        )

        missiles_time = (start_time + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_MISSILE_TIME_MULTIPLER"])).isoformat()
        next_resolve = kd_info_parse["next_resolve"]
        next_resolve["missiles"] = min(next_resolve["missiles"], missiles_time)
        kd_payload = {
            'money': new_money,
            'fuel': new_fuel,
            'next_resolve': next_resolve,
        }
        return kd_payload, missiles_time

    try:
        missiles_time = occ.update(f'/kingdom/{kd_id}', decide)
        missiles_payload = {
            "new_missiles": [
                {
                    "time": missiles_time,
                    **missiles_request,
                }
            ]
        }
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(missiles_payload),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Successfully began building missiles", "status": "success"}, 200


@bp.route('/api/missiles', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def build_missiles():
    req = flask.request.get_json(force=True)
    missiles_request = {
        k: int(v or 0)
        for k, v in req.items()
        if v not in ("", 0)
    }
    payload, status = _build_missiles(flask_praetorian.current_user().kd_id, missiles_request)
    return flask.jsonify(payload), status

def _validate_engineers(engineers_input, current_available_engineers):
    if engineers_input > current_available_engineers:
        return False
    if engineers_input <= 0:
        return False

    return True


def _get_new_engineers(engineers_input, start_time):
    """The queue entries for ``engineers_input`` engineers trained from ``start_time``."""
    time_splits = _make_time_splits(
        uas.GAME_CONFIG["BASE_ENGINEER_TIME_MIN_MULTIPLIER"],
        uas.GAME_CONFIG["BASE_ENGINEER_TIME_MAX_MUTLIPLIER"],
        uas.GAME_CONFIG["BASE_ENGINEER_TIME_SPLITS"],
    )
    input_splits = _divide_across_splits(time_splits, engineers_input)

    min_time = (
        start_time
        + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * min(input_splits.keys()))
    ).isoformat()
    new_engineers = [
        {
            "time": (
                start_time
                + datetime.timedelta(
                    seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier,
                )
            ).isoformat(),
            "amount": amount,
        }
        for time_multiplier, amount in input_splits.items()
    ]
    return new_engineers, min_time

def _train_engineers(kd_id, engineers_input):
    """Start training ``engineers_input`` engineers for ``kd_id`` with its money. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    modifiers = uag._get_modifiers(kd_id)
    
    

    def decide(kd_info_parse):
        engineers_info = uag._get_engineers_queue(kd_id)
        engineers_building = sum([training["amount"] for training in engineers_info])
        max_workshop_capacity, current_workshop_capacity = uag._calc_workshop_capacity(kd_info_parse, engineers_building)
        max_available_engineers, current_available_engineers = uag._calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity, modifiers)

        valid_engineers = _validate_engineers(engineers_input, current_available_engineers)
        if not valid_engineers:
            raise occ.Rejected('Please enter valid recruits value')

        state = uag._get_state()

        start_time = max(
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
        )
        new_engineers, min_engineers_time = _get_new_engineers(engineers_input, start_time)
        next_resolve = kd_info_parse["next_resolve"]
        next_resolve["engineers"] = min(next_resolve["engineers"], min_engineers_time)
        new_money = kd_info_parse["money"] - uag._engineer_price(modifiers) * engineers_input
        return {'money': new_money, 'next_resolve': next_resolve}, new_engineers

    try:
        new_engineers = occ.update(f'/kingdom/{kd_id}', decide)
        engineers_payload = {
            "new_engineers": new_engineers
        }
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(engineers_payload),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400
    return {"message": "Successfully began training engineers", "status": "success"}, 200


@bp.route('/api/engineers', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def train_engineers():
    req = flask.request.get_json(force=True)
    payload, status = _train_engineers(flask_praetorian.current_user().kd_id, int(req["engineersInput"]))
    return flask.jsonify(payload), status

def _validate_projects_target(req_targets, kd_info_parse):
    """Confirm that spending request is valid"""

    values = req_targets.values()
    if any((value < 0 for value in values)):
        return False, "Target values must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Target values must be less than 100%"
    if sum(values) > 1:
        return False, "Target values must be less than 100%"
    message = _projects_refusal(req_targets, kd_info_parse)
    if message:
        return False, message
    return True, ""


def _projects_refusal(engineers_by_project, kd_info_parse):
    """
    Why engineers (or a share of them) can not go to these projects, or None. Each must be a project, unlocked for
    this kingdom (its race, the projects it requires), and not a one-time project that is already completed.
    """
    for project, value in engineers_by_project.items():
        if project not in uas.PROJECTS:
            return f"There is no project called {project}"
        if not value or value <= 0:
            continue
        locked = uas.project_locked_reason(kd_info_parse, project)
        if locked:
            return locked
        if project in uas.ONE_TIME_PROJECTS and uas.has_project(kd_info_parse, project):
            return f"{uas.PROJECTS[project]['name']} is already completed"
    return None

@bp.route('/api/projects/target', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def allocate_projects():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    
    def decide(kd_info_parse):
        if req.get("enabled", None) is not None:
            if req["enabled"]:
                message = "Auto assigning engineers enabled"
            else:
                message = "Auto assigning engineers disabled"
            return {'auto_assign_projects': req["enabled"]}, message

        # A box left empty keeps its target; one set to 0 takes it out of the allocation (it used to be skipped, so a
        # target could never be lowered to 0).
        req_targets = {
            key: float(value or 0) / 100
            for key, value in req.get("targets", {}).items()
            if value not in ("", None)
        }

        current_targets = kd_info_parse['projects_target']
        new_targets = {
            **current_targets,
            **req_targets,
        }
        valid_targets, message = _validate_projects_target(new_targets, kd_info_parse)
        if not valid_targets:
            raise occ.Rejected(message)

        return {'projects_target': new_targets}, "Updated spending"

    try:
        message = occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    return (flask.jsonify({"message": message, "status": "success"}), 200)

def _validate_assign_projects(req, kd_info_parse):
    """(ok, message) for assigning engineers to projects: the counts in ``req["assign"]`` replace all assignments."""
    engineers_assigned = sum(req["assign"].values())
    if any(value < 0 for value in req["assign"].values()):
        return False, "Please enter valid assign engineers value"
    if engineers_assigned > kd_info_parse["units"]["engineers"]:
        return False, "You do not have that many engineers"
    message = _projects_refusal(req["assign"], kd_info_parse)
    if message:
        return False, message
    return True, ""

def _validate_add_projects(req, available_engineers, kd_info_parse):
    """(ok, message) for adding free engineers to projects."""
    engineers_added = sum(req["add"].values())
    if any(value < 0 for value in req["add"].values()):
        return False, "Please enter valid add engineers value"
    if engineers_added > available_engineers:
        return False, "You do not have that many free engineers"
    message = _projects_refusal(req["add"], kd_info_parse)
    if message:
        return False, message
    return True, ""

@bp.route('/api/projects', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def manage_projects():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    
    

    # Parsed and type-checked before anything is read: counts are whole numbers.
    try:
        for field in ("assign", "add"):
            if field in req:
                req[field] = {k: int(v or 0) for k, v in req[field].items()}
    except (TypeError, ValueError, AttributeError):
        return (flask.jsonify({"message": "Please enter whole numbers of engineers"}), 400)

    def decide(kd_info_parse):
        assigned = {key: kd_info_parse["projects_assigned"].get(key, 0) for key in uas.PROJECTS}
        new_projects_assigned = dict(assigned)
        if "clear" in req.keys():
            for project_to_clear in req["clear"]:
                if project_to_clear in new_projects_assigned:
                    new_projects_assigned[project_to_clear] = 0

        elif "assign" in req.keys():
            valid_assign, message = _validate_assign_projects(req, kd_info_parse)
            if not valid_assign:
                raise occ.Rejected(message)
            new_projects_assigned = {key: req["assign"].get(key, 0) for key in uas.PROJECTS}

        elif "add" in req.keys():
            available_engineers = kd_info_parse["units"]["engineers"] - sum(assigned.values())
            valid_add, message = _validate_add_projects(req, available_engineers, kd_info_parse)
            if not valid_add:
                raise occ.Rejected(message)
            new_projects_assigned = {key: value + req["add"].get(key, 0) for key, value in assigned.items()}

        return {"projects_assigned": new_projects_assigned}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    return (flask.jsonify({"message": "Successfully updated project assignment", "status": "success"}), 200)