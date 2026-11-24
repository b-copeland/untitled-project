import copy
import bisect
import datetime
import json
import math
import os

import flask
import flask_praetorian
from flask_sock import Sock, ConnectionClosed

import untitledapp.shared as uas
import untitledapp.galaxypolicies as uagp
import untitledapp.universepolicies as uaup
from untitledapp import request_cache
import untitledapp.lastknown as uala
import untitledapp.visits as uav
from untitledapp import alive_required, start_required, REQUESTS_SESSION

bp = flask.Blueprint("getters", __name__)

def _get_shared_document(path):
    """A document every kingdom shares, read at most once per request (see request_cache.py)."""
    app = flask.current_app
    return request_cache.read(path, lambda: REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + path,
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
    ).text)


def _get_state():
    return _get_shared_document('/state')

@bp.route('/api/state', methods=["GET"])
# @flask_praetorian.roles_required('verified')
def get_state():
    """
    Get state
    """    
    get_response_json = _get_state()
    start_time = datetime.datetime.fromisoformat(get_response_json["state"]["game_start"]).astimezone(datetime.timezone.utc)
    now_time = datetime.datetime.now(datetime.timezone.utc)
    seconds_elapsed = (now_time - start_time).total_seconds()
    # As every kingdom finds them, after the universe's policies (the rob figure per kingdom is in /api/modifiers).
    everyone = _get_universe_modifiers(state=get_response_json)
    primitives_defense_per_star = uas.GAME_FUNCS["BASE_PRIMITIVES_DEFENSE_PER_STAR"](max(seconds_elapsed, 0)) * max(
        1 + uas.modifier(everyone, "primitives_defense"), 0)
    primitives_rob_per_drone = uas.GAME_FUNCS["BASE_PRIMITIVES_ROB_PER_DRONE"](max(seconds_elapsed, 0)) * max(
        1 + uas.modifier(everyone, "rob_primitives"), 0)
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
        "project_categories": uas.PROJECT_CATEGORIES,
        "missiles": uas.MISSILES,
        "income_per_pop": uas.GAME_CONFIG["BASE_POP_INCOME_PER_EPOCH"],
        "fuel_consumption_per_pop": uas.GAME_CONFIG["BASE_POP_FUEL_CONSUMPTION_PER_EPOCH"],
        "primitives_defense_per_star": primitives_defense_per_star,
        "primitives_rob_per_drone": primitives_rob_per_drone,
        "aggro_operations": uas.AGGRO_OPERATIONS,
        "reveal_operations": uas.REVEAL_OPERATIONS,
        "reveal_operation_stats": uas.REVEAL_OPERATION_STATS,  # what each reveals, for the Spy page's refusal
        "operation_projects": uas.OPERATION_PROJECTS,
        "cluster_benefits": uas.CLUSTER_BENEFITS,
        "galaxy_policies_desc": uas.GALAXY_POLICIES,  # every galaxy policy; the round plays state.galaxy_policies
        "universe_policies_desc": uas.UNIVERSE_POLICIES,
        # The objects above reach the browser with their keys sorted; this is the order the game lists them in.
        "order": {
            "units": list(uas.UNITS),
            "structures": list(uas.STRUCTURES),
            "projects": list(uas.PROJECTS),
            "project_categories": list(uas.PROJECT_CATEGORIES),
            "cluster_benefits": list(uas.CLUSTER_BENEFITS),
            "galaxy_policies": list(uas.GALAXY_POLICIES),
            "universe_policies": list(uas.UNIVERSE_POLICIES),
        },
        "operations_replaced_by_project": uas.OPERATIONS_REPLACED_BY_PROJECT,
        "game_config": uas.GAME_CONFIG,
        "races": uas.RACES,
        "surrender_options": uas.SURRENDER_OPTIONS,
    }), 200

def _round_is_over():
    """Whether the round has ended. No state document yet (a game not set up) means it has not."""
    try:
        state = _get_state()
    except ValueError:
        return False
    return bool((state or {}).get("state", {}).get("game_over"))


def _get_universe_stats():
    """The ``universe_stats`` document (the advisors' comparison of every kingdom), ``{}`` if there is none yet or it
    can not be read: the advisors then compare nothing."""
    app = flask.current_app
    response = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + '/universestats',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
    )
    if response.status_code != 200:
        return {}
    try:
        return json.loads(response.text)
    except ValueError:
        return {}


def _update_universe_stats(fields):
    """Merge ``fields`` into ``universe_stats`` (the refresh only: derived data, no version check)."""
    app = flask.current_app
    response = REQUESTS_SESSION.patch(
        app.config['AZURE_FUNCTION_ENDPOINT'] + '/universestats',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps(fields),
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Updating universe_stats failed with {response.status_code}: {response.text}")


def _get_scores():
    app = flask.current_app
    get_response = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/scores',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
    )
    get_response_json = json.loads(get_response.text)
    return get_response_json


def _get_scores_redacted(revealed, kd_id, galaxies_inverted, everything_public=False):
    scores = _get_scores()

    def mine(other_id):
        return other_id == kd_id or galaxies_inverted[other_id] == galaxies_inverted[kd_id]

    def shown(other_id, needs_reveal=True):
        if everything_public:  # the round is over: every kingdom's name and numbers are public
            return True
        if needs_reveal and "stats" in revealed["revealed"].get(other_id, {}):
            return True
        return mine(other_id)

    def redact(category, needs_reveal=True):
        ranked = sorted(scores[category].items(), key=lambda item: -item[1])
        return [item if shown(item[0], needs_reveal) else ("", item[1]) for item in ranked]

    return {
        "networth": redact("networth"),
        "stars": redact("stars"),
        "points": redact("points", needs_reveal=False),
        "galaxy_networth": sorted(scores["galaxy_networth"].items(), key=lambda x: -x[1]),
        # Missing until the first tick after this field was added.
        "galaxy_kingdoms_alive": scores.get("galaxy_kingdoms_alive", {}),
    }

@bp.route('/api/scores', methods=["GET"])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def get_scores():
    
    kd_id = flask_praetorian.current_user().kd_id
    revealed = _get_revealed(kd_id)
    galaxies_inverted, _ = _get_galaxies_inverted()
    scores_redacted = _get_scores_redacted(revealed, kd_id, galaxies_inverted, everything_public=_round_is_over())
    return flask.jsonify(scores_redacted), 200

