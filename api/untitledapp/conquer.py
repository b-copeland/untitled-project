import datetime
import json
import math
import os
import random
import uuid

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.getters as uag
import untitledapp.shared as uas
from untitledapp import app, alive_required, start_required, _mark_kingdom_death, REQUESTS_SESSION, SOCK_HANDLERS

@app.route('/api/revealrandomgalaxy', methods=['GET'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def reveal_random_galaxy():
    kd_id = flask_praetorian.current_user().kd_id
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if kd_info_parse["spy_attempts"] <= 0:
        return (flask.jsonify({"message": 'You do not have any spy attempts remaining'}), 400)

    revealed_info = uag._get_revealed(kd_id)

    empires_inverted, empires, _, _ = uag._get_empires_inverted()
    galaxies_inverted, galaxy_info = uag._get_galaxies_inverted()

    kd_empire = empires_inverted.get(kd_id, None)
    kd_galaxy = galaxies_inverted[kd_id]

    
    
    excluded_galaxies = list(revealed_info["galaxies"].keys())
    
    if kd_empire:
        
        excluded_galaxies.extend(empires[kd_empire]["galaxies"])
    else:
        excluded_galaxies.append(kd_galaxy)

    potential_galaxies = set(galaxy_info.keys()) - set(excluded_galaxies)

    if not len(potential_galaxies):
        return (flask.jsonify({"message": 'There are no more galaxies to reveal'}), 400)

    galaxy_to_reveal = random.choice(list(potential_galaxies))

    time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"])).isoformat()
    payload = {
        "new_galaxies": {
            galaxy_to_reveal: time
        }
    }

    payload["new_revealed"] = {
        kd_id: {
            "stats": time,
        }
        for kd_id in galaxy_info[galaxy_to_reveal]
    }

    
    reveal_galaxy_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    

    next_resolve = kd_info_parse["next_resolve"]
    next_resolve["revealed"] = min(next_resolve["revealed"], time)
    kd_payload = {"spy_attempts": kd_info_parse["spy_attempts"] - 1, "next_resolve": next_resolve}
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload),
    )

    return (flask.jsonify({"message": f"Reveavled galaxy {galaxy_to_reveal}", "status": "success"}), 200)

def _validate_attack_request(
    attacker_raw_values,
    kd_info
):
    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in uas.UNITS and value != "")
    }
    if any((
        attack_units > kd_info["units"].get(key_unit, 0)
        for key_unit, attack_units in attacker_units.items()
    )):
        return False, "You do not have that many units"
    if any((
        attack_units < 0
        for attack_units in attacker_units.values()
    )):
        return False, "You can not send negative units"
    if sum(attacker_units.values()) == 0:
        return False, "You must send at least 1 unit"
    if int(attacker_raw_values["generals"] or 0) > kd_info["generals_available"]:
        return False, "You do not have that many generals"
    if int(attacker_raw_values["generals"] or 0) == 0:
        return False, "You must send at least 1 general"
    
    return True, ""

def _calc_losses(
    unit_dict,
    loss_rate,
    xo=False,
):
    int_xo = int(xo)
    adjusted_loss_rate = (
        loss_rate
        * (
            1
            - int_xo * uas.GAME_CONFIG["XO_ATTACK_UNIT_LOSSES_REDUCTION"]
        )
    )
    losses = {
        key_unit: math.floor(value_unit * adjusted_loss_rate)
        for key_unit, value_unit in unit_dict.items()
    }
    return losses

def _calc_coordinate_distance(
    coord_a,
    coord_b,
):
    direct_distance = abs(coord_a - coord_b)
    indirect_distance_1 = (coord_a) + (99 - coord_b)
    indirect_distance_2 = (coord_b) + (99 - coord_a)
    return min(direct_distance, indirect_distance_1, indirect_distance_2)

def _calc_generals_return_time(
    generals,
    return_multiplier,
    base_time,
    general_bonus=0,
    is_warlike=False,
    coordinate_distance=25,
):
    coordinate_distance_norm = coordinate_distance - 25
    coordinate_effect = coordinate_distance_norm * uas.GAME_CONFIG["BASE_RETURN_TIME_PENALTY_PER_COORDINATE"]
    return_time_with_bonus = datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * return_multiplier) * (1 - general_bonus - int(is_warlike) * uas.GAME_CONFIG["BASE_WARLIKE_RETURN_REDUCTION"] + coordinate_effect)
    
    return_times = [
        base_time + (return_time_with_bonus / i)
        for i in range(generals, 0, -1)
    ]
    return return_times

