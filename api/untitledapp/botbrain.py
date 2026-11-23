"""
The bot brain (issue #76): the part of a bot that *decides*.

``bots.py`` creates a bot kingdom; the game's auto builder builds, settles, trains, attacks primitives and robs them for
it. This module is the player behind that kingdom. Every think it:

1. **reads the news** and remembers who hit it (``react``);
2. **re-plans its economy** for the phase of the round: the auto spending split, structure and unit targets, engineers
   on projects, shields, auto attack and auto rob (``plan_economy``, sums in ``botstrategy.py``);
3. **spends loose money** the way a player would on the Build pages (``spend_money``);
4. **plays politics**: galaxy policies, the galaxy leader, empires, denouncing and war, universe votes
   (``plan_politics``);
5. **gathers and trades intel**: reveals a galaxy, spies where it matters, accepts what galaxymates offer
   (``plan_intel``, ``accept_intel``);
6. **picks a fight**: a kingdom when it pays better than primitives, and late in the round the leaders, with armies,
   drones and missiles (``plan_attack``, ``plan_drones``, ``plan_missiles``).

The rules it follows are the ones in the guide and the help pages, with the numbers worked out rather than guessed:

* **Know before you hit.** Never attack without military intel; get it, or take it from a galaxymate who has it.
* **Hit what pays.** A target is worth its stars per point of offense, and primitives are always there to compare with.
* **Do not be the best target.** Keep enough defense that primitives are the better deal for anybody looking.
* **Play the round.** Early: primitives, settling while it is cheap, the key project. Mid: keep the bonuses up and the
  defense ahead. Late: military, and gang up on whoever leads.
* **Play as a team.** Vote for what the galaxy needs, share intel for a cut, join an empire, fight its enemies and
  leave its members alone.
* **Learn.** A failed attack widens the buffer, a spy that keeps failing moves on, a kingdom that stops growing changes
  how it grows. What it learned is in ``bot["memory"]``.

How it acts: scheduled actions (attacks, spying, missiles) go on the bot's own **schedule**, at times spread over the
coming interval, and the refresh runs them through the code the routes use. Everything else (votes, settings, purchases)
is done on the spot through the same functions as the routes. Each bot thinks on its own timer (``next_think``), so a
hundred bots think a few at a time.

Everything the brain looks at is what a player could see: its own kingdom, names, galaxies, the scores as shown, and
the intel revealed to it. Every decision is logged on the bot (``bot["log"]``, the last ``LOG_SIZE``), and counted
(``bot["counts"]``).

**All numbers in ``Personality`` are ``TUNE`` values**, tuned with ``scripts/simulate_round.py``.
``problems(personality)`` checks them; ``tests/test_bot_brain.py`` runs it.
"""
import copy
import dataclasses
import datetime
import math
import random
import uuid
import zlib

import flask

import untitledapp.botstrategy as strategy
import untitledapp.build as uab
import untitledapp.conquer as uac
import untitledapp.galaxypolicies as uagp
import untitledapp.getters as uag
import untitledapp.intel as uai
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.politics as uap
import untitledapp.shared as uas
import untitledapp.targets as uat

LOG_SIZE = 40
SCHEDULE_LIMIT = 10  # what the game allows
EPOCH = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
# Generals the auto attack of a bot made before bots set ``reserved_generals`` themselves leaves alone.
RESERVED_GENERALS = 2
TARGET_STYLES = ("none", "primitives", "players", "both")
# TUNE: a kingdom that has grown less than this share in this many epochs has stalled, and changes how it grows.
MAX_EXTRA_WORKSHOPS = 0.06  # TUNE: the most extra land (share) a kingdom with money to spare turns into workshops
MAX_HOMES_SHIFT = 0.5       # TUNE: how far the homes share of homes-and-mines moves with money to spare (or short)
MIN_SPY_CHANCE = 0.15       # TUNE: the least chance worth a try for military intel (twice that for anything else)
EFFICIENT_ARMY_SURPLUS = 0.2  # TUNE: how much money to spare (0 to 1) before defense is bought as flexers
SPY_FAILS = 3               # TUNE: failed intel operations in a row before a target is left alone
SPY_FORGET_EPOCHS = 48      # TUNE: and for how long
MAX_SIPHONS_PER_THINK = 3   # TUNE: siphons scheduled in one think, on different kingdoms
SIPHON_KEEP_ATTEMPTS = 8    # TUNE: spy attempts kept from the auto rob while there are kingdoms worth siphoning
SIPHON_ALL_DRONES = True    # TUNE: send every drone on a siphon, not only as many as the target's income can pay
SIPHON_REVEAL_BELOW = 4     # TUNE: a siphoning bot reveals a galaxy when it has fewer kingdoms than this to siphon
SIPHON_PICK = "spread"      # TUNE: "spread" draws siphon targets in proportion to their worth; "best" takes the best
SIPHON_SHARPNESS = 1.0      # TUNE: siphon targets are drawn in proportion to worth ** this (higher: the best more often)
SIPHON_PRIOR = 2.0          # TUNE: how many siphons' worth of trust the forecast chance gets against what was seen
SIPHON_MEMORY = 0.8         # TUNE: how much of what was seen of a target's spies is kept with each new try
THREAT_MARGIN = 1.05        # TUNE: defense wanted over the strongest offense an outsider is known to have
THREAT_CAP = 2.0            # TUNE: but never more than this many times the deterrence line
THREAT_EPOCHS = 24          # TUNE: how long a threat seen is remembered
HOMES_RULE = "surplus"      # TUNE: "surplus" moves the homes share with money to spare (more homes) or short (more
                            #       mines); "people" sizes homes for the recruits the money could buy (it did worse);
                            #       "training" moves it by whether recruits are being trained at the cap
MIN_DEFENSE = 0.0           # TUNE: the least defense any bot keeps home, in times the peacetime break-even with
                            #       primitives (1.1: a hit on it pays less than primitives, though it still hurts an
                            #       enemy). Off: at 1.1 attackers ended 10% and intel 16% smaller (docs/bots.md).
TRAINING_FULL = 0.9         # TUNE: "training": recruits in training at this share of the cap or more is training flat out
TRAINING_LOW = 0.7          # TUNE: and below this share there are more homes than the army can use
HOMES_STEP = 0.03           # TUNE: how far the homes share moves in one think under "training"
DRONES_GUESS = "fixed"      # TUNE: a kingdom's drones without intel: "fixed" 4 a star; "learned" the median drones per
                            #       star of the kingdoms whose drones the bot has seen
DEFENSE_RISK_MODE = "floor"  # TUNE: with DEFENSE_RISK, "floor" raises the defense to it; "margin" makes it the bot's aim
                            #       (above or below what its playstyle would keep)
DEFENSE_RISK = None         # TUNE: (low, high): each bot keeps at least this range of the break-even with primitives,
                            #       where in it fixed per kingdom (its riskiness); None: off
HOMES_SPARE = 1.15          # TUNE: homes kept over what the recruits and engineers need
ENGINEERS_PER_STAR = None   # TUNE: the most engineers a kingdom keeps per star (None: as many as the workshops hold)
WAR_MARGIN = 1.3            # TUNE: how much more defense a kingdom whose empire is at war keeps
BOMBER_KEEP = 1.5           # TUNE: epochs of income a bomber keeps as money for missiles
TARGET_SHARE = 0.5          # TUNE: the share of attacks, spy attempts and missile strikes a bot puts on its empire's
                            # targets, when it is equipped to (a beatable target, a fair chance)
SUICIDE_TEAM = 8            # TUNE: how many kingdoms' worth of burning a bot counts on when it burns a leader's fuel
STALL_EPOCHS = 24
STALL_GROWTH = 0.02
E, M, L = 0, 1, 2
_PHASE_INDEX = {"early": E, "mid": M, "late": L}


@dataclasses.dataclass(frozen=True)
class Personality:
    """How one playstyle behaves. Times are in epochs. A tuple of three is (early, mid, late)."""
    # TUNE: how often it thinks, as a range in epochs; each gap is drawn at random from it.
    think_epochs: tuple = (1.0, 3.0)
    # TUNE: the most scheduled actions the brain adds in one think, and the most it lets sit in the schedule.
    max_new: int = 3
    max_pending: int = 5

    # TUNE: what a bot of this playstyle hits with its army, and with its drones, drawn once per bot by these weights:
    # "none", "primitives" only, "players" only, or "both". And the chance that it is a bomber (builds missiles).
    army_targets: dict = dataclasses.field(default_factory=lambda: {"primitives": 1.0})
    drone_targets: dict = dataclasses.field(default_factory=lambda: {"primitives": 1.0})
    bomber_chance: float = 0.2

    # TUNE: the economy. How hard it settles when settling still pays, the share of income the army may take beyond
    # the defense it needs, how far above the deterrence line it keeps its defense, and the share of that army money
    # that becomes offense (in ``offense_mix`` proportions) rather than more defense.
    settle_drive: tuple = (1.0, 1.0, 0.8)
    military_drive: tuple = (0.1, 0.2, 0.35)
    defense_margin: float = 1.1
    offense_share: tuple = (0.5, 0.2, 0.2)
    offense_mix: dict = dataclasses.field(default_factory=lambda: {"attack": 1.0})
    # Whether settling stays ahead of the army in the queue for money all round (for a playstyle that grows by it).
    settle_first: bool = False
    # TUNE: land use. Workshops and drone factories as shares of the kingdom; of what hangars and fuel plants leave,
    # the share that is homes (the rest is mines).
    workshops: tuple = (0.06, 0.06, 0.08)
    drone_factories: float = 0.05
    # TUNE: and while the kingdom is under this many stars, at least this share of drone factories (share, stars):
    # drones made early siphon for the rest of the round.
    early_drone_factories: tuple = (0.0, 0)
    homes: float = 0.55
    missile_silos: float = 0.03   # bombers only, from the mid game
    # TUNE: engineers. How much it cares about each continuous bonus, the unlocks it works towards in order, and the
    # share of engineers kept on the unlock.
    project_weights: dict = dataclasses.field(default_factory=lambda: {"money_bonus": 1.0, "fuel_bonus": 0.5, "military_bonus": 0.8})
    key_projects: tuple = ()
    key_share: tuple = (0.5, 0.3, 0.2)
    # TUNE: share of income left as money for bombers' missiles, by phase.
    missile_reserve: tuple = (0.0, 0.04, 0.08)

    # TUNE: attacks on kingdoms. How much more offense than their defense it asks for (percent), how many times better
    # than primitives a kingdom must be for a bot that hits both, how long it will hold its army back waiting for a
    # strike (epochs), and late in the round the least share of a leader's defense worth a losing attack.
    attack_buffer: tuple = (3.0, 10.0)
    player_edge: float = 1.0
    strike_wait: float = 8.0
    chip_ratio: float = 0.7
    # Off: in a week of 100 bots every lost attack was one of these, and without them every playstyle ended larger.
    chip_chance: float = 0.0

    # TUNE: intel. Chance per think of spying for intel, which reveal operations it likes, the success chance it sends
    # drones for, tries, the chance that it offers what it learns to its galaxy, and the cut of the spoils it asks.
    intel_chance: float = 0.3
    intel_ops: tuple = ("spymilitary", "spykingdom")
    intel_aim: float = 0.85
    intel_tries: tuple = (1, 3)
    share_chance: float = 0.3
    share_cut: float = 0.0     # percent

    # TUNE: drones. Share of its drones the auto rob sends, chance per think of an aggressive operation, how much better
    # than robbing a siphon must look, and what it does to a leader late in the round.
    rob_share: float = 0.9
    aggressive_chance: float = 0.0
    siphon_edge: float = 1.2
    sabotage_chance: tuple = (0.0, 0.0, 0.35)
    sabotage_ops: tuple = ("kidnappopulation", "bombhomes", "sabotagefuelplants")

    # TUNE: the share of its missiles it fires at once, and the stock (share of its silos) it waits for.
    missiles_share: tuple = (0.6, 1.0)
    missiles_stock: float = 0.5

    # Politics: the option (as the vote route takes it) it votes for in each galaxy and universe policy, and the share
    # of its loose money it spends on universe votes in an election.
    # The galaxy policy options it votes for, one of each policy: in a round, it votes for the one listed of each of
    # the round's policies.
    galaxy_votes: tuple = ()
    universe_votes: dict = dataclasses.field(default_factory=dict)
    vote_budget: float = 0.25


