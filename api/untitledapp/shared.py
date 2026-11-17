import math
import os
import random
from functools import partial

UNITS = {
    'attack': {
        'offense': 5,
        'defense': 0,
        'cost': 300,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'defense': {
        'offense': 0,
        'defense': 5,
        'cost': 350,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'flex': {
        'offense': 5,
        'defense': 5,
        'cost': 550,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'big_flex': {
        'offense': 10,
        'defense': 10,
        'cost': 1250,
        'fuel': 2,
        'hangar_capacity': 2,
    },
    # Better pure units, unlocked by projects: more strength per hangar space, but more money per point of strength.
    'heavy_attack': {
        'offense': 6,
        'defense': 0,
        'cost': 400,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'elite_attack': {
        'offense': 7,
        'defense': 0,
        'cost': 525,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'heavy_defense': {
        'offense': 0,
        'defense': 6,
        'cost': 460,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'elite_defense': {
        'offense': 0,
        'defense': 7,
        'cost': 600,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'recruits': {
        'offense': 0,
        'defense': 1,
        'fuel': 1,
        'hangar_capacity': 1,
    },
    'engineers': {
        'offense': 0,
        'defense': 0,
        'fuel': 1,
        'hangar_capacity': 0,
    }
}

# The order pages list units in: attackers, defenders, flexers, then recruits and engineers.
UNITS = {key: UNITS[key] for key in (
    "attack", "heavy_attack", "elite_attack",
    "defense", "heavy_defense", "elite_defense",
    "flex", "big_flex",
    "recruits", "engineers",
)}

# A unit with "project" can only be trained once that project is completed.
UNITS["big_flex"]["project"] = "big_flexers"
UNITS["heavy_attack"]["project"] = "heavy_attackers"
UNITS["elite_attack"]["project"] = "elite_attackers"
UNITS["heavy_defense"]["project"] = "heavy_defenders"
UNITS["elite_defense"]["project"] = "elite_defenders"

# Units by role: offense only, defense only. Projects and race rules that name "pure" attackers or defenders use these.
PURE_ATTACK_UNITS = [key for key, unit in UNITS.items() if unit["offense"] > 0 and unit["defense"] == 0]
PURE_DEFENSE_UNITS = [
    key for key, unit in UNITS.items() if unit["defense"] > 0 and unit["offense"] == 0 and key != "recruits"
]

# The units trained from recruits: everything but recruits and engineers.
TRAINABLE_UNITS = [key for key in UNITS if key not in ("recruits", "engineers")]


def unit_fuel(kd_info, unit):
    """Fuel one ``unit`` of this kingdom uses per epoch, after its projects."""
    fuel = UNITS[unit]["fuel"]
    if unit in PURE_ATTACK_UNITS and has_project(kd_info, "solar_attackers"):
        fuel *= 1 - GAME_CONFIG["SOLAR_FUEL_REDUCTION"]
    if unit in PURE_DEFENSE_UNITS and has_project(kd_info, "solar_defenders"):
        fuel *= 1 - GAME_CONFIG["SOLAR_FUEL_REDUCTION"]
    return fuel


def unit_hangar_space(kd_info, unit):
    """Hangar space one ``unit`` of this kingdom takes, after its projects."""
    space = UNITS[unit]["hangar_capacity"]
    if unit == "big_flex" and has_project(kd_info, "compact_flexers"):
        space = GAME_CONFIG["COMPACT_FLEX_HANGAR_CAPACITY"]
    return space


def units_for(kd_info, units_desc=None):
    """``UNITS`` (or ``units_desc``, e.g. with costs adjusted) with this kingdom's fuel and hangar space per unit."""
    units_desc = units_desc if units_desc is not None else UNITS
    return {
        key: {**unit, "fuel": unit_fuel(kd_info, key), "hangar_capacity": unit_hangar_space(kd_info, key)}
        for key, unit in units_desc.items()
    }


def unit_locked(kd_info, unit):
    """Whether ``unit`` needs a project the kingdom has not completed."""
    project = UNITS.get(unit, {}).get("project")
    return bool(project) and not has_project(kd_info, project)


# The order a suggested attack fills units in: pure attackers first, cheapest strength first, then flexers, which also
# defend at home.
AUTOFILL_PRIORITY = [
    "attack",
    "heavy_attack",
    "elite_attack",
    "big_flex",
    "flex",
]

STRUCTURES = [
    "homes",
    "mines",
    "fuel_plants",
    "hangars",
    "drone_factories",
    "missile_silos",
    "workshops",
]

MISSILES = {
    "planet_busters": {
        "stars_damage": 1,
        "fuel_damage": 0,
        "pop_damage": 0,
        "fuel_cost": 1000,
        "cost": 2000,
    },
    "star_busters": {
        "stars_damage": 2,
        "fuel_damage": 500,
        "pop_damage": 0,
        "fuel_cost": 2000,
        "cost": 6000,
    },
    "galaxy_busters": {
        "stars_damage": 4,
        "fuel_damage": 1000,
        "pop_damage": 50,
        "fuel_cost": 4000,
        "cost": 15000,
    },
}

# A missile with "project" can only be built once that project is completed.
MISSILES["star_busters"]["project"] = "star_busters"
MISSILES["galaxy_busters"]["project"] = "galaxy_busters"

RACES = [
    "Gaian",
    "Vult",
    "Lumina",
    "Xo",
    "Fuzi",
]

def _epoch_seconds():
    """Half an hour, unless ``EPOCH_SECONDS`` says otherwise (local simulation only: a short epoch makes a round run fast).
    Set the same value for the function app, whose queue folding scales with it (``funcapp/queues.py``)."""
    value = float(os.environ.get("EPOCH_SECONDS", 30 * 60))
    return int(value) if value == int(value) else value


GAME_CONFIG = {
    "BASE_EPOCH_SECONDS": _epoch_seconds(),

    "BASE_SETTLE_STARS_POWER": 0.5,
    "BASE_SETTLE_COST_CONSTANT": 50,
    "BASE_MAX_SETTLE_CAP": 0.10,
    "BASE_SETTLE_TIME_MIN_MULTIPLIER": 1,
    "BASE_SETTLE_TIME_MAX_MUTLIPLIER": 23,
    "BASE_SETTLE_TIME_SPLITS": 12,

    "BASE_STRUCTURE_STARS_POWER": 0.5,
    "BASE_STRUCTURE_COST_CONSTANT": 50,
    "BASE_STRUCTURE_TIME_MIN_MULTIPLIER": 1,
    "BASE_STRUCTURE_TIME_MAX_MUTLIPLIER": 15,
    "BASE_STRUCTURE_TIME_SPLITS": 8,

    "BASE_MAX_RECRUITS_CAP": 0.12,
    "BASE_RECRUIT_COST": 100, 
    "BASE_RECRUIT_TIME_MIN_MULTIPLIER": 1,
    "BASE_RECRUIT_TIME_MAX_MUTLIPLIER": 23,
    "BASE_RECRUIT_TIME_SPLITS": 12,

    "BASE_SPECIALIST_TIME_MIN_MULTIPLIER": 1,
    "BASE_SPECIALIST_TIME_MAX_MUTLIPLIER": 23,
    "BASE_SPECIALIST_TIME_SPLITS": 12,

    "BASE_DISBAND_COST_RETURN": 0.25,

    "BASE_ENGINEER_COST": 1000, 
    "BASE_ENGINEER_TIME_MIN_MULTIPLIER": 1,
    "BASE_ENGINEER_TIME_MAX_MUTLIPLIER": 23,
    "BASE_ENGINEER_TIME_SPLITS": 12,
    "BASE_ENGINEER_PROJECT_POINTS_PER_EPOCH": 1, 
    "BASE_MAX_ENGINEERS_POP_CAP": 0.05,

    "BASE_HOMES_CAPACITY": 50, 
    "BASE_HANGAR_CAPACITY": 75, 
    "BASE_MISSILE_SILO_CAPACITY": 1, 
    "BASE_WORKSHOP_CAPACITY": 50, 
    "BASE_MINES_INCOME_PER_EPOCH": 150, 
    "BASE_FUEL_PLANTS_INCOME_PER_EPOCH": 200, 
    "BASE_FUEL_PLANTS_CAPACITY": 1000, 
    "BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH": 1, 

    "BASE_STRUCTURES_LOSS_RETURN_RATE": 0.2, 
    "BASE_STRUCTURES_LOSS_PER_STAR_PER_EPOCH": 0.02,
    "BASE_STRUCTURES_RAZE_RETURN": 0.25,

    "BASE_MISSILE_TIME_MULTIPLER": 24, 

    "BASE_GENERALS_ATTACK_MODIFIER": 0.03,
    "BASE_GENERALS_RETURN_TIME_MULTIPLIER": 24, 
    "BASE_RETURN_TIME_PENALTY_PER_COORDINATE": 0.01, 
    "BASE_DEFENDER_UNIT_LOSS_RATE": 0.05, 
    "BASE_ATTACKER_UNIT_LOSS_RATE": 0.05, 
    "BASE_KINGDOM_LOSS_RATE": 0.10, 
    "BASE_FUELLESS_STRENGTH_REDUCTION": 0.2, 
    "BASE_ATTACK_MIN_STARS_GAIN": 25, 

    "BASE_PRIMITIVES_DEFENSE_PER_STAR": 100,
    "BASE_PRIMITIVES_DEFENSE_EPOCH_MULTIPLER": 24,
    "BASE_PRIMITIVES_MONEY_PER_STAR": 1000, 
    "BASE_PRIMITIVES_FUEL_PER_STAR": 100, 
    "BASE_PRIMITIVES_POPULATION_PER_STAR": 10, 
    "BASE_PRIMITIVES_ROB_PER_DRONE": 4,
    "BASE_PRIMITIVES_ROB_EPOCH_MULTIPLIER": 24,

    "BASE_STARS_DRONE_DEFENSE_MULTIPLIER": 4, 
    "BASE_DRONES_DRONE_DEFENSE_MULTIPLIER": 1, 
    "BASE_SPY_MIN_SUCCESS_CHANCE": 0.10, 
    "BASE_DRONES_SUCCESS_LOSS_RATE": 0.01, 
    "BASE_DRONES_FAILURE_LOSS_RATE": 0.02, 
    "BASE_DRONES_SHIELDING_LOSS_REDUCTION": 0.5, 
    "BASE_REVEAL_DURATION_MULTIPLIER": 16, 
    "BASE_DRONE_GADGETS_LOSS_REDUCTION": 0.25,

    "BASE_MAX_SHARE_CUT": 0.15, 

    "BASE_DRONES_SIPHON_PER_DRONE": 8, 
    "BASE_DRONES_SIPHON_TIME_MULTIPLIER": 12, 
    "BASE_DRONES_PER_HOME_DAMAGE": 1500, 
    "BASE_DRONES_MAX_HOME_DAMAGE": 0.05, 
    "BASE_DRONES_PER_FUEL_PLANT_DAMAGE": 1500, 
    "BASE_DRONES_MAX_FUEL_PLANT_DAMAGE": 0.05, 
    "BASE_DRONES_PER_KIDNAP": 10, 
    "BASE_DRONES_MAX_KIDNAP_DAMAGE": 0.05, 
    "BASE_DRONES_SUICIDE_FUEL_DAMAGE": 5, 
    "BASE_KIDNAP_RETURN_RATE": 0.4, 

    "BASE_MAX_SIPHON": 0.15, 

    "BASE_POP_INCOME_PER_EPOCH": 2, 
    "BASE_POP_FUEL_CONSUMPTION_PER_EPOCH": 0.5, 
    "BASE_PCT_POP_GROWTH_PER_EPOCH": 0.10, 
    "BASE_POP_GROWTH_PER_STAR_PER_EPOCH": 0.5, 
    "BASE_FUELLESS_POP_GROWTH_REDUCTION": 0.9, 
    "BASE_FUELLESS_POP_CAP_REDUCTION": 0.2, 
    "BASE_NEGATIVE_FUEL_PER_STAR": 5,

    "BASE_PCT_POP_LOSS_PER_EPOCH": 0.10, 
    "BASE_POP_LOSS_PER_STAR_PER_EPOCH": 0.2, 

    "BASE_SPY_ATTEMPT_TIME_MULTIPLIER": 1,
    "BASE_SPY_ATTEMPTS_MAX": 10, 

    "BASE_MILITARY_SHIELDS_MAX": 0.10, 
    "BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT": 0.1, 
    "BASE_SPY_SHIELDS_MAX": 0.20, 
    "BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT": 0.05, 
    "BASE_SPY_RADAR_MAX": 0.20, 
    "BASE_SPY_RADAR_COST_PER_LAND_PER_PCT": 0.05, 
    "BASE_MISSILES_SHIELDS_MAX": 1.0, 
    "BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT": 0.005, 

    "BASE_VOTES_COST": 10000, 
    "BASE_ELECTION_LENGTH_MULTIPLIER": 24, 
    "BASE_ELECTION_RESULTS_DURATION_MULTIPLIER": 24 * 6, 

    "BASE_AUTO_SPENDING_TIME_MULTIPLIER": 0.1, 

    "BASE_EXPANSIONIST_SETTLE_REDUCTION": 0.15,
    "BASE_WARLIKE_RETURN_REDUCTION": 0.1,
    "BASE_INTELLIGENCE_RETURN_REDUCTION": 0.1,
    "BASE_CONSCRIPTION_TIME_REDUCTION": 0.2,
    "BASE_UNREGULATED_COST_REDUCTION": 0.2,
    "BASE_TREATIED_COST_INCREASE": 0.2,
    "BASE_FREE_TRADE_INCREASE": 0.1,
    "BASE_ISOLATIONIST_DECREASE": 0.1,

    "NETWORTH_VALUES": {
        "stars": 25,
        "structures": 25,
        "money": 0.002,
        "attack": 7,
        "heavy_attack": 8,
        "elite_attack": 9,
        "defense": 8,
        "heavy_defense": 9,
        "elite_defense": 11,
        "flex": 10,
        "big_flex": 20,
        "recruits": 2,
        "engineers": 18,
    },

    "NETWORTH_POINTS": [
        25,
        18,
        15,
        12,
        10,
        8,
        6,
        4,
        2,
        1,
    ],

    "GAIAN_SETTLE_COST_REDUCTION": 0.2,
    "GAIAN_SETTLE_TIME_REDUCTION": 0.1,
    "GAIAN_DEFENSE_REDUCTION": 0.1,

    "VULT_DRONE_PRODUCTION_INCREASE": 0.2,
    "VULT_POPULATION_REDUCTION": 0.1,

    "LUMINA_FUEL_PRODUCTION_INCREASE": 0.5,
    "LUMINA_OFFENSE_REDUCTION": 0.2,

    "XO_ATTACK_GAINS_INCREASE": 0.2,
    "XO_ATTACK_UNIT_LOSSES_REDUCTION": 0.4,
    "XO_WORKSHOP_CAPACITY_REDUCTION": 0.5,

    "FUZI_MISSILE_SHIELDS_MAX": 0.5,
    "FUZI_MISSILE_COST_REDUCTION": 0.3,
    "FUZI_MISSILE_SILO_CAPACITY_INCREASE": 1.0,

    "AGGRO_METER_PER_KD": 10,
    "AGGRO_METER_DECAY_PER_KD_PER_EPOCH": 0.25,
    "AGGRO_PER_ATTACK": 10,
    "AGGRO_PER_AGGRO_SPY": 2,

    "DENOUNCE_AGGRO_METER_INCREASE": 0.2,
    "DENOUNCE_OFFENSE_BONUS": 0.05,
    "DENOUNCE_DURATION_MULTIPLIER": 48,
    "DENOUNCE_COOLDOWN_MULTIPLIER": 48,

    "PEACE_DURATION_MULTIPLIER": 48,
    "PEACE_DEFENSE_BONUS": 0.5,
    "PEACE_PROBE_DEFENSE_BONUS": 0.5,

    "WAR_OFFENSE_INCREASE": 0.1,
    "WAR_GAINS_INCREASE": 0.2,
    "WAR_LOSSES_INCREASE": 0.2,

    "SURPRISE_WAR_PENALTY_OFFENSE_INCREASE": 0.1,
    "SURPRISE_WAR_PENALTY_MULTIPLIER": 48,

    # A galaxy can not join an empire if the empire would then hold more than these shares of the universe's
    # kingdoms or networth. An empire of two galaxies is always allowed.
    "EMPIRE_MAX_KINGDOMS_SHARE": 0.30,
    "EMPIRE_MAX_NETWORTH_SHARE": 0.35,
    "EMPIRE_ALWAYS_ALLOWED_GALAXIES": 2,
    # Playstyle projects, unlocked by the best unit of each kind (proposals).
    "SOLAR_FUEL_REDUCTION": 0.5,  # solar_attackers / solar_defenders: pure units of that kind use this much less fuel
    "SELF_DESTRUCT_LOSSES_INCREASE": 0.5,  # self_destructing_*: the other side's unit losses are this much higher
    "COMPACT_FLEX_HANGAR_CAPACITY": 1,  # compact_flexers: hangar space one big flexer takes
}

GAME_FUNCS = {
    "BASE_SETTLE_COST": lambda stars: math.floor((stars ** GAME_CONFIG["BASE_SETTLE_STARS_POWER"]) * GAME_CONFIG["BASE_SETTLE_COST_CONSTANT"]), 
    "BASE_MAX_SETTLE": lambda stars: math.floor(stars * GAME_CONFIG["BASE_MAX_SETTLE_CAP"]), 
    "BASE_STRUCTURE_COST": lambda stars: math.floor((stars ** GAME_CONFIG["BASE_STRUCTURE_STARS_POWER"]) * GAME_CONFIG["BASE_STRUCTURE_COST_CONSTANT"]), 
    "BASE_MAX_RECRUITS": lambda pop: math.floor(pop * GAME_CONFIG["BASE_MAX_RECRUITS_CAP"]), 
    "BASE_MAX_ENGINEERS": lambda pop: math.floor(pop * GAME_CONFIG["BASE_MAX_ENGINEERS_POP_CAP"]), 
    "BASE_GENERALS_BONUS": lambda generals: (generals - 1) * GAME_CONFIG["BASE_GENERALS_ATTACK_MODIFIER"], 
    "BASE_PRIMITIVES_DEFENSE_PER_STAR": lambda seconds: GAME_CONFIG["BASE_PRIMITIVES_DEFENSE_PER_STAR"] * math.sqrt(1 + seconds / (GAME_CONFIG["BASE_EPOCH_SECONDS"] * GAME_CONFIG["BASE_PRIMITIVES_DEFENSE_EPOCH_MULTIPLER"])), 
    "BASE_PRIMITIVES_ROB_PER_DRONE": lambda seconds: GAME_CONFIG["BASE_PRIMITIVES_ROB_PER_DRONE"] / math.sqrt(1 + seconds / (GAME_CONFIG["BASE_EPOCH_SECONDS"] * GAME_CONFIG["BASE_PRIMITIVES_ROB_EPOCH_MULTIPLIER"])), 
    "BASE_NEGATIVE_FUEL_CAP": lambda stars: stars * -GAME_CONFIG["BASE_NEGATIVE_FUEL_PER_STAR"], 
}

# Every project, in the order the Projects page lists them. Two kinds:
#   - continuous (has "max_bonus"): the bonus is max_bonus times the share of max points earned, capped at 1. The max
#     points grow with stars (stars ** stars_power * constant), so a growing kingdom needs engineers to keep its bonus.
#   - one-time (no "max_bonus"): done once the points reach the max points; then it is in "completed_projects".
# "category" groups them on the page. "requires" lists projects that must be completed before engineers can work on
# this one; "race" limits it to one race. Read projects through the helpers below (project_bonus, has_project,
# project_locked_reason), never by indexing the kingdom's dicts: kingdoms made before a project existed lack its keys.
PROJECT_CATEGORIES = {
    "economy": "Economy",
    "structures": "Structures",
    "military": "Military",
    "spy": "Drones and spying",
    "missiles": "Missiles",
    "racial": "Racial",
}

PROJECTS = {
    "pop_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases homes capacity by the current bonus",
        "name": "Pop Bonus",
        "category": "structures",
    },
    "fuel_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases fuel production by the current bonus",
        "name": "Fuel Bonus",
        "category": "structures",
    },
    # One continuous project per structure (homes and fuel plants are the two above), to reward engineers.
    "mines_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases the money mines produce by the current bonus",
        "name": "Mines Bonus",
        "category": "structures",
    },
    "hangars_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases the units each hangar houses by the current bonus",
        "name": "Hangars Bonus",
        "category": "structures",
    },
    "drone_factories_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases the drones drone factories produce by the current bonus",
        "name": "Drone Factories Bonus",
        "category": "structures",
    },
    "missile_silos_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases the missiles each missile silo stores by the current bonus",
        "name": "Missile Silos Bonus",
        "category": "structures",
    },
    "workshops_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases the engineers each workshop houses by the current bonus",
        "name": "Workshops Bonus",
        "category": "structures",
    },

    "military_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases offensive and defensive strength by the current bonus",
        "name": "Military Bonus",
        "category": "military",
    },
    "money_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases income from population and mines by the current bonus",
        "name": "Money Bonus",
        "category": "economy",
    },
    "general_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Decreases generals time to return by the current bonus",
        "name": "Generals Speed Bonus",
        "category": "military",
    },
    "spy_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Decreases cooldown of spy attempts by the current bonus",
        "name": "Spy Bonus",
        "category": "spy",
        "requires": ["drone_gadgets"],
    },
    "big_flexers": {
        "stars_power": 0,
        "constant": 100000,
        "desc": "Unlocks the Big Flexer unit",
        "name": "Big Flexers",
        "category": "military",
    },
    # The 7-strength units cost about five times the points of the 6-strength ones, and need them first. Defender
    # projects cost about 20% more than attacker projects.
    # Playstyle projects: two for the best unit of each kind.
    "solar_attackers": {
        "stars_power": 0,
        "constant": 150000,
        "desc": f"Pure attackers use {GAME_CONFIG['SOLAR_FUEL_REDUCTION']:.0%} less fuel",
        "name": "Solar Attackers",
        "category": "military",
        "requires": ["elite_attackers"],
    },
    "self_destructing_attackers": {
        "stars_power": 0,
        "constant": 150000,
        "desc": f"When you attack a kingdom, its units take {GAME_CONFIG['SELF_DESTRUCT_LOSSES_INCREASE']:.0%} more losses",
        "name": "Self-Destructing Attackers",
        "category": "military",
        "requires": ["elite_attackers"],
    },
    "solar_defenders": {
        "stars_power": 0,
        "constant": 180000,
        "desc": f"Pure defenders use {GAME_CONFIG['SOLAR_FUEL_REDUCTION']:.0%} less fuel",
        "name": "Solar Defenders",
        "category": "military",
        "requires": ["elite_defenders"],
    },
    "self_destructing_defenders": {
        "stars_power": 0,
        "constant": 180000,
        "desc": f"Kingdoms that attack you take {GAME_CONFIG['SELF_DESTRUCT_LOSSES_INCREASE']:.0%} more unit losses",
        "name": "Self-Destructing Defenders",
        "category": "military",
        "requires": ["elite_defenders"],
    },
    "warp_speed": {
        "stars_power": 0,
        "constant": 150000,
        "desc": "Big flexers sent on an attack all come home with the first general to return",
        "name": "Warp Speed",
        "category": "military",
        "requires": ["big_flexers"],
    },
    "compact_flexers": {
        "stars_power": 0,
        "constant": 150000,
        "desc": f"Big flexers take {GAME_CONFIG['COMPACT_FLEX_HANGAR_CAPACITY']} hangar space each",
        "name": "Compact Flexers",
        "category": "military",
        "requires": ["big_flexers"],
    },
    "heavy_attackers": {
        "stars_power": 0,
        "constant": 40000,
        "desc": "Unlocks the Heavy Attacker unit (6 offense)",
        "name": "Heavy Attackers",
        "category": "military",
    },
    "elite_attackers": {
        "stars_power": 0,
        "constant": 200000,
        "desc": "Unlocks the Elite Attacker unit (7 offense)",
        "name": "Elite Attackers",
        "category": "military",
        "requires": ["heavy_attackers"],
    },
    "heavy_defenders": {
        "stars_power": 0,
        "constant": 48000,
        "desc": "Unlocks the Heavy Defender unit (6 defense)",
        "name": "Heavy Defenders",
        "category": "military",
    },
    "elite_defenders": {
        "stars_power": 0,
        "constant": 240000,
        "desc": "Unlocks the Elite Defender unit (7 defense)",
        "name": "Elite Defenders",
        "category": "military",
        "requires": ["heavy_defenders"],
    },
    "star_busters": {
        "stars_power": 0,
        "constant": 100000,
        "desc": "Unlocks the Star Buster missile",
        "name": "Star Busters",
        "category": "missiles",
    },
    "galaxy_busters": {
        "stars_power": 0,
        "constant": 250000,
        "desc": "Unlocks the Galaxy Buster missile",
        "name": "Galaxy Busters",
        "category": "missiles",
    },
    "drone_gadgets": {
        "stars_power": 0,
        "constant": 50000,
        "desc": f"Unlocks the Spy Bonus project. Reduces drone losses by {GAME_CONFIG['BASE_DRONE_GADGETS_LOSS_REDUCTION']:.1%}",
        "name": "Drone Gadgets",
        "category": "spy",
    },
}