@app.route('/api/calculate/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_attack(target_kd):
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]
    defender_raw_values = req["defenderValues"]

    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }

    revealed = uag._get_revealed(kd_id)
    shared = uag._get_shared(kd_id)["shared"]
    max_target_kd_info = uag._get_max_kd_info(target_kd, kd_id, revealed)

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
    )
    if not valid_attack_request:
        return (flask.jsonify({"message": attack_request_message}), 400)

    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in uas.UNITS and value != "")
    }
    if "units" in max_target_kd_info:
        defender_units = max_target_kd_info["units"]
    else:
        defender_units = {
            key: int(value)
            for key, value in defender_raw_values.items()
            if (key in uas.UNITS and value != "")
        }
    
    if "current_bonuses" in max_target_kd_info:
        defender_military_bonus = max_target_kd_info["current_bonuses"]["military_bonus"]
    else:
        defender_military_bonus = float(defender_raw_values['military_bonus'] or 0) / 100

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["military"]
    else:
        defender_shields = float(defender_raw_values['shields'] or 0) / 100

    if "fuel" in max_target_kd_info:
        target_fuelless = max_target_kd_info["fuel"] <= 0
    else:
        target_fuelless = False

    attacker_fuelless = kd_info_parse["fuel"] <= 0
    attack = uag._calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless,
        lumina=kd_info_parse["race"] == "Lumina",
    )
    defense = uag._calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
        fuelless=target_fuelless,
        gaian=kd_info_parse["race"] == "Gaian",
    )
    try:
        attack_ratio = min(attack / defense, 1.0)
    except ZeroDivisionError:
        attack_ratio = 1.0
    attacker_losses = _calc_losses(
        attacker_units,
        uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        xo=kd_info_parse["race"] == "Xo",
    )
    defender_losses = _calc_losses(
        defender_units,
        uas.GAME_CONFIG["BASE_DEFENDER_UNIT_LOSS_RATE"] * attack_ratio,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=_calc_coordinate_distance(kd_info_parse["coordinate"], max_target_kd_info["coordinate"]),
    )
    generals_strftime = ', '.join([
        str(general_return_time - time_now).split(".")[0]
        for general_return_time in generals_return_times
    ])
    if attack > defense:
        message = f"The attack will be a success!\n"
        message += f"Your general(s) will return in: {generals_strftime}. \n"
        if target_kd in shared:
            cut = shared[target_kd]["cut"]
            sharer = shared[target_kd]["shared_by"]
        else:
            cut = 0
            sharer = None
        spoils_rate = uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"] * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        )
        min_stars_gain = uas.GAME_CONFIG["BASE_ATTACK_MIN_STARS_GAIN"] * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        )
        spoils_values = {
            key_spoil: math.floor(value_spoil * spoils_rate * (1 - cut))
            for key_spoil, value_spoil in max_target_kd_info.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        try:
            spoils_values["stars"] = max(spoils_values["stars"], math.floor(min_stars_gain * (1 - cut)))
        except KeyError:
            pass
        if spoils_values:
            message += 'You will gain '
            message += ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
            message += '. \n'
            if sharer:
                sharer_spoils_values = {
                    key_spoil: math.floor(value_spoil * spoils_rate * cut)
                    for key_spoil, value_spoil in max_target_kd_info.items()
                    if key_spoil in {"stars", "population", "money", "fuel"}
                }
                try:
                    sharer_spoils_values["stars"] = max(sharer_spoils_values["stars"], math.floor(min_stars_gain * cut))
                except KeyError:
                    pass
                kingdoms = uag._get_kingdoms()
                sharer_name = kingdoms[sharer]
                message += f'Your galaxymate {sharer_name} will gain '
                message += ', '.join([f"{value} {key}" for key, value in sharer_spoils_values.items()])
                message += ' for sharing intel. \n'

                
    else:
        message = f"The attack will fail.\n"
        message += f"Your general(s) will return in: {generals_strftime}\n"

    payload = {
        "defender_defense": defense,
        "attacker_offense": attack,
        "defender_losses": defender_losses,
        "attacker_losses": attacker_losses,
        "defender_unit_losses_rate": uas.GAME_CONFIG["BASE_DEFENDER_UNIT_LOSS_RATE"],
        "attacker_unit_losses_rate": uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        "defender_stars_loss_rate": uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"],
        "generals_return_times": generals_return_times,
        "message": message
    }

    return (flask.jsonify(payload), 200)

def _validate_autofill_request(req, kd_info_parse):
    if req.get("buffer", "") == "":
        return False, "Please choose a buffer amount"
    
    if req.get("generals", "") == "":
        return False, "Please choose a generals amount"
    
    buffer = float(req.get("buffer", 0.0))
    generals = int(req.get("generals"), 0)

    if buffer < 0:
        return False, "Buffer must be greater than 0"
    
    if generals < 0:
        return False, "Generals must be greater than 0"
    
    if generals > kd_info_parse["generals_available"]:
        return False, "You do not have that many generals"
    
    return True, ""
    

def _autofill_attack(req, kd_id, target_kd):
    defender_raw_values = req["defenderValues"]
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }

    revealed = uag._get_revealed(kd_id)
    shared = uag._get_shared(kd_id)["shared"]
    max_target_kd_info = uag._get_max_kd_info(target_kd, kd_id, revealed)

    valid_request, request_message = _validate_autofill_request(
        req,
        kd_info_parse,
    )
    if not valid_request:
        return {"message": request_message}, 400

    if "units" in max_target_kd_info:
        defender_units = max_target_kd_info["units"]
    else:
        defender_units = {
            key: int(value)
            for key, value in defender_raw_values.items()
            if (key in uas.UNITS and value != "")
        }
    
    if "current_bonuses" in max_target_kd_info:
        defender_military_bonus = max_target_kd_info["current_bonuses"]["military_bonus"]
    else:
        defender_military_bonus = float(defender_raw_values['military_bonus'] or 0) / 100

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["military"]
    else:
        defender_shields = float(defender_raw_values['shields'] or 0) / 100

    if "fuel" in max_target_kd_info:
        target_fuelless = max_target_kd_info["fuel"] <= 0
    else:
        target_fuelless = False

    defense = uag._calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
        fuelless=target_fuelless,
        gaian=kd_info_parse["race"] == "Gaian",
    )
    defense_adjusted = math.floor(
        defense 
        * (1 + (float(req.get("buffer", 0.0)) / 100))
    )

    attacker_units = {}
    remaining_defense = max(defense_adjusted, 1)
    generals = int(req.get("generals", 1))
    attacker_fuelless = kd_info_parse["fuel"] <= 0
    for key_unit in uas.AUTOFILL_PRIORITY:
        if remaining_defense == 0:
            attacker_units[key_unit] = 0
        available_units = kd_info_parse["units"].get(key_unit, 0)
        if available_units > 0:
            current_unit_attack = uag._calc_max_offense(
                {
                    key_unit: available_units,
                },
                military_bonus=float(current_bonuses['military_bonus'] or 0), 
                other_bonuses=0,
                generals=generals,
                fuelless=attacker_fuelless,
                lumina=kd_info_parse["race"] == "Lumina",
            )
            if current_unit_attack > remaining_defense:
                required_ratio = remaining_defense / current_unit_attack
                units_fill = math.ceil(required_ratio * available_units)
                attacker_units[key_unit] = units_fill
                remaining_defense = 0
            else:
                attacker_units[key_unit] = available_units
                remaining_defense = remaining_defense - current_unit_attack
        else:
            attacker_units[key_unit] = 0

    attack = uag._calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=generals,
        fuelless=attacker_fuelless,
        lumina=kd_info_parse["race"] == "Lumina",
    )
    try:
        attack_ratio = min(attack / defense_adjusted, 1.0)
    except ZeroDivisionError:
        attack_ratio = 1.0
    attacker_losses = _calc_losses(
        attacker_units,
        uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        xo=kd_info_parse["race"] == "Xo",
    )
    defender_losses = _calc_losses(
        defender_units,
        uas.GAME_CONFIG["BASE_DEFENDER_UNIT_LOSS_RATE"] * attack_ratio,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        generals,
        uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=_calc_coordinate_distance(kd_info_parse["coordinate"], max_target_kd_info["coordinate"]),
    )
    generals_strftime = ', '.join([
        str(general_return_time - time_now).split(".")[0]
        for general_return_time in generals_return_times
    ])
    if attack > defense:
        message = f"The attack will be a success!\n"
        message += f"Your general(s) will return in: {generals_strftime}. \n"
        if target_kd in shared:
            cut = shared[target_kd]["cut"]
            sharer = shared[target_kd]["shared_by"]
        else:
            cut = 0
            sharer = None
        spoils_rate = uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"] * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        )
        min_stars_gain = uas.GAME_CONFIG["BASE_ATTACK_MIN_STARS_GAIN"] * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        )
        spoils_values = {
            key_spoil: math.floor(value_spoil * spoils_rate * (1 - cut))
            for key_spoil, value_spoil in max_target_kd_info.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        try:
            spoils_values["stars"] = max(spoils_values["stars"], math.floor(min_stars_gain * (1 - cut)))
        except KeyError:
            pass
        if spoils_values:
            message += 'You will gain '
            message += ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
            message += '. \n'
            if sharer:
                sharer_spoils_values = {
                    key_spoil: math.floor(value_spoil * spoils_rate * cut)
                    for key_spoil, value_spoil in max_target_kd_info.items()
                    if key_spoil in {"stars", "population", "money", "fuel"}
                }
                try:
                    sharer_spoils_values["stars"] = max(sharer_spoils_values["stars"], math.floor(min_stars_gain * cut))
                except KeyError:
                    pass
                kingdoms = uag._get_kingdoms()
                sharer_name = kingdoms[sharer]
                message += f'Your galaxymate {sharer_name} will gain '
                message += ', '.join([f"{value} {key}" for key, value in sharer_spoils_values.items()])
                message += ' for sharing intel. \n'

                
    else:
        message = f"The attack will fail.\n"
        message += f"Your general(s) will return in: {generals_strftime}\n"

    payload = {
        "defender_defense": defense,
        "attacker_offense": attack,
        "defender_losses": defender_losses,
        "attacker_losses": attacker_losses,
        "defender_unit_losses_rate": uas.GAME_CONFIG["BASE_DEFENDER_UNIT_LOSS_RATE"],
        "attacker_unit_losses_rate": uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        "defender_stars_loss_rate": uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"],
        "generals_return_times": generals_return_times,
        "message": message,
        "attacker_units": attacker_units,
    }
    return payload, 200



@app.route('/api/autofill/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def autofill_attack(target_kd):
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id

    payload, status_code = _autofill_attack(
        req,
        kd_id,
        target_kd,
    )
    
    payload, status_code = _autofill_attack(req, kd_id, target_kd)
    return (flask.jsonify(payload), status_code)

def _attack(req, kd_id, target_kd):
    
    attacker_raw_values = req["attackerValues"]

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }

    shared = uag._get_shared(kd_id)["shared"]
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    target_kd_info = uag._get_kd_info(target_kd)
    if target_kd_info["status"].lower() == "dead":
        return (flask.jsonify({"message": "You can't attack this kingdom because they are dead!"}), 400)
    target_current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(target_kd_info["projects_points"][project] / target_kd_info["projects_max_points"][project], 1.0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
    )
    if not valid_attack_request:
        return kd_info_parse, {"message": attack_request_message}, 400

    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in uas.UNITS and value != "")
    }
    defender_units = {
        key: value
        for key, value in target_kd_info["units"].items()
        if uas.UNITS[key].get("defense", 0) > 0
    }
    defender_military_bonus = target_current_bonuses['military_bonus']
    defender_shields = target_kd_info["shields"]["military"]

    attacker_fuelless = kd_info_parse["fuel"] <= 0
    target_fuelless = target_kd_info["fuel"] <= 0
    attack = uag._calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless,
        lumina=kd_info_parse["race"] == "Lumina",
    )
    defense = uag._calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
        fuelless=target_fuelless,
        gaian=kd_info_parse["race"] == "Gaian",
    )
    attack_ratio = min(attack / defense, 1.0)
    attacker_losses = _calc_losses(
        attacker_units,
        uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        xo=kd_info_parse["race"] == "Xo",
    )
    defender_losses = _calc_losses(
        defender_units,
        uas.GAME_CONFIG["BASE_DEFENDER_UNIT_LOSS_RATE"] * attack_ratio,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=_calc_coordinate_distance(kd_info_parse["coordinate"], target_kd_info["coordinate"]),
    )
    new_home_attacker_units = {
        key_unit: value_unit - attacker_units.get(key_unit, 0)
        for key_unit, value_unit in kd_info_parse["units"].items()
    }
    remaining_attacker_units = {
        key_unit: value_unit - attacker_losses.get(key_unit, 0)
        for key_unit, value_unit in attacker_units.items()
    }
    generals = [
        {
            "return_time": general_time.isoformat(),
            **{
                key_unit: math.floor(remaining_unit / len(generals_return_times))
                for key_unit, remaining_unit in remaining_attacker_units.items()
            }
        }
        for general_time in generals_return_times
    ]
    next_return_time = min([general["return_time"] for general in generals])
    new_defender_units = {
        key_unit: value_unit - defender_losses.get(key_unit, 0)
        for key_unit, value_unit in target_kd_info["units"].items()
    }
    if target_kd in shared:
        cut = shared[target_kd]["cut"]
        sharer = shared[target_kd]["shared_by"]
    else:
        cut = 0
        sharer = None
    if attack > defense:
        spoils_rate = uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"] * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        )
        min_stars_gain = math.floor(uas.GAME_CONFIG["BASE_ATTACK_MIN_STARS_GAIN"] * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        ))
        total_spoils = {
            key_spoil: math.floor(value_spoil * spoils_rate)
            for key_spoil, value_spoil in target_kd_info.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        total_spoils["stars"] = max(total_spoils["stars"], min_stars_gain)
        spoils_values = {
            key_spoil: math.floor(value_spoil * (1 - cut))
            for key_spoil, value_spoil in total_spoils.items()
            if key_spoil in {"stars", "population", "money", "fuel"}
        }
        if sharer:
            sharer_spoils_values = {
                key_spoil: math.floor(value_spoil * cut)
                for key_spoil, value_spoil in total_spoils.items()
                if key_spoil in {"stars", "population", "money", "fuel"}
            }
            sharer_message = (
                "You have gained "
                + ', '.join([f"{value} {key}" for key, value in sharer_spoils_values.items()])
                + f" for sharing intel leading to a successful attack by your galaxymate {kd_info_parse['name']}"
            )
            sharer_news = {
                "time": time_now.isoformat(),
                "from": kd_id,
                "news": sharer_message,
            }
            sharer_news_patch_response = REQUESTS_SESSION.patch(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{sharer}/news',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                data=json.dumps(sharer_news),
            )
        else:
            sharer_spoils_values = {}

        units_destroyed = sum(defender_losses.values())
        attack_status = "success"
        attacker_message = (
            "Success! You have gained "
            + ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
            + f" and destroyed {units_destroyed} units."
            + " You have lost "
            + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
        )
        defender_message = (
            f"Your kingdom was defeated in battle by {kd_info_parse['name']}. You have lost "
            + ', '.join([f"{value} {key}" for key, value in total_spoils.items()])
            + ' and '
            + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in defender_losses.items()])
        )
    else:
        attack_status = "failure"
        attacker_message = "Failure! You have lost " + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
        defender_message = (
            f"Your kingdom successfully defended an attack by {kd_info_parse['name']}. You have lost "
            + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in defender_losses.items()])
        )
        spoils_values = {}
        sharer_spoils_values = {}
    

    kd_info_parse["units"] = new_home_attacker_units
    kd_info_parse["generals_out"] = kd_info_parse["generals_out"] + generals
    kd_info_parse["generals_available"] = kd_info_parse["generals_available"] - int(attacker_raw_values["generals"])
    kd_info_parse["next_resolve"]["generals"] = min(kd_info_parse["next_resolve"]["generals"], next_return_time)

    target_kd_info["units"] = new_defender_units
    for key_spoil, value_spoil in spoils_values.items():
        if key_spoil != "money":
            kd_info_parse[key_spoil] += value_spoil
        else:
            if kd_info_parse["auto_spending_enabled"]:
                pct_allocated = sum(kd_info_parse["auto_spending"].values())
                for key_spending, pct_spending in kd_info_parse["auto_spending"].items():
                    kd_info_parse["funding"][key_spending] += pct_spending * value_spoil
                kd_info_parse["money"] += value_spoil * (1 - pct_allocated)
            else:
                kd_info_parse["money"] += value_spoil
        target_kd_info[key_spoil] -= value_spoil

    target_kd_info["stars"] = max(target_kd_info["stars"], 0)
    for key_project, project_dict in uas.PROJECTS.items():
        project_max_func = uas.PROJECTS_FUNCS[key_project]
        kd_info_parse["projects_max_points"][key_project] = project_max_func(kd_info_parse["stars"])
        target_kd_info["projects_max_points"][key_project] = project_max_func(target_kd_info["stars"])

    if sharer and sharer_spoils_values:
        sharer_kd_info = uag._get_kd_info(sharer)
        for key_spoil, value_spoil in sharer_spoils_values.items():
            if key_spoil != "money":
                sharer_kd_info[key_spoil] += value_spoil
            else:
                if sharer_kd_info["auto_spending_enabled"]:
                    pct_allocated = sum(sharer_kd_info["auto_spending"].values())
                    for key_spending, pct_spending in sharer_kd_info["auto_spending"].items():
                        sharer_kd_info["funding"][key_spending] += pct_spending * value_spoil
                    sharer_kd_info["money"] += value_spoil * (1 - pct_allocated)
                else:
                    sharer_kd_info["money"] += value_spoil
            sharer_kd_info[key_spoil] += value_spoil
            target_kd_info[key_spoil] -= value_spoil
        sharer_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{sharer}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(sharer_kd_info),
        )
        try:
            ws = SOCK_HANDLERS[sharer]
            ws.send(json.dumps({
                "message": f"You have gained {sharer_spoils_values['stars']} from an attack by your galaxymate {kd_info_parse['name']}",
                "status": "info",
                "category": "Galaxy",
                "delay": 15000,
                "update": [],
            }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    
    if target_kd_info["stars"] <= 0:
        target_kd_info["status"] = "Dead"
        _mark_kingdom_death(target_kd)
    target_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_kd_info),
    )
    target_news = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "news": defender_message,
    }
    try:
        ws = SOCK_HANDLERS[target_kd]
        ws.send(json.dumps({
            "message": defender_message,
            "status": "warning",
            "category": "Attack",
            "delay": 60000,
            "update": ["news", "galaxynews"],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    target_news_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_news),
    )
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_info_parse, default=str),
    )
    kd_attack_history = {
        "time": time_now.isoformat(),
        "to": target_kd,
        "news": attacker_message,
    }
    kd_attack_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_attack_history, default=str),
    )

    
    galaxies_inverted, galaxy_info = uag._get_galaxies_inverted()
    attacker_galaxy = galaxies_inverted[kd_id]
    kds_to_reveal = galaxy_info[attacker_galaxy]

    revealed_until = (time_now + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"])).isoformat()
    payload = {
        "new_galaxies": {
            attacker_galaxy: revealed_until
        }
    }

    payload["new_revealed"] = {
        kd_id: {
            "stats": revealed_until,
        }
        for kd_id in kds_to_reveal
    }

    defender_galaxy = galaxies_inverted[target_kd]
    if attacker_galaxy != defender_galaxy:
        kds_revealed_to = galaxy_info[defender_galaxy]
        for kd_revealed_to in kds_revealed_to:
            reveal_galaxy_response = REQUESTS_SESSION.patch(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_revealed_to}/revealed',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                data=json.dumps(payload),
            )
            kd_revealed_to_info = uag._get_kd_info(kd_revealed_to)
            if revealed_until < kd_revealed_to_info["next_resolve"]["revealed"]:
                kd_revealed_to_next_resolve = kd_revealed_to_info["next_resolve"]
                kd_revealed_to_next_resolve["revealed"] = revealed_until
                kd_revealed_to_patch_payload = {
                    "next_resolve": kd_revealed_to_next_resolve
                }
                REQUESTS_SESSION.patch(
                    os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_revealed_to}',
                    headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                    data=json.dumps(kd_revealed_to_patch_payload),
                )
            if kd_revealed_to != target_kd:
                try:
                    ws = SOCK_HANDLERS[kd_revealed_to]
                    ws.send(json.dumps({
                        "message": f"Your galaxymate {target_kd_info['name']} was attacked by {kd_info_parse['name']}. Galaxy {attacker_galaxy} will be revealed for {uas.GAME_CONFIG['BASE_EPOCH_SECONDS'] * uas.GAME_CONFIG['BASE_REVEAL_DURATION_MULTIPLIER'] / 3600} hours",
                        "status": "info",
                        "category": "Galaxy",
                        "delay": 15000,
                        "update": ["galaxynews"],
                    }))
                except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
                    pass

    attacker_galaxy_payload = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "to": target_kd,
    }
    defender_galaxy_payload = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "to": target_kd,
    }
    if attack > defense:
        attacker_galaxy_payload["news"] = f"Your kingdom {kd_info_parse['name']} successfully attacked {target_kd_info['name']} and gained {spoils_values['stars']} stars."
        if sharer_spoils_values:
            attacker_galaxy_payload["news"] += f" Your kingdom {sharer_kd_info['name']} provided intel and gained {sharer_spoils_values['stars']} stars."

        defender_galaxy_payload["news"] = f"Your kingdom {target_kd_info['name']} was defeated by {kd_info_parse['name']} and lost {total_spoils['stars']} stars."
    else:
        attacker_galaxy_payload["news"] = f"Your kingdom {kd_info_parse['name']} failed an attack on {target_kd_info['name']}."

        defender_galaxy_payload["news"] = f"Your kingdom {target_kd_info['name']} successfully defended an attack by {kd_info_parse['name']}."

    REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{attacker_galaxy}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(attacker_galaxy_payload),
    )
    REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{defender_galaxy}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(defender_galaxy_payload),
    )
    attack_results = {
        "status": attack_status,
        "message": attacker_message,
    }
    return kd_info_parse, attack_results, 200