PERSONALITIES = {
    "explorer": Personality(
        think_epochs=(2.0, 5.0),
        army_targets={"none": 0.1, "primitives": 0.9}, drone_targets={"primitives": 1.0}, bomber_chance=0.15,
        # Defense near the break-even (0.85 of a line that counts war gains: about 1.0 in peace). At 1.2 explorers sat
        # at 1.5 times it, were never hit, and ended a quarter smaller; nobody hunts them at 0.85 either.
        settle_drive=(1.0, 1.0, 1.0), military_drive=(0.4, 0.45, 0.6), defense_margin=0.85,
        offense_share=(1.0, 0.9, 0.4), settle_first=True,
        workshops=(0.06, 0.06, 0.08), drone_factories=0.04, homes=0.5,
        project_weights={"money_bonus": 1.0, "fuel_bonus": 0.6, "military_bonus": 0.8, "general_bonus": 0.3, "spy_bonus": 0.4},
        key_projects=("drone_gadgets", "big_flexers"), key_share=(0.4, 0.25, 0.15),
        intel_chance=0.15, share_chance=0.5,
        galaxy_votes=("expansionist", "drone_foundries", "conscription", "applied_research", "industrialists", "renovators", "mining_guilds", "civic_taxation", "fortification", "plunderers", "drone_recovery", "aegis", "fortress", "rapid_construction"),
        universe_votes={"policy_1": "2", "policy_2": "1"},    # Treatied (it defends), Free trade
    ),
    "attacker": Personality(
        think_epochs=(1.0, 3.0),
        army_targets={"primitives": 0.25, "players": 0.25, "both": 0.5}, drone_targets={"primitives": 1.0},
        bomber_chance=0.3,
        settle_drive=(1.0, 1.0, 0.8), military_drive=(0.4, 0.45, 0.6), defense_margin=0.7,
        offense_share=(1.0, 0.9, 0.7), offense_mix={"attack": 0.8, "flex": 0.2, "big_flex": 0.4},
        workshops=(0.08, 0.07, 0.07), drone_factories=0.05, homes=0.5,
        project_weights={"military_bonus": 1.0, "general_bonus": 1.0, "money_bonus": 0.8, "fuel_bonus": 0.5},
        key_projects=("big_flexers",), key_share=(0.5, 0.3, 0.15),
        attack_buffer=(3.0, 9.0), player_edge=1.0,
        intel_chance=0.7, intel_ops=("spymilitary",), share_chance=0.2,
        galaxy_votes=("raiders", "warlike", "conscription", "applied_research", "industrialists", "shipwrights", "refineries", "efficiency", "offensive_arms", "infiltrators", "veteran_corps", "silo_programme", "fortress", "rapid_construction"),
        universe_votes={"policy_1": "1", "policy_2": "1"},    # Unregulated, Free trade
    ),
    "intel": Personality(
        think_epochs=(1.0, 2.5), max_new=4, max_pending=7,
        army_targets={"none": 0.1, "primitives": 0.9}, drone_targets={"primitives": 0.6, "both": 0.4},
        bomber_chance=0.2,
        settle_drive=(1.0, 1.0, 0.8), military_drive=(0.4, 0.45, 0.6), defense_margin=1.15,
        offense_share=(1.0, 0.9, 0.4),
        workshops=(0.07, 0.07, 0.08), drone_factories=0.06, homes=0.6,
        project_weights={"money_bonus": 1.0, "fuel_bonus": 0.5, "military_bonus": 0.7, "spy_bonus": 1.0},
        key_projects=("drone_gadgets", "big_flexers"), key_share=(0.6, 0.3, 0.15),
        # Military intel is what galaxymates buy and strike with; kingdom intel shows a kingdom out of fuel. Projects
        # and structures intel nobody accepts, so it is no use to a bot.
        intel_chance=0.9, intel_ops=("spymilitary", "spymilitary", "spymilitary", "spykingdom"),
        intel_tries=(1, 3), share_chance=0.95, share_cut=10.0,
        aggressive_chance=0.15, sabotage_chance=(0.0, 0.1, 0.5),
        galaxy_votes=("expansionist", "drone_foundries", "intelligence", "breakthroughs", "engineering_corps", "renovators", "mining_guilds", "civic_taxation", "fortification", "infiltrators", "drone_recovery", "aegis", "counter_intel", "population_boom"),
        universe_votes={"policy_1": "2", "policy_2": "1"},
    ),
    "thief": Personality(
        think_epochs=(1.5, 4.0), max_new=3, max_pending=6,
        army_targets={"none": 0.1, "primitives": 0.9},
        # Every thief siphons kingdoms, with nearly every spy attempt, from drone factories on 15% of its land.
        drone_targets={"players": 0.5, "both": 0.5}, bomber_chance=0.2,
        settle_drive=(1.0, 1.0, 0.8), military_drive=(0.4, 0.45, 0.6), defense_margin=1.0,
        offense_share=(1.0, 0.9, 0.4),
        workshops=(0.06, 0.06, 0.08), drone_factories=0.15, homes=0.6,
        project_weights={"money_bonus": 1.0, "fuel_bonus": 0.5, "military_bonus": 0.7, "spy_bonus": 1.0},
        key_projects=("drone_gadgets", "big_flexers"), key_share=(0.6, 0.3, 0.15),
        intel_chance=0.1, intel_ops=("spykingdom", "spydrones", "spymilitary"), share_chance=0.3,
        aggressive_chance=0.9, sabotage_chance=(0.0, 0.0, 0.1),
        sabotage_ops=("kidnappopulation", "bombhomes", "sabotagefuelplants", "kidnappopulation"),
        galaxy_votes=("expansionist", "drone_foundries", "intelligence", "applied_research", "industrialists", "renovators", "mining_guilds", "civic_taxation", "fortification", "plunderers", "drone_recovery", "aegis", "counter_intel", "population_boom"),
        universe_votes={"policy_1": "2", "policy_2": "1"},
    ),
}


def problems(personality):
    """Everything wrong with a personality, as sentences. Empty if fine."""
    found = []
    for name in ("think_epochs", "attack_buffer", "intel_tries", "missiles_share"):
        low, high = getattr(personality, name)
        if low > high or low < 0:
            found.append(f"{name} must be a range from low to high, not {low}..{high}")
    for name in ("intel_chance", "aggressive_chance", "share_chance", "bomber_chance", "rob_share", "chip_chance",
                 "homes", "drone_factories", "missile_silos", "vote_budget", "missiles_stock", "intel_aim"):
        if not 0 <= getattr(personality, name) <= 1:
            found.append(f"{name} is a share or a chance, from 0 to 1")
    for name in ("settle_drive", "military_drive", "offense_share", "workshops", "key_share", "missile_reserve",
                 "sabotage_chance"):
        values = getattr(personality, name)
        if len(values) != 3 or any(not 0 <= value <= 1 for value in values):
            found.append(f"{name} is three shares (early, mid, late), each from 0 to 1")
    if not 0 <= personality.early_drone_factories[0] <= 0.6:
        found.append("early drone factories are a share of the land, from 0 to 0.6")
    if max(personality.workshops) + personality.drone_factories + personality.missile_silos > 0.5:
        found.append("workshops, drone factories and missile silos leave too little land for anything else")
    if personality.intel_tries[0] < 1 or personality.intel_tries[1] > 10:
        found.append("intel tries are 1 to 10")
    if personality.max_pending > SCHEDULE_LIMIT - 2:
        found.append(f"max_pending must leave room in the schedule of {SCHEDULE_LIMIT}")
    if not 0 <= personality.share_cut <= uas.GAME_CONFIG["BASE_MAX_SHARE_CUT"] * 100:
        found.append("share_cut is a percent, at most the game's maximum cut")
    for name in ("army_targets", "drone_targets"):
        weights = getattr(personality, name)
        if not weights or set(weights) - set(TARGET_STYLES) or sum(weights.values()) <= 0:
            found.append(f"{name} must weigh some of {TARGET_STYLES}")
    for unit in personality.offense_mix:
        if uas.UNITS.get(unit, {}).get("offense", 0) <= 0:
            found.append(f"{unit} is not a unit with offense")
    for project in personality.project_weights:
        if project not in strategy.CONTINUOUS_PROJECTS:
            found.append(f"{project} is not a continuous project")
    for project in personality.key_projects:
        if project not in uas.ONE_TIME_PROJECTS:
            found.append(f"{project} is not a one-time project")
    for operation in personality.intel_ops:
        if operation not in uas.REVEAL_OPERATIONS:
            found.append(f"{operation} is not an intel operation")
    for operation in personality.sabotage_ops:
        if operation not in uas.AGGRO_OPERATIONS:
            found.append(f"{operation} is not an aggressive operation")
    voted_policies = []
    for option in personality.galaxy_votes:
        if option not in uas.GALAXY_POLICY_OF_OPTION:
            found.append(f"no galaxy policy has the option {option}")
        else:
            voted_policies.append(uas.GALAXY_POLICY_OF_OPTION[option])
    if len(set(voted_policies)) != len(voted_policies):
        found.append("galaxy_votes lists two options of one policy")
    for policy, option in personality.universe_votes.items():
        if option not in uas.UNIVERSE_POLICIES.get(policy, {}).get("options", {}):
            found.append(f"universe {policy} has no option {option}")
    return found


def roll_style(personality, rng):
    """What makes one bot of a playstyle different from the next, drawn once when it is created."""
    def draw(weights):
        return rng.choices(list(weights), weights=list(weights.values()))[0]

    return {
        "army": draw(personality.army_targets),
        "drones": draw(personality.drone_targets),
        "bomber": rng.random() < personality.bomber_chance,
        # A cautious bot (below 1) keeps more defense and spends less on offense; a bold one the other way.
        "temper": round(rng.uniform(0.85, 1.15), 3),
    }


def _style(bot, personality):
    """A bot's style, with a sensible one for bots created before styles existed."""
    style = {"army": "primitives" if personality.offense_share[0] > 0.5 else "none", "drones": "primitives",
             "bomber": False, "temper": 1.0}
    style.update(bot.get("style") or {})
    return style


def reserved_generals(kd_info):
    """Generals a bot's auto attack leaves at home."""
    bot = kd_info.get("bot") or {}
    return int(bot.get("reserved_generals", RESERVED_GENERALS)) if bot else 0


@dataclasses.dataclass
class Decision:
    """One thing the bot has decided to do. ``kind`` is a schedule type, or the name of something done on the spot."""
    kind: str
    options: dict
    why: str
    delay: float = 0.0   # seconds from now (scheduled kinds)
    at: float = None     # seconds from now at which it must run, if the time matters (a strike)


_utc = uas.utc  # compare times as datetimes, never as strings


# ------------------------------------------------------------------------------------------------ what a bot can see

