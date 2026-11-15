"""
Bots: computer-run kingdoms, to make a round feel populated and to exercise the game's systems (issue #76).

This is the *setup*. A bot is a normal kingdom that belongs to a normal (but unusable)
account, set up the way a sensible player of one playstyle would set theirs up. The game's own auto builder (auto
spending, build targets, auto attack, auto rob, auto project assignment, all resolved by the periodic refresh) then
plays it. The part that decides to *do* things (pick targets, spy, vote) is botbrain.py.

The four playstyles are the ones in untitled_project.txt, each with the race whose bonuses suit it:

    explorer  Gaian   cheaper, faster settling      grows by claiming stars, defends
    attacker  Xo      bigger spoils, fewer losses   grows by attacking, auto attack on
    intel     Lumina  free reveal operations        drone-heavy support, shares what it learns
    thief     Vult    more drones                   drone-heavy, robs primitives

(The leader playstyle is not ready, so there is no leader bot.)

**Every number below is a first guess.** They are all legal, which ``problems()`` checks against the same validators
the routes use, but none of them has been play-tested. The ones to look at first are marked ``TUNE``. Edit them here;
``tests/test_bots.py`` fails if an edit makes an archetype illegal, so a bad number can not reach a bot.
"""
import dataclasses
import datetime
import json
import random
import secrets

import flask

import untitledapp.botbrain as botbrain
import untitledapp.build as uab
import untitledapp.conquer as uac
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.shared as uas
import untitledapp.getters as uag
from untitledapp import User, UserExists, REQUESTS_SESSION

BOT_PREFIX = "bot_"


@dataclasses.dataclass(frozen=True)
class Archetype:
    key: str
    race: str
    description: str

    # What the kingdom starts with. Units cost points (uas.KINGDOM_CREATOR_POINTS) and must use all of them; structures
    # must use all of the starting stars.
    unit_choices: dict
    structures_choices: dict

    # TUNE: the auto builder. Funding is split between these four by percent (the rest of the income stays as money).
    auto_spending: dict
    # TUNE: what the builder aims for, as a share of stars / of all units / of engineers.
    structures_target: dict
    units_target: dict
    projects_target: dict
    recruits_before_units: bool = True
    max_recruits: int = 99999

    # TUNE: share of units sent out each time generals are free (None: auto attack stays off).
    auto_attack: dict = None
    # TUNE: share of drones used to rob primitives, whether to shield them, spy attempts to keep back (None: off).
    auto_rob: dict = None
    # TUNE: shields (fractions, each within its game maximum). They cost fuel to keep.
    shields: dict = dataclasses.field(default_factory=dict)

    # What a new player sees on the kingdom creator, where the same archetypes are offered as quick starts.
    label: str = ""


