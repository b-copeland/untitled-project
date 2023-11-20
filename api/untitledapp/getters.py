import copy
import datetime
import json
import math
import os

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.shared as uas
from untitledapp import app, alive_required, start_required, REQUESTS_SESSION, SOCK_HANDLERS

def _get_state():
    get_response = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/state',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
    )
    get_response_json = json.loads(get_response.text)
    return get_response_json

@app.route('/api/state', methods=["GET"])
# @flask_praetorian.roles_required('verified')
def get_state():
    """
    Get state
    """    
    get_response_json = _get_state()
    start_time = datetime.datetime.fromisoformat(get_response_json["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    primitives_defense_per_star = uas.GAME_FUNCS["BASE_PRIMITIVES_DEFENSE_PER_STAR"](max(seconds_elapsed, 0))
    primitives_rob_per_drone = uas.GAME_FUNCS["BASE_PRIMITIVES_ROB_PER_DRONE"](max(seconds_elapsed, 0))
    return flask.jsonify({
        **get_response_json,
        "pretty_names": uas.PRETTY_NAMES,
        "units": uas.UNITS,
        "structures": {
            "pop_per_home": uas.GAME_CONFIG["BASE_HOMES_CAPACITY"],
            "income_per_mine": uas.GAME_CONFIG["BASE_MINES_INCOME_PER_EPOCH"],
            "fuel_per_fuel_plant": uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"],
            "fuel_cap_per_fuel_plant": uas.GAME_CONFIG["BASE_FUEL_PLANTS_CAPACITY"],
            "hangar_capacity": uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"],
            "drone_production_per_drone_plant": uas.GAME_CONFIG["BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH"],
            "missile_capacity_per_missile_silo": uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"],
            "engineers_capacity_per_workshop": uas.GAME_CONFIG["BASE_WORKSHOP_CAPACITY"],
        },
        "projects": uas.PROJECTS,
        "missiles": uas.MISSILES,
        "income_per_pop": uas.GAME_CONFIG["BASE_POP_INCOME_PER_EPOCH"],
        "fuel_consumption_per_pop": uas.GAME_CONFIG["BASE_POP_FUEL_CONSUMPTION_PER_EPOCH"],
        "primitives_defense_per_star": primitives_defense_per_star,
        "primitives_rob_per_drone": primitives_rob_per_drone,
        "aggro_operations": uas.AGGRO_OPERATIONS,
        "reveal_operations": uas.REVEAL_OPERATIONS,
        "game_config": uas.GAME_CONFIG,
        "races": uas.RACES,
        "surrender_options": uas.SURRENDER_OPTIONS,
    }), 200

def _get_scores():
    get_response = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/scores',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']},
    )
    get_response_json = json.loads(get_response.text)
    return get_response_json


def _get_scores_redacted(revealed, kd_id, galaxies_inverted):
    scores = _get_scores()

    top_nw = sorted(scores["networth"].items(), key=lambda item: -item[1])
    top_stars = sorted(scores["stars"].items(), key=lambda item: -item[1])
    top_points = sorted(scores["points"].items(), key=lambda item: -item[1])

    top_nw_redacted = []
    top_stars_redacted = []
    top_points_redacted = []
    for item in top_nw:
        if "stats" in revealed["revealed"].get(item[0], {}) or item[0] == kd_id or galaxies_inverted[item[0]] == galaxies_inverted[kd_id]:
            top_nw_redacted.append(item)
        else:
            top_nw_redacted.append(
                ("", item[1])
            )
    for item in top_stars:
        if "stats" in revealed["revealed"].get(item[0], {}) or item[0] == kd_id or galaxies_inverted[item[0]] == galaxies_inverted[kd_id]:
            top_stars_redacted.append(item)
        else:
            top_stars_redacted.append(
                ("", item[1])
            )
    for item in top_points:
        if item[0] == kd_id or galaxies_inverted[item[0]] == galaxies_inverted[kd_id]:
            top_points_redacted.append(item)
        else:
            top_points_redacted.append(
                ("", item[1])
            )
        
    top_galaxy_networth = sorted(scores["galaxy_networth"].items(), key=lambda x: -x[1])
    payload = {
        "networth": top_nw_redacted,
        "stars": top_stars_redacted,
        "points": top_points_redacted,
        "galaxy_networth": top_galaxy_networth,
    }
    return payload