PROJECTS_MAX_POINTS_FUNC = lambda stars, stars_power, constant: (stars ** stars_power) * constant

PROJECTS_FUNCS = {
    key: partial(
        PROJECTS_MAX_POINTS_FUNC,
        stars_power=project_dict["stars_power"],
        constant=project_dict["constant"]
    )
    for key, project_dict in PROJECTS.items()
}

CONTINUOUS_PROJECTS = [key for key, project in PROJECTS.items() if "max_bonus" in project]
ONE_TIME_PROJECTS = [key for key, project in PROJECTS.items() if "max_bonus" not in project]


def projects_max_points(stars):
    """Every project's max points for a kingdom of ``stars`` stars (what ``projects_max_points`` holds)."""
    return {key: PROJECTS_FUNCS[key](stars) for key in PROJECTS}


def has_project(kd_info, project):
    """Whether the kingdom has completed the one-time ``project``."""
    return project in (kd_info.get("completed_projects") or [])


def project_bonus(kd_info, project):
    """The current bonus of a continuous project: its max bonus times the share of max points earned, at most 1."""
    max_bonus = PROJECTS[project].get("max_bonus", 0)
    max_points = (kd_info.get("projects_max_points") or {}).get(project)
    if max_points is None:
        max_points = PROJECTS_FUNCS[project](kd_info.get("stars", 0))
    if not max_points:
        return 0.0
    points = (kd_info.get("projects_points") or {}).get(project, 0)
    return max_bonus * min(points / max_points, 1.0)