ARCHETYPES = {
    # The starts share two ideas. An army can only grow as fast as recruits can be drafted (a share of the population),
    # and early stars compound, so every playstyle starts with attackers to send at primitives from the first hour,
    # while they are easy. And drones are the one thing money can not buy later (a factory makes one an epoch) and
    # they rob primitives from the start, so the rest of the points goes there as far as the role leaves room.
    # Recruits are cheap to draft later, so few are bought with points. Hangars and fuel plants fit the army.
    "explorer": Archetype(
        key="explorer",
        label="Explorer",
        race="Gaian",
        description="Claims stars with cheap fast settling and builds the economy; defends rather than attacks.",
        unit_choices={"drones": 4000, "recruits": 500, "attack": 1000, "defense": 1000, "flex": 0, "engineers": 550},
        structures_choices={"homes": 112, "mines": 92, "fuel_plants": 32, "hangars": 38, "drone_factories": 12,
                            "missile_silos": 0, "workshops": 14},
        auto_spending={"settle": 0.35, "structures": 0.35, "military": 0.2, "engineers": 0.1},
        structures_target={"homes": 0.36, "mines": 0.3, "fuel_plants": 0.1, "hangars": 0.11, "drone_factories": 0.06,
                           "workshops": 0.06},
        units_target={"defense": 0.75, "attack": 0.25},
        projects_target={"money_bonus": 0.3, "military_bonus": 0.2, "fuel_bonus": 0.15, "drone_gadgets": 0.35},
        recruits_before_units=False, max_recruits=500,
        auto_attack={"pure": 1.0, "flex": 0.0},
        auto_rob={"drones": 0.9, "shielded": False, "keep": 2},
        shields={"military": 0.05},
    ),
    "attacker": Archetype(
        key="attacker",
        label="Attacker",
        race="Xo",
        description="Grows by attacking: primitives while they are easy, then other kingdoms, with an army that is mostly offense.",
        unit_choices={"drones": 3000, "recruits": 500, "attack": 2000, "defense": 500, "flex": 0, "engineers": 400},
        structures_choices={"homes": 105, "mines": 80, "fuel_plants": 32, "hangars": 45, "drone_factories": 22,
                            "missile_silos": 0, "workshops": 16},
        auto_spending={"settle": 0.15, "structures": 0.3, "military": 0.45, "engineers": 0.1},
        structures_target={"homes": 0.34, "mines": 0.24, "fuel_plants": 0.11, "hangars": 0.16, "drone_factories": 0.08,
                           "workshops": 0.07},
        units_target={"attack": 0.65, "defense": 0.25, "flex": 0.1},
        projects_target={"military_bonus": 0.2, "general_bonus": 0.2, "money_bonus": 0.1, "big_flexers": 0.5},
        recruits_before_units=False, max_recruits=800,
        auto_attack={"pure": 1.0, "flex": 0.5},
        auto_rob={"drones": 0.9, "shielded": False, "keep": 3},
        shields={"military": 0.05},
    ),
    "intel": Archetype(
        key="intel",
        label="Intel",
        race="Lumina",
        description="Support: drone-heavy, reveals other kingdoms and shares what it learns with its galaxy for a cut of the spoils.",
        unit_choices={"drones": 5000, "recruits": 500, "attack": 800, "defense": 900, "flex": 0, "engineers": 600},
        structures_choices={"homes": 112, "mines": 88, "fuel_plants": 22, "hangars": 33, "drone_factories": 30,
                            "missile_silos": 0, "workshops": 15},
        auto_spending={"settle": 0.3, "structures": 0.35, "military": 0.2, "engineers": 0.15},
        structures_target={"homes": 0.34, "mines": 0.27, "fuel_plants": 0.07, "hangars": 0.09, "drone_factories": 0.15,
                           "workshops": 0.07},
        units_target={"defense": 0.6, "attack": 0.4},
        projects_target={"money_bonus": 0.2, "military_bonus": 0.1, "fuel_bonus": 0.1, "drone_gadgets": 0.6},
        recruits_before_units=False, max_recruits=500,
        auto_attack={"pure": 1.0, "flex": 0.0},
        auto_rob={"drones": 0.9, "shielded": False, "keep": 4},
        shields={"spy": 0.1, "spy_radar": 0.1},
    ),
    "thief": Archetype(
        key="thief",
        label="Thief",
        race="Vult",
        description="Lives off drones: robs primitives, siphons richer kingdoms, and keeps enough defense to be left alone.",
        unit_choices={"drones": 7000, "recruits": 500, "attack": 800, "defense": 900, "flex": 0, "engineers": 400},
        structures_choices={"homes": 112, "mines": 85, "fuel_plants": 24, "hangars": 33, "drone_factories": 36,
                            "missile_silos": 0, "workshops": 10},
        auto_spending={"settle": 0.3, "structures": 0.35, "military": 0.2, "engineers": 0.15},
        structures_target={"homes": 0.33, "mines": 0.25, "fuel_plants": 0.08, "hangars": 0.08, "drone_factories": 0.2,
                           "workshops": 0.06},
        units_target={"defense": 0.6, "attack": 0.4},
        projects_target={"money_bonus": 0.2, "military_bonus": 0.1, "fuel_bonus": 0.1, "drone_gadgets": 0.6},
        recruits_before_units=False, max_recruits=500,
        auto_attack={"pure": 1.0, "flex": 0.0},
        auto_rob={"drones": 0.9, "shielded": False, "keep": 3},
        shields={"spy": 0.1, "spy_radar": 0.05},
    ),
}