class World:
    """
    What a player would see from this kingdom, read as it is needed and at most once per think: names, galaxies,
    empires, the scores as the Scores page shows them, its news, and the intel that is revealed to it.
    """

    def __init__(self, kd_id, me, now, state=None):
        self.kd_id = str(kd_id)
        self.me = me
        self.now = now
        self.state = state if state is not None else uag._get_state()
        self.names = uag._get_kingdoms()
        self.galaxy_of, self.galaxies = uag._get_galaxies_inverted()
        self.revealed_info = uag._get_revealed(kd_id)
        self.revealed = self.revealed_info["revealed"]
        self._seen = {}
        self._cache = {}

    # --- the round

    @property
    def game_start(self):
        return _utc(self.state["state"]["game_start"])

    @property
    def game_end(self):
        return _utc(self.state["state"]["game_end"])

    @property
    def epochs(self):
        return strategy.epochs_since(self.now, self.game_start)

    @property
    def epochs_left(self):
        return max((self.game_end - self.now).total_seconds(), 0) / EPOCH

    @property
    def phase(self):
        return strategy.phase(strategy.round_progress(self.now, self.game_start, self.game_end))

    @property
    def active_policies(self):
        return self.state["state"].get("active_policies") or []

    @property
    def modifiers(self):
        """What politics does to this kingdom now (``getters._get_modifiers``), as the server prices things with it."""
        return self._lazy("modifiers", lambda: uag._get_modifiers(self.kd_id, self.galaxy_of.get(self.kd_id), self.now))

    @property
    def cost_modifier(self):
        """Unit prices as ``getters._get_units_adjusted_costs`` makes them (before the pure-unit discounts)."""
        return (1.0 - ("Unregulated" in self.active_policies) * uas.GAME_CONFIG["BASE_UNREGULATED_COST_REDUCTION"]
                + ("Treatied" in self.active_policies) * uas.GAME_CONFIG["BASE_TREATIED_COST_INCREASE"]
                + uas.modifier(self.modifiers, "unit_cost"))

    # --- lazily read documents

    def _lazy(self, key, read):
        if key not in self._cache:
            self._cache[key] = read()
        return self._cache[key]

    @property
    def my_galaxy(self):
        return self.galaxy_of.get(self.kd_id)

    @property
    def galaxy_politics(self):
        return self._lazy("galaxy_politics", lambda: uag._get_galaxy_politics(self.kd_id, self.my_galaxy)[0])

    @property
    def empires(self):
        """``(empire of each kingdom, the empires, empire of each galaxy)``."""
        def read():
            kd_empire, info, galaxy_empire, _ = uag._get_empires_inverted()
            return kd_empire, info["empires"], galaxy_empire
        return self._lazy("empires", read)

    @property
    def my_empire(self):
        return self.empires[2].get(self.my_galaxy)

    @property
    def empire_targets(self):
        """The empire's targets, as the Targets tab shows them to a member: kingdom to the actions it is marked for.
        Read only when the empire has any."""
        def read():
            mine = self.my_empire
            if mine is None or not self.empires[1].get(mine, {}).get("targets"):
                return {}
            document = uat.normalize(occ.read(uat._path(mine)))
            return {kd: dict(entry["actions"]) for kd, entry in document["targets"].items()}
        return self._lazy("empire_targets", read)

    def marked_for(self, *actions):
        """The empire's targets marked for any of ``actions``, while their empire is at war with the bot's (only then do
        actions on them count)."""
        return [kd for kd, marked in self.empire_targets.items()
                if any(action in marked for action in actions) and self.relation(kd)[0]]

    @property
    def scores(self):
        """The Scores page: ranked lists of ``(kingdom id or "", value)``, and the galaxies' networth."""
        return self._lazy("scores", lambda: uag._get_scores_redacted(self.revealed_info, self.kd_id, self.galaxy_of))

    @property
    def news(self):
        return self._lazy("news", lambda: occ.read(f'/kingdom/{self.kd_id}/news').get("news", []))

    @property
    def intel(self):
        """The galaxy's intel market as the Intel page shows it to this kingdom (intel.view)."""
        members = self.galaxies.get(self.my_galaxy, [])
        return self._lazy("intel", lambda: uai.view(uai._market(self.my_galaxy), self.kd_id, self.revealed_info,
                                                    self.now, members))

    @property
    def spy_history(self):
        return self._lazy("spy_history", lambda: occ.read(f'/kingdom/{self.kd_id}/spyhistory').get("spy_history", []))

    @property
    def attack_history(self):
        return self._lazy("attack_history", lambda: occ.read(f'/kingdom/{self.kd_id}/attackhistory').get("attack_history", []))

    # --- who is who

    def galaxymates(self):
        return [kd for kd in self.galaxies.get(self.my_galaxy, []) if kd != self.kd_id]

    def allies(self):
        """Kingdoms in the bot's empire but not in its galaxy."""
        mine = self.my_empire
        if mine is None:
            return []
        return [kd for kd, empire in self.empires[0].items() if empire == mine and self.galaxy_of.get(kd) != self.my_galaxy]

    def outsiders(self):
        """Kingdoms worth acting against: in another galaxy, and not in the bot's empire."""
        allies = set(self.allies())
        return [kd for kd in self.names
                if kd != self.kd_id and kd in self.galaxy_of and self.galaxy_of[kd] != self.my_galaxy and kd not in allies]

    def relation(self, target):
        """``(at war, denounced by us)`` with the target's empire."""
        mine, theirs = self.my_empire, self.empires[0].get(target)
        if mine is None or theirs is None:
            return False, False
        empire = self.empires[1].get(mine, {})
        return theirs in empire.get("war", []), empire.get("denounced") == theirs

    def seconds_left(self, target, category):
        """How long ``category`` of ``target`` stays revealed to us, in seconds (0 if it is not)."""
        until = self.revealed.get(target, {}).get(category)
        if until is None:
            return 0.0
        return max((_utc(until) - self.now).total_seconds(), 0.0)

    def revealed_with(self, category, at_least=0.0):
        return [kd for kd in self.outsiders() if self.seconds_left(kd, category) > at_least]

    def target_info(self, target):
        """What we are allowed to know about ``target``."""
        if target not in self._seen:
            self._seen[target] = uag._get_max_kd_info(target, self.kd_id, self.revealed_info, galaxies_inverted=self.galaxy_of)
        return self._seen[target]

    def known_stars(self):
        """``{kingdom: (stars, networth)}`` for the outsiders whose stats the bot can see, without reading anybody."""
        networth = {kd: value for kd, value in self.scores["networth"] if kd}
        stars = {kd: value for kd, value in self.scores["stars"] if kd}
        outsiders = set(self.outsiders())
        return {kd: (stars[kd], networth.get(kd, 0)) for kd in stars if kd in outsiders}

    def leaders(self, count=3):
        """The strongest outsiders the bot can put a name to, strongest first."""
        known = self.known_stars()
        return sorted(known, key=lambda kd: -known[kd][1])[:count]

    def defense_of(self, target, info=None):
        """The target's defense as far as its revealed intel shows it, assuming the worst of what is hidden. None
        without military intel."""
        info = info if info is not None else self.target_info(target)
        if "units" not in info or "defense" not in info["units"]:
            return None
        war, _ = self.relation(target)
        peace = False
        if self.my_empire is not None:
            peace = self.empires[0].get(target) in self.empires[1].get(self.my_empire, {}).get("peace", {})
        return uag._calc_max_defense(
            {unit: count for unit, count in info["units"].items() if unit in uas.UNITS},
            military_bonus=info["current_bonuses"]["military_bonus"] if "current_bonuses" in info
            else uas.PROJECTS["military_bonus"]["max_bonus"],
            other_bonuses=0,
            shields=info["shields"]["military"] if "shields" in info else uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"],
            fuelless=info.get("fuel", 1) <= 0,
            gaian=self.me["race"] == "Gaian",
            peace=peace,
        )

    def offense_with(self, units, generals, target=None):
        """The offense ``units`` make when ``generals`` lead them, against ``target`` if given."""
        war, denounced = self.relation(target) if target else (False, False)
        surprise = False
        if target and self.my_empire is not None:
            surprise = self.empires[1].get(self.empires[0].get(target), {}).get("surprise_war_penalty", False)
        return uag._calc_max_offense(
            units, military_bonus=strategy.bonuses(self.me)["military_bonus"], other_bonuses=0, generals=max(generals, 1),
            fuelless=self.me["fuel"] <= 0, lumina=self.me["race"] == "Lumina", denounced=denounced, war=war,
            surprise_war_penalty=surprise,
        )


# ------------------------------------------------------------------------------------------------------- the rules

def _between(rng, span):
    low, high = span
    return rng.uniform(low, high)


def _whole_between(rng, span):
    low, high = span
    return rng.randint(int(low), int(high))


def _by_phase(values, phase_name):
    return values[_PHASE_INDEX[phase_name]]


def react(world, memory):
    """
    Read the news since the last think. An attack makes its sender a grudge and the bot want more defense; missiles
    raise the missile shields; spies it caught raise the spy shields. Returns notes for the log.
    """
    seen = memory.get("seen_news", "")
    fresh = [item for item in world.news if uas.is_after(item.get("time", ""), seen)]
    notes = []
    grudges = memory.setdefault("grudges", {})
    for item in fresh:
        sender, kind, text = str(item.get("from") or ""), item.get("kind"), str(item.get("news", ""))
        if kind == "attack" and sender:
            grudges[sender] = grudges.get(sender, 0) + (2 if "defeated" in text else 1)
            boost = 1.25 if "defeated" in text else 1.08
            memory["defense_boost"] = round(min(memory.get("defense_boost", 1.0) * boost, 2.5), 3)
            if "defeated" in text:
                memory["hit_at"] = item["time"]
            notes.append(f"attacked by {world.names.get(sender, sender)}")
        elif kind == "missiles" and sender:
            grudges[sender] = grudges.get(sender, 0) + 1
            memory["missiles_at"] = item["time"]
            notes.append(f"missiles from {world.names.get(sender, sender)}")
        elif kind == "spy":
            memory["spied_at"] = item["time"]
            if sender:
                grudges[sender] = grudges.get(sender, 0) + 0.5
    if fresh:
        memory["seen_news"] = max((item["time"] for item in fresh), key=_utc)
    # Caution wears off: a tenth of the extra defense wanted goes with every think that passes quietly.
    if not notes and memory.get("defense_boost", 1.0) > 1.0:
        memory["defense_boost"] = round(max(1.0, 1.0 + (memory["defense_boost"] - 1.0) * 0.97), 3)
    return notes


def _recent(memory, key, now, epochs):
    stamp = memory.get(key)
    return bool(stamp) and (now - _utc(stamp)).total_seconds() < epochs * EPOCH


def note_growth(world, memory):
    """Keep a short record of the kingdom's stars, and say whether it has stopped growing."""
    record = memory.setdefault("stars_log", [])
    record.append([round(world.epochs, 2), world.me["stars"]])
    del record[:-16]
    a_day_ago = [entry for entry in record if world.epochs - entry[0] >= STALL_EPOCHS]
    if not a_day_ago:
        return False
    return world.me["stars"] < a_day_ago[-1][1] * (1 + STALL_GROWTH)


def growth_rate(memory, world):
    """Stars gained per epoch as a share of the kingdom, over what the bot remembers (a guess when it remembers little)."""
    record = memory.get("stars_log") or []
    if len(record) >= 2 and record[-1][0] - record[0][0] >= 6 and record[0][1] > 0:
        rate = (record[-1][1] / record[0][1] - 1) / (record[-1][0] - record[0][0])
        return min(max(rate, 0.002), 0.05)
    return 0.012


