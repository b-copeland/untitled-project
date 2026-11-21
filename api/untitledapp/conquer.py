import copy
import datetime
import json
import math
import os
import random
import uuid

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.getters as uag
import untitledapp.intel as uai
import untitledapp.shared as uas
import untitledapp.targets as uat
from untitledapp import alive_required, start_required, REQUESTS_SESSION, SOCK_HANDLERS

bp = flask.Blueprint("conquer", __name__)

def _reveal_random_galaxy(kd_id):
    """Spend a spy attempt to reveal a random galaxy's stats to ``kd_id``. Returns ``(payload, status_code)``. The route and the bots both come through here."""
    app = flask.current_app
    

    try:
        kd_info = occ.read(f'/kingdom/{kd_id}')
        if kd_info["spy_attempts"] <= 0:
            return {"message": 'You do not have any spy attempts remaining'}, 400

        revealed_info = uag._get_revealed(kd_id)

        empires_inverted, empires, _, _ = uag._get_empires_inverted()
        galaxies_inverted, galaxy_info = uag._get_galaxies_inverted()

        kd_empire = empires_inverted.get(kd_id, None)
        kd_galaxy = galaxies_inverted[kd_id]

        
        
        excluded_galaxies = list(revealed_info["galaxies"].keys())
        
        if kd_empire:
            excluded_galaxies.extend(empires["empires"][kd_empire]["galaxies"])
        else:
            excluded_galaxies.append(kd_galaxy)

        potential_galaxies = set(galaxy_info.keys()) - set(excluded_galaxies)

        if not len(potential_galaxies):
            return {"message": 'There are no more galaxies to reveal'}, 400

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

        def spend_attempt(kd):
            # The attempt is spent against the kingdom as it is right now, so duplicates can not reveal twice for one.
            if kd["spy_attempts"] <= 0:
                raise occ.Rejected('You do not have any spy attempts remaining')
            next_resolve = kd["next_resolve"]
            next_resolve["revealed"] = min(next_resolve["revealed"], time)
            return {"spy_attempts": kd["spy_attempts"] - 1, "next_resolve": next_resolve}, None

        occ.update(f'/kingdom/{kd_id}', spend_attempt, document=kd_info)
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(payload),
        )
    except occ.Rejected as rejection:
        return {"message": rejection.message}, rejection.status
    except occ.Busy:
        return {"message": "Server is busy"}, 400

    return {"message": f"Reveavled galaxy {galaxy_to_reveal}", "status": "success"}, 200