def problems(archetype):
    """Everything illegal about an archetype, as plain sentences, using the validators the routes use. Empty if fine."""
    found = []

    def check(result, what):
        valid, message = result
        if not valid:
            found.append(f"{what}: {message}")

    unfinished = {"completed_projects": []}
    check(uam._validate_kingdom_choices(archetype.unit_choices, archetype.structures_choices, archetype.race),
          "kingdom choices")
    check(uam._validate_spending(archetype.auto_spending), "auto spending")
    check(uab._validate_structures_target(archetype.structures_target), "structures target")
    check(uab._validate_mobis_target(archetype.units_target, unfinished), "units target")
    check(uab._validate_projects_target(archetype.projects_target, unfinished), "projects target")
    check(uam._validate_shields(archetype.shields), "shields")
    if archetype.auto_attack:
        check(uac._validate_auto_attack_settings(archetype.auto_attack), "auto attack")
    if archetype.auto_rob:
        check(uac._validate_auto_rob_settings(archetype.auto_rob), "auto rob")
    return found


def vary(values, rng, spread=0.25):
    """
    Give each bot slightly different numbers than the archetype so a hundred bots are not a hundred copies: every value
    is scaled by a random factor within ``spread``, then the whole is scaled back to the original total so a share that
    summed to 90% still does.
    """
    total = sum(values.values())
    scaled = {key: value * rng.uniform(1 - spread, 1 + spread) for key, value in values.items()}
    scaled_total = sum(scaled.values())
    if scaled_total == 0:
        return dict(values)
    return {key: round(value * total / scaled_total, 4) for key, value in scaled.items()}


def settings_for(archetype, rng):
    """The auto builder fields for one bot's kingdom document (the part that is not the starting units/structures)."""
    personality = botbrain.PERSONALITIES[archetype.key]
    settings = {
        # What marks a kingdom as a bot, and the brain's state: its type, when it next thinks (spread out so a hundred
        # new bots do not all think at once) and the log of what it decided. See botbrain.py. The auto builder fields
        # below are only how it starts: the brain re-plans them every time it thinks.
        "bot": {
            "type": archetype.key,
            "next_think": botbrain.first_think_time(personality, rng, datetime.datetime.now(datetime.timezone.utc)).isoformat(),
            "log": [],
            # What this bot hits (primitives, players, both or nothing, with its army and with its drones), whether it
            # builds missiles, and how bold it is. Drawn once, so a hundred bots of a type are not a hundred copies.
            "style": botbrain.roll_style(personality, rng),
            "memory": {},
            "counts": {},
            "reserved_generals": 0,
        },
        "auto_spending_enabled": True,
        "auto_spending": vary(archetype.auto_spending, rng, 0.2),
        "structures_target": vary(archetype.structures_target, rng),
        "units_target": vary(archetype.units_target, rng),
        "projects_target": vary(archetype.projects_target, rng),
        "auto_assign_projects": True,
        "recruits_before_units": archetype.recruits_before_units,
        "max_recruits": archetype.max_recruits,
        # All four, as the shields route keeps them: income reads every one.
        "shields": {"military": 0.0, "spy": 0.0, "spy_radar": 0.0, "missiles": 0.0, **archetype.shields},
    }
    if archetype.auto_attack:
        settings["auto_attack_enabled"] = True
        settings["auto_attack_settings"] = {key: round(min(value * rng.uniform(0.6, 1.4), 1.0), 3)
                                            for key, value in archetype.auto_attack.items()}
    if archetype.auto_rob:
        settings["auto_rob_enabled"] = True
        settings["auto_rob_settings"] = dict(archetype.auto_rob)
    return settings


def player_settings(archetype, auto_builder):
    """
    The auto builder fields for a *player* who picked this archetype as a quick start. The plan is stored exactly as the
    archetype has it (no variation: a player sees the same numbers every time), but nothing runs unless the player chose
    to switch the auto builder on: the spending split, build targets and auto attack / rob settings are only filled in,
    where the Status and Primitives pages show them. ``auto_builder`` switches on auto spending, auto assigning engineers
    to projects, auto attack or rob (where the archetype has one) and its shields.
    """
    settings = {
        "auto_spending": dict(archetype.auto_spending),
        "structures_target": dict(archetype.structures_target),
        "units_target": dict(archetype.units_target),
        "projects_target": dict(archetype.projects_target),
        "recruits_before_units": archetype.recruits_before_units,
        "max_recruits": archetype.max_recruits,
    }
    if archetype.auto_attack:
        settings["auto_attack_settings"] = dict(archetype.auto_attack)
    if archetype.auto_rob:
        settings["auto_rob_settings"] = dict(archetype.auto_rob)
    if auto_builder:
        settings["auto_spending_enabled"] = True
        settings["auto_assign_projects"] = True
        settings["shields"] = {"military": 0.0, "spy": 0.0, "spy_radar": 0.0, "missiles": 0.0, **archetype.shields}
        if archetype.auto_attack:
            settings["auto_attack_enabled"] = True
        if archetype.auto_rob:
            settings["auto_rob_enabled"] = True
    return settings