def plan_economy(world, personality, style, memory):
    """
    The auto builder's settings for the coming hours. Returns ``(settings, why)``: the kingdom fields to write, each
    checked by the validator its route uses.
    """
    me, phase_name = world.me, world.phase
    temper = style.get("temper", 1.0)
    army_style = style.get("army", "none")
    settle_cost = uas.modifier(world.modifiers, "settle_cost")
    income = (me.get("income") or {}).get("money", {}).get("net") or strategy.guess_income(me["stars"])
    growth = growth_rate(memory, world)
    stalled = memory.get("stalled", False)
    hit_lately = _recent(memory, "hit_at", world.now, 24)

    # Defense: enough that primitives are the better target, more for a cautious bot or one that has been hit.
    margin = personality.defense_margin / temper * memory.get("defense_boost", 1.0)
    if world.my_empire is not None and world.empires[1].get(world.my_empire, {}).get("war"):
        margin *= WAR_MARGIN  # an enemy at war gains more from us, and wants to
    line = strategy.defense_wanted(me, world.epochs, margin)
    # Whatever the playstyle, never so little that hitting it pays better than primitives.
    floor = MIN_DEFENSE
    if DEFENSE_RISK and DEFENSE_RISK_MODE == "margin":
        # Its own riskiness instead of the playstyle's margin, still raised when hit and at war.
        line = me["stars"] * strategy.break_even_per_star(world.epochs) * risk_floor(world.kd_id) * (
            margin / (personality.defense_margin / temper))
    elif DEFENSE_RISK:
        floor = max(floor, risk_floor(world.kd_id))
    line = max(line, me["stars"] * strategy.break_even_per_star(world.epochs) * floor)
    # And at least what keeps out the strongest army it knows of (its own intel and what galaxymates shared), up to a
    # point: a kingdom can not out-defend everybody.
    threat = note_threat(world, memory)
    wanted = max(line, min(threat * THREAT_MARGIN, line * THREAT_CAP))
    units = strategy.all_units(me)
    multiplier = max(strategy.defense_multiplier(me), 0.5)
    # A bot that strikes kingdoms counts its flex units for half: they are away when it attacks. One that does not
    # keeps them at home, where they are defense.
    flex_at_home = army_style in ("none", "primitives")
    counted = (units["defense"] * 5 + units["recruits"]
               + (units["flex"] * 5 + units["big_flex"] * 10) * (1.0 if flex_at_home else 0.5))
    deficit = max(wanted / multiplier - counted, 0) / uas.UNITS["defense"]["defense"]

    # Money: what each category can use, most urgent first.
    worth = strategy.settle_worth(me, world.epochs_left, settle_cost, income / max(me["stars"], 1))
    settle_drive = _by_phase(personality.settle_drive, phase_name) * min(max(worth, 0.0), 1.0)
    if stalled:
        settle_drive = max(settle_drive, min(worth, 1.0), 0.5)
    military_drive = min(_by_phase(personality.military_drive, phase_name) * temper, 0.9)
    order = {"early": ["structures", "settle", "military", "engineers"],
             "mid": ["structures", "military", "settle", "engineers"],
             "late": ["military", "structures", "engineers", "settle"]}[phase_name]
    if personality.settle_first:
        order = ["structures", "settle"] + [key for key in order if key not in ("structures", "settle")]
    if hit_lately or deficit * strategy.unit_cost("defense") > income * strategy.HORIZON:
        order = ["military"] + [key for key in order if key != "military"]
    reserve = _by_phase(personality.missile_reserve, phase_name) if style.get("bomber") else 0.0
    shares, wants = strategy.spending_plan(
        me, income, order, settle_drive, military_drive, deficit, settle_cost=settle_cost, growth_per_epoch=growth,
        reserve=reserve, cost_modifier=world.cost_modifier, engineers_per_star=ENGINEERS_PER_STAR)

    # The army the money buys, and the land to keep it on.
    offense_share = 0.0 if army_style == "none" else min(_by_phase(personality.offense_share, phase_name) * temper, 1.0)
    if army_style == "players":
        offense_share = max(offense_share, 0.6)
    military_money = shares["military"] * income * strategy.HORIZON + me["funding"].get("military", 0)
    # With money to spare and no more people to draft, strength per recruit is what counts: flexers, and big flexers
    # once unlocked, for defense. Late in the round that is the army to have as soon as money is not short.
    spare_money = memory.get("surplus", 0.0)
    efficient = spare_money > (0.0 if phase_name == "late" else EFFICIENT_ARMY_SURPLUS)
    units_target, to_buy = strategy.army_plan(me, military_money, deficit, offense_share, personality.offense_mix,
                                              cost_modifier=world.cost_modifier,
                                              defender="big_flex" if efficient else "defense")
    shields, shields_fuel = strategy.shields_plan(
        me, phase_name,
        wants_spy_shields=_recent(memory, "spied_at", world.now, 48) and phase_name != "early",
        under_missiles=_recent(memory, "missiles_at", world.now, 96))
    # Money nothing can use is a sign the kingdom is short of things to spend on: more workshops (and the engineers to
    # fill them) is the one sink that is always open, and engineers are worth as much networth as an army.
    # People, not money, are what the army and the engineers run out of first (recruits and trainees are a share of
    # the population), and only homes hold people; mines only make money. So the split between the two follows what the
    # kingdom is short of: more homes while money is left over, more mines while the army is short of money.
    waiting = me["money"] - (BOMBER_KEEP * income if style.get("bomber") else 0) + me["funding"].get("military", 0)
    loose = waiting > 3 * income
    short = wants["military"] > shares["military"] * income * 1.25 and waiting < income
    memory["surplus"] = round(min(max(memory.get("surplus", 0.0) + (0.05 if loose else -0.05 if short else -0.01), -0.5), 1.0), 3)
    surplus = memory["surplus"]
    land = {
        "workshops": min(_by_phase(personality.workshops, phase_name) + min(max(surplus, 0.0), 1.0) * MAX_EXTRA_WORKSHOPS,
                         # No workshops beyond what the engineers it keeps need.
                         (ENGINEERS_PER_STAR or 99) / max(strategy.workshop_capacity({**me, "structures": {"workshops": 1}}), 1)),
        "drone_factories": max(personality.drone_factories, personality.early_drone_factories[0])
        if me["stars"] < personality.early_drone_factories[1] else personality.drone_factories,
        "missile_silos": personality.missile_silos if style.get("bomber") and phase_name != "early" else 0.0,
        "homes": min(max(personality.homes + surplus * MAX_HOMES_SHIFT, 0.35), 0.9),
    }
    if HOMES_RULE == "training":
        # Mines earn more than homes; homes are for the people recruits are drafted from. Training recruits flat out
        # with money waiting for them: more homes. Not training flat out: more homes than the army uses, so fewer.
        share = recruits_training_share(world)
        waiting = me["funding"].get("military", 0) > income
        shift = memory.get("homes_shift", 0.0)
        if share >= TRAINING_FULL and waiting:
            shift += HOMES_STEP
        elif share < TRAINING_LOW:
            shift -= HOMES_STEP
        memory["homes_shift"] = round(min(max(shift, -0.3), 0.4), 3)
        land["homes"] = min(max(personality.homes + memory["homes_shift"], 0.2), 0.9)
    if HOMES_RULE == "people":
        # Homes for the people the army and the engineers draft from, a little over; mines for the rest of the land.
        # The army's share of the spending plan is itself capped by how fast recruits can be drafted, so sizing homes
        # from it would shrink both in turn: size them for all the money the other categories do not take, so that
        # money, not people, is what limits the army.
        army_money = income * max(1 - shares["settle"] - shares["structures"] - shares["engineers"] - reserve, 0)
        average_unit = (strategy.unit_cost("attack", world.cost_modifier) + strategy.unit_cost("defense", world.cost_modifier)) / 2
        units_per_epoch = army_money / average_unit
        engineers_per_epoch = shares["engineers"] * income / uag._engineer_price(world.modifiers)
        homes = strategy.homes_for_people(units_per_epoch, engineers_per_epoch, vult=me["race"] == "Vult") * HOMES_SPARE
        taken = sum(land[key] for key in ("workshops", "drone_factories", "missile_silos")) * me["stars"]
        taken += me["structures"].get("hangars", 0) + me["structures"].get("fuel_plants", 0)
        free = max(me["stars"] - taken, 1)
        land["homes"] = min(max(homes / free, 0.2), 0.9)
    structures_target = strategy.structures_plan(me, land, to_buy, shields_fuel)

    key_projects = personality.key_projects + (("star_busters",) if style.get("bomber") else ())
    projects = strategy.projects_plan(me, personality.project_weights, key_projects,
                                      _by_phase(personality.key_share, phase_name), growth_per_epoch=growth)

    settings = {}
    why = []

    def keep(field, value, check):
        valid, message = check
        if valid:
            settings[field] = value
        else:
            why.append(f"{field} refused: {message}")

    keep("auto_spending", shares, uam._validate_spending(shares))
    keep("structures_target", structures_target, uab._validate_structures_target(structures_target))
    keep("units_target", units_target, uab._validate_mobis_target(units_target, me))
    if me["fuel"] > 0:
        keep("shields", shields, uam._validate_shields(shields))
    if uab._validate_assign_projects({"assign": projects}, me):
        settings["projects_assigned"] = projects
        # Engineers that finish training before the next think join the projects in the same proportions.
        engineers = max(sum(projects.values()), 1)
        projects_target = {project: math.floor(count / engineers * 10000) / 10000 for project, count in projects.items()}
        keep("projects_target", projects_target, uab._validate_projects_target(projects_target, me))
        settings["auto_assign_projects"] = True
    settings["auto_spending_enabled"] = True
    # Recruits are only worth drafting as fast as the money turns them into units; the rest would sit in the hangars.
    settings["recruits_before_units"] = False
    settings["max_recruits"] = int(max(sum(to_buy.values()) * 1.2, 50))

    # Auto attack on primitives: every pure attacker goes (they are no use at home), and the flex units the home
    # defense can spare. Off while the army is being held for a strike on a kingdom.
    strike = memory.get("strike")
    holding = bool(strike) and _utc(strike["time"]) > world.now - datetime.timedelta(seconds=EPOCH)
    has_offense = strategy.raw_offense(units) > 0
    spare = max(counted * multiplier - wanted, 0) / max(multiplier, 0.5)
    flex_defense = units["flex"] * 5 + units["big_flex"] * 10
    flex_out = round(min(spare / flex_defense, 1.0), 3) if flex_defense > 0 and not flex_at_home else 0.0
    auto_attack = {"pure": 1.0, "flex": flex_out}
    primitives = army_style in ("primitives", "both") or (stalled and army_style != "players")
    settings["auto_attack_settings"] = auto_attack
    settings["auto_attack_enabled"] = bool(primitives and has_offense and not holding)

    rob = style.get("drones", "primitives") in ("primitives", "both")
    settings["auto_rob_settings"] = {"drones": personality.rob_share, "shielded": False,
                                     "keep": int(memory.get("keep_attempts", 2))}
    settings["auto_rob_enabled"] = bool(rob)

    why.append(
        f"{phase_name}: spend settle {shares['settle']:.0%} structures {shares['structures']:.0%} "
        f"military {shares['military']:.0%} engineers {shares['engineers']:.0%}; "
        f"defense {counted * multiplier:,.0f} of {wanted:,.0f} wanted"
        + (", stalled" if stalled else "") + (", holding for a strike" if holding else ""))
    return settings, "; ".join(why)


def recruits_training_share(world):
    """Recruits in training as a share of the most there can be (``BASE_MAX_RECRUITS_CAP`` of the people), as the
    Military page counts them. One read: the mobis queue."""
    me = world.me
    units = uag._calc_units(world.now, me["units"], me.get("generals_out", []), uag._get_mobis_queue(world.kd_id))
    cap = uas.GAME_FUNCS["BASE_MAX_RECRUITS"](int(me.get("population", 0)))
    return units["queued"].get("recruits", 0) / max(cap, 1)


def risk_floor(kd_id):
    """Where in ``DEFENSE_RISK`` this kingdom keeps its defense: fixed per kingdom, so each bot has its own riskiness."""
    low, high = DEFENSE_RISK
    return low + (high - low) * (zlib.crc32(str(kd_id).encode()) / 2 ** 32)


def plan_survival(world, memory):
    """
    A kingdom that has lost stars can be left with an army its hangars and fuel plants can not keep: units without a
    hangar push people out of their homes (a kingdom with no people is dead), and without fuel everything weakens.
    With no empty star to build on, the only way out is to disband what can not be kept: recruits first, then
    offense, defenders last.
    """
    me = world.me
    if me["stars"] > sum(me["structures"].values()) + 1:
        return []  # room to build hangars and fuel plants instead
    units = strategy.all_units(me)
    housed = sum(count * uas.UNITS[unit]["hangar_capacity"] for unit, count in units.items())
    capacity = math.floor(me["structures"].get("hangars", 0)) * uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"]
    overflow = housed - capacity
    excess = overflow if overflow > 0.15 * max(housed, 1) else 0
    fuel_net = (me.get("income") or {}).get("fuel", {}).get("net", 0)
    if me["fuel"] <= 0 and fuel_net < 0:
        excess = max(excess, -fuel_net * 1.1)
    if excess < 50:
        return []
    disband = {}
    for unit in ("recruits", "attack", "flex", "big_flex", "defense"):
        size = uas.UNITS[unit]["hangar_capacity"]
        count = int(min(me["units"].get(unit, 0), math.ceil(excess / size)))
        if count > 0:
            disband[unit] = count
            excess -= count * size
        if excess <= 0:
            break
    if not disband:
        return []
    return [Decision("disband", disband, "more army than the hangars and fuel plants left can keep: disband "
                     + ", ".join(f"{count:,} {unit}" for unit, count in disband.items()))]