@app.route('/api/attack/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def attack(target_kd):
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    _, payload, status_code = _attack(req, kd_id, target_kd)
    return (flask.jsonify(payload), status_code)

@app.route('/api/calculateprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_attack_primitives():
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )

    state = uag._get_state()
    
    start_time = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_defense_per_star = uas.GAME_FUNCS["BASE_PRIMITIVES_DEFENSE_PER_STAR"](max(seconds_elapsed, 0))
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
    )
    if not valid_attack_request:
        return (flask.jsonify({"message": attack_request_message}), 400)

    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in uas.UNITS and value != "")
    }
    attacker_fuelless = kd_info_parse["fuel"] <= 0
    attack = uag._calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless,
        lumina=kd_info_parse["race"] == "Lumina",
    )
    stars = math.floor(
        attack
        / primitives_defense_per_star
        * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        )
    )
    money = stars * uas.GAME_CONFIG["BASE_PRIMITIVES_MONEY_PER_STAR"]
    fuel = stars * uas.GAME_CONFIG["BASE_PRIMITIVES_FUEL_PER_STAR"]
    pop = stars * uas.GAME_CONFIG["BASE_PRIMITIVES_POPULATION_PER_STAR"]
    attacker_losses = _calc_losses(
        attacker_units,
        uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        xo=kd_info_parse["race"] == "Xo",
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=25,
    )
    generals_strftime = ', '.join([
        str(general_return_time - time_now).split(".")[0]
        for general_return_time in generals_return_times
    ])
    
    message = f"Your general(s) will return in: {generals_strftime}. \n"
    spoils_values = {
        "stars": stars,
        "money": money,
        "fuel": fuel,
        "population": pop,
    }
    if spoils_values:
        message += 'You will gain '
        message += ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
        message += '. \n'

    payload = {
        "attacker_offense": attack,
        "attacker_losses": attacker_losses,
        "attacker_unit_losses_rate": uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        "generals_return_times": generals_return_times,
        "message": message
    }

    return (flask.jsonify(payload), 200)