def preset_view(archetype):
    """An archetype as the kingdom creator page needs it: what it starts with and what its plan would do."""
    return {
        "key": archetype.key,
        "label": archetype.label or archetype.key.title(),
        "description": archetype.description,
        "race": archetype.race,
        "unitsChoices": dict(archetype.unit_choices),
        "structuresChoices": dict(archetype.structures_choices),
        "autoSpending": dict(archetype.auto_spending),
        "autoAttack": bool(archetype.auto_attack),
        "autoRob": bool(archetype.auto_rob),
    }


def _smallest_galaxy(rng):
    galaxies = uag._get_galaxy_info()
    smallest = min(len(members) for members in galaxies.values())
    return rng.choice([galaxy_id for galaxy_id, members in galaxies.items() if len(members) == smallest])


def create_bot(name, archetype_key, rng=None):
    """
    Create one bot: an account nobody can log in to, and a kingdom set up as the archetype, with its auto builder on.
    Returns the new kingdom id. Raises ``ValueError`` if the name is taken or the archetype is unknown or illegal.
    """
    rng = rng or random.Random()
    archetype = ARCHETYPES.get(archetype_key)
    if archetype is None:
        raise ValueError(f"Unknown bot type {archetype_key!r}; choose from {sorted(ARCHETYPES)}")
    if problems(archetype):
        raise ValueError(f"The {archetype_key} bot is not legal: {problems(archetype)}")

    app = flask.current_app
    guard = app.extensions["praetorian"]
    try:
        # The account first: claiming the name is the uniqueness check, so a taken name makes no kingdom.
        user = User.create(
            name,
            # Nobody knows this password, so nobody can log in as a bot.
            guard.hash_password(secrets.token_urlsafe(32)),
            roles='operator',
            kd_created=False,
            is_active=True,
        )
    except UserExists:
        raise ValueError(f"The name {name!r} is taken")

    created = REQUESTS_SESSION.post(
        app.config['AZURE_FUNCTION_ENDPOINT'] + '/kingdom',
        headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
        data=json.dumps({"kingdom_name": name, "galaxy": _smallest_galaxy(rng)}),
    )
    if created.status_code != 201:
        raise ValueError(f"The function app could not create the kingdom ({created.status_code})")
    kd_id = created.text

    for table, initial_state in uas.INITIAL_KINGDOM_STATE.items():
        state = initial_state.copy()
        if table == "kingdom":
            state["kdId"] = kd_id
            state["name"] = name
        REQUESTS_SESSION.post(
            app.config['AZURE_FUNCTION_ENDPOINT'] + '/createitem',
            headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
            data=json.dumps({"item": f"{table}_{kd_id}", "state": state}),
        )

    settings = settings_for(archetype, rng)

    def set_up(kd_info):
        payload = uam._kingdom_setup_payload(kd_info, archetype.unit_choices, archetype.structures_choices, archetype.race)
        payload.update(settings)
        next_resolve = payload["next_resolve"]
        # Same as a player switching auto spending on: it first runs after one auto-spending interval.
        next_resolve["auto_spending"] = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"])
        ).isoformat()
        return payload, None

    occ.update(f'/kingdom/{kd_id}', set_up)

    user.save(kd_id=kd_id, kd_created=True)
    return kd_id


def create_bots(counts, rng=None, first_number=None):
    """
    Create several bots. ``counts`` maps archetype key to how many, e.g. ``{"explorer": 25, "attacker": 25}``. Returns
    the names created.
    """
    rng = rng or random.Random()
    existing = len(User.with_prefix(BOT_PREFIX))
    number = existing + 1 if first_number is None else first_number
    created = []
    for key, how_many in counts.items():
        for _ in range(int(how_many)):
            name = f"{BOT_PREFIX}{key}_{number}"
            create_bot(name, key, rng)
            created.append(name)
            number += 1
    return created