def project_bonuses(kd_info):
    """Every continuous project's current bonus, by project."""
    return {project: project_bonus(kd_info, project) for project in CONTINUOUS_PROJECTS}


def max_project_bonuses():
    """Every continuous project's largest bonus, by project."""
    return {project: PROJECTS[project]["max_bonus"] for project in CONTINUOUS_PROJECTS}


def project_locked_reason(kd_info, project):
    """
    Why engineers can not work on ``project`` yet, as a sentence for the player, or None if they can. A project is
    locked while it belongs to another race or a project it requires is not completed.
    """
    project_dict = PROJECTS[project]
    race = project_dict.get("race")
    if race and kd_info.get("race") != race:
        return f"Only {race} kingdoms can research {project_dict['name']}"
    missing = [required for required in project_dict.get("requires", []) if not has_project(kd_info, required)]
    if missing:
        return "Complete " + ", ".join(f'"{PROJECTS[required]["name"]}"' for required in missing) + " first"
    return None


def with_new_fields(kd_info):
    """
    Fill in, in place, the unit and project keys a kingdom made before they existed does not have, with their starting
    values, and return the kingdom. Only nested objects that are already there are filled. The refresh calls it, and
    writes the whole kingdom, so every kingdom has the keys after its next tick.
    """
    stars = kd_info.get("stars", 0)
    starting = INITIAL_KINGDOM_STATE["kingdom"]
    for field in ("units", "units_target", "projects_points", "projects_target", "projects_assigned"):
        if isinstance(kd_info.get(field), dict):
            for key, value in starting[field].items():
                kd_info[field].setdefault(key, value)
    if isinstance(kd_info.get("projects_max_points"), dict):
        for key in PROJECTS:
            kd_info["projects_max_points"].setdefault(key, PROJECTS_FUNCS[key](stars))
    return kd_info

