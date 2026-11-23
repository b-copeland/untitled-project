import datetime
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
    # Playstyle units, unlocked by projects: as strong as the best unit of their line and dearer, each with a trait.
    # The traits that are numbers come from GAME_CONFIG, below it.
    'solar_attack': {
        'offense': 7,
        'defense': 0,
        'cost': 650,
        'fuel': 1,  # less SOLAR_FUEL_REDUCTION
        'hangar_capacity': 1,
    },
    'self_destruct_attack': {
        'offense': 7,
        'defense': 0,
        'cost': 650,
        'fuel': 1,
        'hangar_capacity': 1,
        'self_destruct': True,  # see self_destruct_share
    },
    'solar_defense': {
        'offense': 0,
        'defense': 7,
        'cost': 750,
        'fuel': 1,  # less SOLAR_FUEL_REDUCTION
        'hangar_capacity': 1,
    },
    'self_destruct_defense': {
        'offense': 0,
        'defense': 7,
        'cost': 750,
        'fuel': 1,
        'hangar_capacity': 1,
        'self_destruct': True,
    },
    'warp_big_flex': {
        'offense': 10,
        'defense': 10,
        'cost': 1800,
        'fuel': 2,
        'hangar_capacity': 2,
        'warp': True,  # all go with the general who returns first (conquer._split_across_generals)
    },
    'compact_big_flex': {
        'offense': 10,
        'defense': 10,
        'cost': 1600,
        'fuel': 2,
        'hangar_capacity': 2,  # COMPACT_FLEX_HANGAR_CAPACITY
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
    "attack", "heavy_attack", "elite_attack", "solar_attack", "self_destruct_attack",
    "defense", "heavy_defense", "elite_defense", "solar_defense", "self_destruct_defense",
    "flex", "big_flex", "warp_big_flex", "compact_big_flex",
    "recruits", "engineers",
)}

# A unit with "project" can only be trained, or upgraded to, once that project is completed.
UNITS["big_flex"]["project"] = "big_flexers"
UNITS["heavy_attack"]["project"] = "heavy_attackers"
UNITS["elite_attack"]["project"] = "elite_attackers"
UNITS["heavy_defense"]["project"] = "heavy_defenders"
UNITS["elite_defense"]["project"] = "elite_defenders"
UNITS["solar_attack"]["project"] = "solar_attackers"
UNITS["self_destruct_attack"]["project"] = "self_destructing_attackers"
UNITS["solar_defense"]["project"] = "solar_defenders"
UNITS["self_destruct_defense"]["project"] = "self_destructing_defenders"
UNITS["warp_big_flex"]["project"] = "warp_speed"
UNITS["compact_big_flex"]["project"] = "compact_flexers"

# A unit with "upgrades_from" can also be made from units of that kind at home, one tier at a time, for the difference
# in cost (upgrade_cost). Upgrades only go up a line: never back down, never across to another line or playstyle.
UNITS["heavy_attack"]["upgrades_from"] = "attack"
UNITS["elite_attack"]["upgrades_from"] = "heavy_attack"
UNITS["solar_attack"]["upgrades_from"] = "elite_attack"
UNITS["self_destruct_attack"]["upgrades_from"] = "elite_attack"
UNITS["heavy_defense"]["upgrades_from"] = "defense"
UNITS["elite_defense"]["upgrades_from"] = "heavy_defense"
UNITS["solar_defense"]["upgrades_from"] = "elite_defense"
UNITS["self_destruct_defense"]["upgrades_from"] = "elite_defense"
UNITS["warp_big_flex"]["upgrades_from"] = "big_flex"
UNITS["compact_big_flex"]["upgrades_from"] = "big_flex"
UPGRADABLE_UNITS = [key for key, unit in UNITS.items() if "upgrades_from" in unit]

# Units by role: offense only, defense only. Projects and race rules that name "pure" attackers or defenders use these.
PURE_ATTACK_UNITS = [key for key, unit in UNITS.items() if unit["offense"] > 0 and unit["defense"] == 0]
PURE_DEFENSE_UNITS = [
    key for key, unit in UNITS.items() if unit["defense"] > 0 and unit["offense"] == 0 and key != "recruits"
]

# The units trained from recruits: everything but recruits and engineers.
TRAINABLE_UNITS = [key for key in UNITS if key not in ("recruits", "engineers")]


def unit_hangar_space(kd_info, unit):
    """Hangar space one ``unit`` of this kingdom takes, after its projects."""
    space = UNITS[unit]["hangar_capacity"]
    if unit in PURE_ATTACK_UNITS and has_project(kd_info, "gaian_evolution"):
        space *= GAME_CONFIG["GAIAN_EVOLUTION_ATTACK_HANGAR_MULTIPLIER"]
    return space


def units_for(kd_info, units_desc=None, modifiers=None):
    """``UNITS`` (or ``units_desc``, e.g. with costs adjusted) with this kingdom's hangar space per unit, and for each
    unit that can be upgraded to, what one upgrade costs at those prices and ``modifiers`` (``upgrade_cost``)."""
    units_desc = units_desc if units_desc is not None else UNITS
    return {
        key: {
            **unit,
            "hangar_capacity": unit_hangar_space(kd_info, key),
            **({"upgrade_cost": upgrade_cost(units_desc, key, modifiers)} if "upgrades_from" in unit else {}),
        }
        for key, unit in units_desc.items()
    }


def upgrade_cost(units_desc, unit, modifiers=None):
    """What upgrading one unit to ``unit`` costs: its price less the price of the unit it is made from, after the
    kingdom's ``modifiers``. ``units_desc`` is ``UNITS`` with the prices the kingdom pays
    (``getters._get_units_adjusted_costs``)."""
    difference = units_desc[unit]["cost"] - units_desc[UNITS[unit]["upgrades_from"]]["cost"]
    return difference * max(1 + modifier(modifiers, "upgrade_cost"), 0)


# Each kind of shield: the constant for the fuel it costs, and the effect that changes that.
SHIELD_FUEL = {
    "military": ("BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT", "military_shield_fuel"),
    "spy": ("BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT", "spy_shield_fuel"),
    "spy_radar": ("BASE_SPY_RADAR_COST_PER_LAND_PER_PCT", "spy_shield_fuel"),
    "missiles": ("BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT", "missile_shield_fuel"),
}


def shield_fuel_per_pct(kind, modifiers=None):
    """Fuel per epoch one point of ``kind`` shields costs per star, after the kingdom's ``modifiers``: the effect for
    that kind of shield and ``shield_fuel``, for every kind."""
    constant, effect = SHIELD_FUEL[kind]
    return GAME_CONFIG[constant] * max(1 + modifier(modifiers, effect) + modifier(modifiers, "shield_fuel"), 0)


def self_destruct_share(units, stat):
    """The share of these units' raw ``stat`` ("offense" or "defense") that comes from self-destructing units, which is
    how much of ``SELF_DESTRUCT_LOSSES_INCREASE`` they add to the other side's losses. Zero if they have none."""
    total = sum(UNITS[key][stat] * count for key, count in units.items() if key in UNITS)
    if total <= 0:
        return 0.0
    destructing = sum(
        UNITS[key][stat] * count for key, count in units.items() if UNITS.get(key, {}).get("self_destruct")
    )
    return destructing / total


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
    "solar_attack",
    "self_destruct_attack",
    "big_flex",
    "warp_big_flex",
    "compact_big_flex",
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


def per_hour(per_epoch):
    """A per-epoch amount as the per-hour figure players are shown (they never see epochs), e.g. ``300`` or ``1.5``."""
    return f"{per_epoch * 3600 / GAME_CONFIG['BASE_EPOCH_SECONDS']:g}"