def _attack_primitives(req, kd_id):
    attacker_raw_values = req["attackerValues"]
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }
    state = uag._get_state()
    
    start_time = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_defense_per_star = uas.GAME_FUNCS["BASE_PRIMITIVES_DEFENSE_PER_STAR"](max(seconds_elapsed, 0))

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
    )
    if not valid_attack_request:
        return kd_info_parse, {"message": attack_request_message}, 400

    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in uas.UNITS and value != "")
    }

    attacker_fuelless = kd_info_parse["fuel"] <= 0
    attack = uag._calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values["generals"]),
        fuelless=attacker_fuelless,
        lumina=kd_info_parse["race"] == "Lumina",
    )
    attacker_losses = _calc_losses(
        attacker_units,
        uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"],
        xo=kd_info_parse["race"] == "Xo",
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values["generals"]),
        uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
        time_now,
        current_bonuses["general_bonus"],
        is_warlike=is_warlike,
        coordinate_distance=25,
    )
    new_home_attacker_units = {
        key_unit: value_unit - attacker_units.get(key_unit, 0)
        for key_unit, value_unit in kd_info_parse["units"].items()
    }
    remaining_attacker_units = {
        key_unit: value_unit - attacker_losses.get(key_unit, 0)
        for key_unit, value_unit in attacker_units.items()
    }
    generals = [
        {
            "return_time": general_time.isoformat(),
            **{
                key_unit: math.floor(remaining_unit / len(generals_return_times))
                for key_unit, remaining_unit in remaining_attacker_units.items()
            }
        }
        for general_time in generals_return_times
    ]
    next_return_time = min([general["return_time"] for general in generals])

    stars = math.floor(
        attack
        / primitives_defense_per_star
        * (
            1
            + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        )
    )
    money = stars * uas.GAME_CONFIG["BASE_PRIMITIVES_MONEY_PER_STAR"]
    fuel = stars * uas.GAME_CONFIG["BASE_PRIMITIVES_FUEL_PER_STAR"]
    pop = stars * uas.GAME_CONFIG["BASE_PRIMITIVES_POPULATION_PER_STAR"]
    spoils_values = {
        "stars": stars,
        "money": money,
        "fuel": fuel,
        "population": pop,
    }

    attack_status = "success"
    attacker_message = (
        "You have attacked primitives and gained "
        + ', '.join([f"{value} {key}" for key, value in spoils_values.items()])
        + ". You have lost "
        + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
    )

    kd_info_parse["units"] = new_home_attacker_units
    kd_info_parse["generals_out"] = kd_info_parse["generals_out"] + generals
    kd_info_parse["generals_available"] = kd_info_parse["generals_available"] - int(attacker_raw_values["generals"])
    kd_info_parse["next_resolve"]["generals"] = min(kd_info_parse["next_resolve"]["generals"], next_return_time)

    for key_spoil, value_spoil in spoils_values.items():
        if key_spoil != "money":
            kd_info_parse[key_spoil] += value_spoil
        else:
            if kd_info_parse["auto_spending_enabled"]:
                pct_allocated = sum(kd_info_parse["auto_spending"].values())
                for key_spending, pct_spending in kd_info_parse["auto_spending"].items():
                    kd_info_parse["funding"][key_spending] += pct_spending * value_spoil
                kd_info_parse["money"] += value_spoil * (1 - pct_allocated)
            else:
                kd_info_parse["money"] += value_spoil

    for key_project, project_dict in uas.PROJECTS.items():
        project_max_func = uas.PROJECTS_FUNCS[key_project]
        kd_info_parse["projects_max_points"][key_project] = project_max_func(kd_info_parse["stars"])

    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_info_parse, default=str),
    )
    kd_attack_history = {
        "time": time_now.isoformat(),
        "to": "",
        "news": attacker_message,
    }
    kd_attack_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_attack_history, default=str),
    )

    attack_results = {
        "status": attack_status,
        "message": attacker_message,
    }
    return kd_info_parse, attack_results, 200