def spend_money(world, personality, style, memory, settings):
    """
    Loose money (the starting money, and whatever the spending split leaves over) spent as a player would on the Build
    pages: settle, then structures on empty stars, then engineers. A bomber keeps money for missiles, and everybody
    keeps some during an election. Returns the decisions made; they are carried out on the spot.
    """
    me = world.me
    income = (me.get("income") or {}).get("money", {}).get("net") or strategy.guess_income(me["stars"])
    keep = 0.0
    if style.get("bomber") and world.phase != "early":
        keep += BOMBER_KEEP * income
    if _election_on(world) and memory.get("election") != world.state["state"].get("election_end", ""):
        keep += personality.vote_budget * me["money"]
    money = me["money"] - keep
    if money < max(1.0 * income, 20000) or _recent(memory, "nothing_to_buy", world.now, 8):
        return []
    decisions = []
    if settings.get("auto_spending", {}).get("settle", 0) > 0 or world.phase == "early":
        decisions.append(Decision("buy_settle", {"money": money * 0.4}, "settle with loose money"))
        money *= 0.6
    decisions.append(Decision("buy_structures", {"money": money * 0.6, "target": settings.get("structures_target")},
                              "build with loose money"))
    decisions.append(Decision("buy_engineers", {"money": money * 0.4}, "train engineers with loose money"))
    return decisions


def _election_on(world):
    return world.state["state"].get("election_end", "") not in ("", None)