@app.route('/api/scores', methods=["GET"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def get_scores():
    
    kd_id = flask_praetorian.current_user().kd_id
    revealed = _get_revealed(kd_id)
    galaxies_inverted, _ = _get_galaxies_inverted()
    scores_redacted = _get_scores_redacted(revealed, kd_id, galaxies_inverted)
    return flask.jsonify(scores_redacted), 200

@app.route('/api/kingdomid')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdomid():
    kd_id = flask_praetorian.current_user().kd_id
    kd_created = flask_praetorian.current_user().kd_created
    if kd_id == None:
        return flask.jsonify({"kd_id": "", "created": kd_created}), 200
    
    return flask.jsonify({"kd_id": kd_id, "created": kd_created}), 200

@app.route('/api/kingdom')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdom():
    kd_id = flask_praetorian.current_user().kd_id
    app.logger.info('Fetching kingdom %s', kd_id)

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    return (flask.jsonify(kd_info_parse), 200)


@app.route('/api/shields')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def shields():
    return {
        "desc": {
            "military": {
                "max": uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"],
                "cost": uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT"],
            },
            "spy": {
                "max": uas.GAME_CONFIG["BASE_SPY_SHIELDS_MAX"],
                "cost": uas.GAME_CONFIG["BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT"],
            },
            "spy_radar": {
                "max": uas.GAME_CONFIG["BASE_SPY_RADAR_MAX"],
                "cost": uas.GAME_CONFIG["BASE_SPY_RADAR_COST_PER_LAND_PER_PCT"],
            },
            "missiles": {
                "max": uas.GAME_CONFIG["BASE_MISSILES_SHIELDS_MAX"],
                "cost": uas.GAME_CONFIG["BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT"],
            },
        }
    }

@app.route('/api/news')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def news():
    kd_id = flask_praetorian.current_user().kd_id
    
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)

@app.route('/api/messages')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def messages():
    kd_id = flask_praetorian.current_user().kd_id
    
    messages = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/messages',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    messages_parse = json.loads(messages.text)
    return (flask.jsonify(messages_parse["messages"]), 200)

def _get_kingdoms():
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdoms',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    return kd_info_parse["kingdoms"]

@app.route('/api/kingdoms')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdoms():
    kingdoms = _get_kingdoms()
    return (flask.jsonify(kingdoms), 200)

def _get_galaxy_info():
    galaxy_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxies',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    galaxy_info_parse = json.loads(galaxy_info.text)
    
    return galaxy_info_parse["galaxies"]




@app.route('/api/galaxies')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxies():
    galaxy_info = _get_galaxy_info()
    return (flask.jsonify(galaxy_info), 200)

def _get_galaxies_inverted():
    galaxy_info = _get_galaxy_info()

    galaxies_inverted = {}
    for galaxy_name, kd_list in galaxy_info.items():
        for kd in kd_list:
            galaxies_inverted[kd] = galaxy_name
    return galaxies_inverted, galaxy_info

@app.route('/api/galaxies_inverted')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxies_inverted():
    galaxies_inverted, _ = _get_galaxies_inverted()
    return (flask.jsonify(galaxies_inverted), 200)

def _get_empire_info():
    empire_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empires',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    empire_info_parse = json.loads(empire_info.text)
    
    return empire_info_parse


def _get_empires_inverted():
    empire_infos = _get_empire_info()
    galaxy_info = _get_galaxy_info()

    galaxy_empires = {}
    empires_inverted = {}
    for empire_id, empire_info in empire_infos["empires"].items():
        for galaxy in empire_info["galaxies"]:
            galaxy_empires[galaxy] = empire_id
            galaxy_kds = galaxy_info[galaxy]
            for galaxy_kd in galaxy_kds:
                empires_inverted[galaxy_kd] = empire_id
    return empires_inverted, empire_infos, galaxy_empires, galaxy_info

@app.route('/api/empires')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empires():
    empires = _get_empire_info()
    return (flask.jsonify(empires["empires"]), 200)

@app.route('/api/empires_inverted')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empires_inverted():
    empires_inverted, _, galaxy_empires, _ = _get_empires_inverted()
    payload = {
        "empires_inverted": empires_inverted,
        "galaxy_empires": galaxy_empires
    }
    return (flask.jsonify(payload), 200)

def _get_empire_politics(empire_id):
    empire_politics = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{empire_id}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    empire_politics_parse = json.loads(empire_politics.text)
    
    return empire_politics_parse

@app.route('/api/empirepolitics')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empire_politics():
    kd_id = flask_praetorian.current_user().kd_id
    empires_inverted, _, _, _ = _get_empires_inverted()
    kd_empire = empires_inverted.get(kd_id)
    if not kd_empire:
        return flask.jsonify({}), 200
    
    empire_politics = _get_empire_politics(kd_empire)
    return (flask.jsonify(empire_politics), 200)

@app.route('/api/galaxynews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy_news():
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy = galaxies_inverted[kd_id]
    
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


@app.route('/api/empirenews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empire_news():
    kd_id = flask_praetorian.current_user().kd_id
    
    empires_inverted, _, _, _ = _get_empires_inverted()
    try:
        kd_empire = empires_inverted[kd_id]
    except KeyError:
        return (flask.jsonify([]), 200)
    
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/news',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


@app.route('/api/universenews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def universe_news():
    news = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)



@app.route('/api/attackhistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def attack_history():
    kd_id = flask_praetorian.current_user().kd_id
    
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["attack_history"]), 200)


@app.route('/api/spyhistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def spy_history():
    kd_id = flask_praetorian.current_user().kd_id
    
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["spy_history"]), 200)


@app.route('/api/missilehistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def missile_history():
    kd_id = flask_praetorian.current_user().kd_id
    
    history = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missilehistory',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["missile_history"]), 200)


def _calc_units(
    start_time,
    current_units,
    generals_units,
    mobis_units,
):
    units = {
        "current": {k: v for k, v in current_units.items() if k in uas.UNITS.keys()}
    }
    for i_general, general in enumerate(generals_units):
        units[f"general_{i_general}"] = general

    current_total = {
        key: 0
        for key in uas.UNITS.keys()
    }
    for dict_units in units.values():
        for key_unit in uas.UNITS.keys():
            current_total[key_unit] += dict_units.get(key_unit, 0)

    units["current_total"] = current_total

    for hours in [1, 2, 4, 8, 24]:
        hour_units = {
            key: 0
            for key in uas.UNITS.keys()
        }
        max_time = start_time + datetime.timedelta(hours=hours)
        for mobi in mobis_units:
            
            
            
            if datetime.datetime.fromisoformat(mobi["time"]).astimezone(datetime.timezone.utc) < max_time:
                for key_unit in hour_units.keys():
                    hour_units[key_unit] += mobi.get(key_unit, 0)

        units[f"hour_{hours}"] = hour_units
    return units

def _calc_max_offense(
    unit_dict,
    military_bonus=0.25,
    other_bonuses=0.0,
    generals=4,
    fuelless=False,
    lumina=False,
    denounced=False,
    war=False,
    surprise_war_penalty=False,
):
    int_fuelless = int(fuelless)
    int_lumina = int(lumina)
    if war:
        int_denounced = 0
    else:
        int_denounced = int(denounced)
    int_war = int(war)
    if war:
        int_surprise_war_penalty = 0
    else:
        int_surprise_war_penalty = int(surprise_war_penalty)
    raw_attack = sum([
        stat_map["offense"] * unit_dict.get(key, 0)
        for key, stat_map in uas.UNITS.items() 
    ])
    attack_w_bonuses = raw_attack * (
        1
        + uas.GAME_FUNCS["BASE_GENERALS_BONUS"](generals)
        + military_bonus
        + other_bonuses
        - (int_fuelless * uas.GAME_CONFIG["BASE_FUELLESS_STRENGTH_REDUCTION"])
        - (int_lumina * uas.GAME_CONFIG["LUMINA_OFFENSE_REDUCTION"])
        + (int_denounced * uas.GAME_CONFIG["DENOUNCE_OFFENSE_BONUS"])
        + (int_war * uas.GAME_CONFIG["WAR_OFFENSE_INCREASE"])
        + (int_surprise_war_penalty * uas.GAME_CONFIG["SURPRISE_WAR_PENALTY_OFFENSE_INCREASE"])
    )
    return math.floor(attack_w_bonuses)

def _calc_max_defense(
    unit_dict,
    military_bonus=0.25,
    other_bonuses=0.0,
    shields=0.10,
    fuelless=False,
    gaian=False,
    peace=False
):

    int_fuelless = int(fuelless)
    int_gaian = int(gaian)
    int_peace = int(peace)
    raw_defense = sum([
        stat_map["defense"] * unit_dict.get(key, 0)
        for key, stat_map in uas.UNITS.items() 
    ])
    defense_w_bonuses = raw_defense * (
        1
        + shields
        + military_bonus
        + other_bonuses
        - (int_fuelless * uas.GAME_CONFIG["BASE_FUELLESS_STRENGTH_REDUCTION"])
        - (int_gaian * uas.GAME_CONFIG["GAIAN_DEFENSE_REDUCTION"])
        + (int_peace * uas.GAME_CONFIG["PEACE_DEFENSE_BONUS"])
    )
    return math.floor(defense_w_bonuses)

def _calc_maxes(
    units,
    kd_info_parse,
):
    maxes = {}
    maxes["defense"] = {
        type_max: _calc_max_defense(type_units, gaian=kd_info_parse["race"] == "Gaian")
        for type_max, type_units in units.items() 
    }
    maxes["offense"] = {
        type_max: _calc_max_offense(type_units, lumina=kd_info_parse["race"] == "Lumina")
        for type_max, type_units in units.items() 
    }
    return maxes

def _calc_hangar_capacity(kd_info, units):
    max_hangar_capacity = math.floor(kd_info["structures"]["hangars"]) * uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"]
    current_hangar_capacity = sum([
        stat_map["hangar_capacity"] * (units["current_total"].get(key, 0) + units["hour_24"].get(key, 0))
        for key, stat_map in uas.UNITS.items()
    ])
    return max_hangar_capacity, current_hangar_capacity

def _calc_max_recruits(kd_info, units):
    recruits_training = units["hour_24"]["recruits"]
    max_total_recruits = uas.GAME_FUNCS["BASE_MAX_RECRUITS"](int(kd_info["population"]))
    max_available_recruits = max(max_total_recruits - recruits_training, 0)
    max_recruits_cost = uas.GAME_CONFIG["BASE_RECRUIT_COST"] * max_available_recruits
    try:
        current_available_recruits = min(
            math.floor((kd_info["money"] / max_recruits_cost) * max_available_recruits),
            max_available_recruits,
        )
    except ZeroDivisionError:
        current_available_recruits = 0
    return max_available_recruits, current_available_recruits

def _calc_recruit_time(is_conscription, time_multiplier):
    return uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier * (1 - int(is_conscription) * uas.GAME_CONFIG["BASE_CONSCRIPTION_TIME_REDUCTION"])

def _get_units_adjusted_costs(state):
    is_unregulated = "Unregulated" in state["state"]["active_policies"]
    is_treatied = "Treatied" in state["state"]["active_policies"]
    
    cost_modifier = 1.0 - is_unregulated * uas.GAME_CONFIG["BASE_UNREGULATED_COST_REDUCTION"] + is_treatied * uas.GAME_CONFIG["BASE_TREATIED_COST_INCREASE"]
    units_desc = copy.deepcopy(uas.UNITS)
    for unit, unit_dict in units_desc.items():
        if "cost" in unit_dict:
            unit_dict["cost"] = unit_dict["cost"] * cost_modifier

    return units_desc

def _get_mobis_queue(kd_id):
    mobis_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    mobis_info_parse = json.loads(mobis_info.text)
    return mobis_info_parse["mobis"]

def _get_mobis(kd_id):
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    mobis_info_parse = _get_mobis_queue(kd_id)
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_units = mobis_info_parse

    state = _get_state()

    start_time = max(
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    )
    units = _calc_units(start_time, current_units, generals_units, mobis_units)
    maxes = _calc_maxes(units, kd_info_parse)

    top_queue = sorted(
        mobis_info_parse,
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(mobis_info_parse)

    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_conscription = "Conscription" in galaxy_policies["active_policies"]
    recruit_time = _calc_recruit_time(is_conscription, (uas.GAME_CONFIG["BASE_RECRUIT_TIME_MIN_MULTIPLIER"] + uas.GAME_CONFIG["BASE_RECRUIT_TIME_MAX_MUTLIPLIER"]) / 2)

    units_adjusted_costs = _get_units_adjusted_costs(state)

    max_hangar_capacity, current_hangar_capacity = _calc_hangar_capacity(kd_info_parse, units)
    max_available_recruits, current_available_recruits = _calc_max_recruits(kd_info_parse, units)
    payload = {
        'units': units,
        'maxes': maxes,
        'recruit_price': uas.GAME_CONFIG["BASE_RECRUIT_COST"],
        'recruit_time': recruit_time,
        'max_hangar_capacity': max_hangar_capacity,
        'current_hangar_capacity': current_hangar_capacity,
        'max_available_recruits': max_available_recruits,
        'current_available_recruits': current_available_recruits,
        'units_desc': units_adjusted_costs,
        'top_queue': top_queue,
        'len_queue': len_queue,
        'is_conscription': is_conscription,
        }
    return payload

@app.route('/api/mobis', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def mobis():
    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_mobis(kd_id)
    return (flask.jsonify(payload), 200)


def _calc_structures(
    start_time,
    current_structures,
    building_structures,
    epochs=[1, 2, 4, 8, 24]
):
    structures = {
        "current": {k: current_structures.get(k, 0) for k in uas.STRUCTURES}
    }

    for hours in epochs:
        epoch_seconds = hours * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
        hour_structures = {
            key: 0
            for key in uas.STRUCTURES
        }
        max_time = start_time + datetime.timedelta(seconds=epoch_seconds)
        for building_structure in building_structures:
            if datetime.datetime.fromisoformat(building_structure["time"]).astimezone(datetime.timezone.utc) < max_time:
                for key_structure in hour_structures.keys():
                    hour_structures[key_structure] += building_structure.get(key_structure, 0)

        structures[f"hour_{hours}"] = hour_structures
    return structures

def _get_structure_price(kd_info):
    return uas.GAME_FUNCS["BASE_STRUCTURE_COST"](int(kd_info["stars"]))

def _calc_available_structures(structure_price, kd_info, structures_info):
    total_structures = math.ceil(sum(structures_info["current"].values()) + sum(structures_info["hour_24"].values()))
    max_available_structures = max(int(kd_info["stars"]) - total_structures, 0)
    max_structures_cost = structure_price * max_available_structures
    try:
        current_available_structures = min(
            math.floor((kd_info["money"] / max_structures_cost) * max_available_structures),
            max_available_structures,
        )
    except ZeroDivisionError:
        current_available_structures = 0
    return max_available_structures, current_available_structures


def _get_structures_info(kd_id):
    
    structures_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    structures_info_parse = json.loads(structures_info.text)

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    top_queue = sorted(
        structures_info_parse["structures"],
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(structures_info_parse["structures"])

    current_price = _get_structure_price(kd_info_parse)
    current_structures = kd_info_parse["structures"]
    building_structures = structures_info_parse["structures"]

    state = _get_state()

    start_time = max(
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    )
    structures = _calc_structures(start_time, current_structures, building_structures)

    max_available_structures, current_available_structures = _calc_available_structures(current_price, kd_info_parse, structures)

    payload = {
        **structures,
        "price": current_price,
        "max_available_structures": max_available_structures,
        "current_available_structures": current_available_structures,
        "top_queue": top_queue,
        "len_queue": len_queue,
    }
    return payload


@app.route('/api/structures', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def structures():
    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_structures_info(kd_id)

    return (flask.jsonify(payload), 200)


def _get_kd_info(kd_id):
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    return kd_info_parse


def _get_max_kd_info(other_kd_id, kd_id, revealed_info, max=False, galaxies_inverted=None):
    if galaxies_inverted == None:
        galaxies_inverted, _ = _get_galaxies_inverted()
    always_allowed_keys = {"name", "race", "status", "coordinate"}
    allowed_keys = {
        "stats": ["stars", "networth"],
        "kingdom": ["stars", "fuel", "population", "networth", "money", "missiles"],
        "military": ["units", "generals_available", "generals_out"],
        "structures": ["structures"],
        "shields": ["shields"],
        "projects": ["projects_points", "projects_max_points", "projects_assigned", "completed_projects"],
        "drones": ["drones", "spy_attempts"],
    }
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{other_kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    if max:
        return kd_info_parse

    if other_kd_id in revealed_info["revealed_galaxymates"]:
        return kd_info_parse
    
    revealed_categories = revealed_info["revealed"].get(other_kd_id, {}).keys()
    kingdom_info_keys = always_allowed_keys
    for revealed_category in revealed_categories:
        kingdom_info_keys = kingdom_info_keys.union(allowed_keys[revealed_category])

    if galaxies_inverted[other_kd_id] == galaxies_inverted[kd_id]:
        kingdom_info_keys = kingdom_info_keys.union(allowed_keys["stats"])

    kd_info_parse_allowed = {
        k: v
        for k, v in kd_info_parse.items()
        if k in kingdom_info_keys
    }
    if "projects_points" in kd_info_parse_allowed:
        kd_info_parse_allowed["max_bonuses"] = {
            project: project_dict.get("max_bonus", 0)
            for project, project_dict in uas.PROJECTS.items()
            if "max_bonus" in project_dict
        }
        kd_info_parse_allowed["current_bonuses"] = {
            project: project_dict.get("max_bonus", 0) * min(kd_info_parse_allowed["projects_points"][project] / kd_info_parse_allowed["projects_max_points"][project], 1.0)
            for project, project_dict in uas.PROJECTS.items()
            if "max_bonus" in project_dict
        }
        kd_info_parse_allowed["engineers"] = kd_info_parse["units"]["engineers"]
        try:
            kd_info_parse_allowed["units"]["engineers"] = kd_info_parse["units"]["engineers"]
        except KeyError:
            kd_info_parse_allowed["units"] = {
                "engineers": kd_info_parse["units"]["engineers"]
            }
    return kd_info_parse_allowed


@app.route('/api/kingdom/<other_kd_id>', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def max_kingdom(other_kd_id):
    kd_id = flask_praetorian.current_user().kd_id
    

    revealed_info = _get_revealed(kd_id)
    max_kd_info = _get_max_kd_info(other_kd_id, kd_id, revealed_info)

    return (flask.jsonify(max_kd_info), 200)


@app.route('/api/galaxy/<galaxy>', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy(galaxy):
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxies_inverted, galaxy_info = _get_galaxies_inverted()
    current_galaxy_kingdoms = galaxy_info[galaxy]
    galaxy_kd_info = _get_max_kingdoms(kd_id, current_galaxy_kingdoms)  
    

    return (flask.jsonify(galaxy_kd_info), 200)

def _get_settle_queue(kd_id):
    settle_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    settle_info_parse = json.loads(settle_info.text)
    return settle_info_parse["settles"]


def _get_settle_price(kd_info, is_expansionist):
    return (
        uas.GAME_FUNCS["BASE_SETTLE_COST"](int(kd_info["stars"]))
        * (
            1
            - (int(is_expansionist) * uas.GAME_CONFIG["BASE_EXPANSIONIST_SETTLE_REDUCTION"])
            - (int(kd_info["race"] == "Gaian") * uas.GAME_CONFIG["GAIAN_SETTLE_COST_REDUCTION"])
        )
    )

def _get_settle_time(kd_info, time_multiplier):
    seconds = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier * (
        1 - (int(kd_info["race"] == "Gaian") * uas.GAME_CONFIG["GAIAN_SETTLE_TIME_REDUCTION"])
    )
    return seconds

def _get_available_settle(kd_info, settle_info, is_expansionist):
    max_settle = uas.GAME_FUNCS["BASE_MAX_SETTLE"](int(kd_info["stars"]))
    current_settle = sum([
        int(settle_item["amount"])
        for settle_item in settle_info
    ])
    max_available_settle = max(max_settle - current_settle, 0)
    current_settle_cost = _get_settle_price(kd_info, is_expansionist)
    max_settle_cost = current_settle_cost * max_available_settle
    try:
        current_available_settle = min(
            math.floor((kd_info["money"] / max_settle_cost) * max_available_settle),
            max_available_settle,
        )
    except ZeroDivisionError:
        current_available_settle = 0
    return max_available_settle, current_available_settle



def _get_settle(kd_id):
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    settle_info = _get_settle_queue(kd_id)

    top_queue = sorted(
        settle_info,
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(settle_info)

    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy_policies, _ = _get_galaxy_politics(kd_id, galaxies_inverted[kd_id])
    is_expansionist = "Expansionist" in galaxy_policies["active_policies"]
    settle_price = _get_settle_price(kd_info_parse, is_expansionist)
    max_settle, available_settle = _get_available_settle(kd_info_parse, settle_info, is_expansionist)
    avg_settle_time = (
        uas.GAME_CONFIG["BASE_SETTLE_TIME_MIN_MULTIPLIER"]
        + uas.GAME_CONFIG["BASE_SETTLE_TIME_MAX_MUTLIPLIER"]
    ) / 2
    settle_time = _get_settle_time(
        kd_info_parse, 
        avg_settle_time,
    )

    payload = {
        "settle_price": settle_price,
        "settle_time": settle_time,
        "max_available_settle": max_settle,
        "current_available_settle": available_settle,
        "top_queue": top_queue,
        "len_queue": len_queue,
    }
    return payload


@app.route('/api/settle', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def get_settle():
    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_settle(kd_id)
    return (flask.jsonify(payload), 200)


def _get_missiles_info(kd_id):
    missiles_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    missiles_info_parse = json.loads(missiles_info.text)
    return missiles_info_parse["missiles"]

def _get_missiles_building(missiles_info):
    missiles_building = {
        k: 0
        for k in uas.MISSILES
    }
    for missile_queue in missiles_info:
        for key_missile, amt_missile in missile_queue.items():
            if key_missile != "time":
                missiles_building[key_missile] += amt_missile
    return missiles_building


@app.route('/api/missiles', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def missiles():
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    missiles_info = _get_missiles_info(kd_id)
    top_queue = sorted(
        missiles_info,
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(missiles_info)
    missiles_building = _get_missiles_building(missiles_info)

    current_missiles = kd_info_parse["missiles"]

    max_available_missiles = math.floor(kd_info_parse["structures"]["missile_silos"]) * math.floor(
        uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"]
        * (
            1
            + int(kd_info_parse["race"] == "Fuzi") * uas.GAME_CONFIG["FUZI_MISSILE_SILO_CAPACITY_INCREASE"]
        )
    )

    cost_modifier = (
        1
        - int(kd_info_parse["race"] == "Fuzi") * uas.GAME_CONFIG["FUZI_MISSILE_COST_REDUCTION"]
    )

    payload = {
        "current": current_missiles,
        "building": missiles_building,
        "build_time": uas.GAME_CONFIG["BASE_MISSILE_TIME_MULTIPLER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"],
        "capacity": max_available_missiles,
        "desc": uas.MISSILES,
        "top_queue": top_queue,
        "len_queue": len_queue,
        "cost_modifier": cost_modifier,
    }

    return (flask.jsonify(payload), 200)


def _get_engineers_queue(kd_id):
    engineers_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    engineers_info_parse = json.loads(engineers_info.text)
    return engineers_info_parse["engineers"]

def _calc_workshop_capacity(kd_info, engineers_building):
    max_workshop_capacity = math.floor(kd_info["structures"]["workshops"]) * math.floor(
        uas.GAME_CONFIG["BASE_WORKSHOP_CAPACITY"]
        * (
            1
            - int(kd_info["race"] == "Xo") * uas.GAME_CONFIG["XO_WORKSHOP_CAPACITY_REDUCTION"]
        )
    )
    current_engineers = kd_info["units"]["engineers"]
    current_workshop_capacity = current_engineers + engineers_building
    return max_workshop_capacity, current_workshop_capacity

def _calc_max_engineers(kd_info, engineers_building, max_workshop_capacity):
    engineers_total = kd_info["units"]["engineers"] + engineers_building
    available_workshop_capacity = max(max_workshop_capacity - engineers_total, 0)
    max_trainable_engineers = uas.GAME_FUNCS["BASE_MAX_ENGINEERS"](int(kd_info["population"]))
    untrained_engineers = max(max_trainable_engineers - engineers_building, 0)
    max_available_engineers = min(available_workshop_capacity, untrained_engineers)
    try:
        current_available_engineers = min(
            math.floor(kd_info["money"] / uas.GAME_CONFIG["BASE_ENGINEER_COST"]),
            max_available_engineers,
        )
    except ZeroDivisionError:
        current_available_engineers = 0
    return max_available_engineers, current_available_engineers


def _get_engineers(kd_id):
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    engineers_info = _get_engineers_queue(kd_id)
    engineers_building = sum([training["amount"] for training in engineers_info])
    max_workshop_capacity, current_workshop_capacity = _calc_workshop_capacity(kd_info_parse, engineers_building)
    max_available_engineers, current_available_engineers = _calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity)
    top_queue = sorted(
        engineers_info,
        key=lambda queue: queue["time"],
    )[:10]
    len_queue = len(engineers_info)

    payload = {
        'engineers_price': uas.GAME_CONFIG["BASE_ENGINEER_COST"],
        'max_workshop_capacity': max_workshop_capacity,
        'current_workshop_capacity': current_workshop_capacity,
        'max_available_engineers': max_available_engineers,
        'current_available_engineers': current_available_engineers,
        'current_engineers': kd_info_parse["units"]["engineers"],
        'engineers_building': engineers_building,
        "top_queue": top_queue,
        "len_queue": len_queue,
        }
    return payload

@app.route('/api/engineers', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def engineers():
    """
    Ret
    .. example::
       $ curl http://localhost:5000/api/protected -X GET \
         -H "Authorization: Bearer <your_token>"
    """
    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_engineers(kd_id)
    return (flask.jsonify(payload), 200)


@app.route('/api/projects', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def projects():
    kd_id = flask_praetorian.current_user().kd_id
    

    kd_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    max_bonuses = {
        project: project_dict.get("max_bonus", 0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }
    current_bonuses = {
        project: project_dict.get("max_bonus", 0) * min(kd_info_parse["projects_points"][project] / kd_info_parse["projects_max_points"][project], 1.0)
        for project, project_dict in uas.PROJECTS.items()
        if "max_bonus" in project_dict
    }
    available_engineers = kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values())

    payload = {
        "current_bonuses": current_bonuses,
        "max_bonuses": max_bonuses,
        "available_engineers": available_engineers,
    }
    return (flask.jsonify(payload), 200)


def _get_revealed(kd_id):
    revealed_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    revealed_info_parse = json.loads(revealed_info.text)
    return revealed_info_parse

@app.route('/api/revealed', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def revealed():
    kd_id = flask_praetorian.current_user().kd_id
    
    revealed_info = _get_revealed(kd_id)
    return (flask.jsonify(revealed_info), 200)

def _get_shared(kd_id):
    shared_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/shared',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    shared_info_parse = json.loads(shared_info.text)
    return shared_info_parse

@app.route('/api/shared', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def shared():
    kd_id = flask_praetorian.current_user().kd_id
    
    shared_info = _get_shared(kd_id)
    return (flask.jsonify(shared_info), 200)

def _get_pinned(kd_id):
    pinned_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    pinned_info_parse = json.loads(pinned_info.text)
    return pinned_info_parse

@app.route('/api/pinned', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def pinned():
    kd_id = flask_praetorian.current_user().kd_id
    
    pinned_info = _get_pinned(kd_id)
    return (flask.jsonify(pinned_info["pinned"]), 200)

def _get_max_kingdoms(kd_id, kingdoms):
    revealed_info = _get_revealed(kd_id)
    galaxies_inverted, _ = _get_galaxies_inverted()

    payload = {
        other_kd_id: _get_max_kd_info(other_kd_id, kd_id, revealed_info, galaxies_inverted=galaxies_inverted)
        for other_kd_id in kingdoms
    }
    return payload

@app.route('/api/kingdomsinfo', methods=['POST'])
@flask_praetorian.auth_required
@alive_required
# @flask_praetorian.roles_required('verified')
def max_kingdoms():
    req = flask.request.get_json(force=True)
    kingdoms = req["kingdoms"]

    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_max_kingdoms(kd_id, kingdoms)
    return (flask.jsonify(payload), 200)

def _get_galaxy_politics(kd_id, galaxy_id=None):
    if not galaxy_id:
        galaxies_inverted, _ = _get_galaxies_inverted()
        galaxy_id = galaxies_inverted[kd_id]
    galaxy_politics_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy_id}/politics',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    galaxy_politics_info_parse = json.loads(galaxy_politics_info.text)
    return galaxy_politics_info_parse, galaxy_id

@app.route('/api/galaxypolitics', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy_politics():
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, _ = _get_galaxy_politics(kd_id)
    payload = {
        **galaxy_votes,
        "desc": uas.GALAXY_POLICIES,
    }
    return (flask.jsonify(payload), 200)

def _get_universe_politics():
    universe_politics_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/universevotes',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    universe_politics_info_parse = json.loads(universe_politics_info.text)
    return universe_politics_info_parse


@app.route('/api/universepolitics', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def universe_politics():
    kd_id = flask_praetorian.current_user().kd_id
    
    universe_politics = _get_universe_politics()
    kd_payload = {
        "policy_1": {
            "option_1": "",
            "option_2": "",
        },
        "policy_2": {
            "option_1": "",
            "option_2": "",
        },
    }
    for policy_name, policy_options in universe_politics["votes"].items():
        for option_name, option_votes in policy_options.items():
            for vote_kd_id, votes_cast in option_votes.items():
                if kd_id == vote_kd_id:
                    kd_payload[policy_name][option_name] = votes_cast
    payload = {
        **kd_payload,
        "desc": uas.UNIVERSE_POLICIES,
    }
    return (flask.jsonify(payload), 200)

def _get_siphons_in(kd_id):
    siphons_in_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsin',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    siphons_in_info_parse = json.loads(siphons_in_info.text)
    return siphons_in_info_parse["siphons_in"]
    
def _get_siphons_out(kd_id):
    siphons_out_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsout',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    siphons_out_info_parse = json.loads(siphons_out_info.text)
    return siphons_out_info_parse["siphons_out"]

@app.route('/api/siphonsout', methods=['GET'])
@flask_praetorian.auth_required
def get_siphons_out():
    kd_id = flask_praetorian.current_user().kd_id

    siphons_out = _get_siphons_out(kd_id)
    siphons_out_redacted = [
        {
            k: v
            for k, v in item.items()
            if k != "from"
        }
        for item in siphons_out
    ]
    return flask.jsonify(siphons_out_redacted), 200
    
def _get_history(kd_id):
    history_info = REQUESTS_SESSION.get(
        os.environ['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/history',
        headers={'x-functions-key': os.environ['AZURE_FUNCTIONS_HOST_KEY']}
    )
    
    history_info_parse = json.loads(history_info.text)
    return history_info_parse["history"]

@app.route('/api/history', methods=['GET'])
@flask_praetorian.auth_required
def get_history():
    kd_id = flask_praetorian.current_user().kd_id

    history = _get_history(kd_id)
    return flask.jsonify(history), 200

    
@app.route('/api/time')
@flask_praetorian.auth_required
def get_time():
    return (flask.jsonify(datetime.datetime.now(datetime.timezone.utc).isoformat()), 200)