REVEAL_OPERATIONS = [
    "spykingdom",
    "spymilitary",
    "spyshields",
    "spyprojects",
    "spystructures",
    "spydrones",
]
AGGRO_OPERATIONS = [
    "siphonfunds",
    "bombhomes",
    "sabotagefuelplants",
    "kidnappopulation",
    "suicidedrones"
]

DATE_SENTINEL = "2099-01-01T00:00:00+00:00"

INITIAL_KINGDOM_STARS = 300
# What a new kingdom starts with: some points in the first continuous projects, and engineers spread over them.
INITIAL_PROJECT_POINTS = {
    "pop_bonus": 1000,
    "fuel_bonus": 1000,
    "military_bonus": 1000,
    "money_bonus": 1000,
    "general_bonus": 1000,
}
INITIAL_PROJECTS_TARGET = {
    "pop_bonus": 0.2,
    "fuel_bonus": 0.2,
    "military_bonus": 0.2,
    "money_bonus": 0.2,
    "general_bonus": 0.2,
}
INITIAL_KINGDOM_STATE = {
    "kingdom": {
        "kdId": "",
        "name": "",
        "race": "",
        "status": "Active",
        "coordinate": 0,
        "last_income": "",
        "next_resolve": {
            "generals": DATE_SENTINEL,
            "spy_attempt": DATE_SENTINEL,
            "settles": DATE_SENTINEL,
            "mobis": DATE_SENTINEL,
            "missiles": DATE_SENTINEL,
            "engineers": DATE_SENTINEL,
            "structures": DATE_SENTINEL,
            "revealed": DATE_SENTINEL,
            "shared": DATE_SENTINEL,
            "auto_spending": DATE_SENTINEL,
        },
        "stars": INITIAL_KINGDOM_STARS,
        "fuel": 10000,
        "population": 2500,
        "networth": 0,
        "votes": 0,
        "money": 100000,
        "drones": 1000,
        "spy_attempts": 10,
        "generals_available": 4,
        "generals_out": [],
        "units": {key: 0 for key in UNITS},
        "max_recruits": 99999,
        "recruits_before_units": True,
        "units_target": {key: 0 for key in TRAINABLE_UNITS},
        "structures": {
            "homes": 0,
            "mines": 0,
            "fuel_plants": 0,
            "hangars": 0,
            "drone_factories": 0,
            "missile_silos": 0,
            "workshops": 0,
        },
        "structures_target": {
            "homes": 0,
            "mines": 0,
            "fuel_plants": 0,
            "hangars": 0,
            "drone_factories": 0,
            "missile_silos": 0,
            "workshops": 0,
        },
        "revealed_to": {},
        "auto_spending_enabled": False,
        "auto_spending": {
            "settle": 0,
            "structures": 0,
            "military": 0,
            "engineers": 0,
        },
        "funding": {
            "settle": 0,
            "structures": 0,
            "military": 0,
            "engineers": 0,
        },
        "auto_attack_enabled": False,
        "auto_attack_settings": {
            "flex": 0,
            "pure": 0,
        },
        "auto_rob_enabled": False,
        "auto_rob_settings": {
            "drones": 0,
            "shielded": False,
            "keep": 0,
        },
        "projects_points": {key: INITIAL_PROJECT_POINTS.get(key, 0) for key in PROJECTS},
        "auto_assign_projects": True,
        "projects_target": {key: INITIAL_PROJECTS_TARGET.get(key, 0) for key in PROJECTS},
        "projects_max_points": {
            key: PROJECTS_FUNCS[key](INITIAL_KINGDOM_STARS if key in CONTINUOUS_PROJECTS else 0) for key in PROJECTS
        },
        "projects_assigned": {key: 0 for key in PROJECTS},
        "completed_projects": [],
        "missiles": {
            "planet_busters": 0,
            "star_busters": 0,
            "galaxy_busters": 0,
        },
        "shields": {
            "military": 0.0,
            "spy": 0.0,
            "spy_radar": 0.0,
            "missiles": 0.0
        },
        "income": {},
        "schedule": [],
        "siphons": [],
    },
    "siphons_in": {"siphons_in": []},
    "siphons_out": {"siphons_out": []},
    "news": {"news": []},
    "settles": {"settles": []},
    "mobis": {"mobis": []},
    "structures": {"structures": []},
    "missiles": {"missiles": []},
    "engineers": {"engineers": []},
    "revealed": {
        "revealed": {},
        "galaxies": {},
        "revealed_galaxymates": [],
        "revealed_to_galaxymates": [],
    },
    "shared": {
        "shared": {},
        "shared_requests": {},
        "shared_offers": {},
    },
    "pinned": {"pinned": []},
    "spy_history": {"spy_history": []},
    "attack_history": {"attack_history": []},
    "missile_history": {"missile_history": []},
    "messages": {"messages": []},
    "notifs": {
        "news_kingdom": 0,
        "news_galaxy": 0,
        "messages": 0,
        "shared": 0,
    },
    "history": {
        "history": {
            "networth": [],
            "stars": [],
            "population": [],
            "drones": [],
            "engineers": [],
            "max_offense": [],
            "max_defense": [],
        }
    },
}