def plan_politics(world, personality, style, memory, rng):
    """
    Galaxy policies that suit the playstyle; the strongest galaxymate for leader; as leader, an empire (found one, or
    join one with room), and against the strongest other empire a denouncement in the mid game and war late; in an
    election, votes bought and cast for the universe policies that suit it.
    """
    decisions = []
    me = world.me
    politics = world.galaxy_politics
    votes = politics.get("votes", {})
    # Galaxy policies: the option it likes of each of this round's policies. Votes have no cooldown (the tally weighs
    # them by time), so it only votes where its vote is not that already.
    policy_votes = politics.get("policy_votes") or {}
    for policy in uagp.round_policies(world.state.get("state")):
        option = next((o for o in personality.galaxy_votes if uas.GALAXY_POLICY_OF_OPTION.get(o) == policy), None)
        if option and (policy_votes.get(policy) or {}).get(world.kd_id) != option:
            decisions.append(Decision("vote_galaxy", {"policy": policy, "option": option},
                                      f"vote {uas.GALAXY_POLICIES[policy]['options'][option]['name']} in the galaxy"))

    # Leader: the galaxymate with the most networth (the bot can see its galaxy's stats), itself included.
    networth = dict((kd, value) for kd, value in world.scores["networth"] if kd)
    members = [kd for kd in world.galaxies.get(world.my_galaxy, [])]
    if members:
        networth.setdefault(world.kd_id, me.get("networth", 0))
        cast = votes.get("leader", {})
        tally = {}
        for voter, choice in cast.items():
            if choice in members and voter != world.kd_id:
                tally[choice] = tally.get(choice, 0) + 1
        # A galaxy needs one leader more than it needs the best one: back whoever the others back, and only with no
        # votes to go by, the strongest. (Everybody voting for today's strongest splits the vote and elects nobody.)
        best = max(members, key=lambda kd: (tally.get(kd, 0), networth.get(kd, 0), -int(kd) if kd.isdigit() else 0))
        if cast.get(world.kd_id) != best and not uas.galaxy_vote_unlocks_at(politics, "leader", world.kd_id, world.now):
            decisions.append(Decision("vote_leader", {"selected": best}, f"vote {world.names.get(best, best)} for galaxy leader"))

    if politics.get("leader") == world.kd_id:
        decisions.extend(_plan_empire(world, memory, rng))

    # The universe: buy votes with some of the loose money and spend them all, half on each doctrine.
    election = world.state["state"].get("election_end", "")
    if _election_on(world) and personality.universe_votes:
        # Votes are bought once an election, with a share of the loose money. Nobody can see the tally, so most go
        # on the first doctrine listed (arms, where playstyles disagree) and a few on the others.
        buy = 0
        if memory.get("election") != election:
            buy = int(me["money"] * personality.vote_budget // uas.GAME_CONFIG["BASE_VOTES_COST"])
            memory["election"] = election
            if buy > 0:
                decisions.append(Decision("buy_votes", {"votes": buy}, f"buy {buy} universe votes"))
        total = int(me.get("votes") or 0) + buy
        policies = list(personality.universe_votes.items())
        rest = total // 5 if len(policies) > 1 and total >= 5 else 0
        amounts = [total - rest * (len(policies) - 1)] + [rest] * (len(policies) - 1)
        for (policy, option), amount in zip(policies, amounts):
            if amount > 0:
                # The tally is kept under "option_1" and "option_2", as the Universe page sends them.
                decisions.append(Decision("vote_universe", {"policy": policy, "option": f"option_{option}", "votes": amount},
                                          f"cast {amount} votes for {uas.UNIVERSE_POLICIES[policy]['options'][option]['name']}"))
    return decisions


def fits_in_empire(world, empire_galaxies, galaxy):
    """Whether ``galaxy`` may join an empire of ``empire_galaxies`` under the game's size rule (asked before inviting or
    asking, so the bot does not ask for what will be refused)."""
    return uap.empire_size_problem(empire_galaxies, galaxy, world.galaxies,
                                   dict(world.scores["galaxy_networth"])) is None


def _empire_networth(world, empire):
    galaxy_networth = dict(world.scores["galaxy_networth"])
    return sum(galaxy_networth.get(galaxy, 0) for galaxy in empire.get("galaxies", []))


def _plan_empire(world, memory, rng):
    """What a galaxy leader does about empires."""
    decisions = []
    kd_empire, empires, galaxy_empire = world.empires
    politics = world.galaxy_politics
    mine = world.my_empire
    if mine is None:
        here = world.my_galaxy
        invitations = [eid for eid in politics.get("empire_invitations", [])
                       if eid in empires and fits_in_empire(world, empires[eid].get("galaxies", []), here)]
        with_room = [eid for eid, empire in empires.items()
                     if empire.get("galaxies") and fits_in_empire(world, empire["galaxies"], here)]
        requested = [eid for eid in politics.get("empire_join_requests", []) if eid in empires]
        if invitations:
            decisions.append(Decision("empire_accept_invite", {"empire": invitations[0]},
                                      f"accept the invitation of {empires[invitations[0]]['name']}"))
        elif requested and requested[0] not in with_room:
            # It filled up while we waited: take the request back and look elsewhere next time.
            decisions.append(Decision("empire_withdraw", {"empire": requested[0]},
                                      f"{empires[requested[0]]['name']} is full: withdraw the request to join"))
        elif requested:
            pass  # waiting for an answer
        elif with_room:
            # The strongest empire that still has room: allies worth having.
            choice = max(with_room, key=lambda eid: _empire_networth(world, empires[eid]))
            decisions.append(Decision("empire_join", {"empire": choice}, f"ask to join {empires[choice]['name']}"))
        elif len(world.galaxies) >= 2:
            decisions.append(Decision("empire_found", {"name": f"League {world.my_galaxy}"[:24]}, "found an empire"))
        return decisions

    empire = empires.get(mine, {})
    empire_politics = uag._get_empire_politics(mine)
    if empire_politics.get("leader") != world.my_galaxy:
        return decisions
    members = empire.get("galaxies", [])
    for galaxy in empire_politics.get("empire_join_requests", [])[:1]:
        if galaxy not in galaxy_empire and fits_in_empire(world, members, galaxy):
            decisions.append(Decision("empire_admit", {"galaxy": galaxy}, f"admit galaxy {galaxy} to the empire"))
    if not empire_politics.get("empire_join_requests") and not empire_politics.get("empire_invitations"):
        free = [galaxy for galaxy in world.galaxies
                if galaxy not in galaxy_empire and world.galaxies[galaxy] and fits_in_empire(world, members, galaxy)]
        if free:
            decisions.append(Decision("empire_invite", {"galaxy": rng.choice(free)}, "invite a galaxy without an empire"))

    # The rival: the strongest other empire. Denounce it from the mid game (the aggression that follows can bring a
    # war without the penalty for a surprise), and declare war late if it has not come by itself.
    rivals = {eid: _empire_networth(world, other) for eid, other in empires.items() if eid != mine and other.get("galaxies")}
    if rivals and world.phase != "early":
        rival = max(rivals, key=rivals.get)
        at_war = rival in empire.get("war", [])
        if not at_war and not empire.get("denounced"):
            decisions.append(Decision("empire_denounce", {"empire": rival}, f"denounce {empires[rival]['name']}"))
        elif not at_war and world.phase == "late" and rival not in empire.get("peace", {}):
            decisions.append(Decision("empire_war", {"empire": rival}, f"declare war on {empires[rival]['name']}"))
    return decisions


def _attempts_free(world, memory):
    return int(world.me.get("spy_attempts") or 0)


def _spy_decision(world, personality, target, operation, stars, drones_known, rng, share, why):
    """An intel schedule entry sized to succeed: enough drones for the aim, or all of them."""
    mine = max(world.me.get("drones") or 0, 1)
    need = strategy.drones_for_chance(personality.intel_aim, drones_known, stars)
    percent = min(max(need / mine * 100, 5.0), 100.0)
    chance = strategy.spy_chance(mine * percent / 100, drones_known, stars)
    tries = _whole_between(rng, personality.intel_tries) if chance < 0.8 else 1
    return Decision("intelspy", {
        "target": target, "operation": operation, "drones_pct": round(percent, 1),
        "max_tries": max(1, min(tries, _attempts_free(world, None))), "shielded": False,
        "share_to_galaxy": share, "cut": personality.share_cut if share else 0,
    }, f"{why} ({chance:.0%} a try with {percent:.0f}% of the drones)"), chance


def _guess_drones(world, target, stars, memory=None):
    """
    The target's drones if revealed, else a guess from its size (which only costs sending too many or too few): 4 a
    star, or with ``DRONES_GUESS = "learned"`` the median drones per star of the kingdoms the bot has seen the drones
    of (kept in ``memory["drones_seen"]``).
    """
    info = world._seen.get(target) or {}
    drones = info.get("drones")
    if drones is None and world.seconds_left(target, "drones") > 0:
        drones = world.target_info(target).get("drones")
    learned = DRONES_GUESS == "learned" and memory is not None
    if drones is not None:
        if learned:
            seen = memory.setdefault("drones_seen", {})
            seen.pop(target, None)
            seen[target] = round(drones / max(stars, 1), 2)
            while len(seen) > 20:
                seen.pop(next(iter(seen)))
        return drones
    per_star = 4.0
    if learned and memory.get("drones_seen"):
        values = sorted(memory["drones_seen"].values())
        per_star = values[len(values) // 2]
    return stars * per_star


def plan_intel(world, personality, style, memory, rng, want_military=False):
    """
    Intel worth having. With no stats on anybody, reveal a galaxy. Otherwise spy on the most promising kingdom the bot
    lacks intel on: for military intel, the one with the most stars for the army its networth could hide; and offer it
    to the galaxy, for a cut if the playstyle asks one. A target that keeps beating its spies is left alone for a while.
    """
    if not want_military and rng.random() >= personality.intel_chance:
        return []
    attempts = _attempts_free(world, memory)
    if attempts < 1 or (world.me.get("drones") or 0) < 100:
        return []
    known = world.known_stars()
    window = personality.think_epochs[1] * EPOCH + EPOCH
    if len(known) < 3:
        hidden = [galaxy for galaxy in world.galaxies if galaxy != world.my_galaxy
                  and galaxy not in world.revealed_info.get("galaxies", {})
                  and world.empires[2].get(galaxy, -1) != world.my_empire]
        if hidden:
            return [Decision("reveal_galaxy", {}, "reveal a galaxy to see who is out there")]
    if not known:
        return []

    operation = "spymilitary" if want_military else rng.choice(personality.intel_ops)
    category = operation.replace("spy", "")
    fails = memory.get("spy_fails", {})
    lacking = [kd for kd in known if world.seconds_left(kd, category) <= window and fails.get(kd, 0) < SPY_FAILS]
    if not lacking:
        return []
    # Intel on an empire target is shared with the whole empire and earns points, so about half goes there.
    marked = [kd for kd in lacking if kd in world.marked_for("intel")]
    if marked and rng.random() < TARGET_SHARE:
        lacking = marked
    mine = max(world.me.get("drones") or 0, 1)
    leaders = world.leaders(3) if world.phase == "late" else []

    def promise(kd):
        stars, networth = known[kd]
        chance = strategy.spy_chance(mine, _guess_drones(world, kd, stars, memory), stars)
        if category == "military":
            # Stars to take for the least army: networth beyond land is mostly army.
            value = stars / (1 + strategy.military_networth(networth, stars) / 1000)
        else:
            value = networth
        grudge = 1 + 0.5 * memory.get("grudges", {}).get(kd, 0)
        leader = 3.0 if kd in leaders else 1.0
        return value * min(chance, 1.0) * grudge * leader * rng.uniform(0.8, 1.2)

    target = max(lacking, key=promise)
    stars, _ = known[target]
    share = rng.random() < personality.share_chance
    decision, chance = _spy_decision(world, personality, target, operation, stars, _guess_drones(world, target, stars, memory), rng,
                                     share, f"{operation} on {world.names[target]}")
    if chance < (MIN_SPY_CHANCE if want_military else 2 * MIN_SPY_CHANCE):
        return []  # not worth the spy attempt and the drones
    return [decision]


def accept_intel(world, personality, style, memory):
    """Buy what galaxymates list: military intel if the bot attacks kingdoms, anything if it runs drones on them."""
    wanted = set()
    if style.get("army") in ("players", "both"):
        wanted.add("military")
    if style.get("drones") in ("players", "both"):
        wanted.update(("kingdom", "drones", "shields"))
    if not wanted:
        return []
    outsiders = set(world.outsiders())
    decisions = []
    for listing in world.intel.get("listings") or []:
        target, category = listing["target"], listing["category"]
        if listing.get("problem") is None and category in wanted and target in outsiders and world.seconds_left(target, category) <= 0:
            if _utc(listing["time"]) > world.now + datetime.timedelta(seconds=2 * EPOCH):
                decisions.append(Decision("accept_intel", {"listing": listing["id"]},
                                          f"buy {category} intel on {world.names.get(target, target)}"))
        if len(decisions) >= 3:
            break
    return decisions


def _sendable(world, units_home, flex_share):
    return {"attack": units_home.get("attack", 0), "big_flex": units_home.get("big_flex", 0),
            "flex": math.floor(units_home.get("flex", 0) * flex_share)}


def _army_timeline(world):
    """``[(seconds from now, units at home then, generals at home then)]``: now, and after each general returns."""
    me = world.me
    units = {unit: me["units"].get(unit, 0) for unit in ("attack", "flex", "big_flex")}
    generals = me.get("generals_available", 0)
    timeline = [(0.0, dict(units), generals)]
    for general in sorted(me.get("generals_out", []), key=lambda g: _utc(g["return_time"])):
        for unit in units:
            units[unit] += general.get(unit, 0)
        generals += 1
        wait = max((_utc(general["return_time"]) - world.now).total_seconds(), 0.0)
        timeline.append((wait + 0.05 * EPOCH, dict(units), generals))
    return timeline


def _best_strike(world, personality, pool, known, leaders, timeline, max_wait, window, buffer, grudges, late, me):
    """
    ``(best, chip)`` among the kingdoms of ``pool``: the best strike the army can win (edge, target, wait, generals,
    offense, defense), and late in the round a leader worth wearing down (target, offense, defense, generals, wait).
    """
    best, chip = None, None
    for target in sorted(pool, key=lambda kd: -known.get(kd, (0, 0))[0])[:6]:
        info = world.target_info(target)
        if str(info.get("status", "")).lower() == "dead":
            continue
        defense = world.defense_of(target, info)
        if defense is None:
            continue
        stars = info.get("stars") or known.get(target, (0, 0))[0] or uas.GAME_CONFIG["BASE_ATTACK_MIN_STARS_GAIN"] * 10
        war, denounced = world.relation(target)
        need = defense * (1 + buffer / 100) + 1
        intel_left = world.seconds_left(target, "military")
        for wait, units, generals in timeline:
            if generals < 1 or wait > max_wait or wait + window > intel_left:
                continue
            count = min(generals, 4)
            offense = world.offense_with(_sendable(world, units, 1.0), count, target)
            if offense >= need:
                edge = strategy.player_edge(stars, need, world.epochs, me["race"], war)
                edge *= (1.3 if war or denounced else 1.0) * (1 + 0.1 * min(grudges.get(target, 0), 5))
                # Stars taken from a leader count twice in the race for points: once gained, once lost by a rival.
                edge *= 2.0 if target in leaders else 1.0
                edge /= 1 + wait / (24 * EPOCH)  # an army held back is an army not at the primitives
                if best is None or edge > best[0]:
                    best = (edge, target, wait, count, offense, defense)
                break
        else:
            # Not beatable. Late, a leader within reach is still worth weakening.
            if late and target in leaders:
                reachable = [entry for entry in timeline
                             if entry[2] >= 1 and entry[0] <= max_wait and entry[0] + window <= intel_left]
                if reachable:
                    wait, units, generals = reachable[-1]  # when the most of the army is home
                    offense = world.offense_with(_sendable(world, units, 0.5), min(generals, 4), target)
                    if offense >= personality.chip_ratio * defense and (chip is None or defense < chip[2]):
                        chip = (target, offense, defense, min(generals, 4), wait)
    return best, chip


def plan_attack(world, personality, style, memory, rng):
    """
    A strike on a kingdom, if one pays. Of the kingdoms the bot has military intel on, find those its army can beat
    (now, or once generals on their way home are back) with the buffer it asks for, and value each by how many times
    more stars it gives than the same offense sent at primitives; enemies at war, grudges and (late) the leaders count
    for more. A bot that hits only kingdoms takes the best; one that hits both takes it only if it beats primitives.
    Late in the round, a bot may also send a losing attack at a leader to wear its defense down for the next one.
    With nothing to hit, it goes looking for military intel.
    """
    army_style = style.get("army", "none")
    late = world.phase == "late"
    if army_style not in ("players", "both") and not (late and army_style == "primitives"):
        return []
    strike = memory.get("strike")
    if strike and _utc(strike["time"]) > world.now:
        return []  # one at a time
    me = world.me
    if strategy.raw_offense(strategy.all_units(me)) <= 0:
        return []
    buffer = _between(rng, personality.attack_buffer) + memory.get("buffer_extra", 0.0)
    window = EPOCH  # the intel must outlast the wait
    candidates = world.revealed_with("military", at_least=window)
    known = world.known_stars()
    leaders = world.leaders(3) if late else []
    timeline = _army_timeline(world)
    # Late in the round the whole army may be gathered for one strike; before that, a bot that also farms primitives
    # only waits a little.
    max_wait = (personality.strike_wait if army_style == "both" and not late else 24.0) * EPOCH
    grudges = memory.get("grudges", {})

    # About half the strikes go to the empire's targets marked for attacks, if one can be beaten: it earns points on
    # top of the spoils, so it is taken whatever primitives would give.
    marked = [kd for kd in candidates if kd in world.marked_for("successful_attacks")]
    focus = bool(marked) and rng.random() < TARGET_SHARE
    for pool in ([marked, candidates] if focus else [candidates]):
        best, chip = _best_strike(world, personality, pool, known, leaders, timeline, max_wait, window, buffer,
                                  grudges, late, me)
        if best:
            break
    on_target = focus and best is not None and best[1] in marked

    threshold = 0.0 if army_style == "players" or on_target else personality.player_edge
    if best and best[0] >= threshold and (army_style in ("players", "both") or on_target):
        edge, target, wait, count, offense, defense = best
        return [Decision("attack", {
            "target": target, "generals": count, "prefer_autofill": True, "autofill_buffer": buffer,
            # Only used if the intel has gone by the time it runs, and then nothing is sent.
            "pure_offense": 0, "flex_offense": 0,
        }, f"attack {world.names[target]}: {offense:,.0f} offense vs {defense:,.0f} defense with a {buffer:.0f}% buffer, "
           f"{edge:.1f}x what primitives would give" + (f", in {wait / EPOCH:.1f} epochs" if wait else ""),
            at=wait + rng.uniform(0.05, 0.3) * EPOCH)]
    if chip and rng.random() < personality.chip_chance:
        target, offense, defense, count, wait = chip
        return [Decision("attack", {
            "target": target, "generals": count, "prefer_autofill": False, "autofill_buffer": 0,
            "pure_offense": 100, "flex_offense": 50,
        }, f"wear down {world.names[target]}: {offense:,.0f} offense into {defense:,.0f} defense, to lose and cost them units",
            at=wait + rng.uniform(0.05, 0.3) * EPOCH)]
    if army_style in ("players", "both"):
        return plan_intel(world, personality, style, memory, rng, want_military=True)
    return []


def plan_drones(world, personality, style, memory, rng):
    """
    Aggressive spying. A siphon, when one on a kingdom the bot knows would bring in more than the same spy attempt
    robbing primitives (it does more and more as primitives are robbed bare); and late in the round, sabotage on a
    leader: burn its fuel if that would run it dry, else kidnap, bomb homes or wreck fuel plants.
    """
    me = world.me
    drones = me.get("drones") or 0
    drone_style = style.get("drones", "primitives")
    attempts = _attempts_free(world, memory)
    if drones < 500 or attempts < 1:
        return []
    decisions = []
    known = world.known_stars()
    vult = me["race"] == "Vult"

    def chance_against(kd, sent):
        stars = known[kd][0]
        shields = 0.0
        if not vult and world.seconds_left(kd, "shields") > 0:
            shields = world.target_info(kd).get("shields", {}).get("spy", 0.0)
        return strategy.spy_chance(sent, _guess_drones(world, kd, stars, memory), stars, shields)

    def learned_chance(kd, forecast):
        # What the spies have seen of a target counts with what the forecast says: one that keeps catching them (a
        # kingdom with more drones than its stars suggest, say) is tried less and less.
        ok, tried = memory.get("siphon_record", {}).get(kd, (0.0, 0.0))
        return (forecast * SIPHON_PRIOR + ok) / (SIPHON_PRIOR + tried)

    # About half the sabotage goes to the empire's targets marked for it, when the chance is fair.
    operations = {"kidnap": "kidnappopulation", "bomb_homes": "bombhomes", "sabotage_fuel_plants": "sabotagefuelplants"}
    targeted = False
    marked = [kd for kd in world.marked_for(*operations) if kd in known]
    if marked and rng.random() < TARGET_SHARE:
        target = rng.choice(marked)
        if chance_against(target, drones * 0.6) >= 0.2:
            chosen = rng.choice([operation for action, operation in operations.items() if action in world.empire_targets[target]])
            decisions.append(Decision("aggressivespy", {
                "target": target, "operation": chosen, "attempts": min(2, attempts), "drones_pct": 60.0, "shielded": False,
            }, f"{chosen} against the empire target {world.names[target]}"))
            targeted = True

    # Sabotage a leader.
    if not targeted and rng.random() < _by_phase(personality.sabotage_chance, world.phase):
        leaders = [kd for kd in world.leaders(3) if kd in known]
        if leaders:
            target = rng.choice(leaders)
            info = world.target_info(target) if world.seconds_left(target, "kingdom") > 0 else {}
            fuel = info.get("fuel")
            burn = drones * 0.5 * uas.GAME_CONFIG["BASE_DRONES_SUICIDE_FUEL_DAMAGE"]
            # Burning fuel is teamwork: one kingdom's drones rarely empty a leader's tanks, a galaxy's do. So a bot
            # joins in when its own half would be a real share of what is left.
            if fuel is not None and world.phase == "late" and 0 < fuel <= burn * SUICIDE_TEAM:
                percent = min(fuel / uas.GAME_CONFIG["BASE_DRONES_SUICIDE_FUEL_DAMAGE"] / drones * 100 * 1.1, 50.0)
                decisions.append(Decision("aggressivespy", {
                    "target": target, "operation": "suicidedrones", "attempts": 1, "drones_pct": round(max(percent, 1.0), 1),
                    "shielded": False,
                }, f"burn the fuel of {world.names[target]} ({fuel:,.0f} left): without fuel its shields drop and its army weakens"))
            else:
                chance = chance_against(target, drones * 0.6)
                if chance >= 0.2:
                    operation = rng.choice(personality.sabotage_ops)
                    decisions.append(Decision("aggressivespy", {
                        "target": target, "operation": operation, "attempts": min(2, attempts), "drones_pct": 60.0,
                        "shielded": False,
                    }, f"{operation} against the leader {world.names[target]} ({chance:.0%} a try)"))

    # Siphons instead of robs. A siphon is worth 8 money for every drone sent, a rob a few (fewer as primitives are
    # robbed bare), and the drones come home either way, so every spy attempt a siphon beats a rob for goes to a
    # siphon: one per kingdom, the best first, as many as there are attempts to spare.
    if drone_style in ("players", "both") and rng.random() < personality.aggressive_chance:
        rob = drones * personality.rob_share * strategy.rob_per_drone(world.epochs)
        running = memory.setdefault("siphons", {})
        for kd in [kd for kd, until in running.items() if _utc(until) <= world.now]:
            del running[kd]
        options = []
        for kd, (stars, _networth) in known.items():
            if kd in running or memory.get("spy_fails", {}).get(kd, 0) >= SPY_FAILS:
                continue
            # The richer the target the more there is to take: income from its structures if they are revealed.
            revealed = world.seconds_left(kd, "structures") > 0 or world.seconds_left(kd, "kingdom") > 0
            income = strategy.income_from_intel(world.target_info(kd) if revealed else {}, stars)
            # No more drones than the siphon can use, or (SIPHON_ALL_DRONES) all of them: the guess at the target's
            # income may be low, and more drones make the siphon likelier to work.
            useful = strategy.siphon_take(10 ** 12, income) / uas.GAME_CONFIG["BASE_DRONES_SIPHON_PER_DRONE"]
            sent = drones if SIPHON_ALL_DRONES else min(drones, useful)
            chance = learned_chance(kd, chance_against(kd, sent))
            options.append((chance * strategy.siphon_take(sent, income), kd, sent, chance))
        threshold = rob * personality.siphon_edge if drone_style == "both" else 0.0
        spare = max(attempts - len(decisions) - 1, 1)
        # Siphons on one kingdom are held to its 15%, and a new one cuts the oldest for good, so thieves that all pick
        # the best target take from each other. Spread them: each pick is drawn in proportion to what it is worth,
        # among those worth more than robbing.
        worth = sorted((option for option in options if option[0] > threshold and option[3] >= 0.2), reverse=True)
        memory["siphon_options"] = len(worth)
        if len(options) < SIPHON_REVEAL_BELOW:
            # Siphons need kingdoms to see: one attempt shows a whole galaxy for longer than a siphon runs.
            hidden = [galaxy for galaxy in world.galaxies if galaxy != world.my_galaxy
                      and galaxy not in world.revealed_info.get("galaxies", {})
                      and world.empires[2].get(galaxy, -1) != world.my_empire]
            if hidden:
                decisions.append(Decision("reveal_galaxy", {}, f"reveal a galaxy: only {len(options)} kingdoms to siphon"))
                spare -= 1
        picked = []
        while worth and len(picked) < min(spare, MAX_SIPHONS_PER_THINK):
            weights = [option[0] ** SIPHON_SHARPNESS for option in worth]
            draw = rng.random() * sum(weights) if SIPHON_PICK == "spread" else 0.0
            index = 0
            while index < len(worth) - 1 and draw > weights[index]:
                draw -= weights[index]
                index += 1
            picked.append(worth.pop(index))
        for value, target, sent, chance in picked:
            decisions.append(Decision("aggressivespy", {
                "target": target, "operation": "siphonfunds", "attempts": 1,
                "drones_pct": round(min(max(sent / drones * 100, 1.0), 100.0), 1), "shielded": False,
            }, f"siphon {world.names[target]}: worth about {value:,.0f} against {rob:,.0f} from robbing primitives "
               f"({chance:.0%} to work)"))
        if not known and not any(d.kind == "reveal_galaxy" for d in decisions):
            decisions.extend(plan_intel(world, personality, style, memory, rng, want_military=False))
    return decisions


def _silo_capacity(me):
    return math.floor(me["structures"].get("missile_silos", 0)) * math.floor(uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"] * (
        1 + (uas.GAME_CONFIG["FUZI_MISSILE_SILO_CAPACITY_INCREASE"] if me["race"] == "Fuzi" else 0)))


def plan_missiles(world, personality, style, memory, rng):
    """
    Bombers fill their silos with the best missile they have unlocked and can pay for, and once enough are stocked fire
    them at whoever hit them, or at the leader. Anybody who finds itself holding missiles fires them too.
    """
    me = world.me
    decisions = []
    stock = {kind: count for kind, count in (me.get("missiles") or {}).items() if count > 0}
    capacity = _silo_capacity(me)
    if style.get("bomber") and capacity > 0 and not _recent(memory, "missiles_ordered", world.now, 24):
        kinds = [kind for kind in ("galaxy_busters", "star_busters") if kind in me.get("completed_projects", [])] + ["planet_busters"]
        discount = uag._missile_cost_modifier(me, world.modifiers)
        money, fuel = me["money"] * 0.9, max(me["fuel"] - 0.3 * me["structures"].get("fuel_plants", 0) * uas.GAME_CONFIG["BASE_FUEL_PLANTS_CAPACITY"], 0)
        order = {}
        for kind in kinds:
            room = capacity - me["missiles"].get(kind, 0)
            cost, fuel_cost = uas.MISSILES[kind]["cost"] * discount, uas.MISSILES[kind]["fuel_cost"] * discount
            count = int(min(room, money // cost, fuel // fuel_cost))
            if count > 0:
                order[kind] = count
                money -= count * cost
                fuel -= count * fuel_cost
        if order:
            decisions.append(Decision("build_missiles", order, "fill the silos: " + ", ".join(f"{n} {k}" for k, n in order.items())))

    held = sum(stock.values())
    if held >= max(1, capacity * personality.missiles_stock) or (held and world.epochs_left < 30):
        grudges = memory.get("grudges", {})
        outsiders = set(world.outsiders())
        targets = [kd for kd in sorted(grudges, key=grudges.get, reverse=True) if kd in outsiders][:1] or world.leaders(1)
        marked = [kd for kd in world.marked_for("missiles") if kd in outsiders]
        if marked and rng.random() < TARGET_SHARE:
            targets = [rng.choice(marked)]
        if targets:
            share = _between(rng, personality.missiles_share)
            options = {kind: int(math.ceil(stock.get(kind, 0) * share)) for kind in ("planet_busters", "star_busters", "galaxy_busters")}
            if sum(options.values()) >= 1:
                decisions.append(Decision("missiles", {"target": targets[0], **options},
                                          f"missiles at {world.names[targets[0]]}"))
    return decisions


def learn(world, personality, style, memory):
    """
    What the last hours taught. A strike that failed widens the buffer the bot asks for (one that worked narrows it
    again); a kingdom that has stopped growing is marked stalled, which makes it settle harder and send its army at
    primitives whatever its style. Returns notes for the log.
    """
    notes = []
    strike = memory.get("strike")
    if strike and _utc(strike["time"]) <= world.now:
        since = strike.get("planned", "")
        results = [entry for entry in world.attack_history if entry.get("to") == strike["target"] and (not since or (entry.get("time") and _utc(entry["time"]) >= _utc(since)))]
        if results:
            won = str(results[-1].get("news", "")).startswith("Success")
            extra = memory.get("buffer_extra", 0.0)
            memory["buffer_extra"] = round(max(extra - 1.0, 0.0) if won else min(extra + 4.0, 20.0), 1)
            if not won and not strike.get("chip"):
                notes.append(f"the attack on {world.names.get(strike['target'], strike['target'])} failed: asking {memory['buffer_extra']:.0f}% more offense from now on")
        memory.pop("strike", None)
    # Intel operations that have run: the intel is there, or it is not. A target that beats the spies several times
    # in a row is left alone for a while.
    fails = memory.setdefault("spy_fails", {})
    spying = memory.setdefault("spying", {})
    for target in list(spying):
        if _utc(spying[target]["due"]) > world.now:
            continue
        if world.seconds_left(target, spying[target]["category"]) > 0:
            fails.pop(target, None)
        else:
            fails[target] = fails.get(target, 0) + 1
            if fails[target] == SPY_FAILS:
                memory["spy_fails_at"] = world.now.isoformat()
                notes.append(f"spies keep failing on {world.names.get(target, target)}: leaving it alone for a while")
        del spying[target]
    if fails and memory.get("spy_fails_at") and not _recent(memory, "spy_fails_at", world.now, SPY_FORGET_EPOCHS):
        fails.clear()
        memory.pop("spy_fails_at", None)
    if style.get("drones") in ("players", "both") and memory.get("siphons"):
        note_siphons(world, memory)
    stalled = note_growth(world, memory)
    if stalled != memory.get("stalled", False):
        memory["stalled"] = stalled
        notes.append("stopped growing: settling harder and sending the army at primitives" if stalled else "growing again")
    return notes


def note_siphons(world, memory):
    """Count how the siphons the bot has sent went, per target, the older ones counting less."""
    seen = memory.get("siphons_seen", "")
    record = memory.setdefault("siphon_record", {})
    fresh = [entry for entry in world.spy_history
             if entry.get("operation") == "Siphon Funds" and uas.is_after(entry.get("time", ""), seen) and entry.get("to")]
    for entry in fresh:
        ok, tried = record.get(entry["to"], (0.0, 0.0))
        won = not str(entry.get("news", "")).startswith("Failure")
        record[entry["to"]] = [round(ok * SIPHON_MEMORY + won, 3), round(tried * SIPHON_MEMORY + 1, 3)]
    if fresh:
        memory["siphons_seen"] = max((entry["time"] for entry in fresh), key=_utc)


def note_threat(world, memory):
    """
    The strongest offense the bot knows an outsider has, from the military intel revealed to it (its own, and what it
    accepted from galaxymates), remembered for a while after the intel runs out. Returns it, or 0.
    """
    strongest, who = 0.0, None
    known = world.known_stars()
    for kd in sorted(world.revealed_with("military"), key=lambda k: -known.get(k, (0, 0))[1])[:3]:
        info = world.target_info(kd)
        units = dict(info.get("units") or {})
        for general in info.get("generals_out") or []:
            for unit, count in general.items():
                if unit in uas.UNITS:
                    units[unit] = units.get(unit, 0) + count
        offense = uag._calc_max_offense(
            {unit: count for unit, count in units.items() if unit in uas.UNITS},
            military_bonus=uas.PROJECTS["military_bonus"]["max_bonus"], other_bonuses=0,
            generals=max(int(info.get("generals_available", 0)) + len(info.get("generals_out") or []), 1),
            lumina=info.get("race") == "Lumina", war=world.relation(kd)[0])
        if offense > strongest:
            strongest, who = float(offense), kd
    old = memory.get("threat")
    if old and not _recent({"at": old.get("at")}, "at", world.now, THREAT_EPOCHS):
        old = None
    if who is not None and (not old or strongest >= old["offense"]):
        memory["threat"] = {"offense": round(strongest), "from": who, "at": world.now.isoformat()}
        return strongest
    if not old:
        memory.pop("threat", None)
        return 0.0
    return float(old["offense"])


def plan(world, personality, style, memory, rng):
    """Everything the bot wants to do this think: ``(settings, decisions, notes)``."""
    notes = react(world, memory) + learn(world, personality, style, memory)
    settings, why = plan_economy(world, personality, style, memory)
    notes.append(why)

    decisions = []
    decisions.extend(plan_survival(world, memory))
    decisions.extend(spend_money(world, personality, style, memory, settings))
    decisions.extend(plan_politics(world, personality, style, memory, rng))
    decisions.extend(accept_intel(world, personality, style, memory))

    pending = len(world.me.get("schedule", []))
    room = max(min(personality.max_pending - pending, SCHEDULE_LIMIT - pending, personality.max_new), 0)
    acting = []
    for rule in (plan_attack, plan_drones, plan_missiles, plan_intel):
        if rule is plan_intel and any(d.kind in ("intelspy", "reveal_galaxy") for d in acting):
            continue  # the attack rule already asked for intel
        acting.extend(rule(world, personality, style, memory, rng))
    scheduled = [d for d in acting if d.kind in _SCHEDULERS][:room]
    decisions.extend(d for d in acting if d.kind not in _SCHEDULERS)
    decisions.extend(scheduled)

    if any(d.kind == "attack" for d in scheduled):
        settings["auto_attack_enabled"] = False  # the army waits at home for the strike

    # Spy attempts the scheduled operations will need are kept back from the auto rob.
    needed = sum(d.options.get("max_tries", d.options.get("attempts", 1)) for d in scheduled if d.kind in ("intelspy", "aggressivespy"))
    keep = min(needed + (1 if personality.intel_chance >= 0.5 else 0), 8)
    if style.get("drones") in ("players", "both") and memory.get("siphon_options"):
        # A siphon is worth more than a rob, so with kingdoms worth siphoning the attempts wait for the next think
        # instead of going to the auto rob as soon as they come back.
        keep = max(keep, SIPHON_KEEP_ATTEMPTS)
    memory["keep_attempts"] = int(keep)
    if "auto_rob_settings" in settings:
        settings["auto_rob_settings"]["keep"] = memory["keep_attempts"]

    # Spread the actions over the coming interval so bots (and one bot's own actions) do not land together. A strike
    # runs when its army is home.
    interval = personality.think_epochs[0] * EPOCH
    for decision in scheduled:
        decision.delay = decision.at if decision.at is not None else rng.uniform(EPOCH * 0.05, interval)
    # The schedule refuses a time outside the round.
    game_end = world.game_end
    decisions = [d for d in decisions if d.kind not in _SCHEDULERS or world.now + datetime.timedelta(seconds=d.delay) < game_end]
    return settings, decisions, notes


# --------------------------------------------------------------------------------------------------- carrying it out

# The same handlers the Schedule page's route uses. They take percents the way the form sends them (and scale them
# down), so the options in a Decision are in percent.
_SCHEDULERS = {
    "attack": uac._schedule_attack,
    "attackprimitives": uac._schedule_attackprimitives,
    "intelspy": uac._schedule_intelspy,
    "aggressivespy": uac._schedule_aggressivespy,
    "missiles": uac._schedule_missiles,
}


def next_think_time(personality, rng, now):
    low, high = personality.think_epochs
    return now + datetime.timedelta(seconds=rng.uniform(low, high) * EPOCH)


def first_think_time(personality, rng, now):
    """When a new bot first thinks: somewhere in its first interval, so a hundred new bots are spread out."""
    return now + datetime.timedelta(seconds=rng.uniform(0, personality.think_epochs[0] * EPOCH))


def _log_entry(now, kind, why, outcome):
    return {"time": now.isoformat(), "kind": kind, "why": why, "outcome": outcome}


def _answer(result):
    payload, status = result
    if status in (200, 201):
        return "done"
    return f"refused: {payload.get('message') if isinstance(payload, dict) else payload}"


def _buy_structures(kd_id, money, target):
    """Structures for ``money``, on the empty stars, towards the target shares."""
    kingdom = uag._get_kd_info(kd_id)
    info = uag._get_structures_info(kd_id, kingdom)
    count = int(min(info["max_available_structures"], min(money, kingdom["money"]) // max(info["price"], 1)))
    if count < 1 or not target:
        return {"message": "nothing to build"}, 400
    stars = max(kingdom["stars"], 1)
    have = {key: info["current"].get(key, 0) + info["queued"].get(key, 0) for key in uas.STRUCTURES}
    gaps = {key: max(target.get(key, 0) - have[key] / stars, 0) for key in uas.STRUCTURES}
    total = sum(gaps.values())
    if total <= 0:
        return {"message": "nothing to build"}, 400
    request = {key: math.floor(count * gap / total) for key, gap in gaps.items() if gap > 0}
    request = {key: value for key, value in request.items() if value > 0}
    if not request:
        return {"message": "nothing to build"}, 400
    return uab._build_structures(kd_id, request)


def _buy_settle(kd_id, money):
    kingdom = uag._get_kd_info(kd_id)
    info = uag._get_settle(kd_id, kingdom)
    count = int(min(info["max_available_settle"], min(money, kingdom["money"]) // max(info["settle_price"], 1)))
    if count < 1:
        return {"message": "nothing to settle"}, 400
    return uab._settle(kd_id, count)


def _buy_engineers(kd_id, money):
    kingdom = uag._get_kd_info(kd_id)
    info = uag._get_engineers(kd_id, kingdom)
    count = int(min(info["max_available_engineers"], min(money, kingdom["money"]) // info["engineers_price"]))
    if count < 1:
        return {"message": "no room for engineers"}, 400
    return uab._train_engineers(kd_id, count)


def _do(kd_id, world, decision):
    """Carry out one on-the-spot decision through the function its route uses. Returns the outcome for the log."""
    kind, options = decision.kind, decision.options
    try:
        if kind == "vote_galaxy":
            uap.cast_galaxy_vote(kd_id, world.my_galaxy, options["policy"], options["option"])
            return "voted"
        if kind == "vote_universe":
            return _answer(uap.cast_universe_votes(kd_id, options["policy"], options["option"], options["votes"]))
        if kind == "vote_leader":
            return _answer(uap.cast_leader_vote(kd_id, options["selected"]))
        if kind == "buy_votes":
            return _answer(uap.buy_universe_votes(kd_id, options["votes"]))
        if kind == "empire_found":
            return _answer(uap.found_empire(kd_id, options["name"]))
        if kind == "empire_join":
            return _answer(uap.ask_to_join_empire(kd_id, options["empire"]))
        if kind == "empire_withdraw":
            return _answer(uap.withdraw_join_request(kd_id, options["empire"]))
        if kind == "empire_accept_invite":
            return _answer(uap.join_invited_empire(kd_id, options["empire"]))
        if kind == "empire_admit":
            return _answer(uap.admit_galaxy_to_empire(kd_id, options["galaxy"]))
        if kind == "empire_invite":
            return _answer(uap.invite_galaxy_to_empire(kd_id, options["galaxy"]))
        if kind == "empire_denounce":
            return _answer(uap.denounce_empire(kd_id, options["empire"]))
        if kind == "empire_war":
            return _answer(uap.declare_war_on(kd_id, options["empire"]))
        if kind == "reveal_galaxy":
            return _answer(uac._reveal_random_galaxy(kd_id))
        if kind == "accept_intel":
            return _answer(uai._buy(kd_id, options["listing"]))
        if kind == "build_missiles":
            return _answer(uab._build_missiles(kd_id, dict(options)))
        if kind == "disband":
            return _answer(uab._disband(kd_id, dict(options)))
        if kind == "buy_settle":
            return _answer(_buy_settle(kd_id, options["money"]))
        if kind == "buy_structures":
            return _answer(_buy_structures(kd_id, options["money"], options.get("target")))
        if kind == "buy_engineers":
            return _answer(_buy_engineers(kd_id, options["money"]))
        return "unknown"
    except (occ.Busy, occ.Rejected, KeyError, ValueError, TypeError, RuntimeError) as problem:
        return f"failed: {problem!r}"


def _write(kd_id, settings, scheduled, personality, style, memory, rng, now, log_extra, phase_name):
    """The settings, the new schedule entries, the bot's memory and its next think, in one write."""
    refused = []

    def decide(kd_info):
        refused.clear()
        schedule = list(kd_info["schedule"])
        entries = []
        new_memory = copy.deepcopy(memory)
        for decision in scheduled:
            if len(schedule) >= SCHEDULE_LIMIT:
                refused.append((decision, "schedule full"))
                continue
            when = (now + datetime.timedelta(seconds=decision.delay)).isoformat()
            ok, entry, message = _SCHEDULERS[decision.kind](
                id=str(uuid.uuid4()), time=when, options=copy.deepcopy(decision.options), kd_info=kd_info)
            if ok:
                schedule.append(entry)
                entries.append(_log_entry(now, decision.kind, decision.why, f"scheduled for {when}"))
                if decision.kind == "attack":
                    new_memory["strike"] = {"target": decision.options["target"], "time": when, "planned": now.isoformat(),
                                            "chip": not decision.options.get("prefer_autofill")}
                if decision.kind == "intelspy":
                    new_memory.setdefault("spying", {})[decision.options["target"]] = {
                        "category": decision.options["operation"].replace("spy", ""),
                        "due": (now + datetime.timedelta(seconds=decision.delay + 0.1 * EPOCH)).isoformat()}
                if decision.kind == "aggressivespy" and decision.options.get("operation") == "siphonfunds":
                    until = now + datetime.timedelta(
                        seconds=decision.delay + EPOCH * uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"])
                    new_memory.setdefault("siphons", {})[decision.options["target"]] = until.isoformat()
            else:
                refused.append((decision, message))
        schedule.sort(key=lambda item: _utc(item["time"]))
        bot = dict(kd_info.get("bot", {}))
        bot["next_think"] = next_think_time(personality, rng, now).isoformat()
        bot["style"] = style
        bot["phase"] = phase_name
        bot["memory"] = new_memory
        bot["reserved_generals"] = 0
        counts = dict(bot.get("counts", {}))
        for entry in log_extra + entries:
            if entry["kind"] != "plan":
                done = entry["outcome"] in ("done", "voted") or entry["outcome"].startswith("scheduled")
                key = entry["kind"] if done else f"{entry['kind']} refused"
                counts[key] = counts.get(key, 0) + 1
        bot["counts"] = counts
        bot["log"] = (bot.get("log", []) + log_extra + entries
                      + [_log_entry(now, d.kind, d.why, f"not scheduled: {m}") for d, m in refused])[-LOG_SIZE:]
        payload = {"schedule": schedule, "bot": bot}
        for field, value in settings.items():
            if field == "shields" and kd_info["fuel"] <= 0:
                continue  # as the Shields page: no fuel, no shields
            if field == "projects_assigned" and sum(value.values()) > kd_info["units"]["engineers"]:
                continue
            payload[field] = value
        if settings.get("auto_spending_enabled") and not kd_info.get("auto_spending_enabled"):
            next_resolve = kd_info["next_resolve"]
            next_resolve["auto_spending"] = (now + datetime.timedelta(
                seconds=EPOCH * uas.GAME_CONFIG["BASE_AUTO_SPENDING_TIME_MULTIPLIER"])).isoformat()
            payload["next_resolve"] = next_resolve
        return payload, None

    occ.update(f'/kingdom/{kd_id}', decide)


def think(kd_id, now=None, rng=None, state=None, me=None):
    """
    One think for one bot: look, decide, act. Returns the decisions. Does nothing for a kingdom that is not a bot or
    is dead. Safe to call at any time; ``maybe_think`` is the one the refresh uses.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    rng = rng or random.Random()
    me = me if me is not None else uag._get_kd_info(kd_id)
    bot = me.get("bot")
    if not bot or str(me.get("status", "")).lower() == "dead":
        return []
    personality = PERSONALITIES[bot["type"]]
    style = _style(bot, personality)
    memory = copy.deepcopy(bot.get("memory") or {})

    world = World(kd_id, me, now, state=state)
    settings, decisions, notes = plan(world, personality, style, memory, rng)

    log = [_log_entry(now, "plan", note, "") for note in notes if note][-3:]
    bought = []
    for decision in decisions:
        if decision.kind in _SCHEDULERS:
            continue
        outcome = _do(kd_id, world, decision)
        if decision.kind == "build_missiles" and outcome == "done":
            memory["missiles_ordered"] = now.isoformat()
        if decision.kind.startswith("buy_") and decision.kind != "buy_votes":
            bought.append(outcome == "done")
            if outcome != "done":
                continue  # nothing to buy is not news
        log.append(_log_entry(now, decision.kind, decision.why, outcome))
    if bought and not any(bought):
        memory["nothing_to_buy"] = now.isoformat()  # no room anywhere: do not ask again for a while
    _write(kd_id, settings, [d for d in decisions if d.kind in _SCHEDULERS], personality, style, memory, rng, now, log,
           world.phase)
    return decisions


def maybe_think(kd_info, now, state=None):
    """Called by the refresh for every kingdom: thinks if this is a bot whose time has come. Never raises."""
    bot = kd_info.get("bot")
    if not bot or str(kd_info.get("status", "")).lower() == "dead":
        return False
    try:
        if _utc(bot["next_think"]) > now:
            return False
        think(kd_info["kdId"], now=now, state=state, me=kd_info)
        return True
    except Exception:
        flask.current_app.logger.exception("Bot %s failed to think", kd_info.get("kdId"))
        return False
