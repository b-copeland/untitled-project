"""
Bots: computer-run kingdoms, to make a round feel populated and to exercise the game's systems (issue #76).

This is the first half of the plan, the *setup*. A bot is a normal kingdom that belongs to a normal (but unusable)
account, set up the way a sensible player of one playstyle would set theirs up. The game's own auto builder (auto
spending, build targets, auto attack, auto rob, auto project assignment, all resolved by the periodic refresh) then
plays it. The second half, bots that decide to *do* things (pick targets, spy, vote), is not here yet; see
"Not yet" in docs/bots.md.

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

import untitledapp.build as uab
import untitledapp.conquer as uac
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.shared as uas
import untitledapp.getters as uag
from untitledapp import User, REQUESTS_SESSION

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
    "explorer": Archetype(
        key="explorer",
        label="Explorer",
        race="Gaian",
        description="Claims stars with cheap fast settling and builds the economy; defends rather than attacks.",
        unit_choices={"drones": 2000, "recruits": 2000, "attack": 0, "defense": 1400, "flex": 0, "engineers": 900},
        structures_choices={"homes": 110, "mines": 60, "fuel_plants": 40, "hangars": 20, "drone_factories": 10,
                            "missile_silos": 0, "workshops": 60},
        auto_spending={"settle": 0.5, "structures": 0.3, "military": 0.1, "engineers": 0.1},
        structures_target={"homes": 0.35, "mines": 0.2, "fuel_plants": 0.12, "hangars": 0.06, "drone_factories": 0.03,
                           "workshops": 0.15},
        units_target={"defense": 0.7, "attack": 0.0, "flex": 0.1},
        projects_target={"pop_bonus": 0.3, "money_bonus": 0.25, "fuel_bonus": 0.15, "military_bonus": 0.1},
        shields={"military": 0.05},
    ),
    "attacker": Archetype(
        key="attacker",
        label="Attacker",
        race="Xo",
        description="Grows by attacking other kingdoms with a mix of pure offense and flex units, on a timer.",
        unit_choices={"drones": 1000, "recruits": 1000, "attack": 1200, "defense": 0, "flex": 1000, "engineers": 400},
        structures_choices={"homes": 90, "mines": 70, "fuel_plants": 50, "hangars": 70, "drone_factories": 0,
                            "missile_silos": 0, "workshops": 20},
        auto_spending={"settle": 0.1, "structures": 0.2, "military": 0.6, "engineers": 0.1},
        structures_target={"homes": 0.25, "mines": 0.2, "fuel_plants": 0.15, "hangars": 0.25, "workshops": 0.05},
        units_target={"attack": 0.4, "flex": 0.4, "defense": 0.1},
        projects_target={"military_bonus": 0.35, "general_bonus": 0.25, "money_bonus": 0.2, "pop_bonus": 0.1},
        auto_attack={"pure": 0.5, "flex": 0.3},
        shields={"military": 0.05},
    ),
    "intel": Archetype(
        key="intel",
        label="Intel",
        race="Lumina",
        description="Support: drone-heavy, reveals other kingdoms and shares what it learns with its galaxy.",
        unit_choices={"drones": 6000, "recruits": 1000, "attack": 0, "defense": 1000, "flex": 0, "engineers": 800},
        structures_choices={"homes": 90, "mines": 50, "fuel_plants": 40, "hangars": 20, "drone_factories": 70,
                            "missile_silos": 0, "workshops": 30},
        auto_spending={"settle": 0.2, "structures": 0.3, "military": 0.3, "engineers": 0.2},
        structures_target={"homes": 0.28, "mines": 0.15, "fuel_plants": 0.12, "hangars": 0.07, "drone_factories": 0.25,
                           "workshops": 0.1},
        units_target={"defense": 0.5, "flex": 0.2},
        projects_target={"money_bonus": 0.3, "pop_bonus": 0.25, "fuel_bonus": 0.2, "military_bonus": 0.1},
        shields={"spy": 0.1, "spy_radar": 0.1},
    ),
    "thief": Archetype(
        key="thief",
        label="Thief",
        race="Vult",
        description="Lives off drones: robs primitives on a timer and keeps enough defense to be left alone.",
        unit_choices={"drones": 8000, "recruits": 1000, "attack": 0, "defense": 800, "flex": 0, "engineers": 700},
        structures_choices={"homes": 80, "mines": 50, "fuel_plants": 40, "hangars": 10, "drone_factories": 90,
                            "missile_silos": 0, "workshops": 30},
        auto_spending={"settle": 0.2, "structures": 0.3, "military": 0.3, "engineers": 0.2},
        structures_target={"homes": 0.25, "mines": 0.15, "fuel_plants": 0.12, "hangars": 0.03, "drone_factories": 0.3,
                           "workshops": 0.1},
        units_target={"defense": 0.6},
        projects_target={"money_bonus": 0.3, "pop_bonus": 0.2, "fuel_bonus": 0.1, "drone_gadgets": 0.2},
        auto_rob={"drones": 0.5, "shielded": False, "keep": 5},
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
    settings = {
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
    db = app.extensions["sqlalchemy"]
    guard = app.extensions["praetorian"]
    if db.session.query(User).filter_by(username=name).count():
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

    db.session.add(User(
        username=name,
        # Nobody knows this password, so nobody can log in as a bot.
        password=guard.hash_password(secrets.token_urlsafe(32)),
        roles='operator',
        kd_id=kd_id,
        kd_created=True,
        is_active=True,
    ))
    db.session.commit()
    return kd_id


def create_bots(counts, rng=None, first_number=None):
    """
    Create several bots. ``counts`` maps archetype key to how many, e.g. ``{"explorer": 25, "attacker": 25}``. Returns
    the names created. The account list is synced to the function app once at the end, like any other sign-up.
    """
    import untitledapp.account as uaa

    rng = rng or random.Random()
    db = flask.current_app.extensions["sqlalchemy"]
    existing = db.session.query(User).filter(User.username.like(f"{BOT_PREFIX}%")).count()
    number = existing + 1 if first_number is None else first_number
    created = []
    for key, how_many in counts.items():
        for _ in range(int(how_many)):
            name = f"{BOT_PREFIX}{key}_{number}"
            create_bot(name, key, rng)
            created.append(name)
            number += 1
    uaa._update_accounts()
    return created