@app.route('/api/attackprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def attack_primitives():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    _, attack_results, status_code = _attack_primitives(req, kd_id)
    return (flask.jsonify(attack_results), status_code)

def _validate_spy_request(
    drones,
    kd_info,
    shielded,
):
    if drones > kd_info["drones"]:
        return False, "You do not have that many drones"
    if drones < 0:
        return False, "You can not send negative drones"
    if shielded:
        if kd_info["fuel"] < drones:
            return False, "You do not have enough fuel"
    if kd_info["spy_attempts"] == 0:
        return False, "You do not have any more spy attempts"
    
    return True, ""

def _validate_auto_attack_settings(req_settings):
    """Confirm that spending request is valid"""

    values = req_settings.values()
    if any((value < 0 for value in values)):
        return False, "Unit percents must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Unit percents must be less than 100%"
    
    return True, ""


@app.route('/api/attackprimitives/auto', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def auto_attack_primitives():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("enabled", None) != None:
        if kd_info_parse["auto_attack_settings"].get("pure", 0) == 0 and kd_info_parse["auto_attack_settings"].get("flex", 0) == 0:
            return (flask.jsonify({"message": "Could not enable auto attack. You must first specify the percent of units to send"}), 400)
        enabled = req["enabled"]
        payload = {'auto_attack_enabled': enabled}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if enabled:
            message = "Enabled auto attacking primitives"
        else:
            message = "Disabled auto attacking primitives"
        return (flask.jsonify({"message": message, "status": "success"}), 200)
    
    req_settings = {
        "pure": float(
            req.get("pure") or (kd_info_parse["auto_attack_settings"].get("pure", 0) * 100)
        ) / 100,
        "flex": float(
            req.get("flex") or (kd_info_parse["auto_attack_settings"].get("flex", 0) * 100)
        ) / 100,
    }

    current_settings = kd_info_parse['auto_attack_settings']
    new_settings = {
        **current_settings,
        **req_settings,
    }
    valid_settings, message = _validate_auto_attack_settings(new_settings)
    if not valid_settings:
        return (flask.jsonify({"message": message}), 400)

    payload = {'auto_attack_settings': new_settings}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated auto attack settings", "status": "success"}), 200)


def _calculate_spy_probability(
    drones_to_send,
    target_drones,
    target_stars,
    target_shields,
    aggro_vult=False,
):
    drones_defense = target_drones * uas.GAME_CONFIG["BASE_DRONES_DRONE_DEFENSE_MULTIPLIER"]
    stars_defense = target_stars * uas.GAME_CONFIG["BASE_STARS_DRONE_DEFENSE_MULTIPLIER"]
    total_defense = max(drones_defense + stars_defense, 1)

    base_probability = min(max(drones_to_send / total_defense, uas.GAME_CONFIG["BASE_SPY_MIN_SUCCESS_CHANCE"]), 1.0)
    if aggro_vult:
        shielded_probability = base_probability
    else:
        shielded_probability = base_probability * (1 - target_shields)

    return shielded_probability, drones_defense, stars_defense

def _calculate_spy_losses(
    drones_to_send,
    shielded,
):
    shielded_reduction = 1 - (int(shielded) * uas.GAME_CONFIG["BASE_DRONES_SHIELDING_LOSS_REDUCTION"])
    success_loss = math.floor(drones_to_send * uas.GAME_CONFIG["BASE_DRONES_SUCCESS_LOSS_RATE"] * shielded_reduction)
    failure_loss = math.floor(drones_to_send * uas.GAME_CONFIG["BASE_DRONES_FAILURE_LOSS_RATE"] * shielded_reduction)
    return success_loss, failure_loss
    
        
@app.route('/api/calculatespy/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_spy(target_kd):
    req = flask.request.get_json(force=True)
    drones = int(req["drones"])
    shielded = req["shielded"]
    defender_raw_values = req["defenderValues"]
    operation = req["operation"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    if not operation:
        return (flask.jsonify({"message": "You must select an operation"}), 400)
    
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    
    revealed = uag._get_revealed(kd_id)
    max_target_kd_info = uag._get_max_kd_info(target_kd, kd_id, revealed)
    
    if "drones" in max_target_kd_info:
        defender_drones = max_target_kd_info["drones"]
    else:
        defender_drones = int(defender_raw_values["drones"] or 0)
    
    if "stars" in max_target_kd_info:
        defender_stars = max_target_kd_info["stars"]
    else:
        defender_stars = int(defender_raw_values["stars"] or 0)

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["spy"]
    else:
        defender_shields = float(defender_raw_values['shields'] or 0) / 100
    
    spy_probability, drones_defense, stars_defense = _calculate_spy_probability(
        drones,
        defender_drones,
        defender_stars,
        defender_shields,
        aggro_vult=(kd_info_parse["race"] == "Vult") and (operation in uas.AGGRO_OPERATIONS),
    )
    success_losses, failure_losses = _calculate_spy_losses(drones, shielded)

    message = f"The operation has a {spy_probability:.2%} chance of success. \n\nIf successful, {success_losses} drones will be lost. \nIf unsuccessful, {failure_losses} drones will be lost.\n"

    if operation in uas.REVEAL_OPERATIONS:
        revealed_stat = operation.replace('spy', '')
        reveal_duration_seconds = uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        reveal_duration_hours = reveal_duration_seconds / 3600
        message += f"If successful, the target's {revealed_stat} will be revealed for {reveal_duration_hours} hours.\n"
    if operation == "siphonfunds":
        siphon_damage = math.floor(drones * uas.GAME_CONFIG["BASE_DRONES_SIPHON_PER_DRONE"])
        siphon_seconds = uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        siphon_hours = siphon_seconds / 3600
        message += f"If successful, you will siphon up to {siphon_damage} money over the next {siphon_hours} hours."
    if operation == "bombhomes":
        if "structures" in max_target_kd_info.keys():
            homes_damage = min(math.floor(max_target_kd_info["structures"]["homes"] * uas.GAME_CONFIG["BASE_DRONES_MAX_HOME_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_HOME_DAMAGE"]))
            message += f"If successful, you will destroy {homes_damage} homes."
        else:
            homes_damage = math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_HOME_DAMAGE"])
            message += f"If successful, you will destroy up to {homes_damage} homes."
    if operation == "sabotagefuelplants":
        if "structures" in max_target_kd_info.keys():
            fuel_plant_damage = min(math.floor(max_target_kd_info["structures"]["fuel_plants"] * uas.GAME_CONFIG["BASE_DRONES_MAX_FUEL_PLANT_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_FUEL_PLANT_DAMAGE"]))
            message += f"If successful, you will destroy {fuel_plant_damage} fuel plants."
        else:
            fuel_plant_damage = math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_FUEL_PLANT_DAMAGE"])
            message += f"If successful, you will destroy up to {fuel_plant_damage} fuel plants."
    if operation == "kidnappopulation":
        if "population" in max_target_kd_info.keys():
            kidnap_damage = min(math.floor(max_target_kd_info["population"] * uas.GAME_CONFIG["BASE_DRONES_MAX_KIDNAP_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_KIDNAP"]))
            kidnap_return = math.floor(kidnap_damage * uas.GAME_CONFIG["BASE_KIDNAP_RETURN_RATE"])
            message += f"If successful, you will kidnap {kidnap_damage} civilians. {kidnap_return} civilians will join your population."
        else:
            kidnap_damage = math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_KIDNAP"])
            kidnap_return = math.floor(kidnap_damage * uas.GAME_CONFIG["BASE_KIDNAP_RETURN_RATE"])
            message += f"If successful, you will kidnap up to {kidnap_damage} civilians. Up to {kidnap_return} civilians will join your population."
    if operation == "suicidedrones":
        fuel_damage = drones * 5
        if "fuel" in max_target_kd_info.keys():
            fuel_damage = min(fuel_damage, max_target_kd_info["fuel"])
            message = f"You will destroy {fuel_damage} fuel."
        else:
            message = f"You will destroy up to {fuel_damage} fuel."

    payload = {
        "message": message,
        "stars_defense": stars_defense,
        "drones_defense": drones_defense,
        "total_defense": stars_defense + drones_defense,
    }
    return (flask.jsonify(payload), 200)
    
def _spy(req, kd_id, target_kd):
    
    drones = int(req["drones"])
    shielded = req["shielded"]
    operation = req["operation"]

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return kd_info_parse, {"message": message}, 400, False
    
    revealed = uag._get_revealed(kd_id)["revealed"]
    max_target_kd_info = uag._get_kd_info(target_kd)
    if max_target_kd_info["status"].lower() == "dead":
        return (flask.jsonify({"message": "You can't attack this kingdom because they are dead!"}), 400)
    
    defender_drones = max_target_kd_info["drones"]
    defender_stars = max_target_kd_info["stars"]
    defender_shields = max_target_kd_info["shields"]["spy"]
    
    spy_probability, drones_defense, stars_defense = _calculate_spy_probability(
        drones,
        defender_drones,
        defender_stars,
        defender_shields,
        aggro_vult=(kd_info_parse["race"] == "Vult") and (operation in uas.AGGRO_OPERATIONS),
    )
    
    success_losses, failure_losses = _calculate_spy_losses(drones, shielded)

    roll = random.uniform(0, 1)
    spy_radar_roll = random.uniform(0, 1)
    success = roll < spy_probability
    if (kd_info_parse["race"] == "Vult") and operation in uas.AGGRO_OPERATIONS:
        spy_radar_success = False
    else:
        spy_radar_success = spy_radar_roll < max_target_kd_info["shields"]["spy_radar"]

    time_now = datetime.datetime.now(datetime.timezone.utc)
    revealed_until = None
    siphon_damage = None
    siphon_until = None
    homes_damage = None
    fuel_plant_damage = None
    kidnap_damage = None
    kidnap_return = None
    fuel_damage = None
    revealed = False

    if operation == "suicidedrones":
        burnable_fuel = max_target_kd_info["fuel"] - uas.GAME_FUNCS["BASE_NEGATIVE_FUEL_CAP"](max_target_kd_info["stars"])
        fuel_damage = min(burnable_fuel, drones * uas.GAME_CONFIG["BASE_DRONES_SUICIDE_FUEL_DAMAGE"])
        losses = drones
        status = "success"
        message = f"You have destroyed {fuel_damage} fuel. You have lost {losses} drones"
        target_message = f"Enemy drones have destroyed {fuel_damage} fuel"
    else:
        if success:
            status = "success"
            if operation in uas.REVEAL_OPERATIONS:
                revealed_stat = operation.replace('spy', '')
                reveal_duration_seconds = uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
                revealed_until = time_now + datetime.timedelta(seconds=reveal_duration_seconds)
                reveal_duration_hours = reveal_duration_seconds / 3600

                revealed_payload = {
                    "new_revealed": {
                        target_kd: {
                            revealed_stat: revealed_until.isoformat()
                        }
                    }
                }
                reveal_response = REQUESTS_SESSION.patch(
                    os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
                    headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                    data=json.dumps(revealed_payload),
                )
                message = f"Success! The target will be revealed for {reveal_duration_hours} hours. You have lost {success_losses} drones."
                target_message = "You were infiltrated by drones on a spy operation."
            
            if operation == "siphonfunds":
                siphon_damage = drones * uas.GAME_CONFIG["BASE_DRONES_SIPHON_PER_DRONE"]
                siphon_seconds = uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
                siphon_hours = siphon_seconds / 3600
                siphon_until = time_now + datetime.timedelta(seconds=siphon_seconds)
                message = f"Success! Your drones will siphon up to {siphon_damage} money over the next {siphon_hours} hours. You have lost {success_losses} drones."
                target_message = f"Enemy drones have begun siphoning up to {siphon_damage} money over the next {siphon_hours} hours."
            if operation == "bombhomes":
                homes_damage = min(math.floor(max_target_kd_info["structures"]["homes"] * uas.GAME_CONFIG["BASE_DRONES_MAX_HOME_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_HOME_DAMAGE"]))
                message = f"Success! You have destroyed {homes_damage} homes. You have lost {success_losses} drones."
                target_message = f"Enemy drones have destroyed {homes_damage} homes."
            if operation == "sabotagefuelplants":
                fuel_plant_damage = min(math.floor(max_target_kd_info["structures"]["fuel_plants"] * uas.GAME_CONFIG["BASE_DRONES_MAX_FUEL_PLANT_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_FUEL_PLANT_DAMAGE"]))
                message = f"Success! You have destroyed {fuel_plant_damage} fuel plants. You have lost {success_losses} drones."
                target_message = f"Enemy drones have destroyed {fuel_plant_damage} fuel plants."
            if operation == "kidnappopulation":
                kidnap_damage = min(math.floor(max_target_kd_info["population"] * uas.GAME_CONFIG["BASE_DRONES_MAX_KIDNAP_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_KIDNAP"]))
                kidnap_return = math.floor(kidnap_damage * uas.GAME_CONFIG["BASE_KIDNAP_RETURN_RATE"])
                message = f"Success! You have kidnapped {kidnap_damage} civilians. {kidnap_return} civilians have joined your population. You have lost {success_losses} drones."
                target_message = f"Enemy drones have kidnapped {kidnap_damage} civilians."

            losses = success_losses
        else:
            status = "failure"
            message = f"Failure! You have lost {failure_losses} drones."
            if operation in uas.REVEAL_OPERATIONS:
                target_message = f"{kd_info_parse['name']} failed a spy operation on you."
            else:
                target_message = f"{kd_info_parse['name']} failed an aggressive spy operation on you."
            losses = failure_losses
            if operation in uas.AGGRO_OPERATIONS:
                revealed = True

    if spy_radar_success and not revealed:
        revealed = True
        target_message += f" Your spy radar has revealed the operation came from {kd_info_parse['name']}."

    kd_patch_payload = {
        "drones": kd_info_parse["drones"] - losses,
    }
    is_lumina_intel = (kd_info_parse["race"] == "Lumina") and operation in uas.REVEAL_OPERATIONS
    if not is_lumina_intel:
        kd_patch_payload["spy_attempts"] = kd_info_parse["spy_attempts"] - 1
    if kidnap_return:
        kd_patch_payload["population"] = kd_info_parse["population"] + kidnap_return
    if shielded:
        kd_patch_payload["fuel"] = kd_info_parse["fuel"] - drones
    if revealed_until:
        next_resolve = kd_info_parse["next_resolve"]
        next_resolve["revealed"] = min(next_resolve["revealed"], revealed_until.isoformat())
        kd_patch_payload["next_resolve"] = next_resolve
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload, default=str),
    )

    target_patch_payload = {}
    if siphon_damage:
        siphons_out_payload = {
            "new_siphons": {
                "from": kd_id,
                "time": siphon_until,
                "siphon": siphon_damage
            }
        }
        siphons_out_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/siphonsout',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(siphons_out_payload, default=str),
        )
    if homes_damage:
        target_patch_payload["structures"] = {
            **max_target_kd_info["structures"],
            "homes": max_target_kd_info["structures"]["homes"] - homes_damage
        }
    if fuel_plant_damage:
        target_patch_payload["structures"] = {
            **max_target_kd_info["structures"],
            "fuel_plants": max_target_kd_info["structures"]["fuel_plants"] - fuel_plant_damage
        }
    if kidnap_damage:
        target_patch_payload["population"] = max_target_kd_info["population"] - kidnap_damage
    if fuel_damage:
        target_patch_payload["fuel"] = max_target_kd_info["fuel"] - fuel_damage


    if revealed:
        revealed_until = (time_now + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"])).isoformat()
        if revealed_until < max_target_kd_info["next_resolve"]["revealed"]:
            next_resolve = max_target_kd_info["next_resolve"]
            next_resolve["revealed"] = min(next_resolve["revealed"], revealed_until)
            target_patch_payload["next_resolve"] = next_resolve

        revealed_payload = {
            "new_revealed": {
                kd_id: {
                    "stats": revealed_until,
                    "drones": revealed_until,
                }
            }
        }
        reveal_galaxy_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/revealed',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(revealed_payload),
        )
        target_message += f" Their kingdom 'stats' and 'drones' will be revealed for {uas.GAME_CONFIG['BASE_EPOCH_SECONDS'] * uas.GAME_CONFIG['BASE_REVEAL_DURATION_MULTIPLIER'] / 3600} hours"

    if target_patch_payload:
        target_kd_patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(target_patch_payload, default=str),
        )
    history_payload = {
        "time": time_now.isoformat(),
        "to": target_kd,
        "operation": uas.PRETTY_NAMES.get(operation, operation),
        "news": message,
    }
    kd_spy_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(history_payload, default=str),
    )

    target_news_payload = {
        "time": time_now.isoformat(),
        "from": "" if success else kd_id,
        "news": target_message,
    }
    target_news_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_news_payload),
    )
    try:
        ws = SOCK_HANDLERS[target_kd]
        ws.send(json.dumps({
            "message": target_message,
            "status": "warning",
            "category": "Spy",
            "delay": 15000,
            "update": ["news"],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass

    new_kd_info = {
        **kd_info_parse,
        **kd_patch_payload,
    }
    payload = {
        "status": status,
        "message": message,
    }
    return new_kd_info, payload, 200, success
        
@app.route('/api/spy/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def spy(target_kd):
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)
    if not req["operation"]:
        return (flask.jsonify({"message": "You must select an operation"}), 400)
    
    _, payload, status_code, success = _spy(req, kd_id, target_kd)

    return (flask.jsonify(payload), status_code)

def _rob_primitives(req, kd_id):
    drones = int(req["drones"])
    shielded = req["shielded"]
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    state = uag._get_state()
    
    start_time = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_rob_per_drone = uas.GAME_FUNCS["BASE_PRIMITIVES_ROB_PER_DRONE"](max(seconds_elapsed, 0))

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return kd_info_parse, {"message": message}, 400

    success_losses, _ = _calculate_spy_losses(drones, shielded)

    status = "success"
    rob = math.floor(drones * primitives_rob_per_drone)
    message = f"You have robbed {rob} money from primitives. You have lost {success_losses} drones."
    

    losses = success_losses

    if kd_info_parse["auto_spending_enabled"]:
        pct_allocated = sum(kd_info_parse["auto_spending"].values())
        new_funding = kd_info_parse["funding"]
        for key_spending, pct_spending in kd_info_parse["auto_spending"].items():
            new_funding[key_spending] += pct_spending * rob
        new_money = rob * (1 - pct_allocated)
    else:
        new_funding = kd_info_parse["funding"]
        new_money = rob
    kd_patch_payload = {
        "drones": kd_info_parse["drones"] - losses,
        "spy_attempts": kd_info_parse["spy_attempts"] - 1,
        "money": kd_info_parse["money"] + new_money,
        "funding": new_funding,
    }
    if shielded:
        kd_patch_payload["fuel"] = kd_info_parse["fuel"] - drones
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload, default=str),
    )

    time_now = datetime.datetime.now(datetime.timezone.utc)
    history_payload = {
        "time": time_now.isoformat(),
        "to": "",
        "operation": uas.PRETTY_NAMES.get("robprimitives", "robprimitives"),
        "news": message,
    }
    kd_spy_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(history_payload, default=str),
    )

    new_kd_info = {
        **kd_info_parse,
        **kd_patch_payload,
    }
    payload = {
        "status": status,
        "message": message,
    }
    return new_kd_info, payload, 200