@bp.route('/api/kingdomid')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdomid():
    # Called when the app loads, so a token from an earlier round is turned away here, not on every poll.
    from untitledapp import users
    if users.token_is_stale():
        return flask.jsonify({"message": users.STALE_MESSAGE}), 401
    kd_id = flask_praetorian.current_user().kd_id
    kd_created = flask_praetorian.current_user().kd_created
    if kd_id == None:
        return flask.jsonify({"kd_id": "", "created": kd_created}), 200
    
    return flask.jsonify({"kd_id": kd_id, "created": kd_created}), 200

@bp.route('/api/kingdom')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdom():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id

    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    return (flask.jsonify(kd_info_parse), 200)


@bp.route('/api/shields')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def shields():
    # The fuel each costs is this kingdom's, after its policies.
    modifiers = _get_modifiers(flask_praetorian.current_user().kd_id)
    return {
        "desc": {
            "military": {
                "max": uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"],
                "cost": uas.shield_fuel_per_pct("military", modifiers),
            },
            "spy": {
                "max": uas.GAME_CONFIG["BASE_SPY_SHIELDS_MAX"],
                "cost": uas.shield_fuel_per_pct("spy", modifiers),
            },
            "spy_radar": {
                "max": uas.GAME_CONFIG["BASE_SPY_RADAR_MAX"],
                "cost": uas.shield_fuel_per_pct("spy_radar", modifiers),
            },
            "missiles": {
                "max": uas.GAME_CONFIG["BASE_MISSILES_SHIELDS_MAX"],
                "cost": uas.shield_fuel_per_pct("missiles", modifiers),
            },
        }
    }

@bp.route('/api/news')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def news():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    news = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/news',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)

@bp.route('/api/messages')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def messages():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    messages = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/messages',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    messages_parse = json.loads(messages.text)
    return (flask.jsonify(messages_parse["messages"]), 200)

def _get_kingdoms():
    return _get_shared_document('/kingdoms')["kingdoms"]

@bp.route('/api/kingdoms')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def kingdoms():
    kingdoms = _get_kingdoms()
    return (flask.jsonify(kingdoms), 200)

def _get_galaxy_info():
    return _get_shared_document('/galaxies')["galaxies"]




@bp.route('/api/galaxies')
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

@bp.route('/api/galaxies_inverted')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxies_inverted():
    galaxies_inverted, _ = _get_galaxies_inverted()
    return (flask.jsonify(galaxies_inverted), 200)

def _get_empire_info():
    return _get_shared_document('/empires')


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

@bp.route('/api/empires')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empires():
    empires = _get_empire_info()
    # Each empire's ``targets`` (targets.py) is its own business: nobody else, the targets least of all, sees them.
    payload = {
        empire_id: {key: value for key, value in info.items() if key != "targets"}
        for empire_id, info in empires["empires"].items()
    }
    return (flask.jsonify(payload), 200)

@bp.route('/api/empires_inverted')
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
    app = flask.current_app
    empire_politics = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{empire_id}/politics',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    empire_politics_parse = json.loads(empire_politics.text)
    
    return empire_politics_parse

@bp.route('/api/empirepolitics')
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