GAME_CONFIG = {
    "BASE_EPOCH_SECONDS": _epoch_seconds(),
    # How far ahead the Status page shows queued units and structures, in epochs (1, 2, 4, 8 and 24 hours at the
    # default epoch), so the columns follow the epoch length. Limits that count everything queued use "queued" instead.
    "QUEUE_FORECAST_EPOCHS": [2, 4, 8, 16, 48],
    # The galaxy board: the longest post, in characters, and how many posts it keeps (the oldest go first).
    "GALAXY_BOARD_MAX_LENGTH": 500,
    "GALAXY_BOARD_KEEP_POSTS": 100,

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
    # The most a kingdom gives up to all the intel it has accepted on one target (each category is paid to its sharer).
    "BASE_MAX_TOTAL_SHARE_CUT": 0.30,
    # The longest an intel bounty (a request on the galaxy's board) can stay up, in epochs.
    "BASE_INTEL_BOUNTY_MAX_EPOCHS": 48,
    # How old last-known intel (what was seen when a reveal ended) is shown as: fresh under the first, aging under the
    # second, stale after. The pages colour it yellow, orange and red.
    "LAST_KNOWN_FRESH_EPOCHS": 12,
    "LAST_KNOWN_AGING_EPOCHS": 24,

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
    # Not a gameplay limit: only a guard against a kingdom document grown huge by a script.
    "BASE_MAX_SCHEDULE_ENTRIES": 200,

    "BASE_MILITARY_SHIELDS_MAX": 0.10, 
    "BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT": 0.1, 
    "BASE_SPY_SHIELDS_MAX": 0.20, 
    "BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT": 0.05, 
    "BASE_SPY_RADAR_MAX": 0.20, 
    "BASE_SPY_RADAR_COST_PER_LAND_PER_PCT": 0.05, 
    "BASE_MISSILES_SHIELDS_MAX": 1.0, 
    "BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT": 0.005, 

    "BASE_VOTES_COST": 10000,
    "BASE_GALAXY_VOTE_COOLDOWN_EPOCHS": 6,  # once a kingdom has changed its vote for galaxy leader, that vote stays this long 
    "BASE_ELECTION_LENGTH_MULTIPLIER": 24, 
    "BASE_ELECTION_RESULTS_DURATION_MULTIPLIER": 24 * 6, 

    "BASE_AUTO_SPENDING_TIME_MULTIPLIER": 0.1, 

    # Galaxy policies (galaxypolicies.py): how many of GALAXY_POLICIES a round plays, and how often a galaxy's votes are
    # tallied. Between tallies the policies hold; each tally weighs every vote by how long it was held since the last.
    "GALAXY_POLICIES_PER_ROUND": 4,
    "GALAXY_POLICY_TALLY_EPOCHS": 12,
    # Universe policies (universepolicies.py): the first election opens this many epochs after the round starts (unless
    # the admin sets another time), and each ballot has this many policies. Wealth's options hit the leaders.
    "BASE_FIRST_ELECTION_START_MULTIPLIER": 48,
    "UNIVERSE_POLICIES_PER_ELECTION": 2,
    "UNIVERSE_WEALTH_TOP_KINGDOMS": 10,
    "UNIVERSE_WEALTH_TOP_GALAXIES": 2,

    # Cluster politics (clusters.py). Placeholders: the framework is in, the balance is not.
    "CLUSTER_SIZE": 5,  # galaxies per cluster when /api/admin/newround makes them
    "CLUSTER_REF_SIZE": 5,  # a cluster of this many galaxies gains exactly CLUSTER_VOTE_RATE per vote
    "CLUSTER_VOTE_COOLDOWN_EPOCHS": 6,  # once a galaxy's vote has changed (cast, switched or withdrawn), it stays this long
    "CLUSTER_VOTE_RATE": 0.005,  # per galaxy vote per epoch, as a fraction of the benefit's max
    "CLUSTER_DECAY_RATE": 0.005,  # per epoch, as a fraction of the benefit's max, voted for or not
    "CLUSTER_BENEFITS_PER_ROUND": 7,  # of CLUSTER_BENEFITS, drawn when the round is made, for the whole round

    # Empire targets (targets.py). Placeholders: the framework is in, the balance is not. The points each kind of damage
    # earns are in TARGET_ACTIONS.
    "TARGET_MAX_DELEGATES": 3,  # kingdoms the emperor can name to manage the empire's targets with them
    "TARGET_DEFAULT_FUND_SHARE": 0.10,  # of a successful attack's stars and money on a target, into its spoils fund
    "TARGET_MAX_FUND_SHARE": 0.50,  # the most leadership can set the fund share to
    "TARGET_MAX_POINTS_MULTIPLIER": 5.0,  # leadership can scale each action's points from 0 up to this many times
    "TARGET_HISTORY_LENGTH": 20,  # ended targets kept in the empire's history
    "TARGET_REMARK_COOLDOWN_EPOCHS": 24,  # a kingdom removed as a target can be marked again by that empire after this
    # A dead target's land and money go into the fund in proportion to the empire's points on it, all of it once it has
    # this many points for every star the target had when it was marked; the rest leaves the game.
    "TARGET_REMAINS_POINTS_PER_STAR": 0.5,
    "TARGET_MAX_PAYOUT_STARS_SHARE": 0.10,  # the most stars one payout gives a kingdom, as a share of its own land

    "NETWORTH_VALUES": {
        "stars": 25,
        "structures": 25,
        "money": 0.002,
        "attack": 7,
        "heavy_attack": 8,
        "elite_attack": 9,
        "solar_attack": 10,
        "self_destruct_attack": 10,
        "defense": 8,
        "heavy_defense": 9,
        "elite_defense": 11,
        "solar_defense": 12,
        "self_destruct_defense": 12,
        "flex": 10,
        "big_flex": 20,
        "warp_big_flex": 25,
        "compact_big_flex": 24,
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

    # One-time structure projects: what each structure of that kind gains once completed (proposals).
    "MINES_PROJECT_MONEY_PER_MINE": 20,  # per epoch
    "HANGARS_PROJECT_UNITS_PER_HANGAR": 10,
    "DRONE_FACTORIES_PROJECT_DRONES_PER_FACTORY": 0.25,  # per epoch
    "MISSILE_SILOS_PROJECT_MISSILES_PER_SILO": 0.5,
    "WORKSHOPS_PROJECT_ENGINEERS_PER_WORKSHOP": 10,

    # One-time economy and military projects: the share they give once completed (proposals).
    "SETTLE_COST_PROJECT_REDUCTION": 0.1,
    "RECRUIT_COST_PROJECT_REDUCTION": 0.5,
    "POP_GROWTH_PROJECT_INCREASE": 1,
    "CASUALTIES_PROJECT_REDUCTION": 0.25,
    "SPY_PROTECTION_PROJECT_REDUCTION": 0.25,

    # Playstyle units, each unlocked by its project.
    "SOLAR_FUEL_REDUCTION": 0.5,  # solar attackers and defenders use this much less fuel than the unit they come from
    # Self-destructing units raise the other side's unit losses by up to this much, scaled by their share of the
    # strength on their side of the battle (the attack's offense, or the defense at home): self_destruct_share.
    "SELF_DESTRUCT_LOSSES_INCREASE": 0.3,
    "COMPACT_FLEX_HANGAR_CAPACITY": 1,  # hangar space one compact big flexer takes

    # Racial capstones.
    "GAIAN_CAPSTONE_SETTLE_TIME_REDUCTION": 0.50,
    "GAIAN_CAPSTONE_STRUCTURE_TIME_REDUCTION": 0.50,
    "XO_CAPSTONE_RETURN_REDUCTION": 0.10,  # added to the generals speed bonus
    "XO_CAPSTONE_WAR_LOSSES_INCREASE": 0.25,  # the defender's losses when Xo attacks an empire it is at war with
    "VULT_CAPSTONE_DRONE_DAMAGE_INCREASE": 0.25,  # damage of aggressive spy operations
    "LUMINA_CAPSTONE_SHIELDING_FUEL_REDUCTION": 0.5,  # fuel a shielded drone costs
    "FUZI_CAPSTONE_MISSILE_DAMAGE_INCREASE": 0.25,
    "BASE_DRONES_SHIELDING_FUEL_PER_DRONE": 1,

    # Racial evolutions.
    "GAIAN_EVOLUTION_ATTACK_HANGAR_MULTIPLIER": 0.5,  # hangar space a pure attacker takes, as a share of its usual
    "XO_EVOLUTION_SETTLE_COST_REDUCTION": 0.25,
    "XO_EVOLUTION_MONEY_PER_OPEN_HANGAR_SPACE": 1.75,  # per epoch
    "LUMINA_EVOLUTION_WAR_DRONE_DAMAGE_INCREASE": 0.40,  # aggressive spy damage against empires at war with you
    "FUZI_EVOLUTION_DRONES_PER_EMPTY_SILO": 0.5,  # per epoch
    "FUZI_EVOLUTION_MONEY_PER_EMPTY_SILO": 50,  # per epoch
    "FUZI_EVOLUTION_FUEL_PER_EMPTY_SILO": 100,  # per epoch
    "FUZI_EVOLUTION_FUEL_STORAGE_PER_EMPTY_SILO": 500,
    "FUZI_EVOLUTION_POP_PER_EMPTY_SILO": 25,
}

# The playstyle units' traits that are numbers in GAME_CONFIG.
UNITS["solar_attack"]["fuel"] *= 1 - GAME_CONFIG["SOLAR_FUEL_REDUCTION"]
UNITS["solar_defense"]["fuel"] *= 1 - GAME_CONFIG["SOLAR_FUEL_REDUCTION"]
UNITS["compact_big_flex"]["hangar_capacity"] = GAME_CONFIG["COMPACT_FLEX_HANGAR_CAPACITY"]

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
#   - one-time (no "max_bonus"): done once the points reach the max points; then it is in "completed_projects". A
#     one-time project with "bonus" gives that whole bonus (a share) from the moment it is completed, and nothing
#     before; one with "increase" adds that raw amount to each structure of its kind (read with project_increase).
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
    # One project per structure. Homes and fuel plants have the continuous ones above; the others are one-time, and
    # once completed each structure of that kind gives a fixed amount more.
    "mines_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "increase": GAME_CONFIG["MINES_PROJECT_MONEY_PER_MINE"],
        "desc": f"Each mine produces {per_hour(GAME_CONFIG['MINES_PROJECT_MONEY_PER_MINE'])} more money per hour",
        "name": "Mines Bonus",
        "category": "structures",
    },
    "hangars_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "increase": GAME_CONFIG["HANGARS_PROJECT_UNITS_PER_HANGAR"],
        "desc": f"Each hangar houses {GAME_CONFIG['HANGARS_PROJECT_UNITS_PER_HANGAR']} more units",
        "name": "Hangars Bonus",
        "category": "structures",
    },
    "drone_factories_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "increase": GAME_CONFIG["DRONE_FACTORIES_PROJECT_DRONES_PER_FACTORY"],
        "desc": f"Each drone factory produces {per_hour(GAME_CONFIG['DRONE_FACTORIES_PROJECT_DRONES_PER_FACTORY'])} more drones per hour",
        "name": "Drone Factories Bonus",
        "category": "structures",
    },
    "missile_silos_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "increase": GAME_CONFIG["MISSILE_SILOS_PROJECT_MISSILES_PER_SILO"],
        "desc": f"Each missile silo stores {GAME_CONFIG['MISSILE_SILOS_PROJECT_MISSILES_PER_SILO']} more missiles",
        "name": "Missile Silos Bonus",
        "category": "structures",
    },
    "workshops_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "increase": GAME_CONFIG["WORKSHOPS_PROJECT_ENGINEERS_PER_WORKSHOP"],
        "desc": f"Each workshop houses {GAME_CONFIG['WORKSHOPS_PROJECT_ENGINEERS_PER_WORKSHOP']} more engineers",
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
    "settle_cost_bonus": {
        "stars_power": 0,
        "constant": 500000,
        "bonus": GAME_CONFIG["SETTLE_COST_PROJECT_REDUCTION"],
        "desc": f"Decreases the cost of settling new stars by {GAME_CONFIG['SETTLE_COST_PROJECT_REDUCTION']:.0%} once completed",
        "name": "Cheaper Exploring",
        "category": "economy",
    },
    "recruit_cost_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "bonus": GAME_CONFIG["RECRUIT_COST_PROJECT_REDUCTION"],
        "desc": f"Decreases the cost of recruits by {GAME_CONFIG['RECRUIT_COST_PROJECT_REDUCTION']:.0%} once completed",
        "name": "Cheaper Recruits",
        "category": "economy",
    },
    "pop_growth_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "bonus": GAME_CONFIG["POP_GROWTH_PROJECT_INCREASE"],
        "desc": f"Increases population growth by {GAME_CONFIG['POP_GROWTH_PROJECT_INCREASE']:.0%} once completed",
        "name": "Population Growth",
        "category": "economy",
    },
    "casualties_bonus": {
        "stars_power": 0,
        "constant": 100000,
        "bonus": GAME_CONFIG["CASUALTIES_PROJECT_REDUCTION"],
        "desc": f"Decreases the units you lose in battle, attacking or defending, by {GAME_CONFIG['CASUALTIES_PROJECT_REDUCTION']:.0%} once completed",
        "name": "Fewer Casualties",
        "category": "military",
    },
    "spy_protection_bonus": {
        "stars_power": 0,
        "constant": 200000,
        "bonus": GAME_CONFIG["SPY_PROTECTION_PROJECT_REDUCTION"],
        "desc": f"Decreases the damage aggressive spy operations do to you by {GAME_CONFIG['SPY_PROTECTION_PROJECT_REDUCTION']:.0%} once completed",
        "name": "Counter-Intelligence",
        "category": "spy",
    },
    "general_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Decreases generals time to return by the current bonus",
        "name": "Generals Speed Bonus",
        "category": "military",
        "requires": ["casualties_bonus"],
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
    # The 7-strength units cost more points than the 6-strength ones, and need them first. Defender
    # projects cost about 20% more than attacker projects.
    # Playstyle projects: two for the best unit of each kind.
    "heavy_attackers": {
        "stars_power": 0,
        "constant": 100000,
        "desc": "Unlocks the Heavy Attacker unit (6 offense)",
        "name": "Heavy Attackers",
        "category": "military",
    },
    "elite_attackers": {
        "stars_power": 0,
        "constant": 250000,
        "desc": "Unlocks the Elite Attacker unit (7 offense)",
        "name": "Elite Attackers",
        "category": "military",
        "requires": ["heavy_attackers"],
    },
    "heavy_defenders": {
        "stars_power": 0,
        "constant": 120000,
        "desc": "Unlocks the Heavy Defender unit (6 defense)",
        "name": "Heavy Defenders",
        "category": "military",
    },
    "elite_defenders": {
        "stars_power": 0,
        "constant": 300000,
        "desc": "Unlocks the Elite Defender unit (7 defense)",
        "name": "Elite Defenders",
        "category": "military",
        "requires": ["heavy_defenders"],
    },
    "solar_attackers": {
        "stars_power": 0,
        "constant": 500000,
        "desc": f"Unlocks the Solar Attacker unit (7 offense, {GAME_CONFIG['SOLAR_FUEL_REDUCTION']:.0%} less fuel)",
        "name": "Solar Attackers",
        "category": "military",
        "requires": ["elite_attackers"],
    },
    "self_destructing_attackers": {
        "stars_power": 0,
        "constant": 500000,
        "desc": f"Unlocks the Self-Destructing Attacker unit (7 offense): kingdoms it attacks lose up to "
                f"{GAME_CONFIG['SELF_DESTRUCT_LOSSES_INCREASE']:.0%} more units, by its share of the attack's offense",
        "name": "Self-Destructing Attackers",
        "category": "military",
        "requires": ["elite_attackers"],
    },
    "solar_defenders": {
        "stars_power": 0,
        "constant": 600000,
        "desc": f"Unlocks the Solar Defender unit (7 defense, {GAME_CONFIG['SOLAR_FUEL_REDUCTION']:.0%} less fuel)",
        "name": "Solar Defenders",
        "category": "military",
        "requires": ["elite_defenders"],
    },
    "self_destructing_defenders": {
        "stars_power": 0,
        "constant": 600000,
        "desc": f"Unlocks the Self-Destructing Defender unit (7 defense): kingdoms that attack you lose up to "
                f"{GAME_CONFIG['SELF_DESTRUCT_LOSSES_INCREASE']:.0%} more units, by its share of your defense",
        "name": "Self-Destructing Defenders",
        "category": "military",
        "requires": ["elite_defenders"],
    },
    "warp_speed": {
        "stars_power": 0,
        "constant": 800000,
        "desc": "Unlocks the Warp Speed Big Flexer unit (10 / 10): sent on an attack, they all come home with the "
                "first general to return",
        "name": "Warp Speed",
        "category": "military",
        "requires": ["big_flexers"],
    },
    "compact_flexers": {
        "stars_power": 0,
        "constant": 800000,
        "desc": f"Unlocks the Compact Big Flexer unit (10 / 10), which takes "
                f"{GAME_CONFIG['COMPACT_FLEX_HANGAR_CAPACITY']} hangar space",
        "name": "Compact Flexers",
        "category": "military",
        "requires": ["big_flexers"],
    },
    "gaian_capstone": {
        "stars_power": 0,
        "constant": 500000,
        "desc": f"Settling takes {GAME_CONFIG['GAIAN_CAPSTONE_SETTLE_TIME_REDUCTION']:.0%} less time and building structures "
                f"{GAME_CONFIG['GAIAN_CAPSTONE_STRUCTURE_TIME_REDUCTION']:.0%} less time",
        "name": "Gaian Terraforming",
        "category": "racial",
        "race": "Gaian",
    },
    "xo_capstone": {
        "stars_power": 0,
        "constant": 500000,
        "desc": f"Generals return {GAME_CONFIG['XO_CAPSTONE_RETURN_REDUCTION']:.0%} faster, and kingdoms of empires you are "
                f"at war with lose {GAME_CONFIG['XO_CAPSTONE_WAR_LOSSES_INCREASE']:.0%} more units to your attacks",
        "name": "Xo Warlords",
        "category": "racial",
        "race": "Xo",
    },
    "vult_capstone": {
        "stars_power": 0,
        "constant": 500000,
        "desc": f"Aggressive spy operations do {GAME_CONFIG['VULT_CAPSTONE_DRONE_DAMAGE_INCREASE']:.0%} more damage",
        "name": "Vult Swarm",
        "category": "racial",
        "race": "Vult",
    },
    "lumina_capstone": {
        "stars_power": 0,
        "constant": 500000,
        "desc": f"Shielding drones costs {GAME_CONFIG['LUMINA_CAPSTONE_SHIELDING_FUEL_REDUCTION']:.0%} less fuel",
        "name": "Lumina Prisms",
        "category": "racial",
        "race": "Lumina",
    },
    "fuzi_capstone": {
        "stars_power": 0,
        "constant": 500000,
        "desc": f"Missiles do {GAME_CONFIG['FUZI_CAPSTONE_MISSILE_DAMAGE_INCREASE']:.0%} more damage",
        "name": "Fuzi Warheads",
        "category": "racial",
        "race": "Fuzi",
    },
    "gaian_evolution": {
        "stars_power": 0,
        "constant": 1000000,
        "desc": f"Pure attackers take {GAME_CONFIG['GAIAN_EVOLUTION_ATTACK_HANGAR_MULTIPLIER']:.0%} of their usual hangar space",
        "name": "Gaian Evolution: Living Hangars",
        "category": "racial",
        "race": "Gaian",
    },
    "xo_evolution": {
        "stars_power": 0,
        "constant": 1000000,
        "desc": f"Settling costs {GAME_CONFIG['XO_EVOLUTION_SETTLE_COST_REDUCTION']:.0%} less, and each open hangar space "
                f"earns {per_hour(GAME_CONFIG['XO_EVOLUTION_MONEY_PER_OPEN_HANGAR_SPACE'])} money per hour",
        "name": "Xo Evolution: Mercenary Hangars",
        "category": "racial",
        "race": "Xo",
    },
    "vult_evolution": {
        "stars_power": 0,
        "constant": 1000000,
        "desc": "Unlocks Full Infiltration, a drone operation that reveals everything about the target at once",
        "name": "Vult Evolution: Full Infiltration",
        "category": "racial",
        "race": "Vult",
    },
    "lumina_evolution": {
        "stars_power": 0,
        "constant": 1000000,
        "desc": f"Every galaxy is always revealed to you, and aggressive spy operations against empires at war with you "
                f"do {GAME_CONFIG['LUMINA_EVOLUTION_WAR_DRONE_DAMAGE_INCREASE']:.0%} more damage",
        "name": "Lumina Evolution: All-Seeing",
        "category": "racial",
        "race": "Lumina",
    },
    "fuzi_evolution": {
        "stars_power": 0,
        "constant": 1000000,
        "desc": f"Each empty missile silo makes {per_hour(GAME_CONFIG['FUZI_EVOLUTION_DRONES_PER_EMPTY_SILO'])} drones, "
                f"{per_hour(GAME_CONFIG['FUZI_EVOLUTION_MONEY_PER_EMPTY_SILO'])} money and "
                f"{per_hour(GAME_CONFIG['FUZI_EVOLUTION_FUEL_PER_EMPTY_SILO'])} fuel per hour, stores "
                f"{GAME_CONFIG['FUZI_EVOLUTION_FUEL_STORAGE_PER_EMPTY_SILO']} fuel and houses "
                f"{GAME_CONFIG['FUZI_EVOLUTION_POP_PER_EMPTY_SILO']} population",
        "name": "Fuzi Evolution: Silo Cities",
        "category": "racial",
        "race": "Fuzi",
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
BONUS_PROJECTS = [key for key, project in PROJECTS.items() if "max_bonus" in project or "bonus" in project]


def projects_max_points(stars):
    """Every project's max points for a kingdom of ``stars`` stars (what ``projects_max_points`` holds)."""
    return {key: PROJECTS_FUNCS[key](stars) for key in PROJECTS}


def has_project(kd_info, project):
    """Whether the kingdom has completed the one-time ``project``."""
    return project in (kd_info.get("completed_projects") or [])


def project_bonus(kd_info, project):
    """
    The current bonus of ``project``. Continuous: its max bonus times the share of max points earned, at most 1.
    One-time with a "bonus": that bonus once completed, 0 before. Any other one-time project: 0.
    """
    if "max_bonus" not in PROJECTS[project]:
        return PROJECTS[project].get("bonus", 0.0) if has_project(kd_info, project) else 0.0
    max_bonus = PROJECTS[project]["max_bonus"]
    max_points = (kd_info.get("projects_max_points") or {}).get(project)
    if max_points is None:
        max_points = PROJECTS_FUNCS[project](kd_info.get("stars", 0))
    if not max_points:
        return 0.0
    points = (kd_info.get("projects_points") or {}).get(project, 0)
    return max_bonus * min(points / max_points, 1.0)


def project_increase(kd_info, project):
    """What a one-time project with an "increase" adds to each structure of its kind: the increase once completed, else 0."""
    return PROJECTS[project].get("increase", 0) if has_project(kd_info, project) else 0


def project_bonuses(kd_info):
    """The current bonus of every project that gives one (continuous, or one-time with a "bonus"), by project."""
    return {project: project_bonus(kd_info, project) for project in BONUS_PROJECTS}


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
    "spyall",
]
# What each intel operation reveals: its name without "spy", except Full Infiltration, which reveals everything.
REVEAL_OPERATION_STATS = {operation: [operation.replace("spy", "")] for operation in REVEAL_OPERATIONS}
REVEAL_OPERATION_STATS["spyall"] = ["kingdom", "military", "shields", "projects", "structures", "drones"]
# The kingdom fields each kind of intel reveals (``revealed_fields``). Name, race, status and coordinate are public.
PUBLIC_KINGDOM_FIELDS = ("name", "race", "status", "coordinate")
REVEAL_FIELDS = {
    "stats": ["stars", "networth"],
    "kingdom": ["stars", "fuel", "population", "networth", "money", "missiles"],
    "military": ["units", "generals_available", "generals_out"],
    "structures": ["structures"],
    "shields": ["shields"],
    "projects": ["projects_points", "projects_max_points", "projects_assigned", "completed_projects"],
    "drones": ["drones", "spy_attempts"],
}


