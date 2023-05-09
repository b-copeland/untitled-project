import math
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
        'offense': 6,
        'defense': 6,
        'cost': 900,
        'fuel': 2,
        'hangar_capacity': 2,
    },
    'big_flex': {
        'offense': 9,
        'defense': 9,
        'cost': 1350,
        'fuel': 2,
        'hangar_capacity': 2,
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
        "pop_damage": 100,
        "fuel_cost": 4000,
        "cost": 15000,
    },
}

PROJECTS = {
    "pop_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases homes capacity by the current bonus",
        "name": "Pop Bonus",
    },
    "fuel_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases fuel production by the current bonus",
        "name": "Fuel Bonus",
    },
    "military_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases offensive and defensive strength by the current bonus",
        "name": "Military Bonus",
    },
    "money_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Increases income from population and mines by the current bonus",
        "name": "Money Bonus",
    },
    "general_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Decreases generals time to return by the current bonus",
        "name": "Generals Speed Bonus",
    },
    "spy_bonus": {
        "stars_power": 1.5,
        "constant": 0.1,
        "max_bonus": 0.25,
        "desc": "Decreases cooldown of spy attempts by the current bonus",
        "name": "Spy Bonus",
    },
    "big_flexers": {
        "stars_power": 0,
        "constant": 100000,
        "desc": "Unlocks the Big Flexer unit",
        "name": "Big Flexers",
    },
    "star_busters": {
        "stars_power": 0,
        "constant": 100000,
        "desc": "Unlocks the Star Buster missile",
        "name": "Star Busters",
    },
    "galaxy_busters": {
        "stars_power": 0,
        "constant": 250000,
        "desc": "Unlocks the Galaxy Buster missile",
        "name": "Galaxy Busters",
    },
    "drone_gadgets": {
        "stars_power": 0,
        "constant": 50000,
        "desc": "Unlocks the Spy Bonus project",
        "name": "Drone Gadgets",
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

ONE_TIME_PROJECTS = [
    "big_flexers",
    "star_busters",
    "galaxy_busters",
    "drone_gadgets",
]

GAME_CONFIG = {
    "BASE_EPOCH_SECONDS": 60 * 60, 

    "BASE_SETTLE_STARS_POWER": 0.5,
    "BASE_SETTLE_COST_CONSTANT": 50,
    "BASE_MAX_SETTLE_CAP": 0.15,
    "BASE_SETTLE_TIME_MULTIPLIER": 12, 

    "BASE_STRUCTURE_STARS_POWER": 0.5,
    "BASE_STRUCTURE_COST_CONSTANT": 50,
    "BASE_STRUCTURE_TIME_MULTIPLIER": 8, 

    "BASE_MAX_RECRUITS_CAP": 0.12,
    "BASE_RECRUIT_COST": 100, 
    "BASE_RECRUIT_TIME_MULTIPLIER": 12, 

    "BASE_SPECIALIST_TIME_MULTIPLIER": 12, 

    "BASE_ENGINEER_COST": 1000, 
    "BASE_ENGINEER_TIME_MULTIPLIER": 12, 
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

    "BASE_MISSILE_TIME_MULTIPLER": 24, 

    "BASE_GENERALS_ATTACK_MODIFIER": 0.03,
    "BASE_GENERALS_RETURN_TIME_MULTIPLIER": 12, 
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
    "BASE_REVEAL_DURATION_MULTIPLIER": 8, 

    "BASE_MAX_SHARE_CUT": 0.15, 

    "BASE_DRONES_SIPHON_PER_DRONE": 8, 
    "BASE_DRONES_SIPHON_TIME_MULTIPLIER": 8, 
    "BASE_DRONES_PER_HOME_DAMAGE": 1500, 
    "BASE_DRONES_MAX_HOME_DAMAGE": 0.05, 
    "BASE_DRONES_PER_FUEL_PLANT_DAMAGE": 1500, 
    "BASE_DRONES_MAX_FUEL_PLANT_DAMAGE": 0.05, 
    "BASE_DRONES_PER_KIDNAP": 10, 
    "BASE_DRONES_MAX_KIDNAP_DAMAGE": 0.05, 
    "BASE_DRONES_SUICIDE_FUEL_DAMAGE": 5, 
    "BASE_KIDNAP_RETURN_RATE": 0.4, 

    "BASE_MAX_SIPHON": 0.10, 

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
        "defense": 8,
        "flex": 16,
        "big_flex": 24,
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
}

GAME_FUNCS = {
    "BASE_SETTLE_COST": lambda stars: math.floor((stars ** GAME_CONFIG["BASE_SETTLE_STARS_POWER"]) * GAME_CONFIG["BASE_SETTLE_COST_CONSTANT"]), 
    "BASE_MAX_SETTLE": lambda stars: math.floor(stars * GAME_CONFIG["BASE_MAX_SETTLE_CAP"]), 
    "BASE_STRUCTURE_COST": lambda stars: math.floor((stars ** GAME_CONFIG["BASE_STRUCTURE_STARS_POWER"]) * GAME_CONFIG["BASE_STRUCTURE_COST_CONSTANT"]), 
    "BASE_MAX_RECRUITS": lambda pop: math.floor(pop * GAME_CONFIG["BASE_MAX_RECRUITS_CAP"]), 
    "BASE_MAX_ENGINEERS": lambda pop: math.floor(pop * GAME_CONFIG["BASE_MAX_ENGINEERS_POP_CAP"]), 
    "BASE_GENERALS_BONUS": lambda generals: (generals - 1) * GAME_CONFIG["BASE_GENERALS_ATTACK_MODIFIER"], 
    "BASE_PRIMITIVES_DEFENSE_PER_STAR": lambda seconds: GAME_CONFIG["BASE_PRIMITIVES_DEFENSE_PER_STAR"] * math.sqrt(1 + seconds / (GAME_CONFIG["BASE_EPOCH_SECONDS"] * GAME_CONFIG["BASE_PRIMITIVES_DEFENSE_EPOCH_MULTIPLER"])), 
    "BASE_PRIMITIVES_ROB_PER_DRONE": lambda seconds: GAME_CONFIG["BASE_PRIMITIVES_ROB_PER_DRONE"] / math.sqrt(1 + seconds / (GAME_CONFIG["BASE_EPOCH_SECONDS"] * GAME_CONFIG["BASE_PRIMITIVES_DEFENSE_EPOCH_MULTIPLER"])), 
    "BASE_NEGATIVE_FUEL_CAP": lambda stars: stars * -GAME_CONFIG["BASE_NEGATIVE_FUEL_PER_STAR"], 
}

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
        "units": {
            "attack": 0,
            "defense": 0,
            "flex": 0,
            "recruits": 0,
            "engineers": 0,
            "big_flex": 0,
        },
        "max_recruits": 99999,
        "recruits_before_units": True,
        "units_target": {
            "attack": 0,
            "defense": 0,
            "flex": 0,
            "big_flex": 0,
        },
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
        "projects_points": {
            "pop_bonus": 1000,
            "fuel_bonus": 1000,
            "military_bonus": 1000,
            "money_bonus": 1000,
            "general_bonus": 1000,
            "spy_bonus": 0,
            "big_flexers": 0,
            "star_busters": 0,
            "galaxy_busters": 0,
            "drone_gadgets": 0
        },
        "auto_assign_projects": False,
        "projects_target": {
            "pop_bonus": 0,
            "fuel_bonus": 0,
            "military_bonus": 0,
            "money_bonus": 0,
            "general_bonus": 0,
            "spy_bonus": 0,
            "big_flexers": 0,
            "star_busters": 0,
            "galaxy_busters": 0,
            "drone_gadgets": 0
        },
        "projects_max_points": {
            "pop_bonus": PROJECTS_FUNCS["pop_bonus"](INITIAL_KINGDOM_STARS),
            "fuel_bonus": PROJECTS_FUNCS["fuel_bonus"](INITIAL_KINGDOM_STARS),
            "military_bonus": PROJECTS_FUNCS["military_bonus"](INITIAL_KINGDOM_STARS),
            "money_bonus": PROJECTS_FUNCS["money_bonus"](INITIAL_KINGDOM_STARS),
            "general_bonus": PROJECTS_FUNCS["general_bonus"](INITIAL_KINGDOM_STARS),
            "spy_bonus": PROJECTS_FUNCS["spy_bonus"](INITIAL_KINGDOM_STARS),
            "big_flexers": PROJECTS_FUNCS["big_flexers"](0),
            "star_busters": PROJECTS_FUNCS["star_busters"](0),
            "galaxy_busters": PROJECTS_FUNCS["galaxy_busters"](0),
            "drone_gadgets": PROJECTS_FUNCS["drone_gadgets"](0),
        },
        "projects_assigned": {
            "pop_bonus": 0,
            "fuel_bonus": 0,
            "military_bonus": 0,
            "money_bonus": 0,
            "general_bonus": 0,
            "spy_bonus": 0,
            "big_flexers": 0,
            "star_busters": 0,
            "galaxy_busters": 0,
            "drone_gadgets": 0
        },
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
        "schedule": [],
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
}

KINGDOM_CREATOR_STARTING_POINTS = 20000
KINGDOM_CREATOR_POINTS = {
    "drones": 1,
    "recruits": 1,
    "attack": 5,
    "defense": 5,
    "flex": 10,
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
}