KINGDOM_CREATOR_STARTING_POINTS = 20000
KINGDOM_CREATOR_POINTS = {
    "drones": 1,
    "recruits": 1,
    "attack": 5,
    "defense": 5,
    "flex": 8,
    "engineers": 10,
}

GALAXY_POLICIES = {
    "policy_1": {
        "name": "Growth Doctrine",
        "options": {
            "1": {
                "name": "Expansionist",
                "desc": "You grow your kingdoms through exploring new frontiers. Your galaxy's settling costs 15% less"
            },
            "2": {
                "name": "Warlike",
                "desc": "You grow your kingdoms through military force. Your galaxy's generals return 10% faster"
            }
        }
    },
    "policy_2": {
        "name": "Defense Doctrine",
        "options": {
            "1": {
                "name": "Intelligence",
                "desc": "You protect your kingdoms through proactive intelligence gathering. Your galaxy's spy attempts return 10% faster"
            },
            "2": {
                "name": "Conscription",
                "desc": "You protect your kingdoms through mandatory military enlistment. Your galaxy's recruits are trained 20% faster"
            }
        }
    },
}

UNIVERSE_POLICIES = {
    "policy_1": {
        "name": "Arms Doctrine",
        "options": {
            "1": {
                "name": "Unregulated",
                "desc": "Militarization has no universal regulation. All military units cost 20% less."
            },
            "2": {
                "name": "Treatied",
                "desc": "Universal treaties enforce demilitarization. All military units cost 20% more."
            }
        }
    },
    "policy_2": {
        "name": "Trade Doctrine",
        "options": {
            "1": {
                "name": "Free Trade",
                "desc": "Kingdoms freely engage in mutually beneficial trade. Universal income is increased by 10%"
            },
            "2": {
                "name": "Isolationist",
                "desc": "Kingdoms impose tariffs on imported goods. Universal income is decreased by 10%"
            }
        }
    },
}