def revealed_fields(kd_info, categories, public=True, derived=True):
    """
    What of ``kd_info`` the intel ``categories`` reveal, as another kingdom sees it: the fields of each category (with
    the engineers when projects are revealed) and the public fields unless ``public`` is false. ``derived`` adds what
    is worked out from them (``with_project_bonuses``); last-known snapshots leave it out and add it when read.
    """
    keys = set(PUBLIC_KINGDOM_FIELDS) if public else set()
    for category in categories:
        keys.update(REVEAL_FIELDS[category])
    shown = {key: value for key, value in kd_info.items() if key in keys}
    if "projects_points" in shown:
        shown["units"] = {**shown.get("units", {}), "engineers": kd_info["units"]["engineers"]}
        if derived:
            with_project_bonuses(shown)
    return shown


def with_project_bonuses(shown):
    """Add, in place, the project bonuses and engineers worked out from revealed projects, and return ``shown``."""
    # A kingdom with no stars left (a dead one) has no project caps: project_bonus gives it no bonuses.
    shown["max_bonuses"] = max_project_bonuses()
    shown["current_bonuses"] = project_bonuses(shown)
    shown["engineers"] = shown.get("units", {}).get("engineers", 0)
    return shown


# Operations that need a project first.
OPERATION_PROJECTS = {"spyall": "vult_evolution"}
# Operations a project makes obsolete: the pages stop offering them once it is done (the server still accepts them, so
# schedules made before keep working).
OPERATIONS_REPLACED_BY_PROJECT = {"vult_evolution": [op for op in REVEAL_OPERATIONS if op != "spyall"]}
AGGRO_OPERATIONS = [
    "siphonfunds",
    "bombhomes",
    "sabotagefuelplants",
    "kidnappopulation",
    "suicidedrones"
]