@bp.route('/api/galaxynews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy_news():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxies_inverted, _ = _get_galaxies_inverted()
    galaxy = galaxies_inverted[kd_id]
    
    news = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/galaxy/{galaxy}/news',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


@bp.route('/api/empirenews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def empire_news():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    empires_inverted, _, _, _ = _get_empires_inverted()
    try:
        kd_empire = empires_inverted[kd_id]
    except KeyError:
        return (flask.jsonify([]), 200)
    
    news = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/empire/{kd_empire}/news',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)


@bp.route('/api/universenews')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def universe_news():
    app = flask.current_app
    news = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universenews',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    news_parse = json.loads(news.text)
    return (flask.jsonify(news_parse["news"]), 200)



@bp.route('/api/attackhistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def attack_history():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    history = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/attackhistory',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["attack_history"]), 200)


@bp.route('/api/spyhistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def spy_history():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    history = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/spyhistory',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    history_parse = json.loads(history.text)
    return (flask.jsonify(history_parse["spy_history"]), 200)


@bp.route('/api/missilehistory')
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def missile_history():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    history = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missilehistory',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
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

    units.update(_queue_forecast(start_time, mobis_units, uas.UNITS.keys()))
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

def _strength_now(kd_info):
    """
    The kingdom's own strength at home right now, with what it really has: its military bonus, military shields,
    fuel and race, and for offense the generals at home. ``maxes`` is the best case (full bonus and shields, every
    general); this is what an attack on it would face, and what it could send. Bonuses that depend on the other side
    (war, denouncing, peace) are left out.
    """
    units_home = {key: value for key, value in kd_info["units"].items() if key in uas.UNITS}
    military_bonus = float(uas.project_bonuses(kd_info)["military_bonus"] or 0)
    fuelless = kd_info.get("fuel", 0) <= 0
    return {
        "defense": _calc_max_defense(
            units_home,
            military_bonus=military_bonus,
            other_bonuses=0,
            shields=kd_info.get("shields", {}).get("military", 0),
            fuelless=fuelless,
            gaian=kd_info.get("race") == "Gaian",
        ),
        "offense": _calc_max_offense(
            units_home,
            military_bonus=military_bonus,
            other_bonuses=0,
            generals=int(kd_info.get("generals_available", 0) or 0),
            fuelless=fuelless,
            lumina=kd_info.get("race") == "Lumina",
        ),
    }


def _calc_hangar_capacity(kd_info, units, modifiers=None):
    """The hangar space the kingdom has (after its projects and ``modifiers``) and the space its units take."""
    max_hangar_capacity = math.floor(
        math.floor(kd_info["structures"]["hangars"])
        * (uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"] + uas.project_increase(kd_info, "hangars_bonus"))
        * max(1 + uas.modifier(modifiers, "hangar_capacity"), 0)
    )
    current_hangar_capacity = sum([
        uas.unit_hangar_space(kd_info, key) * (units["current_total"].get(key, 0) + units["queued"].get(key, 0))
        for key, stat_map in uas.UNITS.items()
    ])
    return max_hangar_capacity, current_hangar_capacity

def _recruit_price(kd_info, modifiers=None):
    """What one recruit costs this kingdom, after its projects and ``modifiers``."""
    return uas.GAME_CONFIG["BASE_RECRUIT_COST"] * max(
        1 - uas.project_bonus(kd_info, "recruit_cost_bonus") + uas.modifier(modifiers, "recruit_cost"), 0)


def _max_recruits(kd_info, modifiers=None):
    """The most recruits the kingdom can have in training at once, after its ``modifiers``."""
    return math.floor(uas.GAME_FUNCS["BASE_MAX_RECRUITS"](int(kd_info["population"]))
                      * max(1 + uas.modifier(modifiers, "recruit_cap"), 0))


def _calc_max_recruits(kd_info, units, modifiers=None):
    recruits_training = units["queued"]["recruits"]
    max_total_recruits = _max_recruits(kd_info, modifiers)
    max_available_recruits = max(max_total_recruits - recruits_training, 0)
    max_recruits_cost = _recruit_price(kd_info, modifiers) * max_available_recruits
    try:
        current_available_recruits = min(
            math.floor((kd_info["money"] / max_recruits_cost) * max_available_recruits),
            max_available_recruits,
        )
    except ZeroDivisionError:
        current_available_recruits = 0
    return max_available_recruits, current_available_recruits

def _calc_recruit_time(time_multiplier, modifiers=None):
    """Seconds drafting recruits takes for ``time_multiplier`` epochs, after the kingdom's ``modifiers``."""
    return uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier * max(1 + uas.modifier(modifiers, "recruit_time"), 0)

def _get_cluster_document(cluster_id):
    """The cluster's stored document (with its ``_etag``), read at most once per request."""
    return _get_shared_document(f'/cluster/{cluster_id}')


def _get_cluster_modifiers(kd_id, galaxy_id=None, now=None):
    """What the benefits of ``kd_id``'s cluster are worth now: effect to value, e.g. ``{"unit_cost": 0.02, ...}``."""
    import untitledapp.clusters as uacl  # clusters imports this module

    galaxies_inverted, galaxies = _get_galaxies_inverted()
    galaxy_id = galaxy_id or galaxies_inverted.get(str(kd_id))
    if galaxy_id is None:
        return {}
    cluster_id = uacl.cluster_of(galaxy_id)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cluster = uacl.advance(_get_cluster_document(cluster_id), uacl.members(galaxies, cluster_id), now)
    return uacl.modifiers(cluster, uacl.round_benefits(_get_state().get("state")))


def _round_start(state):
    """When the round starts (or started), from the state; long ago for a state with no round set up."""
    try:
        return uas.utc(state["state"]["game_start"])
    except (KeyError, TypeError, ValueError):
        return datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)


def _galaxy_policies_now(galaxy_politics, state, now):
    """A galaxy's policies as of ``now`` (``galaxypolicies.advance``), from its politics document and the state."""
    return uagp.advance(galaxy_politics, uagp.round_policies(state.get("state")), _round_start(state), now)


def _get_galaxy_policies(kd_id, galaxy_id=None, now=None):
    """``kd_id``'s galaxy's policies as of now (``galaxypolicies.advance``), and the galaxy id."""
    galaxy_politics, galaxy_id = _get_galaxy_politics(kd_id, galaxy_id)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return _galaxy_policies_now(galaxy_politics, _get_state(), now), galaxy_id


def _get_scores_shared():
    """The scores document, read at most once per request (for who leads, which some universe policies hit)."""
    return _get_shared_document('/scores')


def _get_universe_modifiers(kd_id=None, galaxy_id=None, state=None):
    """
    What the universe policies in force do to ``kd_id`` (of ``galaxy_id``), or, with no kingdom, what they do to
    everyone (the options that hit only the leaders left out).
    """
    state = state if state is not None else _get_state()
    active = uaup.active_options(state.get("state"))
    if kd_id is None:
        active = [option for option in active if not uaup.needs_scores([option])]
        return uaup.modifiers(active)
    scores = _get_scores_shared() if uaup.needs_scores(active) else None
    return uaup.modifiers(active, kd_id, galaxy_id, scores)


def _get_modifiers(kd_id, galaxy_id=None, now=None):
    """
    Everything politics does to ``kd_id`` now, as one ``{effect: signed value}`` (``shared.EFFECTS``): its galaxy's
    active policies, its cluster's benefits and the universe's policies, added up. Each source document is read at
    most once per request.
    """
    if galaxy_id is None:
        galaxy_id = _get_galaxies_inverted()[0].get(str(kd_id))
    if galaxy_id is None:
        return _get_universe_modifiers(kd_id)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    galaxy, _ = _get_galaxy_policies(kd_id, galaxy_id, now)
    return uas.add_modifiers(uagp.modifiers(galaxy), _get_cluster_modifiers(kd_id, galaxy_id, now),
                             _get_universe_modifiers(kd_id, galaxy_id))


def _get_units_adjusted_costs(state, modifiers=None):
    """``UNITS`` with each cost after the kingdom's ``modifiers`` (``_get_modifiers``: the universe's arms policy
    among them)."""
    cost_modifier = 1.0 + uas.modifier(modifiers, "unit_cost")
    units_desc = copy.deepcopy(uas.UNITS)
    for unit, unit_dict in units_desc.items():
        if "cost" in unit_dict:
            unit_modifier = cost_modifier
            if unit in uas.PURE_ATTACK_UNITS:
                unit_modifier += uas.modifier(modifiers, "pure_attack_cost")
            if unit in uas.PURE_DEFENSE_UNITS:
                unit_modifier += uas.modifier(modifiers, "pure_defense_cost")
            unit_dict["cost"] = unit_dict["cost"] * max(unit_modifier, 0)

    return units_desc

def _queue_total(queue):
    """How many items a queue holds in all: every count of every entry (an entry is its `time` and counts)."""
    return int(sum(value for entry in queue for key, value in entry.items() if key != "time"))


def _get_mobis_queue(kd_id):
    app = flask.current_app
    mobis_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/mobis',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    mobis_info_parse = json.loads(mobis_info.text)
    return mobis_info_parse["mobis"]

def _get_mobis(kd_id, kd_info=None, mobis_queue=None, state=None, modifiers=None):
    """What the Military page shows. A caller that already holds the kingdom, its mobis queue, the state or its
    modifiers (``_get_modifiers``) passes them, and only what is missing is read."""
    kd_info_parse = kd_info if kd_info is not None else _get_kd_info(kd_id)
    mobis_info_parse = mobis_queue if mobis_queue is not None else _get_mobis_queue(kd_id)
    current_units = kd_info_parse["units"]
    generals_units = kd_info_parse["generals_out"]
    mobis_units = mobis_info_parse

    if state is None:
        state = _get_state()

    start_time = max(
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.fromisoformat(state["state"]["game_start"]).astimezone(datetime.timezone.utc)
    )
    units = _calc_units(start_time, current_units, generals_units, mobis_units)
    maxes = _calc_maxes(units, kd_info_parse)

    top_queue = sorted(
        mobis_info_parse,
        key=lambda queue: uas.utc(queue["time"]),
    )[:10]
    len_queue = len(mobis_info_parse)
    total_queue = _queue_total(mobis_info_parse)

    if modifiers is None:
        modifiers = _get_modifiers(kd_id)
    recruit_time = _calc_recruit_time((uas.GAME_CONFIG["BASE_RECRUIT_TIME_MIN_MULTIPLIER"] + uas.GAME_CONFIG["BASE_RECRUIT_TIME_MAX_MUTLIPLIER"]) / 2, modifiers)
    units_adjusted_costs = _get_units_adjusted_costs(state, modifiers)

    max_hangar_capacity, current_hangar_capacity = _calc_hangar_capacity(kd_info_parse, units, modifiers)
    max_available_recruits, current_available_recruits = _calc_max_recruits(kd_info_parse, units, modifiers)
    payload = {
        'units': units,
        'maxes': maxes,
        'now': _strength_now(kd_info_parse),
        'recruit_price': _recruit_price(kd_info_parse, modifiers),
        'recruit_time': recruit_time,
        'max_hangar_capacity': max_hangar_capacity,
        'current_hangar_capacity': current_hangar_capacity,
        'max_available_recruits': max_available_recruits,
        'current_available_recruits': current_available_recruits,
        'units_desc': uas.units_for(kd_info_parse, units_adjusted_costs, modifiers),
        'top_queue': top_queue,
        'len_queue': len_queue,
        'total_queue': total_queue,
        'modifiers': modifiers,  # what the refresh's auto spending needs from here (recruit time)
        }
    return payload

@bp.route('/api/mobis', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def mobis():
    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_mobis(kd_id)
    return (flask.jsonify(payload), 200)


def _queue_forecast(start_time, queue, keys, horizons=None):
    """What a queue adds by each horizon: ``future_<n>`` for what lands within ``n`` epochs of ``start_time`` (one per
    ``QUEUE_FORECAST_EPOCHS``), and ``queued`` for everything in it, which is what limits on training or building count."""
    horizons = uas.GAME_CONFIG["QUEUE_FORECAST_EPOCHS"] if horizons is None else horizons
    # Entries in time order with running totals, so each horizon is one search instead of a pass over the queue.
    timed = sorted(((uas.utc(entry["time"]), entry) for entry in queue), key=lambda item: item[0])
    times = [entry_time for entry_time, _ in timed]
    running = {key: [0] for key in keys}
    for _, entry in timed:
        for key in keys:
            totals = running[key]
            totals.append(totals[-1] + entry.get(key, 0))
    forecast = {}
    for epochs in horizons:
        max_time = start_time + datetime.timedelta(seconds=epochs * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])
        landed = bisect.bisect_left(times, max_time)  # the entries before max_time
        forecast[f"future_{epochs}"] = {key: running[key][landed] for key in keys}
    forecast["queued"] = {key: running[key][-1] for key in keys}
    return forecast


def _calc_structures(
    start_time,
    current_structures,
    building_structures,
):
    structures = {
        "current": {k: current_structures.get(k, 0) for k in uas.STRUCTURES}
    }
    structures.update(_queue_forecast(start_time, building_structures, uas.STRUCTURES))
    return structures

def _get_structure_price(kd_info, modifiers=None):
    """The price of one structure, after the kingdom's ``modifiers``."""
    return uas.GAME_FUNCS["BASE_STRUCTURE_COST"](int(kd_info["stars"])) * max(1 + uas.modifier(modifiers, "structure_cost"), 0)

def _calc_available_structures(structure_price, kd_info, structures_info):
    total_structures = math.ceil(sum(structures_info["current"].values()) + sum(structures_info["queued"].values()))
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


def _get_structures_queue(kd_id):
    app = flask.current_app
    structures_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    return json.loads(structures_info.text)["structures"]


def _raze_return(modifiers=None):
    """The share of today's build cost razing a structure refunds, after the kingdom's ``modifiers``."""
    return uas.GAME_CONFIG["BASE_STRUCTURES_RAZE_RETURN"] * max(1 + uas.modifier(modifiers, "raze_return"), 0)


def _get_structures_info(kd_id, kd_info=None, structures_queue=None, state=None, modifiers=None):
    """What the Build page shows. A caller that already holds the kingdom, its structures queue, the state or its
    modifiers passes them, and only what is missing is read."""
    building_structures = structures_queue if structures_queue is not None else _get_structures_queue(kd_id)
    kd_info_parse = kd_info if kd_info is not None else _get_kd_info(kd_id)

    top_queue = sorted(
        building_structures,
        key=lambda queue: uas.utc(queue["time"]),
    )[:10]
    len_queue = len(building_structures)
    total_queue = _queue_total(building_structures)

    if modifiers is None:
        modifiers = _get_modifiers(kd_id)
    current_price = _get_structure_price(kd_info_parse, modifiers)
    current_structures = kd_info_parse["structures"]

    if state is None:
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
        "raze_return": _raze_return(modifiers),
        "max_available_structures": max_available_structures,
        "current_available_structures": current_available_structures,
        "top_queue": top_queue,
        "len_queue": len_queue,
        "total_queue": total_queue,
    }
    return payload


@bp.route('/api/structures', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def structures():
    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_structures_info(kd_id)

    return (flask.jsonify(payload), 200)


def _get_kd_info(kd_id):
    app = flask.current_app
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    return kd_info_parse


def _get_max_kd_info(other_kd_id, kd_id, revealed_info, max=False, galaxies_inverted=None, last_known=None):
    """
    Another kingdom as ``kd_id`` sees it: the fields of what ``revealed_info`` reveals now. With ``last_known`` (the
    caller's last-known intel, ``lastknown.read``), also ``last_known``: the snapshots of the categories not revealed
    now. ``max=True`` returns the whole kingdom, for server-side calculations only.
    """
    app = flask.current_app
    if galaxies_inverted == None:
        galaxies_inverted, _ = _get_galaxies_inverted()
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{other_kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)
    if max:
        return kd_info_parse

    if _round_is_over():  # everything about every kingdom is public once the round is over
        return kd_info_parse

    if other_kd_id in revealed_info["revealed_galaxymates"]:
        return kd_info_parse
    
    revealed_categories = set(revealed_info["revealed"].get(other_kd_id, {}).keys())
    if galaxies_inverted[other_kd_id] == galaxies_inverted[kd_id]:
        revealed_categories.add("stats")

    kd_info_parse_allowed = uas.revealed_fields(kd_info_parse, revealed_categories)
    if last_known is not None:
        snapshots = uala.visible(last_known.get(str(other_kd_id)), revealed_categories)
        if snapshots:
            kd_info_parse_allowed["last_known"] = snapshots
    return kd_info_parse_allowed


@bp.route('/api/kingdom/<other_kd_id>', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def max_kingdom(other_kd_id):
    kd_id = flask_praetorian.current_user().kd_id
    

    revealed_info = _get_revealed(kd_id)
    max_kd_info = _get_max_kd_info(other_kd_id, kd_id, revealed_info, last_known=uala.read(kd_id))

    return (flask.jsonify(max_kd_info), 200)


@bp.route('/api/galaxy/<galaxy>', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy(galaxy):
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxies_inverted, galaxy_info = _get_galaxies_inverted()
    current_galaxy_kingdoms = galaxy_info[galaxy]
    galaxy_kd_info = _get_max_kingdoms(kd_id, current_galaxy_kingdoms)  
    

    return (flask.jsonify(galaxy_kd_info), 200)

def _get_settle_queue(kd_id):
    app = flask.current_app
    settle_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/settles',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    settle_info_parse = json.loads(settle_info.text)
    return settle_info_parse["settles"]


def _get_settle_price(kd_info, modifiers=None):
    """The price of one star, after the kingdom's race, projects and ``modifiers`` (``_get_modifiers``)."""
    return (
        uas.GAME_FUNCS["BASE_SETTLE_COST"](int(kd_info["stars"]))
        * (
            1
            + uas.modifier(modifiers, "settle_cost")
            - (int(kd_info["race"] == "Gaian") * uas.GAME_CONFIG["GAIAN_SETTLE_COST_REDUCTION"])
            - uas.project_bonus(kd_info, "settle_cost_bonus")
            - (int(uas.has_project(kd_info, "xo_evolution")) * uas.GAME_CONFIG["XO_EVOLUTION_SETTLE_COST_REDUCTION"])
        )
    )

def _get_settle_time(kd_info, time_multiplier):
    seconds = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * time_multiplier * (
        1 - (int(kd_info["race"] == "Gaian") * uas.GAME_CONFIG["GAIAN_SETTLE_TIME_REDUCTION"])
    ) * (
        1 - int(uas.has_project(kd_info, "gaian_capstone")) * uas.GAME_CONFIG["GAIAN_CAPSTONE_SETTLE_TIME_REDUCTION"]
    )
    return seconds

def _get_available_settle(kd_info, settle_info, modifiers=None):
    max_settle = uas.GAME_FUNCS["BASE_MAX_SETTLE"](int(kd_info["stars"]))
    current_settle = sum([
        int(settle_item["amount"])
        for settle_item in settle_info
    ])
    max_available_settle = max(max_settle - current_settle, 0)
    current_settle_cost = _get_settle_price(kd_info, modifiers)
    max_settle_cost = current_settle_cost * max_available_settle
    try:
        current_available_settle = min(
            math.floor((kd_info["money"] / max_settle_cost) * max_available_settle),
            max_available_settle,
        )
    except ZeroDivisionError:
        current_available_settle = 0
    return max_available_settle, current_available_settle



def _get_settle(kd_id, kd_info=None, settle_queue=None, modifiers=None):
    """What the Settle page shows. A caller that already holds the kingdom, its settle queue or its modifiers
    (``_get_modifiers``) passes them, and only what is missing is read."""
    kd_info_parse = kd_info if kd_info is not None else _get_kd_info(kd_id)
    settle_info = settle_queue if settle_queue is not None else _get_settle_queue(kd_id)

    top_queue = sorted(
        settle_info,
        key=lambda queue: uas.utc(queue["time"]),
    )[:10]
    len_queue = len(settle_info)
    total_queue = _queue_total(settle_info)

    if modifiers is None:
        modifiers = _get_modifiers(kd_id)
    settle_price = _get_settle_price(kd_info_parse, modifiers)
    max_settle, available_settle = _get_available_settle(kd_info_parse, settle_info, modifiers)
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
        "total_queue": total_queue,
    }
    return payload


@bp.route('/api/settle', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def get_settle():
    kd_id = flask_praetorian.current_user().kd_id
    payload = _get_settle(kd_id)
    return (flask.jsonify(payload), 200)


def _get_missiles_info(kd_id):
    app = flask.current_app
    missiles_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/missiles',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    missiles_info_parse = json.loads(missiles_info.text)
    return missiles_info_parse["missiles"]

def _calc_missile_capacity(kd_info, modifiers=None):
    """How many of each missile the kingdom's silos hold: per silo, more for Fuzi and with the Missile Silos project,
    and after the kingdom's ``modifiers``."""
    per_silo = math.floor(
        uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"]
        * (
            1
            + int(kd_info["race"] == "Fuzi") * uas.GAME_CONFIG["FUZI_MISSILE_SILO_CAPACITY_INCREASE"]
        )
    )
    return math.floor(
        math.floor(kd_info["structures"]["missile_silos"])
        * (per_silo + uas.project_increase(kd_info, "missile_silos_bonus"))
        * max(1 + uas.modifier(modifiers, "missile_silo_capacity"), 0)
    )


def _empty_missile_silos(kd_info, modifiers=None):
    """
    Silos holding no missile: the silos less those needed for the largest stock of one missile (each silo holds some of
    every missile). Missiles still being built are not counted.
    """
    silos = math.floor(kd_info["structures"].get("missile_silos", 0))
    if silos <= 0:
        return 0
    per_silo = _calc_missile_capacity(kd_info, modifiers) / silos
    most_of_one = max((kd_info.get("missiles") or {}).values(), default=0)
    used = math.ceil(most_of_one / per_silo) if per_silo > 0 else silos
    return max(silos - used, 0)


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


@bp.route('/api/missiles', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def missiles():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    
    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    missiles_info = _get_missiles_info(kd_id)
    top_queue = sorted(
        missiles_info,
        key=lambda queue: uas.utc(queue["time"]),
    )[:10]
    len_queue = len(missiles_info)
    total_queue = _queue_total(missiles_info)
    missiles_building = _get_missiles_building(missiles_info)

    current_missiles = kd_info_parse["missiles"]

    modifiers = _get_modifiers(kd_id)
    max_available_missiles = _calc_missile_capacity(kd_info_parse, modifiers)

    cost_modifier = _missile_cost_modifier(kd_info_parse, modifiers)

    payload = {
        "current": current_missiles,
        "building": missiles_building,
        "build_time": uas.GAME_CONFIG["BASE_MISSILE_TIME_MULTIPLER"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"],
        "capacity": max_available_missiles,
        "desc": uas.MISSILES,
        "top_queue": top_queue,
        "len_queue": len_queue,
        "total_queue": total_queue,
        "cost_modifier": cost_modifier,
    }

    return (flask.jsonify(payload), 200)


def _missile_cost_modifier(kd_info, modifiers=None):
    """The share of the listed money and fuel this kingdom pays for a missile: its race and its ``modifiers``."""
    return max(
        1
        - int(kd_info["race"] == "Fuzi") * uas.GAME_CONFIG["FUZI_MISSILE_COST_REDUCTION"]
        + uas.modifier(modifiers, "missile_cost"),
        0,
    )


def _get_engineers_queue(kd_id):
    app = flask.current_app
    engineers_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/engineers',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    engineers_info_parse = json.loads(engineers_info.text)
    return engineers_info_parse["engineers"]

def _calc_workshop_capacity(kd_info, engineers_building, modifiers=None):
    per_workshop = math.floor(
        uas.GAME_CONFIG["BASE_WORKSHOP_CAPACITY"]
        * (
            1
            - int(kd_info["race"] == "Xo") * uas.GAME_CONFIG["XO_WORKSHOP_CAPACITY_REDUCTION"]
        )
    )
    max_workshop_capacity = math.floor(
        math.floor(kd_info["structures"]["workshops"])
        * (per_workshop + uas.project_increase(kd_info, "workshops_bonus"))
        * max(1 + uas.modifier(modifiers, "workshop_capacity"), 0)
    )
    current_engineers = kd_info["units"]["engineers"]
    current_workshop_capacity = current_engineers + engineers_building
    return max_workshop_capacity, current_workshop_capacity

def _engineer_price(modifiers=None):
    """The price of one engineer, after the kingdom's ``modifiers``."""
    return uas.GAME_CONFIG["BASE_ENGINEER_COST"] * max(1 + uas.modifier(modifiers, "engineer_cost"), 0)


def _calc_max_engineers(kd_info, engineers_building, max_workshop_capacity, modifiers=None):
    engineers_total = kd_info["units"]["engineers"] + engineers_building
    available_workshop_capacity = max(max_workshop_capacity - engineers_total, 0)
    max_trainable_engineers = uas.GAME_FUNCS["BASE_MAX_ENGINEERS"](int(kd_info["population"]))
    untrained_engineers = max(max_trainable_engineers - engineers_building, 0)
    max_available_engineers = min(available_workshop_capacity, untrained_engineers)
    try:
        current_available_engineers = min(
            math.floor(kd_info["money"] / _engineer_price(modifiers)),
            max_available_engineers,
        )
    except ZeroDivisionError:
        current_available_engineers = 0
    return max_available_engineers, current_available_engineers


def _get_engineers(kd_id, kd_info=None, engineers_queue=None, modifiers=None):
    """What the Engineers page shows. A caller that already holds the kingdom, its engineers queue or its modifiers
    passes them, and only what is missing is read."""
    kd_info_parse = kd_info if kd_info is not None else _get_kd_info(kd_id)
    engineers_info = engineers_queue if engineers_queue is not None else _get_engineers_queue(kd_id)
    if modifiers is None:
        modifiers = _get_modifiers(kd_id)
    engineers_building = sum([training["amount"] for training in engineers_info])
    max_workshop_capacity, current_workshop_capacity = _calc_workshop_capacity(kd_info_parse, engineers_building, modifiers)
    max_available_engineers, current_available_engineers = _calc_max_engineers(kd_info_parse, engineers_building, max_workshop_capacity, modifiers)
    top_queue = sorted(
        engineers_info,
        key=lambda queue: uas.utc(queue["time"]),
    )[:10]
    len_queue = len(engineers_info)
    total_queue = _queue_total(engineers_info)

    payload = {
        'engineers_price': _engineer_price(modifiers),
        'max_workshop_capacity': max_workshop_capacity,
        'current_workshop_capacity': current_workshop_capacity,
        'max_available_engineers': max_available_engineers,
        'current_available_engineers': current_available_engineers,
        'current_engineers': kd_info_parse["units"]["engineers"],
        'engineers_building': engineers_building,
        "top_queue": top_queue,
        "len_queue": len_queue,
        "total_queue": total_queue,
        }
    return payload

@bp.route('/api/engineers', methods=['GET'])
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


@bp.route('/api/projects', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def projects():
    app = flask.current_app
    kd_id = flask_praetorian.current_user().kd_id
    

    kd_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    kd_info_parse = json.loads(kd_info.text)

    max_bonuses = uas.max_project_bonuses()
    current_bonuses = uas.project_bonuses(kd_info_parse)
    available_engineers = kd_info_parse["units"]["engineers"] - sum(kd_info_parse["projects_assigned"].values())

    payload = {
        "current_bonuses": current_bonuses,
        "max_bonuses": max_bonuses,
        "available_engineers": available_engineers,
        # Why each project engineers can not work on yet is locked; projects that are not listed are open.
        "locked": {
            project: reason
            for project in uas.PROJECTS
            if (reason := uas.project_locked_reason(kd_info_parse, project))
        },
        # Each project's points and max points, including projects added after this kingdom was made.
        "points": {project: kd_info_parse.get("projects_points", {}).get(project, 0) for project in uas.PROJECTS},
        "max_points": {
            project: kd_info_parse.get("projects_max_points", {}).get(project, uas.PROJECTS_FUNCS[project](kd_info_parse["stars"]))
            for project in uas.PROJECTS
        },
    }
    # Each project's points an hour from the engineers on it now, and the seconds until it reaches its max points at
    # that rate (None with nobody on it, 0 once there). A continuous project's max points grow with stars, so its
    # time is an estimate at today's size.
    per_epoch = uas.project_points_per_epoch(kd_info_parse, _get_modifiers(kd_id))
    completed = kd_info_parse.get("completed_projects", [])
    payload["points_per_hour"] = {
        project: per_epoch.get(project, 0) * 3600 / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] for project in uas.PROJECTS
    }
    payload["seconds_left"] = {
        project: uas.project_seconds_left(payload["points"][project], payload["max_points"][project],
                                          per_epoch.get(project, 0), done=project in completed)
        for project in uas.PROJECTS
    }
    return (flask.jsonify(payload), 200)


def _get_revealed(kd_id):
    app = flask.current_app
    revealed_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/revealed',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    revealed_info_parse = json.loads(revealed_info.text)
    return revealed_info_parse

@bp.route('/api/revealed', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def revealed():
    kd_id = flask_praetorian.current_user().kd_id
    
    revealed_info = _get_revealed(kd_id)
    return (flask.jsonify(revealed_info), 200)

def _get_pinned(kd_id):
    app = flask.current_app
    pinned_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/pinned',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    pinned_info_parse = json.loads(pinned_info.text)
    return pinned_info_parse

@bp.route('/api/pinned', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def pinned():
    kd_id = flask_praetorian.current_user().kd_id
    
    pinned_info = _get_pinned(kd_id)
    return (flask.jsonify(pinned_info["pinned"]), 200)

def _military_estimate(info):
    """
    What a kingdom's army is worth at most, from the units that are revealed: all its units counted (those out with
    generals too) with the largest military bonus, shields and generals bonus there can be, so a target that looks
    beatable by this really is. Only when the units are revealed; otherwise None.
    """
    if "units" not in info:
        return None
    units = dict(info["units"])
    for general_units in info.get("generals_out", []) or []:
        for key, value in general_units.items():
            if key != "return_time":
                units[key] = units.get(key, 0) + value
    return {
        "offense": _calc_max_offense(units, lumina=info.get("race") == "Lumina"),
        "defense": _calc_max_defense(units, gaian=info.get("race") == "Gaian"),
    }


def _get_max_kingdoms(kd_id, kingdoms):
    revealed_info = _get_revealed(kd_id)
    galaxies_inverted, _ = _get_galaxies_inverted()
    last_known = uala.read(kd_id)

    payload = {
        other_kd_id: _get_max_kd_info(other_kd_id, kd_id, revealed_info, galaxies_inverted=galaxies_inverted,
                                      last_known=last_known)
        for other_kd_id in kingdoms
    }
    for info in payload.values():
        # Only from the army (military intel): projects intel reveals the engineers alone, which says nothing of it.
        estimate = _military_estimate(info) if "generals_out" in info else None
        if estimate is not None:
            info["military_estimate"] = estimate
        known_military = info.get("last_known", {}).get("military")
        if known_military is not None:
            # The estimate from the army as it was last seen, for the pages to show where the army is not revealed now.
            estimate = _military_estimate({**known_military["values"], "race": info.get("race")})
            if estimate is not None:
                known_military["values"]["military_estimate"] = estimate
    return payload

@bp.route('/api/kingdomsinfo', methods=['POST'])
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
    return _get_shared_document(f'/galaxy/{galaxy_id}/politics'), galaxy_id

@bp.route('/api/galaxypolitics', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def galaxy_politics():
    kd_id = flask_praetorian.current_user().kd_id
    
    galaxy_votes, _ = _get_galaxy_politics(kd_id)
    state = _get_state()
    now = datetime.datetime.now(datetime.timezone.utc)
    galaxy = _galaxy_policies_now(galaxy_votes, state, now)
    unlocks = uas.galaxy_vote_unlocks_at(galaxy_votes, "leader", kd_id, now)
    stored_votes = galaxy_votes.get("votes") or {}
    payload = {
        "leader": galaxy_votes.get("leader", ""),
        "votes": {"leader": stored_votes.get("leader") or {}},
        "empire_invitations": galaxy_votes.get("empire_invitations", []),
        "empire_join_requests": galaxy_votes.get("empire_join_requests", []),
        # This round's policies: the options, the active one, the votes, and the weight towards the next tally.
        **uagp.view(galaxy, uagp.round_policies(state.get("state")), _round_start(state), now, kd_id),
        # When this kingdom can change its vote for leader again (null: now), and how long a change holds.
        "vote_unlocks_at": {"leader": unlocks.isoformat() if unlocks else None},
        "vote_cooldown_hours": uas.GAME_CONFIG["BASE_GALAXY_VOTE_COOLDOWN_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600,
    }
    return (flask.jsonify(payload), 200)

@bp.route('/api/modifiers', methods=['GET'])
@flask_praetorian.auth_required
def get_modifiers():
    """
    What politics does to the caller's kingdom now (``_get_modifiers``): each effect with its value and sentence, and
    the few figures pages show that it changes and that no other route carries. Only the caller's own kingdom.
    """
    kd_id = flask_praetorian.current_user().kd_id
    modifiers = {effect: value for effect, value in _get_modifiers(kd_id).items() if abs(value) > 1e-9}
    state = _get_state()
    seconds_elapsed = max((datetime.datetime.now(datetime.timezone.utc) - _round_start(state)).total_seconds(), 0)
    rob_per_drone = uas.GAME_FUNCS["BASE_PRIMITIVES_ROB_PER_DRONE"](seconds_elapsed)
    return flask.jsonify({
        "modifiers": modifiers,
        "texts": {effect: uas.effect_text(effect, value) for effect, value in modifiers.items() if effect in uas.EFFECTS},
        "primitives_rob_per_drone": rob_per_drone * max(1 + uas.modifier(modifiers, "rob_primitives"), 0),
    }), 200


def _get_universe_politics():
    app = flask.current_app
    universe_politics_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/universevotes',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    universe_politics_info_parse = json.loads(universe_politics_info.text)
    return universe_politics_info_parse


@bp.route('/api/universepolitics', methods=['GET'])
@flask_praetorian.auth_required
# @flask_praetorian.roles_required('verified')
def universe_politics():
    kd_id = flask_praetorian.current_user().kd_id
    state = _get_state()
    inner = state.get("state", {})
    galaxy_id = _get_galaxies_inverted()[0].get(str(kd_id))
    # Only this kingdom's own votes: nobody sees the tally until the election closes.
    election_open = bool(inner.get("election_end"))
    active = uaup.active_options(inner)
    # The votes document is read while an election is open (this kingdom's votes in it) and once one has closed (the
    # last one's results); before the first has closed, nothing in it is worth reading.
    document = _get_universe_politics() if election_open or active else {}
    tally = (document.get("votes") or {}) if election_open else {}
    scores = _get_scores_shared() if uaup.needs_scores(active) else None
    ballot = uaup.ballot_of(inner)
    payload = {
        "election": {
            "open": bool(inner.get("election_end")),
            "start": inner.get("election_start", ""),
            "end": inner.get("election_end", ""),
        },
        # The next election's policies while none is open, the open one's while it is.
        "ballot": [
            {
                "key": policy,
                "name": uas.UNIVERSE_POLICIES[policy]["name"],
                "first_election_only": bool(uas.UNIVERSE_POLICIES[policy].get("first_election_only")),
                "options": [
                    {**uaup.describe(option),
                     "my_votes": ((tally.get(policy) or {}).get(option) or {}).get(str(kd_id), 0)}
                    for option in uas.UNIVERSE_POLICIES[policy]["options"]
                ],
            }
            for policy in ballot
        ],
        # In force now, and whether each hits this kingdom.
        "active": [{**uaup.describe(option), "hits_me": uaup.applies(option, kd_id, galaxy_id, scores)}
                   for option in active],
        # The last closed election: each option's total votes and this kingdom's own. None before the first closes.
        "results": uaup.results(uaup.last_votes(document, election_open), active, kd_id) if active else [],
        "votes_cost": uas.GAME_CONFIG["BASE_VOTES_COST"],
    }
    return (flask.jsonify(payload), 200)

def _get_siphons_in(kd_id):
    app = flask.current_app
    siphons_in_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsin',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    siphons_in_info_parse = json.loads(siphons_in_info.text)
    return siphons_in_info_parse["siphons_in"]
    
def _get_siphons_out(kd_id):
    app = flask.current_app
    siphons_out_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/siphonsout',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    siphons_out_info_parse = json.loads(siphons_out_info.text)
    return siphons_out_info_parse["siphons_out"]

@bp.route('/api/siphonsout', methods=['GET'])
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
    app = flask.current_app
    history_info = REQUESTS_SESSION.get(
        app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/history',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']}
    )
    
    history_info_parse = json.loads(history_info.text)
    return history_info_parse["history"]

@bp.route('/api/history', methods=['GET'])
@flask_praetorian.auth_required
def get_history():
    kd_id = flask_praetorian.current_user().kd_id

    history = _get_history(kd_id)
    return flask.jsonify(history), 200


# The history series that hold a dict of counts instead of one number. The refresh keeps only their newest week.
HISTORY_BREAKDOWNS = ("units", "structures")
# The single-number series the "since you were last here" summary compares. Max offense and defense are the best case,
# not what the kingdom has now, so it leaves them out; the units breakdown shows the military instead.
SUMMARY_SERIES = ("stars", "networth", "population", "drones", "engineers")


def _history_values(kd_info):
    """
    What a history point records for ``kd_info``: the kingdom's numbers, its best-case max offense and defense with
    every unit it owns, and the breakdowns: military units owned (at home and out with generals, engineers left out
    as they have their own series) and structures built, without zero counts.
    """
    total_units = {key: value for key, value in kd_info["units"].items()}
    for general_units in kd_info.get("generals_out", []):
        for key_unit, value_unit in general_units.items():
            if key_unit == "return_time":
                continue
            total_units[key_unit] = total_units.get(key_unit, 0) + value_unit
    return {
        "networth": kd_info["networth"],
        "stars": kd_info["stars"],
        "drones": kd_info["drones"],
        "population": kd_info["population"],
        "engineers": kd_info["units"]["engineers"],
        "max_offense": _calc_max_offense(total_units),
        "max_defense": _calc_max_defense(total_units),
        "units": {key: int(value) for key, value in total_units.items()
                  if key in uas.UNITS and key != "engineers" and value},
        "structures": {key: int(value) for key, value in (kd_info.get("structures") or {}).items()
                       if key in uas.STRUCTURES and value},
    }


def _baseline(series, since):
    """The newest point at or before ``since``, or the oldest one if they are all later. None for an empty series."""
    if not series:
        return None
    before = [point for point in series if uas.utc(point["time"]) <= since]
    return max(before, key=lambda point: uas.utc(point["time"])) if before else min(
        series, key=lambda point: uas.utc(point["time"]))


def _history_summary(history, kd_info, since):
    """
    What changed since ``since``: each summary series and each unit and structure count, from the history point
    nearest before it to the kingdom as it is now. ``from`` is when that point was taken (later than ``since`` when
    the history does not go back that far: the round started later, or the breakdowns are kept only a week), None if
    there is none yet. Counts that did not change are left out.
    """
    now = _history_values(kd_info)
    summary = {"since": since.isoformat()}
    first = _baseline(history.get("stars", []), since)
    summary["from"] = first["time"] if first else None
    summary["changes"] = {}
    for key in SUMMARY_SERIES:
        point = _baseline(history.get(key, []), since)
        if point is not None:
            summary["changes"][key] = {"from": point["value"], "to": now[key]}
    for key in HISTORY_BREAKDOWNS:
        point = _baseline(history.get(key, []), since)
        summary[f"{key}_from"] = point["time"] if point else None
        before = point["value"] if point else {}
        changes = {}
        for name in sorted(set(before) | set(now[key])):
            if before.get(name, 0) != now[key].get(name, 0):
                changes[name] = {"from": before.get(name, 0), "to": now[key].get(name, 0)}
        summary[key] = changes if point else {}
    return summary


@bp.route('/api/history/summary', methods=['GET'])
@flask_praetorian.auth_required
def get_history_summary():
    """
    What changed in the caller's kingdom (``_history_summary``) since they were last here, or in the last hour
    (``visits.summary_window``), with ``since_visit`` saying which. Records the visit too, as this may be the first
    request of a visit and must not answer from before it.
    """
    kd_id = flask_praetorian.current_user().kd_id
    now = datetime.datetime.now(datetime.timezone.utc)
    notifs = uav.read_and_record(kd_id, now)
    since, since_visit = uav.summary_window(notifs, now)
    history = _get_history(kd_id)
    kd_info = _get_kd_info(kd_id)
    return flask.jsonify({**_history_summary(history, kd_info, since), "since_visit": since_visit}), 200

    
@bp.route('/api/time')
@flask_praetorian.auth_required
def get_time():
    return (flask.jsonify(datetime.datetime.now(datetime.timezone.utc).isoformat()), 200)