PRETTY_NAMES = {
    "spykingdom": "Spy on Kingdom",
    "spymilitary": "Spy on Military",
    "spyshields": "Spy on Shields",
    "spyprojects": "Spy on Projects",
    "spystructures": "Spy on Structures",
    "spydrones": "Spy on Drones",
    "siphonfunds": "Siphon Funds",
    "bombhomes": "Bomb Homes",
    "sabotagefuelplants": "Sabotage Fuel Plants",
    "kidnappopulation": "Kidnap Population",
    "suicidedrones": "Suicide Drones",
    "robprimitives": "Rob Primitives",
    "recruits": "Recruits",
    "attack": "Attackers",
    "defense": "Defenders",
    "flex": "Flexers",
    "big_flex": "Big Flexers",
    "heavy_attack": "Heavy Attackers",
    "elite_attack": "Elite Attackers",
    "heavy_defense": "Heavy Defenders",
    "elite_defense": "Elite Defenders",
    "engineers": "Engineers",
    "homes": "Homes",
    "mines": "Mines",
    "fuel_plants": "Fuel Plants",
    "hangars": "Hangars",
    "missile_silos": "Missile Silos",
    "drone_factories": "Drone Factories",
    "workshops": "Workshops",
    "planet_busters": "Planet Busters",
    "star_busters": "Star Busters",
    "galaxy_busters": "Galaxy Busters",
    "stars": "Stars",
    "structures": "Structures",
    "money": "Money",
}

SURRENDER_OPTIONS = {
    "stars": [
        0,
        0.05,
        0.1,
    ]
}