@app.route('/api/robprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def rob_primitives():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    _, payload, status_code = _rob_primitives(req, kd_id)
    return (flask.jsonify(payload), status_code)

def _validate_auto_rob_settings(req_settings):
    """Confirm that spending request is valid"""

    if req_settings["drones"] < 0:
        return False, "Drones percent must be greater than 0"
    if req_settings["drones"] > 1:
        return False, "Drones percent must be less than 100%"
    if req_settings["keep"] < 0:
        return False, "Keep spy attempts must be greater than 0"
    if req_settings["keep"] >= 10:
        return False, "Keep spy attempts must be less than 10"
    
    return True, ""


@app.route('/api/robprimitives/auto', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def auto_rob_primitives():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    if req.get("enabled", None) != None:
        if kd_info_parse["auto_rob_settings"].get("drones", 0) == 0:
            return (flask.jsonify({"message": "Could not enable auto robs. You must first specify the percent of drones to send"}), 400)
        enabled = req["enabled"]
        payload = {'auto_rob_enabled': enabled}

        patch_response = REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(payload),
        )
        if enabled:
            message = "Enabled auto robbing primitives"
        else:
            message = "Disabled auto robbing primitives"
        return (flask.jsonify({"message": message, "status": "success"}), 200)
    
    req_settings = {
        "drones": float(
            req.get("drones") or (kd_info_parse["auto_rob_settings"].get("drones", 0) * 100)
        ) / 100,
        "keep": int(
            req.get("keep") or kd_info_parse["auto_rob_settings"].get("keep", 0)
        ),
        "shielded": bool(
            req.get("shielded", kd_info_parse["auto_rob_settings"].get("shielded", False))
        ),
    }

    current_settings = kd_info_parse['auto_rob_settings']
    new_settings = {
        **current_settings,
        **req_settings,
    }
    valid_settings, message = _validate_auto_rob_settings(new_settings)
    if not valid_settings:
        return (flask.jsonify({"message": message}), 400)

    payload = {'auto_rob_settings': new_settings}
    patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(payload),
    )
    return (flask.jsonify({"message": "Updated auto attack settings", "status": "success"}), 200)