@bp.route('/api/revealrandomgalaxy', methods=['GET'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def reveal_random_galaxy():
    payload, status = _reveal_random_galaxy(flask_praetorian.current_user().kd_id)
    return flask.jsonify(payload), status

def _add_aggression(
    source_empire,
    target_empire,
    aggression_increase,
    empires_info=None,
):
    """
    Raise one empire's aggression towards another by an amount. Applied to the latest empires document (the
    ``empires_info`` argument is only kept so callers need not change), so two attacks landing together both count,
    and nothing else written to the empires meanwhile is lost.
    """
    def add(empires_doc):
        empires = empires_doc["empires"]
        if source_empire not in empires:
            return None, None
        aggression = empires[source_empire].setdefault("aggression", {})
        aggression[target_empire] = aggression.get(target_empire, 0) + aggression_increase
        return {"empires": empires}, None

    occ.update('/empires', add)


def _lower_timer(kd_id, field, when):
    """
    Make sure a kingdom's ``next_resolve[field]`` timer fires no later than ``when``. Taking the sooner of the stored
    and the new time is idempotent and does not depend on the order of overlapping calls, which is why this does not
    need to be part of the strict steps of an action.
    """
    def lower(kd):
        next_resolve = kd["next_resolve"]
        if uas.utc(when) >= uas.utc(next_resolve[field]):
            return None, None
        next_resolve[field] = when
        return {"next_resolve": next_resolve}, None

    occ.update(f'/kingdom/{kd_id}', lower)


def _lower_reveal_timer(kd_id, revealed_until):
    _lower_timer(kd_id, "revealed", revealed_until)

def _validate_attack_request(
    attacker_raw_values,
    kd_info,
    calculate=False,
):
    attacker_units = {
        key: int(value)
        for key, value in attacker_raw_values.items()
        if (key in uas.UNITS and value != "")
    }
    if not calculate:
        if any((
            attack_units > kd_info["units"].get(key_unit, 0)
            for key_unit, attack_units in attacker_units.items()
        )):
            return False, "You do not have that many units"
        if sum(attacker_units.values()) == 0:
            return False, "You must send at least 1 unit"
        if int(attacker_raw_values["generals"] or 0) > kd_info["generals_available"]:
            return False, "You do not have that many generals"
        if int(attacker_raw_values["generals"] or 0) <= 0:
            return False, "You must send at least 1 general"
    if any((
        attack_units < 0
        for attack_units in attacker_units.values()
    )):
        return False, "You can not send negative units"
    
    return True, ""

def _home_defense(kd_info_parse, current_bonuses, units_sent):
    """The defense that stays at home once ``units_sent`` have gone out, by the same rules used for any defender."""
    units_home = {
        key: max(value - units_sent.get(key, 0), 0)
        for key, value in kd_info_parse["units"].items()
    }
    return uag._calc_max_defense(
        units_home,
        military_bonus=current_bonuses["military_bonus"],
        other_bonuses=0,
        shields=kd_info_parse.get("shields", {}).get("military", 0),
        fuelless=kd_info_parse["fuel"] <= 0,
        gaian=kd_info_parse["race"] == "Gaian",
    )


def _home_defense_projection(kd_info_parse, current_bonuses, attacker_units):
    return {
        "attacker_home_defense_before": _home_defense(kd_info_parse, current_bonuses, {}),
        "attacker_home_defense_after": _home_defense(kd_info_parse, current_bonuses, attacker_units),
    }


@bp.route('/api/attackcontext/<target_kd>', methods=['GET'])
@flask_praetorian.auth_required
@alive_required
def attack_context(target_kd):
    """
    What the Attack page needs the moment a target is chosen: what is known about the target, a stand-in for what is
    not (clearly marked as an estimate), and how well defended you are now and would be after sending everything.
    """
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    kd_info_parse = json.loads(REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    ).text)
    current_bonuses = uas.project_bonuses(kd_info_parse)
    revealed = uag._get_revealed(kd_id)
    target = uag._get_max_kd_info(target_kd, kd_id, revealed)

    sendable = [key for key, unit in uas.UNITS.items() if unit["offense"] > 0]
    all_out = {key: kd_info_parse["units"].get(key, 0) for key in sendable}
    mine = {
        "defense_now": _home_defense(kd_info_parse, current_bonuses, {}),
        "defense_if_all_sent": _home_defense(kd_info_parse, current_bonuses, all_out),
        "military_bonus": current_bonuses["military_bonus"],
        "shields": kd_info_parse.get("shields", {}).get("military", 0),
        "generals_available": kd_info_parse["generals_available"],
    }
    # A stand-in for whatever is not revealed: an army as big as yours, with the largest bonus and shields there can be. It is a starting point to
    # edit, and the page only uses the parts that "revealed" says are missing.
    estimate = {
        "basis": "your own army",
        "units": {key: kd_info_parse["units"].get(key, 0) for key, unit in uas.UNITS.items() if unit["defense"] > 0},
        "military_bonus": round(uas.PROJECTS["military_bonus"]["max_bonus"] * 100, 1),
        "shields": round(uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"] * 100, 1),
    }
    payload = {
        "revealed": {
            "units": "units" in target,
            "military_bonus": "current_bonuses" in target,
            "shields": "shields" in target,
        },
        "estimate": estimate,
        "mine": mine,
    }
    return (flask.jsonify(payload), 200)


def _calc_losses(
    unit_dict,
    loss_rate,
    war=False,
    xo=False,
):
    int_xo = int(xo)
    int_war = int(war)
    adjusted_loss_rate = (
        loss_rate
        * (
            1
            - int_xo * uas.GAME_CONFIG["XO_ATTACK_UNIT_LOSSES_REDUCTION"]
        )
        * (
            1
            + int_war * uas.GAME_CONFIG["WAR_LOSSES_INCREASE"]
        )
    )
    losses = {
        key_unit: math.floor(value_unit * adjusted_loss_rate)
        for key_unit, value_unit in unit_dict.items()
    }
    return losses

def _general_speed(kd_info, current_bonuses):
    """The share by which this kingdom's generals return sooner, from its projects (not politics or distance)."""
    return current_bonuses["general_bonus"] + (
        int(uas.has_project(kd_info, "xo_capstone")) * uas.GAME_CONFIG["XO_CAPSTONE_RETURN_REDUCTION"]
    )


def _battle_loss_rates(attacker_kd, defender_kd, attack_ratio=1.0, war=False, attacker_units=None, defender_units=None):
    """
    The share of its units each side loses in an attack, before race and war (``_calc_losses`` applies those): the base
    rates, the defender's scaled by how close the attack came (``attack_ratio``), the projects that change them, and
    the self-destructing units on each side (``attacker_units`` sent, ``defender_units`` at home).
    ``defender_kd`` is the defending kingdom, what the attacker knows of it (a forecast), or None for primitives.
    """
    attacker_rate = uas.GAME_CONFIG["BASE_ATTACKER_UNIT_LOSS_RATE"]
    defender_rate = uas.GAME_CONFIG["BASE_DEFENDER_UNIT_LOSS_RATE"] * attack_ratio
    if defender_kd is not None:
        increase = uas.GAME_CONFIG["SELF_DESTRUCT_LOSSES_INCREASE"]
        attacker_rate *= 1 + increase * uas.self_destruct_share(defender_units or {}, "defense")
        defender_rate *= 1 + increase * uas.self_destruct_share(attacker_units or {}, "offense")
        defender_rate *= 1 - uas.project_bonus(defender_kd, "casualties_bonus")
        if war and uas.has_project(attacker_kd, "xo_capstone"):
            defender_rate *= 1 + uas.GAME_CONFIG["XO_CAPSTONE_WAR_LOSSES_INCREASE"]
    attacker_rate *= 1 - uas.project_bonus(attacker_kd, "casualties_bonus")
    return attacker_rate, defender_rate


def _split_across_generals(units, return_times):
    """
    The generals of an attack, each with its return time and its share of the units that survived: an even split, the
    remainder to the earliest. Every warp unit (Warp Speed Big Flexers) goes with the general who returns first.
    """
    n_generals = len(return_times)
    first = min(range(n_generals), key=lambda i: return_times[i])
    generals = []
    for i_general, general_time in enumerate(return_times):
        general = {"return_time": general_time.isoformat()}
        for key_unit, count in units.items():
            if uas.UNITS.get(key_unit, {}).get("warp"):
                general[key_unit] = count if i_general == first else 0
            else:
                general[key_unit] = math.floor(count / n_generals) + int((count % n_generals) > i_general)
        generals.append(general)
    return generals


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

def _spoils_forecast(kd_id, target_kd, max_target_kd_info, race, war):
    """
    The lines of an attack forecast that say what a win would take, for the attacker and for each galaxymate whose
    intel on the target earns a cut. Worked out like the attack (intel.split_spoils), from what the attacker can see.
    """
    spoils_rate = uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"] * (
        1
        + (int(race == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        + (int(war) * uas.GAME_CONFIG["WAR_GAINS_INCREASE"])
    )
    min_stars_gain = math.floor(uas.GAME_CONFIG["BASE_ATTACK_MIN_STARS_GAIN"] * (
        1
        + (int(race == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
        + (int(war) * uas.GAME_CONFIG["WAR_GAINS_INCREASE"])
    ))
    total_spoils = {
        key_spoil: max(math.floor(value_spoil * spoils_rate), 0)
        for key_spoil, value_spoil in max_target_kd_info.items()
        if key_spoil in {"stars", "population", "money", "fuel"}
    }
    if "stars" in total_spoils:
        total_spoils["stars"] = max(total_spoils["stars"], min_stars_gain)
    if not total_spoils:
        return ""
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
    empire_target = uat.active_target(empires_inverted.get(kd_id), target_kd, empires_info, empires_inverted)
    cuts = {} if empire_target else uai.spoils_cuts_for(kd_id, target_kd)
    spoils_values, sharers_spoils = uai.split_spoils(total_spoils, cuts)
    fund = None
    if empire_target:
        spoils_values, fund = uat.fund_split(spoils_values, empire_target["fund_share"])
    message = 'You will gain ' + ', '.join([f"{value} {key}" for key, value in spoils_values.items()]) + '. \n'
    if fund and (fund["stars"] or fund["money"]):
        message += (f"{fund['stars']} stars and {fund['money']} money ({empire_target['fund_share']:.0%}) will go into "
                    "the spoils fund of this empire target. \n")
    if sharers_spoils:
        kingdoms = uag._get_kingdoms()
        for sharer, sharer_spoils in sharers_spoils.items():
            message += (f'Your galaxymate {kingdoms.get(sharer, sharer)} will gain '
                        + ', '.join([f"{value} {key}" for key, value in sharer_spoils.items()])
                        + f' ({cuts[sharer]:.1%}) for sharing intel. \n')
    return message


@bp.route('/api/calculate/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_attack(target_kd):
    app = flask.current_app
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]
    defender_raw_values = req["defenderValues"]

    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = uas.project_bonuses(kd_info_parse)

    revealed = uag._get_revealed(kd_id)
    max_target_kd_info = uag._get_max_kd_info(target_kd, kd_id, revealed)

    valid_attack_request, attack_request_message = _validate_attack_request(
        attacker_raw_values,
        kd_info_parse,
        calculate=True,
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

    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
    attacker_empire = empires_inverted.get(kd_id)
    defender_empire = empires_inverted.get(target_kd)

    war = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("war", [])
    peace = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("peace", {})
    surprise_war_penalty = empires_info["empires"].get(defender_empire, {}).get("surprise_war_penalty", False)
    attacker_fuelless = kd_info_parse["fuel"] <= 0
    attack = uag._calc_max_offense(
        attacker_units,
        military_bonus=float(current_bonuses['military_bonus'] or 0), 
        other_bonuses=0,
        generals=int(attacker_raw_values.get("generals", 0) or 0),
        fuelless=attacker_fuelless,
        lumina=kd_info_parse["race"] == "Lumina",
        denounced=defender_empire == empires_info["empires"].get(attacker_empire, {}).get("denounced", ""),
        war=war,
        surprise_war_penalty=surprise_war_penalty,
    )
    defense = uag._calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
        fuelless=target_fuelless,
        gaian=kd_info_parse["race"] == "Gaian",
        peace=peace,
    )
    try:
        attack_ratio = min(attack / defense, 1.0)
    except ZeroDivisionError:
        attack_ratio = 1.0
    attacker_loss_rate, defender_loss_rate = _battle_loss_rates(
        kd_info_parse, max_target_kd_info, attack_ratio, war, attacker_units, defender_units,
    )
    attacker_losses = _calc_losses(
        attacker_units,
        attacker_loss_rate,
        war=war,
        xo=kd_info_parse["race"] == "Xo",
    )
    defender_losses = _calc_losses(
        defender_units,
        defender_loss_rate,
        war=war,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        int(attacker_raw_values.get("generals", 1) or 1),
        uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
        time_now,
        _general_speed(kd_info_parse, current_bonuses),
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
        message += _spoils_forecast(kd_id, target_kd, max_target_kd_info, kd_info_parse["race"], war)

                
    else:
        message = f"The attack will fail.\n"
        message += f"Your general(s) will return in: {generals_strftime}\n"

    payload = {
        "defender_defense": defense,
        "attacker_offense": attack,
        "defender_losses": defender_losses,
        "attacker_losses": attacker_losses,
        "defender_unit_losses_rate": defender_loss_rate,
        "attacker_unit_losses_rate": attacker_loss_rate,
        "defender_stars_loss_rate": uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"],
        "generals_return_times": generals_return_times,
        "message": message,
        **_home_defense_projection(kd_info_parse, current_bonuses, attacker_units),
    }

    return (flask.jsonify(payload), 200)

def _validate_autofill_request(req, kd_info_parse):
    if req.get("buffer", "") == "":
        return False, "Please choose a buffer amount"
    
    if req.get("generals", "") == "":
        return False, "Please choose a generals amount"
    
    buffer = float(req.get("buffer", 0.0))
    generals = int(req.get("generals", 0))

    if buffer < 0:
        return False, "Buffer must be greater than 0"
    
    if generals <= 0:
        return False, "You must send at least 1 general"
    
    if generals > kd_info_parse["generals_available"]:
        return False, "You do not have that many generals"
    
    return True, ""
    

def _autofill_attack(req, kd_id, target_kd):
    app = flask.current_app
    defender_raw_values = req["defenderValues"]
    
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = uas.project_bonuses(kd_info_parse)

    revealed = uag._get_revealed(kd_id)
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

    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
    attacker_empire = empires_inverted.get(kd_id)
    defender_empire = empires_inverted.get(target_kd)
    war = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("war", [])
    peace = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("peace", {})
    surprise_war_penalty = empires_info["empires"].get(defender_empire, {}).get("surprise_war_penalty", False)

    defense = uag._calc_max_defense(
        defender_units,
        military_bonus=defender_military_bonus, 
        other_bonuses=0,
        shields=defender_shields,
        fuelless=target_fuelless,
        gaian=kd_info_parse["race"] == "Gaian",
        peace=peace,
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
                denounced=defender_empire == empires_info["empires"].get(attacker_empire, {}).get("denounced", ""),
                war=war,
                surprise_war_penalty=surprise_war_penalty,
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
        denounced=defender_empire == empires_info["empires"].get(attacker_empire, {}).get("denounced", ""),
        war=war,
        surprise_war_penalty=surprise_war_penalty,
    )
    try:
        attack_ratio = min(attack / defense_adjusted, 1.0)
    except ZeroDivisionError:
        attack_ratio = 1.0
    attacker_loss_rate, defender_loss_rate = _battle_loss_rates(
        kd_info_parse, max_target_kd_info, attack_ratio, war, attacker_units, defender_units,
    )
    attacker_losses = _calc_losses(
        attacker_units,
        attacker_loss_rate,
        war=war,
        xo=kd_info_parse["race"] == "Xo",
    )
    defender_losses = _calc_losses(
        defender_units,
        defender_loss_rate,
        war=war,
    )
    time_now = datetime.datetime.now(datetime.timezone.utc)
    galaxies_inverted, _ = uag._get_galaxies_inverted()
    galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_warlike = "Warlike" in galaxy_policies["active_policies"]
    generals_return_times = _calc_generals_return_time(
        generals,
        uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
        time_now,
        _general_speed(kd_info_parse, current_bonuses),
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
        message += _spoils_forecast(kd_id, target_kd, max_target_kd_info, kd_info_parse["race"], war)

                
    else:
        message = f"The attack will fail.\n"
        message += f"Your general(s) will return in: {generals_strftime}\n"

    payload = {
        "defender_defense": defense,
        "attacker_offense": attack,
        "defender_losses": defender_losses,
        "attacker_losses": attacker_losses,
        "defender_unit_losses_rate": defender_loss_rate,
        "attacker_unit_losses_rate": attacker_loss_rate,
        "defender_stars_loss_rate": uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"],
        "generals_return_times": generals_return_times,
        "message": message,
        "attacker_units": attacker_units,
        **_home_defense_projection(kd_info_parse, current_bonuses, attacker_units),
    }
    return payload, 200



@bp.route('/api/autofill/<target_kd>', methods=['POST'])
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

def _credit_spoils(spoils):
    """
    A ``decide`` that adds spoils (``{"stars": n, "money": n, ..., "funding": {category: n}}``) to a kingdom's latest
    document, spreading money and funding over auto spending the way attack spoils always have been.
    """
    def add(kd):
        changes = {}
        funding = dict(kd["funding"])
        money = kd["money"]
        for key_spoil, value_spoil in spoils.items():
            if key_spoil == "funding":
                for value_funding in value_spoil.values():
                    if kd["auto_spending_enabled"]:
                        pct_allocated = sum(kd["auto_spending"].values())
                        for key_spending, pct_spending in kd["auto_spending"].items():
                            funding[key_spending] += pct_spending * value_funding
                        money += value_funding * (1 - pct_allocated)
                    else:
                        money += value_funding
            elif key_spoil == "money":
                if kd["auto_spending_enabled"]:
                    pct_allocated = sum(kd["auto_spending"].values())
                    for key_spending, pct_spending in kd["auto_spending"].items():
                        funding[key_spending] += pct_spending * value_spoil
                    money += value_spoil * (1 - pct_allocated)
                else:
                    money += value_spoil
            else:
                changes[key_spoil] = kd[key_spoil] + value_spoil
        changes["money"] = money
        changes["funding"] = funding
        if "stars" in changes:
            changes["projects_max_points"] = {**kd["projects_max_points"], **uas.projects_max_points(changes["stars"])}
        return changes, None
    return add


def _attack(req, kd_id, target_kd):

    app = flask.current_app
    attacker_raw_values = req["attackerValues"]

    galaxies_inverted, galaxy_info = uag._get_galaxies_inverted()

    attacker_galaxy = galaxies_inverted[kd_id]
    defender_galaxy = galaxies_inverted[target_kd]

    try:
        # What follows is the attack in three committed steps, so that two attacks (or an attack and the defender's own
        # actions) can overlap without losing each other's changes. See docs/concurrency.md.
        #   1. The attacker's side: the units leave and the generals go out, checked against the attacker as it is now.
        #      This is what stops a duplicate request from sending the same units twice.
        #   2. The target's side: the losses are worked out from the target as it is now, and written only if it has not
        #      changed since. If it has, the outcome is worked out again, so attacks on one target are resolved one
        #      after another in the order they land on it.
        #   3. The spoils are added to the attacker (and the sharer) as an increment on their latest documents.
        kd_info_parse = occ.read(f'/kingdom/{kd_id}')
        target_kd_info = occ.read(f'/kingdom/{target_kd}')
        if target_kd_info["status"].lower() == "dead":
            return kd_info_parse, {"message": "You can't attack this kingdom because they are dead!"}, 400

        empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
        attacker_empire = empires_inverted.get(kd_id)
        defender_empire = empires_inverted.get(target_kd)
        war = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("war", [])
        peace = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("peace", {})
        surprise_war_penalty = empires_info["empires"].get(defender_empire, {}).get("surprise_war_penalty", False)
        denounced = defender_empire == empires_info["empires"].get(attacker_empire, {}).get("denounced", "")
        galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
        is_warlike = "Warlike" in galaxy_policies["active_policies"]
        n_generals = int(attacker_raw_values["generals"])
        # On one of the attacker's empire's targets, intel cuts do not apply and a share of the spoils goes into the
        # target's spoils fund. Elsewhere, intel on this target the attacker took from galaxymates earns each sharer
        # their cut of the spoils (each category its own cut, added up); the attacker gets the rest. The same split as
        # the forecast (_spoils_forecast).
        empire_target = uat.active_target(attacker_empire, target_kd, empires_info, empires_inverted)
        cuts = {} if empire_target else uai.spoils_cuts_for(kd_id, target_kd)

        def depart(kd):
            current_bonuses = uas.project_bonuses(kd)
            valid_attack_request, attack_request_message = _validate_attack_request(attacker_raw_values, kd)
            if not valid_attack_request:
                raise occ.Rejected(attack_request_message)

            attacker_units = {
                key: int(value)
                for key, value in attacker_raw_values.items()
                if (key in uas.UNITS and value != "")
            }
            attack = uag._calc_max_offense(
                attacker_units,
                military_bonus=float(current_bonuses['military_bonus'] or 0),
                other_bonuses=0,
                generals=n_generals,
                fuelless=kd["fuel"] <= 0,
                lumina=kd["race"] == "Lumina",
                denounced=denounced,
                war=war,
                surprise_war_penalty=surprise_war_penalty,
            )
            # The attacker's losses do not depend on how the battle goes, so they are fixed as the units leave.
            attacker_loss_rate, _ = _battle_loss_rates(kd, target_kd_info, defender_units=target_kd_info["units"])
            attacker_losses = _calc_losses(
                attacker_units,
                attacker_loss_rate,
                war=war,
                xo=kd["race"] == "Xo",
            )
            time_now = datetime.datetime.now(datetime.timezone.utc)
            generals_return_times = _calc_generals_return_time(
                n_generals,
                uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
                time_now,
                _general_speed(kd, current_bonuses),
                is_warlike=is_warlike,
                coordinate_distance=_calc_coordinate_distance(kd["coordinate"], target_kd_info["coordinate"]),
            )
            remaining_attacker_units = {
                key_unit: value_unit - attacker_losses.get(key_unit, 0)
                for key_unit, value_unit in attacker_units.items()
            }
            generals = _split_across_generals(remaining_attacker_units, generals_return_times)
            next_return_time = min([general["return_time"] for general in generals])
            next_resolve = kd["next_resolve"]
            next_resolve["generals"] = min(next_resolve["generals"], next_return_time)
            payload = {
                "units": {
                    key_unit: value_unit - attacker_units.get(key_unit, 0)
                    for key_unit, value_unit in kd["units"].items()
                },
                "generals_out": kd["generals_out"] + generals,
                "generals_available": kd["generals_available"] - n_generals,
                "next_resolve": next_resolve,
            }
            return payload, {
                "attack": attack,
                "attacker_units": attacker_units,
                "attacker_losses": attacker_losses,
                "generals": generals,
                "time_now": time_now,
                "name": kd["name"],
                "race": kd["race"],
                "completed_projects": list(kd.get("completed_projects", [])),
            }

        def resolve(target_doc):
            """The outcome of the attack against the target as it is now, and the changes it makes to the target."""
            if target_doc["status"].lower() == "dead":
                raise occ.Rejected("You can't attack this kingdom because they are dead!")
            target_current_bonuses = uas.project_bonuses(target_doc)
            defender_units = {
                key: value
                for key, value in target_doc["units"].items()
                if uas.UNITS[key].get("defense", 0) > 0
            }
            attack = departure["attack"]
            defense = uag._calc_max_defense(
                defender_units,
                military_bonus=target_current_bonuses['military_bonus'],
                other_bonuses=0,
                shields=target_doc["shields"]["military"],
                fuelless=target_doc["fuel"] <= 0,
                gaian=departure["race"] == "Gaian",
                peace=peace,
            )
            # A kingdom with nothing to defend with has a defense of zero: any attack is at full strength.
            attack_ratio = min(attack / defense, 1.0) if defense > 0 else 1.0
            _, defender_loss_rate = _battle_loss_rates(
                departure, target_doc, attack_ratio, war, attacker_units=departure["attacker_units"],
            )
            defender_losses = _calc_losses(
                defender_units,
                defender_loss_rate,
                war=war,
            )
            attacker_losses = departure["attacker_losses"]
            target_new = {"units": {
                key_unit: value_unit - defender_losses.get(key_unit, 0)
                for key_unit, value_unit in target_doc["units"].items()
            }}
            outcome = {"attack": attack, "defense": defense, "defender_losses": defender_losses}
            if attack > defense:
                xo = int(departure["race"] == "Xo")
                spoils_rate = uas.GAME_CONFIG["BASE_KINGDOM_LOSS_RATE"] * (
                    1
                    + (xo * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
                    + (int(war) * uas.GAME_CONFIG["WAR_GAINS_INCREASE"])
                )
                min_stars_gain = math.floor(uas.GAME_CONFIG["BASE_ATTACK_MIN_STARS_GAIN"] * (
                    1
                    + (xo * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
                    + (int(war) * uas.GAME_CONFIG["WAR_GAINS_INCREASE"])
                ))
                total_spoils = {
                    key_spoil: max(math.floor(value_spoil * spoils_rate), 0)
                    for key_spoil, value_spoil in target_doc.items()
                    if key_spoil in {"stars", "population", "money", "fuel"}
                }
                total_spoils["stars"] = max(total_spoils["stars"], min_stars_gain)
                total_spoils["funding"] = {
                    key_funding: max(math.floor(value_funding * spoils_rate), 0)
                    for key_funding, value_funding in target_doc["funding"].items()
                }
                spoils_values, sharers_spoils = uai.split_spoils(total_spoils, cuts)
                # What the target loses: the attacker's part (before the fund takes its share) and the sharers' cuts.
                taken = spoils_values
                fund = None
                if empire_target:
                    spoils_values, fund = uat.fund_split(spoils_values, empire_target["fund_share"])
                units_destroyed = sum(defender_losses.values())
                attack_status = "success"
                attacker_message = (
                    "Success! You have gained "
                    + ', '.join([f"{value} {key}" for key, value in spoils_values.items() if key != "funding"])
                    + f', {sum(spoils_values["funding"].values())} funding'
                    + f" and destroyed {units_destroyed} units."
                    + (f" {fund['stars']} stars and {fund['money']} money went into the target's spoils fund."
                       if fund and (fund["stars"] or fund["money"]) else "")
                    + " You have lost "
                    + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
                )
                defender_message = (
                    f"Your kingdom was defeated in battle by {departure['name']}. You have lost "
                    + ', '.join([f"{value} {key}" for key, value in total_spoils.items() if key != "funding"])
                    + f', {sum(total_spoils["funding"].values())} funding'
                    + ' and '
                    + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in defender_losses.items()])
                )
                # Everything taken from the target, including the sharers' cuts.
                for key_spoil in ("stars", "population", "money", "fuel"):
                    target_new[key_spoil] = (
                        target_doc[key_spoil] - taken[key_spoil]
                        - sum(spoils.get(key_spoil, 0) for spoils in sharers_spoils.values())
                    )
                target_new["funding"] = {
                    key_funding: (
                        value_funding
                        - taken["funding"].get(key_funding, 0)
                        - sum(spoils.get("funding", {}).get(key_funding, 0) for spoils in sharers_spoils.values())
                    )
                    for key_funding, value_funding in target_doc["funding"].items()
                }
                target_new["stars"] = max(target_new["stars"], 0)
                target_new["projects_max_points"] = {**target_doc["projects_max_points"], **uas.projects_max_points(target_new["stars"])}
                if target_new["stars"] <= 0:
                    target_new["status"] = "Dead"
            else:
                attack_status = "failure"
                attacker_message = "Failure! You have lost " + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in attacker_losses.items()])
                defender_message = (
                    f"Your kingdom successfully defended an attack by {departure['name']}. You have lost "
                    + ', '.join([f"{value} {uas.PRETTY_NAMES.get(key, key)}" for key, value in defender_losses.items()])
                )
                total_spoils = {}
                spoils_values = {}
                sharers_spoils = {}
                fund = None
            outcome.update({
                "fund": fund,
                "status": attack_status,
                "attacker_message": attacker_message,
                "defender_message": defender_message,
                "total_spoils": total_spoils,
                "spoils_values": spoils_values,
                "sharers_spoils": sharers_spoils,
                "target_name": target_doc["name"],
                "target_dead": target_new.get("status") == "Dead",
            })
            return target_new, outcome

        credit = _credit_spoils

        def give_back_units(kd):
            """Undo the departure if the target turned out to be gone, so the units are not stuck out forever."""
            returned = {
                key_unit: value_unit + departure["attacker_units"].get(key_unit, 0)
                for key_unit, value_unit in kd["units"].items()
            }
            ours = {general["return_time"] for general in departure["generals"]}
            return {
                "units": returned,
                "generals_out": [g for g in kd["generals_out"] if g["return_time"] not in ours],
                "generals_available": kd["generals_available"] + n_generals,
            }, None

        # Both start from the documents read above; each write is conditional on them, so if either kingdom has
        # changed since, it is read again and decided again.
        departure = occ.update(f'/kingdom/{kd_id}', depart, document=kd_info_parse)
        time_now = departure["time_now"]
        try:
            outcome = occ.update(f'/kingdom/{target_kd}', resolve, document=target_kd_info)
        except BaseException:
            occ.update(f'/kingdom/{kd_id}', give_back_units)
            raise
        attack = outcome["attack"]
        defense = outcome["defense"]
        attack_status = outcome["status"]
        attacker_message = outcome["attacker_message"]
        defender_message = outcome["defender_message"]
        total_spoils = outcome["total_spoils"]
        spoils_values = outcome["spoils_values"]
        sharers_spoils = outcome["sharers_spoils"]
        target_kd_info["name"] = outcome["target_name"]
        kd_info_parse["name"] = departure["name"]

        fund = outcome["fund"]
        if empire_target:
            # Points for the attack if the target is marked for it, and the fund's share. If the target ended
            # meanwhile, the share goes back to the attacker.
            if attack_status == "success":
                action, measures = "successful_attacks", {"stars": total_spoils.get("stars", 0)}
            else:
                action, measures = "failed_attacks", {"units": sum(outcome["defender_losses"].values())}
            recorded = uat.record_action(attacker_empire, target_kd, kd_id, action, measures, fund=fund, entry=empire_target)
            if not recorded and fund:
                spoils_values = {**spoils_values, "stars": spoils_values["stars"] + fund["stars"],
                                 "money": spoils_values["money"] + fund["money"]}
        if spoils_values:
            occ.update(f'/kingdom/{kd_id}', credit(spoils_values))
        if outcome["target_dead"]:
            uam._mark_kingdom_death(target_kd, killer=kd_id)
        sharer_names = {}
        for sharer, sharer_spoils_values in sharers_spoils.items():
            if not any(value for key, value in sharer_spoils_values.items() if key != "funding") \
                    and not sum(sharer_spoils_values.get("funding", {}).values()):
                continue
            sharer_message = (
                "You have gained "
                + ', '.join([f"{value} {key}" for key, value in sharer_spoils_values.items() if key != "funding"])
                + f', {sum(sharer_spoils_values["funding"].values())} funding'
                + f" ({cuts[sharer]:.1%}) for sharing intel leading to a successful attack by your galaxymate"
                + f" {kd_info_parse['name']}"
            )
            occ.update(f'/kingdom/{sharer}', credit(sharer_spoils_values))
            sharer_names[sharer] = occ.read(f'/kingdom/{sharer}')["name"]
            REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{sharer}/news',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps({"time": time_now.isoformat(), "from": kd_id, "news": sharer_message, "kind": "intel"}),
            )
            uam._add_notifs(sharer, ["news_kingdom"])
            try:
                ws = SOCK_HANDLERS[sharer]
                ws.send(json.dumps({
                    "message": f"You have gained {sharer_spoils_values['stars']} stars from an attack by your galaxymate {kd_info_parse['name']}",
                    "status": "info",
                    "category": "Galaxy",
                    "delay": 15000,
                    "update": [],
                }))
            except (KeyError, ConnectionError, StopIteration, ConnectionClosed):
                pass

        target_news = {
            "time": time_now.isoformat(),
            "from": kd_id,
            "news": defender_message,
            "kind": "attack",
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
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_news),
        )
        uam._add_notifs(target_kd, ["news_kingdom"])
        kd_attack_history = {
            "time": time_now.isoformat(),
            "to": target_kd,
            "news": attacker_message,
        }
        kd_attack_history_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_attack_history, default=str),
        )

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

        attacker_galaxy_payload = {
            "time": time_now.isoformat(),
            "from": kd_id,
            "to": target_kd,
            "kind": "attack",
        }
        defender_galaxy_payload = {
            "time": time_now.isoformat(),
            "from": kd_id,
            "to": target_kd,
            "kind": "attack",
        }
        if attack > defense:
            attacker_galaxy_payload["news"] = f"{kd_info_parse['name']} successfully attacked {target_kd_info['name']} and gained {spoils_values['stars']} stars."
            for sharer, sharer_name in sharer_names.items():
                attacker_galaxy_payload["news"] += f" {sharer_name} provided intel and gained {sharers_spoils[sharer]['stars']} stars."

            defender_galaxy_payload["news"] = f"{target_kd_info['name']} was defeated by {kd_info_parse['name']} and lost {total_spoils['stars']} stars."
        else:
            attacker_galaxy_payload["news"] = f"{kd_info_parse['name']} failed an attack on {target_kd_info['name']}."

            defender_galaxy_payload["news"] = f"{target_kd_info['name']} successfully defended an attack by {kd_info_parse['name']}."

        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{attacker_galaxy}/news',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(attacker_galaxy_payload),
        )
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{defender_galaxy}/news',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(defender_galaxy_payload),
        )
        if attacker_galaxy != defender_galaxy:
            kds_revealed_to = galaxy_info[defender_galaxy]
            for kd_revealed_to in kds_revealed_to:
                reveal_galaxy_response = REQUESTS_SESSION.patch(
                    app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_revealed_to}/revealed',
                    headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                    data=json.dumps(payload),
                )
                _lower_reveal_timer(kd_revealed_to, revealed_until)
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
        for defender_galaxy_kd in galaxy_info[defender_galaxy]:
            uam._add_notifs(defender_galaxy_kd, ["news_galaxy"])

        if attacker_empire is not None and defender_empire is not None and attacker_empire != defender_empire:
            _add_aggression(
                attacker_empire,
                defender_empire,
                uas.GAME_CONFIG["AGGRO_PER_ATTACK"],
                empires_info,
            )

        attack_results = {
            "status": attack_status,
            "message": attacker_message,
        }
    except occ.Rejected as rejection:
        return None, {"message": rejection.message}, rejection.status
    except occ.Busy:
        return None, {"message": "Server is busy"}, 400
    return kd_info_parse, attack_results, 200