DATE_SENTINEL = "2099-01-01T00:00:00+00:00"


def utc(value):
    """
    A time as an aware UTC datetime, from a datetime or an ISO 8601 string ("Z" and a time without a zone both mean
    UTC). Compare, sort and take the min or max of times through this, never as strings: two strings for the same
    instant can differ ("+00:00" or "Z", with or without microseconds, another zone), so string order is not time order.
    """
    if isinstance(value, datetime.datetime):
        parsed = value
    else:
        text = value.strip()
        parsed = datetime.datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def is_after(time, since):
    """True if ``time`` is later than ``since``. An empty or missing ``since`` is the start of time; an empty ``time``
    is never after anything. For cursors such as "the news seen so far"."""
    if not time:
        return False
    return not since or utc(time) > utc(since)

INITIAL_KINGDOM_STARS = 300
# What a new kingdom starts with: some points in the first continuous projects, and engineers spread over them.
INITIAL_PROJECT_POINTS = {
    "pop_bonus": 1000,
    "fuel_bonus": 1000,
    "military_bonus": 1000,
    "money_bonus": 1000,
}
# Generals Speed Bonus is not here: it needs Fewer Casualties first.
INITIAL_PROJECTS_TARGET = {
    "pop_bonus": 0.25,
    "fuel_bonus": 0.25,
    "military_bonus": 0.25,
    "money_bonus": 0.25,
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
        "galaxy_board": 0,
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

# What policies and cluster benefits can change, by name. A policy option or a benefit says how much of each effect it
# has as a signed share: +0.15 makes the thing 15% bigger, -0.15 makes it 15% smaller. The game reads them through
# ``modifier`` where the rule lives; several sources of one effect add up. ``better`` says which way helps the
# kingdom (a cluster benefit always helps, so its level becomes a value of that sign), and ``up``/``down`` are the
# sentences the pages show for a rise or a fall, ``{pct}`` being its size.
EFFECTS = {
    "settle_cost": {"better": "lower", "up": "Settling costs {pct} more", "down": "Settling costs {pct} less"},
    "primitives_attack_stars": {"better": "higher", "up": "Attacks on primitives gain {pct} more stars",
                                "down": "Attacks on primitives gain {pct} fewer stars"},
    "generals_return_time": {"better": "lower", "up": "Generals return {pct} slower",
                             "down": "Generals return {pct} faster"},
    "drone_production": {"better": "higher", "up": "Drone factories make {pct} more drones",
                         "down": "Drone factories make {pct} fewer drones"},
    "spy_attempt_time": {"better": "lower", "up": "Spy attempts come back {pct} slower",
                         "down": "Spy attempts come back {pct} faster"},
    "recruit_time": {"better": "lower", "up": "Drafting recruits takes {pct} longer",
                     "down": "Drafting recruits takes {pct} less time"},
    "project_points_continuous": {"better": "higher", "up": "Engineers earn {pct} more points on continuous projects",
                                  "down": "Engineers earn {pct} fewer points on continuous projects"},
    "project_points_one_time": {"better": "higher", "up": "Engineers earn {pct} more points on one-time projects",
                                "down": "Engineers earn {pct} fewer points on one-time projects"},
    "structure_cost": {"better": "lower", "up": "Structures cost {pct} more", "down": "Structures cost {pct} less"},
    "engineer_cost": {"better": "lower", "up": "Engineers cost {pct} more", "down": "Engineers cost {pct} less"},
    "upgrade_cost": {"better": "lower", "up": "Unit upgrades cost {pct} more", "down": "Unit upgrades cost {pct} less"},
    "raze_return": {"better": "higher", "up": "Razing structures refunds {pct} more",
                    "down": "Razing structures refunds {pct} less"},
    "mines_income": {"better": "higher", "up": "Mines make {pct} more money", "down": "Mines make {pct} less money"},
    "fuel_production": {"better": "higher", "up": "Fuel plants make {pct} more fuel",
                        "down": "Fuel plants make {pct} less fuel"},
    "pop_income": {"better": "higher", "up": "Population pays {pct} more income",
                   "down": "Population pays {pct} less income"},
    "unit_fuel": {"better": "lower", "up": "Units burn {pct} more fuel", "down": "Units burn {pct} less fuel"},
    "unit_cost": {"better": "lower", "up": "Military units cost {pct} more", "down": "Military units cost {pct} less"},
    "pure_attack_cost": {"better": "lower", "up": "Pure attackers cost {pct} more",
                         "down": "Pure attackers cost {pct} less"},
    "pure_defense_cost": {"better": "lower", "up": "Pure defenders cost {pct} more",
                          "down": "Pure defenders cost {pct} less"},
    "rob_primitives": {"better": "higher", "up": "Robbing primitives yields {pct} more money",
                       "down": "Robbing primitives yields {pct} less money"},
    "siphon_shield_fuel": {"better": "lower", "up": "Shielding Siphon Funds operations costs {pct} more fuel",
                           "down": "Shielding Siphon Funds operations costs {pct} less fuel"},
    "reveal_duration": {"better": "higher", "up": "Your reveals last {pct} longer",
                        "down": "Your reveals last {pct} less"},
    "attacker_losses": {"better": "lower", "up": "You lose {pct} more of the units you send to attack",
                        "down": "You lose {pct} fewer of the units you send to attack"},
    "drone_losses": {"better": "lower", "up": "You lose {pct} more drones on spy operations",
                     "down": "You lose {pct} fewer drones on spy operations"},
    "missile_cost": {"better": "lower", "up": "Missiles cost {pct} more", "down": "Missiles cost {pct} less"},
    "missile_shield_fuel": {"better": "lower", "up": "Missile shields cost {pct} more fuel",
                            "down": "Missile shields cost {pct} less fuel"},
    "military_shield_fuel": {"better": "lower", "up": "Military shields cost {pct} more fuel",
                             "down": "Military shields cost {pct} less fuel"},
    "spy_shield_fuel": {"better": "lower", "up": "Spy shields and spy radar cost {pct} more fuel",
                        "down": "Spy shields and spy radar cost {pct} less fuel"},
    "structure_time": {"better": "lower", "up": "Structures take {pct} longer to build",
                       "down": "Structures build {pct} faster"},
    # What only universe policies do: they punish, so each is worded for a rise in what hurts.
    "attack_stars": {"better": "higher", "up": "Attacks on kingdoms gain {pct} more stars",
                     "down": "Attacks on kingdoms gain {pct} fewer stars"},
    "aggressive_failure_losses": {"better": "lower", "up": "Failed aggressive spy operations lose {pct} more drones",
                                  "down": "Failed aggressive spy operations lose {pct} fewer drones"},
    "primitives_defense": {"better": "lower", "up": "Primitives defend {pct} harder", "down": "Primitives defend {pct} less"},
    "aggression": {"better": "lower", "up": "Attacks and aggressive spying raise {pct} more aggression between empires",
                   "down": "Attacks and aggressive spying raise {pct} less aggression between empires"},
    "spy_defense": {"better": "higher", "up": "Spy operations need {pct} more drones to succeed against a kingdom",
                    "down": "Spy operations need {pct} fewer drones to succeed against a kingdom"},
    "money_income": {"better": "higher", "up": "You earn {pct} more money", "down": "You earn {pct} less money"},
    # What only cluster benefits do: capacities, which a vote that switches must not raise (tenet 1).
    "homes_capacity": {"better": "higher", "up": "Homes house {pct} more people", "down": "Homes house {pct} fewer people"},
    "hangar_capacity": {"better": "higher", "up": "Hangars hold {pct} more units", "down": "Hangars hold {pct} fewer units"},
    "workshop_capacity": {"better": "higher", "up": "Workshops house {pct} more engineers",
                          "down": "Workshops house {pct} fewer engineers"},
    "missile_silo_capacity": {"better": "higher", "up": "Missile silos store {pct} more missiles",
                              "down": "Missile silos store {pct} fewer missiles"},
    "fuel_storage": {"better": "higher", "up": "Fuel plants store {pct} more fuel",
                     "down": "Fuel plants store {pct} less fuel"},
    "recruit_cap": {"better": "higher", "up": "You can have {pct} more recruits in training",
                    "down": "You can have {pct} fewer recruits in training"},
    "recruit_cost": {"better": "lower", "up": "Recruits cost {pct} more", "down": "Recruits cost {pct} less"},
    "project_points": {"better": "higher", "up": "Engineers earn {pct} more points on every project",
                       "down": "Engineers earn {pct} fewer points on every project"},
    "shield_fuel": {"better": "lower", "up": "Every kind of shield costs {pct} more fuel",
                    "down": "Every kind of shield costs {pct} less fuel"},
    "pop_growth": {"better": "higher", "up": "Population grows {pct} faster", "down": "Population grows {pct} slower"},
}


def effect_text(effect, value):
    """The sentence for ``value`` of ``effect``: "Settling costs 15% less"."""
    template = EFFECTS[effect]["up" if value > 0 else "down"]
    return template.format(pct=f"{abs(value):.0%}")


def effects_text(effects):
    """The sentences for several effects, joined: what a policy option or a benefit says it does."""
    return ". ".join(effect_text(effect, value) for effect, value in effects.items())


def modifier(modifiers, effect):
    """How much of ``effect`` a kingdom has, from its ``modifiers`` (``getters._get_modifiers``): 0 for none."""
    return (modifiers or {}).get(effect, 0.0)


def add_modifiers(*sources):
    """Several ``{effect: value}`` added up into one."""
    total = {}
    for source in sources:
        for effect, value in (source or {}).items():
            total[effect] = total.get(effect, 0.0) + value
    return total


# The galaxy policies (galaxypolicies.py). A round plays GALAXY_POLICIES_PER_ROUND of them, drawn when it is made.
# Each has two options for competing playstyles, and both only help the galaxy's own kingdoms: none makes what you do
# to others hit harder or softens what others do to you. ``effects`` are what the active option does (EFFECTS
# above). Placeholders: the numbers are the maintainer's to balance.
GALAXY_POLICIES = {
    "growth_doctrine": {
        "name": "Growth Doctrine",
        "options": {
            "expansionist": {"name": "Expansionist", "effects": {"settle_cost": -0.15}},
            "raiders": {"name": "Raiders", "effects": {"primitives_attack_stars": 0.20}},
        },
    },
    "tempo_doctrine": {
        "name": "Tempo Doctrine",
        "options": {
            "warlike": {"name": "Warlike", "effects": {"generals_return_time": -0.10}},
            "drone_foundries": {"name": "Drone Foundries", "effects": {"drone_production": 0.15}},
        },
    },
    "defense_doctrine": {
        "name": "Defense Doctrine",
        "options": {
            "intelligence": {"name": "Intelligence", "effects": {"spy_attempt_time": -0.10}},
            "conscription": {"name": "Conscription", "effects": {"recruit_time": -0.20}},
        },
    },
    "research_focus": {
        "name": "Research Focus",
        "options": {
            "applied_research": {"name": "Applied Research", "effects": {"project_points_continuous": 0.15}},
            "breakthroughs": {"name": "Breakthroughs", "effects": {"project_points_one_time": 0.25}},
        },
    },
    "industry": {
        "name": "Industry",
        "options": {
            "industrialists": {"name": "Industrialists", "effects": {"structure_cost": -0.15}},
            "engineering_corps": {"name": "Engineering Corps", "effects": {"engineer_cost": -0.20}},
        },
    },
    "refit_doctrine": {
        "name": "Refit Doctrine",
        "options": {
            "shipwrights": {"name": "Shipwrights", "effects": {"upgrade_cost": -0.20}},
            "renovators": {"name": "Renovators", "effects": {"raze_return": 1.0}},
        },
    },
    "economy": {
        "name": "Economy",
        "options": {
            "mining_guilds": {"name": "Mining Guilds", "effects": {"mines_income": 0.15}},
            "refineries": {"name": "Refineries", "effects": {"fuel_production": 0.20}},
        },
    },
    "upkeep": {
        "name": "Upkeep",
        "options": {
            "civic_taxation": {"name": "Civic Taxation", "effects": {"pop_income": 0.15}},
            "efficiency": {"name": "Efficiency", "effects": {"unit_fuel": -0.15}},
        },
    },
    "procurement": {
        "name": "Procurement",
        "options": {
            "offensive_arms": {"name": "Offensive Arms", "effects": {"pure_attack_cost": -0.10}},
            "fortification": {"name": "Fortification", "effects": {"pure_defense_cost": -0.10}},
        },
    },
    "shadow_doctrine": {
        "name": "Shadow Doctrine",
        "options": {
            "plunderers": {"name": "Plunderers", "effects": {"rob_primitives": 0.20, "siphon_shield_fuel": -0.25}},
            "infiltrators": {"name": "Infiltrators", "effects": {"reveal_duration": 0.25}},
        },
    },
    "attrition_doctrine": {
        "name": "Attrition Doctrine",
        "options": {
            "veteran_corps": {"name": "Veteran Corps", "effects": {"attacker_losses": -0.20}},
            "drone_recovery": {"name": "Drone Recovery", "effects": {"drone_losses": -0.25}},
        },
    },
    "arsenal": {
        "name": "Arsenal",
        "options": {
            "silo_programme": {"name": "Silo Programme", "effects": {"missile_cost": -0.20}},
            "aegis": {"name": "Aegis", "effects": {"missile_shield_fuel": -0.50}},
        },
    },
    "shield_doctrine": {
        "name": "Shield Doctrine",
        "options": {
            "fortress": {"name": "Fortress", "effects": {"military_shield_fuel": -0.25}},
            "counter_intel": {"name": "Counter-Intel", "effects": {"spy_shield_fuel": -0.25}},
        },
    },
    "home_front": {
        "name": "Home Front",
        "options": {
            "rapid_construction": {"name": "Rapid Construction", "effects": {"structure_time": -0.20}},
            "population_boom": {"name": "Population Boom", "effects": {"pop_growth": 0.50}},
        },
    },
}
for _policy in GALAXY_POLICIES.values():
    for _option in _policy["options"].values():
        _option["desc"] = effects_text(_option["effects"])
# Renovators doubles the refund: say it as the share it becomes.
GALAXY_POLICIES["refit_doctrine"]["options"]["renovators"]["desc"] = (
    f"Razing structures refunds {GAME_CONFIG['BASE_STRUCTURES_RAZE_RETURN'] * 2:.0%} of the build cost instead of "
    f"{GAME_CONFIG['BASE_STRUCTURES_RAZE_RETURN']:.0%}")
# The policy each option belongs to.
GALAXY_POLICY_OF_OPTION = {
    option: policy for policy, entry in GALAXY_POLICIES.items() for option in entry["options"]
}

# What a cluster's galaxy leaders can vote to build up (clusters.py). A round plays CLUSTER_BENEFITS_PER_ROUND of them,
# drawn when it is made. Each benefit's level runs from 0 to ``max``; ``thresholds`` are ``(level as a fraction of max,
# how effective votes are from there up)``, so votes add less the higher the level gets. ``effect`` is what it does
# (EFFECTS): the level times ``max``, signed the way that helps. Capacities live here and not in the galaxy policies
# because a level rises and fades slowly: a kingdom over a cap that fades has time to adjust, and nothing new of that
# kind can be built or trained until it is under again. Placeholders.
def _benefit(name, desc, maximum, effect, thresholds=((0.5, 0.8),)):
    return {"name": name, "desc": desc, "max": maximum, "thresholds": list(thresholds), "effect": effect}


CLUSTER_BENEFITS = {
    "drone_production": _benefit("Drone Production", "Drone factories in the cluster produce more drones", 0.15,
                                 "drone_production", [(1 / 3, 0.8), (2 / 3, 0.6)]),
    "unit_cost": _benefit("Cheaper Units", "Military units in the cluster cost less", 0.05, "unit_cost"),
    "settle_cost": _benefit("Cheaper Settling", "Settling new stars in the cluster costs less", 0.10, "settle_cost"),
    "homes_capacity": _benefit("Roomier Homes", "Homes in the cluster house more people", 0.10, "homes_capacity"),
    "hangar_capacity": _benefit("Bigger Hangars", "Hangars in the cluster hold more units", 0.10, "hangar_capacity"),
    "workshop_capacity": _benefit("Bigger Workshops", "Workshops in the cluster house more engineers", 0.10,
                                  "workshop_capacity"),
    "missile_silo_capacity": _benefit("Deeper Silos", "Missile silos in the cluster store more missiles", 0.25,
                                      "missile_silo_capacity"),
    "fuel_storage": _benefit("Fuel Depots", "Fuel plants in the cluster store more fuel", 0.20, "fuel_storage"),
    "recruit_cap": _benefit("Wider Draft", "Kingdoms in the cluster can have more recruits in training", 0.15,
                            "recruit_cap"),
    "recruit_cost": _benefit("Cheaper Recruits", "Recruits in the cluster cost less", 0.10, "recruit_cost"),
    "project_points": _benefit("Research Network", "Engineers in the cluster earn more project points", 0.10,
                               "project_points"),
    "structure_time": _benefit("Fast Construction", "Structures in the cluster build faster", 0.10, "structure_time"),
    "pop_growth": _benefit("Population Growth", "Population in the cluster grows faster", 0.25, "pop_growth"),
    "shield_fuel": _benefit("Shield Grid", "Every kind of shield in the cluster costs less fuel", 0.15, "shield_fuel"),
}

# What an empire can mark a target for (targets.py), and the participation points each one earns. ``points`` maps each
# measure of the damage done to the points one unit of it earns, so a bigger blow earns more: kidnapping 1000
# civilians earns twice what 500 do. Leadership scales each action's points per target with a multiplier. Placeholders.
TARGET_ACTIONS = {
    "intel": {
        "name": "Intel",
        "desc": "Successful intel operations. Only intel the empire does not already have on the target earns points",
        "points": {"categories": 10},
    },
    "kidnap": {
        "name": "Kidnaps",
        "desc": "Kidnap Population",
        "points": {"population": 0.01},
    },
    "bomb_homes": {
        "name": "Bomb Homes",
        "desc": "Bomb Homes",
        "points": {"homes": 1},
    },
    "sabotage_fuel_plants": {
        "name": "Sabotage Fuel Plants",
        "desc": "Sabotage Fuel Plants",
        "points": {"fuel_plants": 1},
    },
    "missiles": {
        "name": "Missiles",
        "desc": "Missiles launched at the target. The stars they destroy go into the spoils fund",
        "points": {"stars": 1, "population": 0.01, "fuel": 0.001},
    },
    "failed_attacks": {
        "name": "Failed Attacks",
        "desc": "Attacks that lost, by the defending units they destroyed",
        "points": {"units": 0.1},
    },
    "successful_attacks": {
        "name": "Successful Attacks",
        "desc": "Attacks that won, by the stars they took",
        "points": {"stars": 1},
    },
}
# The words for each measure on the pages.
TARGET_MEASURE_NAMES = {
    "categories": "kind of intel", "population": "civilian", "homes": "home", "fuel_plants": "fuel plant",
    "stars": "star", "fuel": "fuel", "units": "unit destroyed",
}

# The universe policies (universepolicies.py). Each election puts UNIVERSE_POLICIES_PER_ELECTION of them on the ballot;
# kingdoms spend bought votes on one option of each, and the winners hold until the next election closes. Every option
# punishes a playstyle, so the vote is the universe deciding whom to rein in. ``first_election_only`` policies are always
# on the first ballot and never on another. ``applies_to`` says who an option hits: everyone, or (``top_kingdoms``,
# ``top_galaxies``) the leaders by networth. Placeholders: the numbers are the maintainer's to balance.
UNIVERSE_POLICIES = {
    "rules_of_war": {
        "name": "Rules of War",
        "options": {
            "ceasefire_accords": {"name": "Ceasefire Accords", "effects": {"attack_stars": -0.15}},
            "land_tax": {"name": "Land Tax", "effects": {"settle_cost": 0.15}},
        },
    },
    "espionage": {
        "name": "Espionage",
        "options": {
            "surveillance_act": {"name": "Surveillance Act", "effects": {"aggressive_failure_losses": 1.0}},
            "open_skies": {"name": "Open Skies", "effects": {"spy_shield_fuel": 1.0}},
        },
    },
    "arms_control": {
        "name": "Arms Control",
        "options": {
            "treatied": {"name": "Treatied", "effects": {"unit_cost": 0.20}},
            "non_proliferation": {"name": "Non-Proliferation", "effects": {"missile_cost": 0.30}},
        },
    },
    "labor": {
        "name": "Labor",
        "options": {
            "draft_limits": {"name": "Draft Limits", "effects": {"recruit_cost": 0.30}},
            "research_moratorium": {"name": "Research Moratorium", "effects": {"project_points": -0.15}},
        },
    },
    "environment": {
        "name": "Environment",
        "options": {
            "carbon_cap": {"name": "Carbon Cap", "effects": {"unit_fuel": 0.25}},
            "population_control": {"name": "Population Control", "effects": {"pop_growth": -0.25}},
        },
    },
    "primitives": {
        "name": "Primitives",
        "first_election_only": True,
        "options": {
            "native_reserves": {"name": "Native Reserves", "effects": {"rob_primitives": -0.30}},
            "wilderness_protection": {"name": "Wilderness Protection", "effects": {"primitives_defense": 0.30}},
        },
    },
    "diplomacy": {
        "name": "Diplomacy",
        "options": {
            "aggression_monitors": {"name": "Aggression Monitors", "effects": {"aggression": 0.50}},
            "shield_levy": {"name": "Shield Levy", "effects": {"military_shield_fuel": 1.0}},
        },
    },
    "secrecy": {
        "name": "Secrecy",
        "options": {
            "classified": {"name": "Classified", "effects": {"reveal_duration": -0.25}},
            "transparency": {"name": "Transparency", "effects": {"spy_defense": -0.25}},
        },
    },
    "wealth": {
        "name": "Wealth",
        "options": {
            "progressive_tax": {"name": "Progressive Tax", "effects": {"money_income": -0.10}, "applies_to": "top_kingdoms"},
            "antitrust": {"name": "Antitrust", "effects": {"money_income": -0.10}, "applies_to": "top_galaxies"},
        },
    },
}
for _policy in UNIVERSE_POLICIES.values():
    for _option in _policy["options"].values():
        _option.setdefault("applies_to", "everyone")
        _option["desc"] = effects_text(_option["effects"])
UNIVERSE_POLICIES["wealth"]["options"]["progressive_tax"]["desc"] = (
    "The {n} kingdoms with the most networth earn {pct:.0%} less money".format(
        n=GAME_CONFIG["UNIVERSE_WEALTH_TOP_KINGDOMS"],
        pct=-UNIVERSE_POLICIES["wealth"]["options"]["progressive_tax"]["effects"]["money_income"]))
UNIVERSE_POLICIES["wealth"]["options"]["antitrust"]["desc"] = (
    "Kingdoms of the {n} galaxies with the most networth earn {pct:.0%} less money".format(
        n=GAME_CONFIG["UNIVERSE_WEALTH_TOP_GALAXIES"],
        pct=-UNIVERSE_POLICIES["wealth"]["options"]["antitrust"]["effects"]["money_income"]))
# Doubling reads better said so.
UNIVERSE_POLICIES["espionage"]["options"]["surveillance_act"]["desc"] = "Failed aggressive spy operations lose twice the drones"
UNIVERSE_POLICIES["espionage"]["options"]["open_skies"]["desc"] = "Spy shields and spy radar cost twice the fuel"
UNIVERSE_POLICIES["diplomacy"]["options"]["shield_levy"]["desc"] = "Military shields cost twice the fuel"
UNIVERSE_POLICIES["secrecy"]["options"]["classified"]["desc"] = "Reveals last {pct:.0%} less".format(
    pct=-UNIVERSE_POLICIES["secrecy"]["options"]["classified"]["effects"]["reveal_duration"])
# The policy each option belongs to.
UNIVERSE_POLICY_OF_OPTION = {
    option: policy for policy, entry in UNIVERSE_POLICIES.items() for option in entry["options"]
}

PRETTY_NAMES = {
    "spykingdom": "Spy on Kingdom",
    "spymilitary": "Spy on Military",
    "spyshields": "Spy on Shields",
    "spyprojects": "Spy on Projects",
    "spystructures": "Spy on Structures",
    "spydrones": "Spy on Drones",
    "spyall": "Full Infiltration",
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
    "solar_attack": "Solar Attackers",
    "self_destruct_attack": "Self-Destructing Attackers",
    "solar_defense": "Solar Defenders",
    "self_destruct_defense": "Self-Destructing Defenders",
    "warp_big_flex": "Warp Speed Big Flexers",
    "compact_big_flex": "Compact Big Flexers",
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


def galaxy_vote_unlocks_at(galaxy_votes, kind, kd_id, now):
    """
    When ``kd_id`` can change its vote of ``kind`` (``leader``; policy votes have no cooldown) in the galaxy politics
    document ``galaxy_votes`` again, or None if it can now: it has never changed it, or the cooldown is over. The first
    vote is free; every change after it starts the wait.
    """
    changed = ((galaxy_votes.get("vote_changed") or {}).get(kind) or {}).get(kd_id)
    if not changed:
        return None
    changed_at = datetime.datetime.fromisoformat(changed)
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=datetime.timezone.utc)
    unlocks = changed_at + datetime.timedelta(
        seconds=GAME_CONFIG["BASE_GALAXY_VOTE_COOLDOWN_EPOCHS"] * GAME_CONFIG["BASE_EPOCH_SECONDS"])
    return unlocks if unlocks > now else None


def wait_text(delta):
    """A wait in real time, rounded up to the minute: "2 hours 5 minutes", "40 minutes"."""
    minutes = max(1, -(-int(delta.total_seconds()) // 60))
    hours, minutes = divmod(minutes, 60)
    parts = ([f"{hours} hour{'s' if hours != 1 else ''}"] if hours else []) + (
        [f"{minutes} minute{'s' if minutes != 1 else ''}"] if minutes else [])
    return " ".join(parts)