def _validate_schedule_attack(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if options["generals"] < 1 or options["generals"] > 4:
        return False, "Generals must be between 1 and 4"
    if options["pure_offense"] < 0 or options["pure_offense"] > 1:
        return False, "Pure offense must be between 0% and 100%"
    if options["flex_offense"] < 0 or options["flex_offense"] > 1:
        return False, "Pure offense must be between 0% and 100%"
    if options["target"] == kd_id:
        return False, "You can not schedule an attack against yourself"
    
    return True, ""

def _schedule_attack(
    id,
    time,
    options,
    kd_info,
):
    options["generals"] = int(options["generals"] or 0)
    options["pure_offense"] = float(options["pure_offense"] or 0) / 100
    options["flex_offense"] = float(options["flex_offense"] or 0) / 100
    valid_schedule, message = _validate_schedule_attack(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message

    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "attack",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_attackprimitives(
    options,
):
    if options["generals"] < 1 or options["generals"] > 4:
        return False, "Generals must be between 1 and 4"
    if options["pure_offense"] < 0 or options["pure_offense"] > 1:
        return False, "Pure offense must be between 0% and 100%"
    if options["flex_offense"] < 0 or options["flex_offense"] > 1:
        return False, "Flex offense must be between 0% and 100%"
    
    return True, ""

def _schedule_attackprimitives(
    id,
    time,
    options,
    kd_info,
):
    options["generals"] = int(options["generals"] or 0)
    options["pure_offense"] = float(options["pure_offense"] or 0) / 100
    options["flex_offense"] = float(options["flex_offense"] or 0) / 100
    valid_schedule, message = _validate_schedule_attackprimitives(options)
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "attackprimitives",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_intelspy(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if options["operation"] is None:
        return False, "Operation must be selected"
    if options["max_tries"] < 1 or options["max_tries"] > 10:
        return False, "Max tries must be between 1 and 10"
    if options["drones_pct"] < 0 or options["drones_pct"] > 1:
        return False, "Drones percent must be between 0% and 100%"
    if options["target"] == kd_id:
        return False, "You can not schedule a spy attempt against yourself"
    if options["operation"] not in uas.REVEAL_OPERATIONS:
        return False, "Intel schedules must be intel operations"
    
    return True, ""

def _schedule_intelspy(
    id,
    time,
    options,
    kd_info,
):
    options["max_tries"] = int(options["max_tries"] or 0)
    options["drones_pct"] = float(options["drones_pct"] or 0) / 100
    valid_schedule, message = _validate_schedule_intelspy(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "intelspy",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_aggressivespy(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if options["operation"] is None:
        return False, "Operation must be selected"
    if options["attempts"] < 1 or options["attempts"] > 10:
        return False, "Attempts must be between 1 and 10"
    if options["drones_pct"] <= 0 or options["drones_pct"] > 1:
        return False, "Drones percent must be between 0% and 100%"
    if options["target"] == kd_id:
        return False, "You can not schedule a spy attempt against yourself"
    if options["operation"] not in uas.AGGRO_OPERATIONS:
        return False, "Aggressive schedules must be aggressive operations"
    
    return True, ""

def _schedule_aggressivespy(
    id,
    time,
    options,
    kd_info,
):
    options["attempts"] = int(options["attempts"] or 0)
    options["drones_pct"] = float(options["drones_pct"] or 0) / 100
    valid_schedule, message = _validate_schedule_aggressivespy(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "aggressivespy",
        "options": options,
    }
    return True, new_schedule, ""

def _validate_schedule_missiles(
    options,
    kd_id,
):
    if options["target"] is None:
        return False, "Target must be selected"
    if (options["planet_busters"] + options["star_busters"] + options["galaxy_busters"]) <= 0:
        return False, "Missiles amount must be greater than 0"
    if options["planet_busters"] < 0:
        return False, "Missiles amount must be greater than 0"
    if options["star_busters"] < 0:
        return False, "Missiles amount must be greater than 0"
    if options["galaxy_busters"] < 0:
        return False, "Missiles amount must be greater than 0"
    if options["target"] == kd_id:
        return False, "You can not schedule missiles against yourself"
    
    return True, ""

def _schedule_missiles(
    id,
    time,
    options,
    kd_info,
):
    options["planet_busters"] = int(options["planet_busters"] or 0)
    options["star_busters"] = int(options["star_busters"] or 0)
    options["galaxy_busters"] = int(options["galaxy_busters"] or 0)
    valid_schedule, message = _validate_schedule_missiles(options, kd_info["kdId"])
    if not valid_schedule:
        return False, {}, message
    
    new_schedule = {
        "id": id,
        "time": time,
        "type": "missiles",
        "options": options,
    }
    return True, new_schedule, ""
    

@app.route('/api/schedule', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def add_schedule():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    kd_info = uag._get_kd_info(kd_id)

    schedule_type = req.get("type")
    schedule_time = datetime.datetime.fromisoformat(req["time"].replace('Z', '+00:00')).isoformat()
    schedule_options = req.get("options", {})
    schedule_id = uuid.uuid4()
    
    state = uag._get_state()

    if schedule_time < state["state"]["game_start"] or schedule_time > state["state"]["game_end"]:
        return flask.jsonify({"message": "Scheduled time occurs outside of game duration"}), 400
    
    if len(kd_info["schedule"]) >= 10:
        return flask.jsonify({"message": "You can not schedule more than 10 actions"}), 400

    handler_funcs = {
        "attack": _schedule_attack,
        "attackprimitives": _schedule_attackprimitives,
        "intelspy": _schedule_intelspy,
        "aggressivespy": _schedule_aggressivespy,
        "missiles": _schedule_missiles,
    }
    scheduled, new_schedule, message = handler_funcs[schedule_type](
        id=schedule_id,
        time=schedule_time,
        options=schedule_options,
        kd_info=kd_info,
    )
    if not scheduled:
        return flask.jsonify({"message": message}), 400
    
    schedule_payload = kd_info["schedule"]
    schedule_payload.append(new_schedule)
    schedule_payload_sorted = sorted(schedule_payload, key=lambda item: item["time"])

    kd_payload = {
        "schedule": schedule_payload_sorted,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload, default=str),
    )

    return (flask.jsonify({"message": "Successfully scheduled", "status": "success"}), 200)

@app.route('/api/schedule/cancel', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def cancel_schedule():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    kd_info = uag._get_kd_info(kd_id)

    schedule_id = req.get("id")

    new_schedule = [
        item
        for item in kd_info["schedule"]
        if item["id"] != schedule_id
    ]
    kd_payload = {
        "schedule": new_schedule,
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_payload, default=str),
    )
    return (flask.jsonify({"message": "Cancelled scheduled action", "status": "success"}), 200)


def _validate_missiles_request(
    attacker_missiles,
    kd_info,
):
    if any((
        value_missile > kd_info["missiles"][key_missile]
        for key_missile, value_missile in attacker_missiles.items()
    )):
        return False, "You do not have that many missiles"
    if any((
        value_missile < 0
        for value_missile in attacker_missiles.values()
    )):
        return False, "You can not send negative missiles"
    
    return True, ""

def _calculate_missiles_damage(
    attacker_missiles,
    defender_shields,
    fuzi=False,
):
    if fuzi:
        adjusted_shields = min(defender_shields, 0.5)
    else:
        adjusted_shields = defender_shields
    damage_categories = {"stars_damage", "fuel_damage", "pop_damage"}
    damage = {}
    for damage_category in damage_categories:
        damage[damage_category] = sum([
            math.floor(value_missiles * uas.MISSILES[key_missile].get(damage_category) * (1 - adjusted_shields))
            for key_missile, value_missiles in attacker_missiles.items()
        ])
    return damage
    

@app.route('/api/calculatemissiles/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_missiles(target_kd):
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    attacker_missiles = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if value != ""
    }

    valid_request, message = _validate_missiles_request(
        attacker_missiles,
        kd_info_parse,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    
    revealed = uag._get_revealed(kd_id)
    max_target_kd_info = uag._get_max_kd_info(target_kd, kd_id, revealed)

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["missiles"]
    else:
        defender_shields = float(req['defenderShields'] or 0) / 100
    
    missile_damage = _calculate_missiles_damage(
        attacker_missiles,
        defender_shields,
        fuzi=kd_info_parse["race"] == "Fuzi",
    )

    message = f"The missiles will destroy " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

    payload = {
        "message": message,
    }
    return (flask.jsonify(payload), 200)         
    
def _launch_missiles(req, kd_id, target_kd):

    attacker_raw_values = req["attackerValues"]
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    attacker_missiles = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if value != ""
    }

    valid_request, message = _validate_missiles_request(
        attacker_missiles,
        kd_info_parse,
    )
    if not valid_request:
        return kd_info_parse, {"message": message}, 400
    
    max_target_kd_info = uag._get_kd_info(target_kd)
    defender_shields = max_target_kd_info["shields"]["missiles"]
    if max_target_kd_info["status"].lower() == "dead":
        return (flask.jsonify({"message": "You can't attack this kingdom because they are dead!"}), 400)
    
    missile_damage = _calculate_missiles_damage(
        attacker_missiles,
        defender_shields,
        fuzi=kd_info_parse["race"] == "Fuzi",
    )

    message = f"Your missiles destroyed " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])
    defender_message = f"Missiles from {kd_info_parse['name']} have destroyed " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

    kd_patch_payload = {
        "missiles": {
            k: v - attacker_missiles.get(k, 0)
            for k, v in kd_info_parse["missiles"].items()
        }
    }
    kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(kd_patch_payload, default=str),
    )

    target_stars = max_target_kd_info["stars"] - missile_damage["stars_damage"]
    target_pop = max_target_kd_info["population"] - missile_damage["pop_damage"]
    defender_patch_payload = {
        "stars": target_stars,
        "population": target_pop,
        "fuel": max_target_kd_info["fuel"] - missile_damage["fuel_damage"],
    }
    if target_stars <= 0 or target_pop <= 0:
        defender_patch_payload["status"] = "Dead"
        _mark_kingdom_death(target_kd)
    defender_patch_payload["stars"] = max(defender_patch_payload["stars"], 0)
    defender_patch_payload["projects_max_points"] = {}
    for key_project, project_dict in uas.PROJECTS.items():
        project_max_func = uas.PROJECTS_FUNCS[key_project]
        defender_patch_payload["projects_max_points"][key_project] = project_max_func(max_target_kd_info["stars"])
    defender_kd_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(defender_patch_payload, default=str),
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    target_news_payload = {
        "time": time_now.isoformat(),
        "from": kd_id,
        "news": defender_message,
    }
    target_news_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(target_news_payload),
    )
    history_payload = {
        "time": time_now.isoformat(),
        "to": target_kd,
        "news": message,
    }
    kd_missile_history_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missilehistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(history_payload, default=str),
    )
    try:
        ws = SOCK_HANDLERS[target_kd]
        ws.send(json.dumps({
            "message": defender_message,
            "status": "warning",
            "category": "Missiles",
            "delay": 30000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass

    new_kd_info = {
        **kd_info_parse,
        **kd_patch_payload,
    }
    payload = {
        "message": message,
    }
    return new_kd_info, payload, 200

@app.route('/api/launchmissiles/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def launch_missiles(target_kd):
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)
    
    _, payload, status_code = _launch_missiles(req, kd_id, target_kd)
    return (flask.jsonify(payload), status_code)
@app.route('/api/shared', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def accept_shared():
    req = flask.request.get_json(force=True)
    accepted_shared_from = str(req["shared"])
    accepted_kd, shared_from_kd = accepted_shared_from.split('_')
    

    kd_id = flask_praetorian.current_user().kd_id
    kingdoms = uag._get_kingdoms()
    
    shared_info = uag._get_shared(kd_id)

    new_shared = shared_info["shared_requests"].pop(accepted_shared_from)
    shared_info["shared"][accepted_kd] = new_shared

    shared_info_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(shared_info),
    )

    revealed_payload = {
        "new_revealed" : {
            accepted_kd: {
                new_shared["shared_stat"]: new_shared["time"],
            }
        }
    }
    revealed_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(revealed_payload),
    )
    
    try:
        ws = SOCK_HANDLERS[shared_from_kd]
        ws.send(json.dumps({
            "message": f"{kingdoms[kd_id]} accepted intel {shared_info['shared'][accepted_kd]['shared_stat']} for target {kingdoms[accepted_kd]}",
            "status": "info",
            "category": "Galaxy",
            "delay": 15000,
            "update": [],
        }))
    except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
        pass
    return (flask.jsonify(shared_info_response.text), 200)

def _offer_shared(req, kd_id):
    shared_kd = str(req["shared"])
    shared_stat = req["shared_stat"]
    shared_to_kd = str(req["shared_to"])
    cut = float(req.get("cut", 0)) / 100
    kingdoms = uag._get_kingdoms()

    if (
        shared_kd == "" or shared_kd == None
        or shared_stat == "" or shared_stat == None
        or shared_to_kd == "" or shared_to_kd == None
    ):
        return {"message": "The request selections are not complete"}, 400
    
    if (
        cut > uas.GAME_CONFIG["BASE_MAX_SHARE_CUT"]
    ):
        return {"message": f"Cut must be less than {uas.GAME_CONFIG['BASE_MAX_SHARE_CUT']:.1%}"}, 400
    

    galaxies_inverted, galaxies = uag._get_galaxies_inverted()
    revealed_info = uag._get_revealed(kd_id)
    
    your_shared_info = uag._get_shared(kd_id)
    your_galaxy = galaxies_inverted[kd_id]
    shared_to_galaxy = galaxies_inverted.get(shared_to_kd, None)

    if your_galaxy != shared_to_galaxy and shared_to_kd != "galaxy":
        return {"message": "You can not share to kingdoms outside of your galaxy"}, 400

    if shared_stat not in revealed_info["revealed"][shared_kd].keys():
        return {"message": "You do not have that revealed stat to share"}, 400
    
    previously_shared_stats = []
    for shared_key, shared_dict in your_shared_info["shared"].items():
        if shared_key.split("_")[0] == shared_kd:
            previously_shared_stats.append(shared_dict["shared_stat"])
    if shared_stat in previously_shared_stats:
        return {"message": "You can not share intel that was shared with you"}, 400

    shared_resolve_time = revealed_info["revealed"][shared_kd][shared_stat]
    your_payload = {
        "shared_offers": your_shared_info["shared_offers"]
    }
    if shared_to_kd == "galaxy":
        kds_to_update = [
            _id
            for _id in galaxies[your_galaxy]
            if _id != kd_id
        ]
    else:
        kds_to_update = [shared_to_kd]
    for kd_to_update in kds_to_update:
        shared_to_shared_info = uag._get_shared(kd_to_update)
        shared_from_key = f"{shared_kd}_{kd_id}"
        shared_to_key = f"{shared_kd}_{kd_to_update}"
        shared_to_payload = {
            "shared_requests": shared_to_shared_info["shared_requests"]
        }

        your_payload["shared_offers"][shared_to_key] = {
            "shared_to": kd_to_update,
            "shared_stat": shared_stat,
            "cut": cut,
            "time": shared_resolve_time,
        }
        shared_to_payload["shared_requests"][shared_from_key] = {
            "shared_by": kd_id,
            "shared_stat": shared_stat,
            "cut": cut,
            "time": shared_resolve_time,
        }

        shared_to_shared_info_response = REQUESTS_SESSION.post(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_to_update}/shared',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps(shared_to_payload),
        )

        shared_to_kd_info = uag._get_kd_info(kd_to_update)
        if shared_resolve_time < shared_to_kd_info["next_resolve"]["shared"]:
            shared_to_next_resolve = shared_to_kd_info["next_resolve"]
            shared_to_next_resolve["shared"] = shared_resolve_time
            REQUESTS_SESSION.patch(
                os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_to_update}',
                headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
                data=json.dumps({"next_resolve": shared_to_next_resolve}),
            )

        
        try:
            ws = SOCK_HANDLERS[kd_to_update]
            ws.send(json.dumps({
                "message": f"{kingdoms[kd_id]} offered intel {shared_stat} for target {kingdoms[shared_kd]} with a cut of {cut:.1%}",
                "status": "info",
                "category": "Galaxy",
                "delay": 15000,
                "update": [],
            }))
        except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
            pass
    
    your_shared_info_response = REQUESTS_SESSION.post(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(your_payload),
    )
    your_info = uag._get_kd_info(kd_id)
    if shared_resolve_time < your_info["next_resolve"]["shared"]:
        your_next_resolve = your_info["next_resolve"]
        your_next_resolve["shared"] = shared_resolve_time
        REQUESTS_SESSION.patch(
            os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
            headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
            data=json.dumps({"next_resolve": your_next_resolve}),
        )
    payload = {
        "message": "Succesfully shared intel", "status": "success"
    }
    return payload, 200

@app.route('/api/offershared', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def offer_shared():
    req = flask.request.get_json(force=True)
    payload, status_code = _offer_shared(req)
    return (flask.jsonify(payload), status_code)

@app.route('/api/pinned', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def update_pinned():
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    
    pinned_patch_response = REQUESTS_SESSION.patch(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
        data=json.dumps(req),
    )
    return (flask.jsonify(pinned_patch_response.text), 200)