@bp.route('/api/attack/<target_kd>', methods=['POST'])
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

@bp.route('/api/calculateprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_attack_primitives():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )

    state = uag._get_state()
    
    start_time = datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_defense_per_star = uas.GAME_FUNCS["BASE_PRIMITIVES_DEFENSE_PER_STAR"](max(seconds_elapsed, 0))
    
    kd_info_parse = json.loads(kd_info.text)
    current_bonuses = uas.project_bonuses(kd_info_parse)

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
    attacker_loss_rate, _ = _battle_loss_rates(kd_info_parse, None)
    attacker_losses = _calc_losses(
        attacker_units,
        attacker_loss_rate,
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
        _general_speed(kd_info_parse, current_bonuses),
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
        "attacker_unit_losses_rate": attacker_loss_rate,
        "generals_return_times": generals_return_times,
        "message": message
    }

    return (flask.jsonify(payload), 200)

def _attack_primitives(req, kd_id):
    app = flask.current_app
    
    attacker_raw_values = req["attackerValues"]

    def decide(kd_info_parse):
        # Validated against the attacker as it is right now: a duplicate request finds the units already gone.
        current_bonuses = uas.project_bonuses(kd_info_parse)
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
            raise occ.Rejected(attack_request_message)

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
        attacker_loss_rate, _ = _battle_loss_rates(kd_info_parse, None)
        attacker_losses = _calc_losses(
            attacker_units,
            attacker_loss_rate,
            xo=kd_info_parse["race"] == "Xo",
        )
        time_now = datetime.datetime.now(datetime.timezone.utc)
        galaxies_inverted, _ = uag._get_galaxies_inverted()
        galaxy_policies, _ = uag._get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
        is_warlike = "Warlike" in galaxy_policies["active_policies"]
        n_generals = int(attacker_raw_values["generals"])
        generals_return_times = _calc_generals_return_time(
            n_generals,
            uas.GAME_CONFIG["BASE_GENERALS_RETURN_TIME_MULTIPLIER"],
            time_now,
            _general_speed(kd_info_parse, current_bonuses),
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
        generals = _split_across_generals(remaining_attacker_units, generals_return_times)
        next_return_time = min([general["return_time"] for general in generals])

        stars = math.floor(
            attack
            / primitives_defense_per_star
            * (
                1
                + (int(kd_info_parse["race"] == "Xo") * uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"])
            )
        )
        if stars == 0:
            raise occ.Rejected("Attacks against primitives should conquer at least 1 star. Send more units")
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

        kd_info_parse["projects_max_points"] = uas.projects_max_points(kd_info_parse["stars"])

        return kd_info_parse, (kd_info_parse, time_now, attack_status, attacker_message)

    try:
        kd_info_parse, time_now, attack_status, attacker_message = occ.update(f'/kingdom/{kd_id}', decide)
        kd_attack_history = {
            "time": time_now.isoformat(),
            "to": "",
            "news": attacker_message,
        }
        kd_attack_history_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(kd_attack_history, default=str),
        )

        attack_results = {
            "status": attack_status,
            "message": attacker_message,
        }
    except occ.Rejected as rejection:
        return None, {"message": rejection.message}, rejection.status
    except occ.Busy:
        return None, {"message": "Server is busy"}, 400
    return kd_info_parse, attack_results, 200

@bp.route('/api/attackprimitives', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
@start_required
# @flask_praetorian.roles_required('verified')
def attack_primitives():
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    _, attack_results, status_code = _attack_primitives(req, kd_id)
    return (flask.jsonify(attack_results), status_code)

def _shielding_fuel(kd_info, drones):
    """Fuel it costs this kingdom to shield ``drones`` drones on one operation."""
    per_drone = uas.GAME_CONFIG["BASE_DRONES_SHIELDING_FUEL_PER_DRONE"] * (
        1 - int(uas.has_project(kd_info, "lumina_capstone")) * uas.GAME_CONFIG["LUMINA_CAPSTONE_SHIELDING_FUEL_REDUCTION"]
    )
    return drones * per_drone


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
        if kd_info["fuel"] < _shielding_fuel(kd_info, drones):
            return False, "You do not have enough fuel"
    if kd_info["spy_attempts"] == 0:
        return False, "You do not have any more spy attempts"
    
    return True, ""

def _already_revealed_problem(revealed_info, target_kd, operation, now):
    """
    Why ``operation`` is refused on ``target_kd``: everything it would reveal is revealed to the spier already (their
    own spying, intel received from a galaxymate, or a galaxymate sharing their kingdom). None if it is not a reveal
    operation or would show something new. Full Infiltration is allowed while any of its categories is not revealed.
    """
    stats = uas.REVEAL_OPERATION_STATS.get(operation)
    if not stats:
        return None
    target_kd = str(target_kd)
    if target_kd not in revealed_info.get("revealed_galaxymates", []):
        held = revealed_info.get("revealed", {}).get(target_kd, {})
        if any(stat not in held or uas.utc(held[stat]) <= now for stat in stats):
            return None
    return f"You already have their {', '.join(stats)} revealed"


def _validate_auto_attack_settings(req_settings):
    """Confirm that spending request is valid"""

    values = req_settings.values()
    if any((value < 0 for value in values)):
        return False, "Unit percents must be greater than 0"
    if any((value > 1 for value in values)):
        return False, "Unit percents must be less than 100%"
    
    return True, ""


@bp.route('/api/attackprimitives/auto', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def auto_attack_primitives():
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id

    if req.get("enabled", None) != None:
        enabled = req["enabled"]

        def switch(kd_info_parse):
            if kd_info_parse["auto_attack_settings"].get("pure", 0) == 0 and kd_info_parse["auto_attack_settings"].get("flex", 0) == 0:
                raise occ.Rejected("Could not enable auto attack. You must first specify the percent of units to send")
            return {'auto_attack_enabled': enabled}, None

        message = "Enabled auto attacking primitives" if enabled else "Disabled auto attacking primitives"
        decide = switch
    else:
        def change_settings(kd_info_parse):
            current_settings = kd_info_parse['auto_attack_settings']
            req_settings = {
                "pure": float(req.get("pure") or (current_settings.get("pure", 0) * 100)) / 100,
                "flex": float(req.get("flex") or (current_settings.get("flex", 0) * 100)) / 100,
            }
            new_settings = {**current_settings, **req_settings}
            valid_settings, message = _validate_auto_attack_settings(new_settings)
            if not valid_settings:
                raise occ.Rejected(message)
            return {'auto_attack_settings': new_settings}, None

        message = "Updated auto attack settings"
        decide = change_settings

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    except (TypeError, ValueError):
        return (flask.jsonify({"message": "The percentages must be numbers"}), 400)
    return (flask.jsonify({"message": message, "status": "success"}), 200)


def _calculate_spy_probability(
    drones_to_send,
    target_drones,
    target_stars,
    target_shields,
    aggro_vult=False,
    peace=False,
):
    drones_defense = target_drones * uas.GAME_CONFIG["BASE_DRONES_DRONE_DEFENSE_MULTIPLIER"]
    stars_defense = target_stars * uas.GAME_CONFIG["BASE_STARS_DRONE_DEFENSE_MULTIPLIER"]
    total_defense = max(drones_defense + stars_defense, 1)
    int_peace = int(peace)

    base_probability = min(max(drones_to_send / total_defense, uas.GAME_CONFIG["BASE_SPY_MIN_SUCCESS_CHANCE"]), 1.0) * (
        1 - int_peace * uas.GAME_CONFIG["PEACE_PROBE_DEFENSE_BONUS"]
    )
    if aggro_vult:
        shielded_probability = base_probability
    else:
        shielded_probability = base_probability * (1 - target_shields)

    return shielded_probability, drones_defense, stars_defense

def _aggro_damage_multiplier(attacker_kd, target_kd, war=False):
    """
    How much of an aggressive spy operation's damage lands, from the projects of both sides: 1 is the base damage.
    ``target_kd`` is the target, or what the attacker knows of it (a forecast). ``war``: the two empires are at war.
    """
    multiplier = 1 - uas.project_bonus(target_kd, "spy_protection_bonus")
    if uas.has_project(attacker_kd, "vult_capstone"):
        multiplier *= 1 + uas.GAME_CONFIG["VULT_CAPSTONE_DRONE_DAMAGE_INCREASE"]
    if war and uas.has_project(attacker_kd, "lumina_evolution"):
        multiplier *= 1 + uas.GAME_CONFIG["LUMINA_EVOLUTION_WAR_DRONE_DAMAGE_INCREASE"]
    return multiplier


def _operation_locked(kd_info, operation):
    """Why this kingdom can not run ``operation`` yet, or None."""
    project = uas.OPERATION_PROJECTS.get(operation)
    if project and not uas.has_project(kd_info, project):
        return f"Complete the {uas.PROJECTS[project]['name']} project to use {uas.PRETTY_NAMES.get(operation, operation)}"
    return None


def _calculate_spy_losses(
    drones_to_send,
    shielded,
    has_drone_gadgets=False,
):
    additive_loss_reduction = 1 - (int(has_drone_gadgets) * uas.GAME_CONFIG["BASE_DRONE_GADGETS_LOSS_REDUCTION"])
    multiplicative_reduction = additive_loss_reduction * (1 - (int(shielded) * uas.GAME_CONFIG["BASE_DRONES_SHIELDING_LOSS_REDUCTION"]))
    success_loss = math.floor(drones_to_send * uas.GAME_CONFIG["BASE_DRONES_SUCCESS_LOSS_RATE"] * multiplicative_reduction)
    failure_loss = math.floor(drones_to_send * uas.GAME_CONFIG["BASE_DRONES_FAILURE_LOSS_RATE"] * multiplicative_reduction)
    return success_loss, failure_loss
    
        
@bp.route('/api/calculatespy/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_spy(target_kd):
    app = flask.current_app
    req = flask.request.get_json(force=True)
    drones = int(req.get("drones", 0) or 0)
    shielded = req["shielded"]
    defender_raw_values = req["defenderValues"]
    operation = req["operation"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    if not operation:
        return (flask.jsonify({"message": "You must select an operation"}), 400)
    
    
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    valid_request, message = _validate_spy_request(
        drones,
        kd_info_parse,
        shielded,
    )
    if not valid_request:
        return (flask.jsonify({"message": message}), 400)
    locked = _operation_locked(kd_info_parse, operation)
    if locked:
        return (flask.jsonify({"message": locked}), 400)
    
    revealed = uag._get_revealed(kd_id)
    max_target_kd_info = uag._get_max_kd_info(target_kd, kd_id, revealed)
    
    if "drones" in max_target_kd_info:
        defender_drones = max_target_kd_info["drones"]
        drones_revealed = True
    else:
        defender_drones = int(defender_raw_values["drones"] or 0)
        drones_revealed = False
    
    if "stars" in max_target_kd_info:
        defender_stars = max_target_kd_info["stars"]
        stars_revealed = True
    else:
        defender_stars = int(defender_raw_values["stars"] or 0)
        stars_revealed = False

    if "shields" in max_target_kd_info:
        defender_shields = max_target_kd_info["shields"]["spy"]
    else:
        defender_shields = float(defender_raw_values['shields'] or 0) / 100
    
    empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
    attacker_empire = empires_inverted.get(kd_id)
    defender_empire = empires_inverted.get(target_kd)
    peace = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("peace", {})
    war = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("war", [])

    spy_probability, drones_defense, stars_defense = _calculate_spy_probability(
        drones,
        defender_drones,
        defender_stars,
        defender_shields,
        aggro_vult=(kd_info_parse["race"] == "Vult") and (operation in uas.AGGRO_OPERATIONS),
        peace=peace,
    )
    success_losses, failure_losses = _calculate_spy_losses(
        drones,
        shielded,
        has_drone_gadgets=uas.has_project(kd_info_parse, "drone_gadgets"),
    )

    damage_multiplier = _aggro_damage_multiplier(kd_info_parse, max_target_kd_info, war)
    message = f"The operation has a {spy_probability:.2%} chance of success. \n\nIf successful, {success_losses} drones will be lost. \nIf unsuccessful, {failure_losses} drones will be lost.\n"

    if operation in uas.REVEAL_OPERATIONS:
        revealed_stat = ", ".join(uas.REVEAL_OPERATION_STATS[operation])
        reveal_duration_seconds = uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        reveal_duration_hours = reveal_duration_seconds / 3600
        message += f"If successful, the target's {revealed_stat} will be revealed for {reveal_duration_hours} hours.\n"
    if operation == "siphonfunds":
        siphon_damage = math.floor(drones * uas.GAME_CONFIG["BASE_DRONES_SIPHON_PER_DRONE"] * damage_multiplier)
        siphon_seconds = uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        siphon_hours = siphon_seconds / 3600
        message += f"If successful, you will siphon up to {siphon_damage} money over the next {siphon_hours} hours."
    if operation == "bombhomes":
        if "structures" in max_target_kd_info.keys():
            homes_damage = math.floor(min(math.floor(max_target_kd_info["structures"]["homes"] * uas.GAME_CONFIG["BASE_DRONES_MAX_HOME_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_HOME_DAMAGE"])) * damage_multiplier)
            message += f"If successful, you will destroy {homes_damage} homes."
        else:
            homes_damage = math.floor(math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_HOME_DAMAGE"]) * damage_multiplier)
            message += f"If successful, you will destroy up to {homes_damage} homes."
    if operation == "sabotagefuelplants":
        if "structures" in max_target_kd_info.keys():
            fuel_plant_damage = math.floor(min(math.floor(max_target_kd_info["structures"]["fuel_plants"] * uas.GAME_CONFIG["BASE_DRONES_MAX_FUEL_PLANT_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_FUEL_PLANT_DAMAGE"])) * damage_multiplier)
            message += f"If successful, you will destroy {fuel_plant_damage} fuel plants."
        else:
            fuel_plant_damage = math.floor(math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_FUEL_PLANT_DAMAGE"]) * damage_multiplier)
            message += f"If successful, you will destroy up to {fuel_plant_damage} fuel plants."
    if operation == "kidnappopulation":
        if "population" in max_target_kd_info.keys():
            kidnap_damage = math.floor(min(math.floor(max_target_kd_info["population"] * uas.GAME_CONFIG["BASE_DRONES_MAX_KIDNAP_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_KIDNAP"])) * damage_multiplier)
            kidnap_return = math.floor(kidnap_damage * uas.GAME_CONFIG["BASE_KIDNAP_RETURN_RATE"])
            message += f"If successful, you will kidnap {kidnap_damage} civilians. {kidnap_return} civilians will join your population."
        else:
            kidnap_damage = math.floor(math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_KIDNAP"]) * damage_multiplier)
            kidnap_return = math.floor(kidnap_damage * uas.GAME_CONFIG["BASE_KIDNAP_RETURN_RATE"])
            message += f"If successful, you will kidnap up to {kidnap_damage} civilians. Up to {kidnap_return} civilians will join your population."
    if operation == "suicidedrones":
        fuel_damage = math.floor(drones * uas.GAME_CONFIG["BASE_DRONES_SUICIDE_FUEL_DAMAGE"] * damage_multiplier)
        if "fuel" in max_target_kd_info.keys():
            fuel_damage = min(fuel_damage, max_target_kd_info["fuel"])
            message = f"You will destroy {fuel_damage} fuel."
        else:
            message = f"You will destroy up to {fuel_damage} fuel."

    
    if operation != "suicidedrones" and not (drones_revealed and stars_revealed):
        message = "With incomplete information, " + message

    payload = {
        "message": message,
        "stars_defense": stars_defense,
        "drones_defense": drones_defense,
        "total_defense": stars_defense + drones_defense,
        "success_chance": spy_probability,
        "drone_losses": {"success": success_losses, "failure": failure_losses},
    }
    return (flask.jsonify(payload), 200)
    
def _spy(req, kd_id, target_kd):
    
    
    app = flask.current_app
    try:
        drones = int(req.get("drones", 0) or 0)
        shielded = req["shielded"]
        operation = req["operation"]

        kd_info_parse = occ.read(f'/kingdom/{kd_id}')

        valid_request, message = _validate_spy_request(
            drones,
            kd_info_parse,
            shielded,
        )
        if not valid_request:
            return kd_info_parse, {"message": message}, 400, False
        locked = _operation_locked(kd_info_parse, operation)
        if locked:
            return kd_info_parse, {"message": locked}, 400, False
        if operation in uas.REVEAL_OPERATIONS:
            # Refused before anything is spent: spying again would cost drones and an attempt to see nothing new.
            known = _already_revealed_problem(uag._get_revealed(kd_id), target_kd, operation, datetime.datetime.now(datetime.timezone.utc))
            if known:
                return kd_info_parse, {"message": known}, 400, False

        max_target_kd_info = uag._get_kd_info(target_kd)
        if max_target_kd_info["status"].lower() == "dead":
            return kd_info_parse, {"message": "You can't spy this kingdom because they are dead!"}, 400, False

        def charge(kd):
            # What the operation costs is taken up front, against the kingdom as it is right now, so a duplicate
            # request can not spend the same drones or spy attempt twice. The drones that survive come back below.
            valid, charge_message = _validate_spy_request(drones, kd, shielded)
            if not valid:
                raise occ.Rejected(charge_message)
            charged = {"drones": kd["drones"] - drones, "spy_attempts": kd["spy_attempts"] - 1}
            if shielded:
                charged["fuel"] = kd["fuel"] - _shielding_fuel(kd, drones)
            return charged, None

        occ.update(f'/kingdom/{kd_id}', charge, document=kd_info_parse)
        
        defender_drones = max_target_kd_info["drones"]
        defender_stars = max_target_kd_info["stars"]
        defender_shields = max_target_kd_info["shields"]["spy"]

        empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
        attacker_empire = empires_inverted.get(kd_id)
        defender_empire = empires_inverted.get(target_kd)
        peace = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("peace", {})
        war = defender_empire in empires_info["empires"].get(attacker_empire, {}).get("war", [])

        spy_probability, drones_defense, stars_defense = _calculate_spy_probability(
            drones,
            defender_drones,
            defender_stars,
            defender_shields,
            aggro_vult=(kd_info_parse["race"] == "Vult") and (operation in uas.AGGRO_OPERATIONS),
            peace=peace,
        )
        
        success_losses, failure_losses = _calculate_spy_losses(
            drones,
            shielded,
            has_drone_gadgets=uas.has_project(kd_info_parse, "drone_gadgets"),
        )

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
            fuel_damage = math.floor(min(
                burnable_fuel,
                drones * uas.GAME_CONFIG["BASE_DRONES_SUICIDE_FUEL_DAMAGE"] * _aggro_damage_multiplier(kd_info_parse, max_target_kd_info, war),
            ))
            losses = drones
            status = "success"
            message = f"You have destroyed {fuel_damage} fuel. You have lost {losses} drones"
            target_message = f"Enemy drones have destroyed {fuel_damage} fuel"
        else:
            if success:
                status = "success"
                if operation in uas.REVEAL_OPERATIONS:
                    reveal_duration_seconds = uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
                    revealed_until = time_now + datetime.timedelta(seconds=reveal_duration_seconds)
                    reveal_duration_hours = reveal_duration_seconds / 3600

                    revealed_payload = {
                        "new_revealed": {
                            target_kd: {
                                revealed_stat: revealed_until.isoformat()
                                for revealed_stat in uas.REVEAL_OPERATION_STATS[operation]
                            }
                        }
                    }
                    reveal_response = REQUESTS_SESSION.patch(
                        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
                        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                        data=json.dumps(revealed_payload),
                    )
                    message = f"Success! The target will be revealed for {reveal_duration_hours} hours. You have lost {success_losses} drones."
                    target_message = "You were infiltrated by drones on a spy operation."
                
                damage_multiplier = _aggro_damage_multiplier(kd_info_parse, max_target_kd_info, war)
                if operation == "siphonfunds":
                    siphon_damage = math.floor(drones * uas.GAME_CONFIG["BASE_DRONES_SIPHON_PER_DRONE"] * damage_multiplier)
                    siphon_seconds = uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
                    siphon_hours = siphon_seconds / 3600
                    siphon_until = time_now + datetime.timedelta(seconds=siphon_seconds)
                    message = f"Success! Your drones will siphon up to {siphon_damage} money over the next {siphon_hours} hours. You have lost {success_losses} drones."
                    target_message = f"Enemy drones have begun siphoning up to {siphon_damage} money over the next {siphon_hours} hours."
                if operation == "bombhomes":
                    homes_damage = math.floor(min(math.floor(max_target_kd_info["structures"]["homes"] * uas.GAME_CONFIG["BASE_DRONES_MAX_HOME_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_HOME_DAMAGE"])) * damage_multiplier)
                    message = f"Success! You have destroyed {homes_damage} homes. You have lost {success_losses} drones."
                    target_message = f"Enemy drones have destroyed {homes_damage} homes."
                if operation == "sabotagefuelplants":
                    fuel_plant_damage = math.floor(min(math.floor(max_target_kd_info["structures"]["fuel_plants"] * uas.GAME_CONFIG["BASE_DRONES_MAX_FUEL_PLANT_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_FUEL_PLANT_DAMAGE"])) * damage_multiplier)
                    message = f"Success! You have destroyed {fuel_plant_damage} fuel plants. You have lost {success_losses} drones."
                    target_message = f"Enemy drones have destroyed {fuel_plant_damage} fuel plants."
                if operation == "kidnappopulation":
                    kidnap_damage = math.floor(min(math.floor(max_target_kd_info["population"] * uas.GAME_CONFIG["BASE_DRONES_MAX_KIDNAP_DAMAGE"]), math.floor(drones / uas.GAME_CONFIG["BASE_DRONES_PER_KIDNAP"])) * damage_multiplier)
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
        is_valid_lumina_intel = (
            (kd_info_parse["race"] == "Lumina")
            and operation in uas.REVEAL_OPERATIONS
            and (
                ((drones / kd_info_parse["drones"]) >= 0.5)
                or spy_probability >= 0.8
            )
        )
        if not is_valid_lumina_intel:
            kd_patch_payload["spy_attempts"] = kd_info_parse["spy_attempts"] - 1
        if kidnap_return:
            kd_patch_payload["population"] = kd_info_parse["population"] + kidnap_return
        if shielded:
            kd_patch_payload["fuel"] = kd_info_parse["fuel"] - _shielding_fuel(kd_info_parse, drones)
        if revealed_until:
            next_resolve = kd_info_parse["next_resolve"]
            next_resolve["revealed"] = min(next_resolve["revealed"], revealed_until.isoformat())
            kd_patch_payload["next_resolve"] = next_resolve
        def settle(kd):
            # Applied to the attacker's latest document: the drones that came home, a refunded attempt for valid
            # Lumina intel, kidnapped civilians, and the earlier of the reveal timers.
            settled = {"drones": kd["drones"] + (drones - losses)}
            if is_valid_lumina_intel:
                settled["spy_attempts"] = kd["spy_attempts"] + 1
            if kidnap_return:
                settled["population"] = kd["population"] + kidnap_return
            if revealed_until:
                settled_next_resolve = kd["next_resolve"]
                settled_next_resolve["revealed"] = min(settled_next_resolve["revealed"], revealed_until.isoformat())
                settled["next_resolve"] = settled_next_resolve
            return settled, None

        occ.update(f'/kingdom/{kd_id}', settle)

        target_patch_payload = {}
        if siphon_damage:
            siphons_out_payload = {
                "new_siphons": {
                    "from": kd_id,
                    "time": siphon_until,
                    "siphon": siphon_damage,
                    # Money per epoch, paid evenly over the siphon's epochs. The refresh may lower it, never raise it.
                    "rate": siphon_damage / uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"],
                }
            }
            siphons_out_patch_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/siphonsout',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps(siphons_out_payload, default=str),
            )
        # The damage is taken off the target's latest document, not the copy read at the start, so it can not wipe
        # out what the target did meanwhile.
        if homes_damage or fuel_plant_damage or kidnap_damage or fuel_damage:
            def damage(target):
                changes = {}
                if homes_damage:
                    changes["structures"] = {**target["structures"], "homes": max(target["structures"]["homes"] - homes_damage, 0)}
                if fuel_plant_damage:
                    changes["structures"] = {**target["structures"], "fuel_plants": max(target["structures"]["fuel_plants"] - fuel_plant_damage, 0)}
                if kidnap_damage:
                    changes["population"] = target["population"] - kidnap_damage
                if fuel_damage:
                    changes["fuel"] = target["fuel"] - fuel_damage
                return changes, None

            occ.update(f'/kingdom/{target_kd}', damage)

        if revealed:
            revealed_until = (time_now + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"])).isoformat()
            def reveal_timer(target):
                # The sooner of the stored and the new time, so the order of overlapping operations does not matter.
                target_next_resolve = target["next_resolve"]
                if uas.utc(revealed_until) >= uas.utc(target_next_resolve["revealed"]):
                    return None, None
                target_next_resolve["revealed"] = revealed_until
                return {"next_resolve": target_next_resolve}, None

            occ.update(f'/kingdom/{target_kd}', reveal_timer)

            revealed_payload = {
                "new_revealed": {
                    kd_id: {
                        "stats": revealed_until,
                        "drones": revealed_until,
                    }
                }
            }
            reveal_galaxy_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/revealed',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps(revealed_payload),
            )
            target_message += f" Their kingdom 'stats' and 'drones' will be revealed for {uas.GAME_CONFIG['BASE_EPOCH_SECONDS'] * uas.GAME_CONFIG['BASE_REVEAL_DURATION_MULTIPLIER'] / 3600} hours"

        if target_patch_payload:
            target_kd_patch_response = REQUESTS_SESSION.patch(
                app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}',
                headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
                data=json.dumps(target_patch_payload, default=str),
            )
        history_payload = {
            "time": time_now.isoformat(),
            "to": target_kd,
            "operation": uas.PRETTY_NAMES.get(operation, operation),
            "news": message,
        }
        kd_spy_history_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(history_payload, default=str),
        )

        target_news_payload = {
            "time": time_now.isoformat(),
            "from": "" if success else kd_id,
            "news": target_message,
            "kind": "spy",
        }
        target_news_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_news_payload),
        )
        uam._add_notifs(target_kd, ["news_kingdom"])
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

        if success and operation in uas.REVEAL_OPERATIONS and req.get("share_to_galaxy", False):
            # Free (no cut) goes to the whole galaxy at once; with a cut it is listed on the galaxy's market.
            for category in uas.REVEAL_OPERATION_STATS[operation]:
                uai._share(kd_id, target_kd, category, req.get("cut") or 0)

        empires_inverted, empires_info, _, empire_galaxy_info = uag._get_empires_inverted()
        attacker_empire = empires_inverted.get(kd_id)
        defender_empire = empires_inverted.get(target_kd)

        if success and attacker_empire is not None and uat.counts(empires_info, attacker_empire, target_kd, empires_inverted):
            # On one of the empire's targets: intel goes to the whole empire (with points for what was new), and
            # sabotage earns points for the damage done.
            if operation in uas.REVEAL_OPERATIONS and revealed_until:
                uat.share_intel(attacker_empire, target_kd, kd_id, uas.REVEAL_OPERATION_STATS[operation], revealed_until,
                                empires_info, empire_galaxy_info)
            damage_done = {
                "kidnappopulation": ("kidnap", {"population": kidnap_damage or 0}),
                "bombhomes": ("bomb_homes", {"homes": homes_damage or 0}),
                "sabotagefuelplants": ("sabotage_fuel_plants", {"fuel_plants": fuel_plant_damage or 0}),
            }.get(operation)
            if damage_done and any(damage_done[1].values()):
                uat.record_action(attacker_empire, target_kd, kd_id, damage_done[0], damage_done[1])

        if (
            attacker_empire is not None
            and defender_empire is not None
            and (attacker_empire != defender_empire)
            and (operation in uas.AGGRO_OPERATIONS)
        ):
            _add_aggression(
                attacker_empire,
                defender_empire,
                uas.GAME_CONFIG["AGGRO_PER_AGGRO_SPY"],
                empires_info,
            )

        new_kd_info = {
            **kd_info_parse,
            **kd_patch_payload,
        }
        payload = {
            "status": status,
            "message": message,
        }
    except occ.Rejected as rejection:
        return None, {"message": rejection.message}, rejection.status, False
    except occ.Busy:
        return None, {"message": "Server is busy"}, 400, False
    return new_kd_info, payload, 200, success
        
@bp.route('/api/spy/<target_kd>', methods=['POST'])
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
    app = flask.current_app

    drones = int(req["drones"])
    shielded = req["shielded"]

    def decide(kd_info_parse):
        # Checked against the kingdom as it is right now: a duplicate request finds the attempt and drones gone.
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
            raise occ.Rejected(message)

        success_losses, _ = _calculate_spy_losses(
            drones,
            shielded,
            has_drone_gadgets=uas.has_project(kd_info_parse, "drone_gadgets"),
        )

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
            kd_patch_payload["fuel"] = kd_info_parse["fuel"] - _shielding_fuel(kd_info_parse, drones)
        return kd_patch_payload, (kd_info_parse, kd_patch_payload, message, status)

    try:
        kd_info_parse, kd_patch_payload, message, status = occ.update(f'/kingdom/{kd_id}', decide)

        time_now = datetime.datetime.now(datetime.timezone.utc)
        history_payload = {
            "time": time_now.isoformat(),
            "to": "",
            "operation": uas.PRETTY_NAMES.get("robprimitives", "robprimitives"),
            "news": message,
        }
        kd_spy_history_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
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
    except occ.Rejected as rejection:
        return None, {"message": rejection.message}, rejection.status
    except occ.Busy:
        return None, {"message": "Server is busy"}, 400
    return new_kd_info, payload, 200

@bp.route('/api/robprimitives', methods=['POST'])
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


@bp.route('/api/robprimitives/auto', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def auto_rob_primitives():
    req = flask.request.get_json(force=True)
    kd_id = flask_praetorian.current_user().kd_id

    if req.get("enabled", None) != None:
        enabled = req["enabled"]

        def switch(kd_info_parse):
            if kd_info_parse["auto_rob_settings"].get("drones", 0) == 0:
                raise occ.Rejected("Could not enable auto robs. You must first specify the percent of drones to send")
            return {'auto_rob_enabled': enabled}, None

        message = "Enabled auto robbing primitives" if enabled else "Disabled auto robbing primitives"
        decide = switch
    else:
        def change_settings(kd_info_parse):
            current_settings = kd_info_parse['auto_rob_settings']
            req_settings = {
                "drones": float(req.get("drones") or (current_settings.get("drones", 0) * 100)) / 100,
                "keep": int(req.get("keep") or current_settings.get("keep", 0)),
                "shielded": bool(req.get("shielded", current_settings.get("shielded", False))),
            }
            new_settings = {**current_settings, **req_settings}
            valid_settings, message = _validate_auto_rob_settings(new_settings)
            if not valid_settings:
                raise occ.Rejected(message)
            return {'auto_rob_settings': new_settings}, None

        message = "Updated auto attack settings"  # sic: the message the page has always shown
        decide = change_settings

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return (flask.jsonify({"message": rejection.message}), rejection.status)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
    except (TypeError, ValueError):
        return (flask.jsonify({"message": "The settings must be numbers"}), 400)
    return (flask.jsonify({"message": message, "status": "success"}), 200)

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
    options["autofill_buffer"] = float(options["autofill_buffer"] or 0) / 100
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
    

@bp.route('/api/schedule', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def add_schedule():
    app = flask.current_app
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    

    schedule_type = req.get("type")
    schedule_time = uas.utc(req["time"]).isoformat()
    schedule_options = req.get("options", {})
    schedule_id = str(uuid.uuid4())

    def decide(kd_info):
        state = uag._get_state()

        if uas.utc(schedule_time) < uas.utc(state["state"]["game_start"]) or uas.utc(schedule_time) > uas.utc(state["state"]["game_end"]):
            raise occ.Rejected("Scheduled time occurs outside of game duration")

        if len(kd_info["schedule"]) >= 10:
            raise occ.Rejected("You can not schedule more than 10 actions")

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
            options=copy.deepcopy(schedule_options),  # the handlers rescale the options, so a rerun must start fresh
            kd_info=kd_info,
        )
        if not scheduled:
            raise occ.Rejected(message)

        schedule_payload = kd_info["schedule"]
        schedule_payload.append(new_schedule)
        schedule_payload_sorted = sorted(schedule_payload, key=lambda item: uas.utc(item["time"]))

        return {"schedule": schedule_payload_sorted}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Rejected as rejection:
        return flask.jsonify({"message": rejection.message}), rejection.status
    except occ.Busy:
        return flask.jsonify({"message": "Server is busy"}), 400

    return (flask.jsonify({"message": "Successfully scheduled", "status": "success"}), 200)

@bp.route('/api/schedule/cancel', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def cancel_schedule():
    app = flask.current_app
    req = flask.request.get_json(force=True)

    kd_id = flask_praetorian.current_user().kd_id
    
    
    schedule_id = req.get("id")

    def decide(kd_info):
        new_schedule = [
            item
            for item in kd_info["schedule"]
            if item["id"] != schedule_id
        ]
        return {"schedule": new_schedule}, None

    try:
        occ.update(f'/kingdom/{kd_id}', decide)
    except occ.Busy:
        return (flask.jsonify({"message": "Server is busy"}), 400)
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
    damage_multiplier=1.0,
):
    if fuzi:
        adjusted_shields = min(defender_shields, 0.5)
    else:
        adjusted_shields = defender_shields
    damage_categories = {"stars_damage", "fuel_damage", "pop_damage"}
    damage = {}
    for damage_category in damage_categories:
        damage[damage_category] = sum([
            math.floor(value_missiles * uas.MISSILES[key_missile].get(damage_category) * (1 - adjusted_shields) * damage_multiplier)
            for key_missile, value_missiles in attacker_missiles.items()
        ])
    return damage
    

def _missile_damage_multiplier(kd_info):
    """How much of its missiles' damage this kingdom deals: 1 is the base damage."""
    return 1 + int(uas.has_project(kd_info, "fuzi_capstone")) * uas.GAME_CONFIG["FUZI_CAPSTONE_MISSILE_DAMAGE_INCREASE"]


@bp.route('/api/calculatemissiles/<target_kd>', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def calculate_missiles(target_kd):
    app = flask.current_app
    req = flask.request.get_json(force=True)
    attacker_raw_values = req["attackerValues"]

    kd_id = flask_praetorian.current_user().kd_id
    if str(target_kd) == str(kd_id):
        return (flask.jsonify({"message": "You cannot attack yourself!"}), 400)

    
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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
        damage_multiplier=_missile_damage_multiplier(kd_info_parse),
    )

    message = f"The missiles will destroy " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

    payload = {
        "message": message,
        # The same damage as numbers, so the page can show it without parsing the sentence.
        "damage": {key.replace('_damage', ''): value for key, value in missile_damage.items()},
        "shields_assumed": defender_shields,
    }
    return (flask.jsonify(payload), 200)         
    
def _launch_missiles(req, kd_id, target_kd):

    app = flask.current_app
    galaxies_inverted, _ = uag._get_galaxies_inverted()

    attacker_galaxy = galaxies_inverted[kd_id]
    defender_galaxy = galaxies_inverted[target_kd]

    
    try:
        attacker_raw_values = req["attackerValues"]
        
        kd_info_parse = occ.read(f'/kingdom/{kd_id}')

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
        
        max_target_kd_info = occ.read(f'/kingdom/{target_kd}')
        if max_target_kd_info["status"].lower() == "dead":
            return kd_info_parse, {"message": "You can't attack this kingdom because they are dead!"}, 400

        def launch(kd):
            # The missiles leave under a version check, so a duplicate request finds them gone.
            valid, launch_message = _validate_missiles_request(attacker_missiles, kd)
            if not valid:
                raise occ.Rejected(launch_message)
            return {"missiles": {k: v - attacker_missiles.get(k, 0) for k, v in kd["missiles"].items()}}, None

        def strike(target):
            # The damage is worked out against the target as it is when the write lands.
            if target["status"].lower() == "dead":
                raise occ.Rejected("You can't attack this kingdom because they are dead!")
            damage = _calculate_missiles_damage(
                attacker_missiles,
                target["shields"]["missiles"],
                fuzi=kd_info_parse["race"] == "Fuzi",
                damage_multiplier=_missile_damage_multiplier(kd_info_parse),
            )
            target_stars = target["stars"] - damage["stars_damage"]
            target_pop = target["population"] - damage["pop_damage"]
            changes = {
                "stars": max(target_stars, 0),
                "population": target_pop,
                "fuel": target["fuel"] - damage["fuel_damage"],
                "projects_max_points": uas.projects_max_points(max(target_stars, 0)),
            }
            if target_stars <= 0 or target_pop <= 0:
                changes["status"] = "Dead"
            # What was really destroyed (a strike can not take more than there is), for an empire target's points.
            destroyed = {
                "stars": target["stars"] - changes["stars"],
                "population": min(damage["pop_damage"], max(target["population"], 0)),
                "fuel": damage["fuel_damage"],
            }
            return changes, (damage, changes, destroyed)

        def give_back_missiles(kd):
            return {"missiles": {k: v + attacker_missiles.get(k, 0) for k, v in kd["missiles"].items()}}, None

        occ.update(f'/kingdom/{kd_id}', launch, document=kd_info_parse)
        try:
            missile_damage, defender_patch_payload, destroyed = occ.update(f'/kingdom/{target_kd}', strike, document=max_target_kd_info)
        except BaseException:
            occ.update(f'/kingdom/{kd_id}', give_back_missiles)
            raise
        empires_inverted, empires_info, _, _ = uag._get_empires_inverted()
        attacker_empire = empires_inverted.get(kd_id)
        if uat.counts(empires_info, attacker_empire, target_kd, empires_inverted):
            # On one of the empire's targets, every star the missiles destroy goes into its spoils fund.
            uat.record_action(attacker_empire, target_kd, kd_id, "missiles", destroyed,
                              fund={"stars": destroyed["stars"], "money": 0})
        if defender_patch_payload.get("status") == "Dead":
            uam._mark_kingdom_death(target_kd, killer=kd_id)
        kd_patch_payload = {
            "missiles": {
                k: v - attacker_missiles.get(k, 0)
                for k, v in kd_info_parse["missiles"].items()
            }
        }

        message = f"Your missiles destroyed " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])
        defender_message = f"Missiles from {kd_info_parse['name']} have destroyed " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

        time_now = datetime.datetime.now(datetime.timezone.utc)
        target_news_payload = {
            "time": time_now.isoformat(),
            "from": kd_id,
            "news": defender_message,
            "kind": "missiles",
        }
        target_news_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{target_kd}/news',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(target_news_payload),
        )
        uam._add_notifs(target_kd, ["news_kingdom"])
        history_payload = {
            "time": time_now.isoformat(),
            "to": target_kd,
            "news": message,
        }
        kd_missile_history_patch_response = REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missilehistory',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(history_payload, default=str),
        )

        attacker_galaxy_payload = {
            "time": time_now.isoformat(),
            "from": kd_id,
            "to": target_kd,
            "kind": "missiles",
        }
        defender_galaxy_payload = {
            "time": time_now.isoformat(),
            "from": kd_id,
            "to": target_kd,
            "kind": "missiles",
        }
        attacker_galaxy_payload["news"] = f"{kd_info_parse['name']} launched missiles at {max_target_kd_info['name']} and destroyed " + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

        defender_galaxy_payload["news"] = f"{max_target_kd_info['name']} was struck by missiles from {kd_info_parse['name']} and lost "  + ', '.join([f"{value} {key.replace('_damage', '')}" for key, value in missile_damage.items()])

        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{attacker_galaxy}/news',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(attacker_galaxy_payload),
        )
        REQUESTS_SESSION.patch(
            app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{defender_galaxy}/news',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps(defender_galaxy_payload),
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
    except occ.Rejected as rejection:
        return None, {"message": rejection.message}, rejection.status
    except occ.Busy:
        return None, {"message": "Server is busy"}, 400
    return new_kd_info, payload, 200

@bp.route('/api/launchmissiles/<target_kd>', methods=['POST'])
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

@bp.route('/api/pinned', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def update_pinned():
    app = flask.current_app
    req = flask.request.get_json(force=True)
    
    kd_id = flask_praetorian.current_user().kd_id
    
    
    pinned_patch_response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(req),
    )
    return (flask.jsonify(pinned_patch_response.text), 200)

