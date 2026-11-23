"""
The advisors: short, plain-English advice on the Status page about what in a kingdom may need fixing, each with links
to where it is fixed (docs/advisors.md, issue #185).

Each advice is a **check**, a plain function of a ``Context`` (the caller's own kingdom and the few shared facts the
route reads once) that returns an ``Advice`` or ``None``. No Flask and no storage in the checks, so they are tested with
plain inputs and the bot simulator can run them on every bot. Thresholds come from the game's formulas in
``shared.py`` and the sums the bots use (``botstrategy.py``), never from numbers copied here.

Kinds, in the order the card shows them:

* ``danger``: something is hurting the kingdom now. Can not be hidden.
* ``waste``: money, land or people doing nothing.
* ``team``: something the galaxy, cluster, empire or universe is waiting on.

A player can hide any advice that is not ``danger``, for good (it is stored in their preferences, so it stays hidden
in later rounds), and turn the advisors off in Settings.
"""
import dataclasses
import datetime
import math

import flask
import flask_praetorian

import untitledapp.botstrategy as strategy
import untitledapp.galaxypolicies as uagp
import untitledapp.getters as uag
import untitledapp.preferences as uapr
import untitledapp.shared as uas
from untitledapp import alive_required

bp = flask.Blueprint("advisors", __name__)

KINDS = ("danger", "waste", "team", "peer")
HIDEABLE_KINDS = ("waste", "team", "peer")

# Fuel that runs out within this many hours is worth a warning: a player who logs in twice a day (tenet 1) would
# otherwise find it gone before they are back.
FUEL_WARNING_HOURS = 12


@dataclasses.dataclass
class Advice:
    id: str
    kind: str
    text: str
    links: list  # [(label, path)], where the fix is made

    def view(self, hidden=False):
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "links": [{"label": label, "to": to} for label, to in self.links],
            "hideable": self.kind in HIDEABLE_KINDS,
            "hidden": hidden,
        }


@dataclasses.dataclass
class Context:
    """What the checks may look at: the caller's own kingdom, and facts about the round. Nothing about another
    kingdom that the caller could not see."""
    kd: dict
    now: datetime.datetime
    epochs: float               # epochs since the round started
    max_hangar: float           # hangar space the kingdom has
    used_hangar: float          # hangar space its units take, those in training included
    home_defense: float         # the defense an attacker would face now, by the rules an attack uses
    at_war: bool = False        # the kingdom's empire is at war
    epochs_left: float = 0.0    # until the round ends
    progress: float = 0.0       # how far through the round, 0 to 1
    structures_queued: float = 0
    # Team: the galaxy's politics as the kingdom sees them on the Galaxy politics page.
    galaxy_votes_missing: list = dataclasses.field(default_factory=list)  # "leader" and/or "policies" not voted for
    galaxy_policies_active: int = None  # options in force in the galaxy now; None without a galaxy
    is_leader: bool = False     # the galaxy's leader
    cluster_voted: bool = True  # the galaxy has a cluster vote in (only looked up for the leader)
    in_empire: bool = True
    election_ends: datetime.datetime = None  # when the universe election that is open closes; None if none is open
    cast_universe_votes: bool = True         # the kingdom has votes in the open election
    war_targets: int = 0        # targets its empire has marked, while at war
    # Peer comparisons: the kingdom's own measures, and the universe's ranges (both empty when there are none).
    peer: dict = dataclasses.field(default_factory=dict)
    peer_ranges: dict = dataclasses.field(default_factory=dict)


def _hours(epochs):
    return epochs * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] / 3600


def _number(value):
    return f"{math.floor(value):,}"


def _percent(share):
    return f"{round(share * 100)}%"


# ------------------------------------------------------------------------------------------------------------ danger

def out_of_fuel(ctx):
    if ctx.kd.get("fuel", 0) > 0:
        return None
    config = uas.GAME_CONFIG
    return Advice(
        "out_of_fuel", "danger",
        f"Your kingdom is out of fuel. Until it has fuel again your army is {_percent(config['BASE_FUELLESS_STRENGTH_REDUCTION'])} "
        f"weaker, your shields are off, your homes hold {_percent(config['BASE_FUELLESS_POP_CAP_REDUCTION'])} fewer people "
        "and your population barely grows. Build fuel plants, or use less fuel.",
        [("Build fuel plants", "/structures"), ("Shields", "/shields")],
    )


def fuel_running_out(ctx):
    fuel = ctx.kd.get("fuel", 0)
    net = ((ctx.kd.get("income") or {}).get("fuel") or {}).get("net") or 0
    if fuel <= 0 or net >= 0:
        return None
    hours_left = _hours(fuel / -net)
    if hours_left > FUEL_WARNING_HOURS:
        return None
    when = "within the hour" if hours_left < 1 else f"in about {math.floor(hours_left)} hours"
    return Advice(
        "fuel_running_out", "danger",
        f"Your fuel runs out {when}: you use more than your fuel plants make. Without fuel your army is weaker and your "
        "shields switch off. Build fuel plants, or lower your shields.",
        [("Build fuel plants", "/structures"), ("Shields", "/shields")],
    )


# Each unit without a hangar takes the room of one person in the homes (refresh._calc_pop_change_per_epoch), so any
# overflow costs people; past this share of the hangars' room (units in training counted, as the game counts them) it
# is worth a warning. A hair over, while the next hangars are being built, is not.
HANGAR_WARNING_SHARE = 1.02
# Defense under this share of the break-even line. Bots aim at about the line (explorers on purpose, bots.md) and sit a
# little under it without being hunted; well under it, a kingdom is clearly the better target.
DEFENSE_WARNING_SHARE = 0.9


def hangars_full(ctx):
    overflow = ctx.used_hangar - ctx.max_hangar
    if overflow <= 0 or ctx.used_hangar <= ctx.max_hangar * HANGAR_WARNING_SHARE:
        return None
    return Advice(
        "hangars_full", "danger",
        f"Your units, with those in training, need {_number(ctx.used_hangar)} hangar space and your hangars hold "
        f"{_number(ctx.max_hangar)}. The {_number(overflow)} without a hangar take that much room from your homes, so "
        "your population shrinks. Build hangars.",
        [("Build hangars", "/structures"), ("Military", "/military")],
    )


def defense_under_break_even(ctx):
    """Below the line, hitting the kingdom pays an attacker more than sending the same army at primitives (bots.md,
    "what the simulations say", 2). The warning starts at DEFENSE_WARNING_SHARE of it; the text gives the full line."""
    stars = ctx.kd.get("stars", 0)
    if stars <= 0:
        return None
    line = stars * strategy.break_even_per_star(ctx.epochs, war=ctx.at_war)
    if ctx.home_defense >= line * DEFENSE_WARNING_SHARE:
        return None
    war = " Your empire is at war, which makes you worth more to its enemies." if ctx.at_war else ""
    return Advice(
        "defense_under_break_even", "danger",
        f"Your defense at home is {_number(ctx.home_defense)} right now, with the bonuses and shields you have, low "
        "enough that attacking you pays better than attacking "
        f"primitives.{war} At least {_number(line)} would make you the worse target. Train defense, or keep more "
        "units at home.",
        [("Train units", "/military"), ("Spending", "/automation?tab=spending")],
    )


# ------------------------------------------------------------------------------------------------------------- waste

# A twentieth of the land with nothing on it and nothing on order is worth a word; a few stars waiting for the next
# build are not. Nor is land the auto builder will build on (after a big attack, the new stars arrive empty).
EMPTY_STARS_SHARE = 0.05
EMPTY_STARS_MIN = 10
# Money and funding unspent for more than this many epochs of income. Well-run bots keep about two epochs' worth idle
# (bots.md, "what the simulations say", 3).
IDLE_MONEY_EPOCHS = 6


def _auto_builds_structures(kd):
    """Auto spending is on, funds structures, and has structures to aim for: it will build on empty land."""
    return bool(kd.get("auto_spending_enabled") and (kd.get("auto_spending") or {}).get("structures", 0) > 0
                and sum((kd.get("structures_target") or {}).values()) > 0)


def empty_stars(ctx):
    stars = ctx.kd.get("stars", 0)
    empty = stars - sum((ctx.kd.get("structures") or {}).values()) - ctx.structures_queued
    if empty < max(stars * EMPTY_STARS_SHARE, EMPTY_STARS_MIN) or _auto_builds_structures(ctx.kd):
        return None
    return Advice(
        "empty_stars", "waste",
        f"{_number(empty)} of your stars have nothing built on them and nothing on order. An empty star earns nothing: "
        "build on it, or set structure targets so auto spending does.",
        [("Build structures", "/structures"), ("Spending", "/automation?tab=spending")],
    )


def idle_money(ctx):
    income = ((ctx.kd.get("income") or {}).get("money") or {}).get("net") or 0
    if income <= 0:
        return None
    idle = max(ctx.kd.get("money", 0), 0) + sum((ctx.kd.get("funding") or {}).values())
    if idle / income <= IDLE_MONEY_EPOCHS:
        return None
    hours = _hours(idle / income)
    return Advice(
        "idle_money", "waste",
        f"You have {_number(idle)} money waiting to be spent, about {math.floor(hours)} hours of income. Money earns "
        "nothing until it becomes stars, structures or units. Spend it, or let auto spending do it.",
        [("Build", "/build"), ("Spending", "/automation?tab=spending")],
    )


def auto_spending_without_targets(ctx):
    kd = ctx.kd
    if not kd.get("auto_spending_enabled"):
        return None
    shares = kd.get("auto_spending") or {}
    missing = []
    if shares.get("structures", 0) > 0 and sum((kd.get("structures_target") or {}).values()) <= 0:
        missing.append("structures")
    if shares.get("military", 0) > 0 and sum((kd.get("units_target") or {}).values()) <= 0:
        missing.append("units")
    if not missing:
        return None
    what = " or ".join(missing)
    return Advice(
        "auto_spending_without_targets", "waste",
        f"Auto spending puts money aside for {what} but has no {what} to aim for, so that money builds nothing. Set "
        "your targets.",
        [("Targets", "/automation?tab=spending")],
    )


def engineers_idle(ctx):
    kd = ctx.kd
    if kd.get("auto_assign_projects", True):
        return None
    engineers = (kd.get("units") or {}).get("engineers", 0)
    idle = engineers - sum((kd.get("projects_assigned") or {}).values())
    if idle <= 0:
        return None
    return Advice(
        "engineers_idle", "waste",
        f"{_number(idle)} of your engineers {'is' if idle == 1 else 'are'} not working on a project. Assign them, or "
        "let them be assigned automatically.",
        [("Projects", "/projects")],
    )


# An army counts as one for attacking when at least this share of its units are pure attackers. A kingdom of flex units
# (offense and defense both) or of defenders keeps them home on purpose.
ATTACKERS_SHARE = 0.05


def _attacker_army(units):
    combat = sum(count for unit, count in units.items() if unit in uas.UNITS and unit not in ("recruits", "engineers"))
    attackers = sum(units.get(unit, 0) for unit in uas.PURE_ATTACK_UNITS)
    return attackers > 0 and attackers >= combat * ATTACKERS_SHARE


def generals_idle(ctx):
    """Primitives are a fifth to a third of a kingdom's stars in the simulations (bots.md, "what the simulations say",
    1): an army that never goes out leaves them to others."""
    kd = ctx.kd
    if kd.get("generals_out") or kd.get("auto_attack_enabled"):
        return None
    if any(str(entry.get("type", "")).startswith("attack") for entry in kd.get("schedule") or []):
        return None
    if not _attacker_army(kd.get("units") or {}):
        return None
    return Advice(
        "generals_idle", "waste",
        "All your generals are at home and nothing will send them out. Attacking primitives brings stars: turn on "
        "auto attack, or send or schedule an attack.",
        [("Primitives", "/primitives"), ("Auto attack", "/automation")],
    )


def spy_attempts_full(ctx):
    kd = ctx.kd
    if kd.get("auto_rob_enabled") or kd.get("spy_attempts", 0) < uas.GAME_CONFIG["BASE_SPY_ATTEMPTS_MAX"]:
        return None
    return Advice(
        "spy_attempts_full", "waste",
        "Your spy attempts are full, so the new ones you earn are lost. Use them: rob primitives, spy on a kingdom, "
        "or turn on auto rob.",
        [("Spy", "/spy"), ("Auto rob", "/automation")],
    )


# -------------------------------------------------------------------------------------------------------------- team

def galaxy_votes_missing(ctx):
    missing = ctx.galaxy_votes_missing
    if not missing:
        return None
    what = "a galaxy leader" if missing == ["leader"] else "your galaxy's leader and policies" if "leader" in missing \
        else "all of your galaxy's policies"
    return Advice(
        "galaxy_votes_missing", "team",
        f"You have not voted for {what}. Your galaxy is your team: its leader speaks for it, and its policies help "
        "every kingdom in it.",
        [("Galaxy politics", "/galaxypolitics")],
    )


def galaxy_without_policies(ctx):
    if ctx.galaxy_policies_active is None or ctx.galaxy_policies_active > 0:
        return None
    return Advice(
        "galaxy_without_policies", "team",
        "Your galaxy has no policies in force. Each one helps every kingdom in the galaxy; agree on them with your "
        "galaxymates and vote.",
        [("Galaxy politics", "/galaxypolitics"), ("Galaxy board", "/message?tab=board")],
    )


def cluster_vote_missing(ctx):
    if not ctx.is_leader or ctx.cluster_voted:
        return None
    return Advice(
        "cluster_vote_missing", "team",
        "As your galaxy's leader you cast its vote for a cluster benefit, and it has none. Every kingdom in the "
        "cluster gets the benefits voted for.",
        [("Cluster politics", "/clusterpolitics")],
    )


def galaxy_without_empire(ctx):
    if not ctx.is_leader or ctx.in_empire or ctx.progress < strategy.EARLY_UNTIL:
        return None
    return Advice(
        "galaxy_without_empire", "team",
        "Your galaxy is in no empire. Empires go to war together and share their targets' spoils; as leader you can "
        "found one, or ask to join one.",
        [("Empire politics", "/empirepolitics")],
    )


def universe_election_open(ctx):
    if ctx.election_ends is None or ctx.cast_universe_votes:
        return None
    hours = max((ctx.election_ends - ctx.now).total_seconds() / 3600, 0)
    when = "within the hour" if hours < 1 else f"in about {math.floor(hours)} hours"
    return Advice(
        "universe_election_open", "team",
        f"A universe election is open and closes {when}; you have not voted. Votes are bought with money, and the "
        "result changes the rules for every kingdom.",
        [("Universe politics", "/universepolitics")],
    )


def empire_war_targets(ctx):
    if not ctx.at_war or ctx.war_targets <= 0:
        return None
    count = "a target" if ctx.war_targets == 1 else f"{ctx.war_targets} targets"
    return Advice(
        "empire_war_targets", "team",
        f"Your empire is at war and has marked {count}. Attacks, spying and missiles on a target earn you points "
        "and a share of its spoils.",
        [("Empire targets", "/empirepolitics")],
    )


CHECKS = [
    out_of_fuel,
    fuel_running_out,
    hangars_full,
    defense_under_break_even,
    empty_stars,
    idle_money,
    auto_spending_without_targets,
    engineers_idle,
    generals_idle,
    spy_attempts_full,
    empire_war_targets,
    universe_election_open,
    cluster_vote_missing,
    galaxy_without_empire,
    galaxy_votes_missing,
    galaxy_without_policies,
]

# Every advice id there is, and its kind, so the hide route can refuse anything else.
IDS = {
    "out_of_fuel": "danger",
    "fuel_running_out": "danger",
    "hangars_full": "danger",
    "defense_under_break_even": "danger",
    "empty_stars": "waste",
    "idle_money": "waste",
    "auto_spending_without_targets": "waste",
    "engineers_idle": "waste",
    "generals_idle": "waste",
    "spy_attempts_full": "waste",
    "empire_war_targets": "team",
    "universe_election_open": "team",
    "cluster_vote_missing": "team",
    "galaxy_without_empire": "team",
    "galaxy_votes_missing": "team",
    "galaxy_without_policies": "team",
}


# -------------------------------------------------------------------------------------------------------------- peer
# How a kingdom compares with everyone else in the universe, bots included (docs/advisors.md, "Peer comparisons").
# Once per history mark the refresh works out, over every live kingdom, the PEER_LOW percentile and the median of each
# measure (``peer_ranges``) and keeps them in the ``universe_stats`` document, which no route sends. The advice only ever
# says "almost every kingdom...": never a figure, so it tells a player nothing about how defended anybody else is.

PEER_LOW = 0.1           # "almost every kingdom": nine in ten have more
PEER_MIN_KINGDOMS = 10   # fewer, and a comparison says too much about too few
PEER_GAP = 0.75          # also under this share of the median: a kingdom a little below the rest is not worth a word


def home_defense(kd):
    """The defense an attacker would face at home now, by the rules an attack uses."""
    return uag._calc_max_defense(
        {key: value for key, value in kd["units"].items() if key in uas.UNITS},
        military_bonus=uas.project_bonuses(kd)["military_bonus"],
        other_bonuses=0,
        shields=kd.get("shields", {}).get("military", 0),
        fuelless=kd.get("fuel", 0) <= 0,
        gaian=kd.get("race") == "Gaian",
    )


def _bonuses_filled(kd):
    """How full the continuous project bonuses are, on average, from 0 to 1."""
    points, maxes = kd.get("projects_points") or {}, kd.get("projects_max_points") or {}
    shares = [min(points.get(key, 0) / max(maxes.get(key, 0), 1e-9), 1.0) for key in strategy.CONTINUOUS_PROJECTS]
    return sum(shares) / max(len(shares), 1)


def peer_measures(kd):
    """The measures a kingdom is compared on, each per star or a share, so kingdoms of any size compare."""
    stars = max(kd.get("stars", 0), 1)
    income = ((kd.get("income") or {}).get("money") or {}).get("net") or 0
    return {
        "income_per_star": income / stars,
        "defense_per_star": home_defense(kd) / stars,
        "offense_per_star": strategy.raw_offense(strategy.all_units(kd)) / stars,
        "drones_per_star": kd.get("drones", 0) / stars,
        "bonuses_filled": _bonuses_filled(kd),
    }


def _percentile(ordered, share):
    position = (len(ordered) - 1) * share
    below = math.floor(position)
    above = min(below + 1, len(ordered) - 1)
    return ordered[below] + (ordered[above] - ordered[below]) * (position - below)


def peer_ranges(kingdoms):
    """Over every live, set-up kingdom: each measure's ``low`` (PEER_LOW percentile) and ``median``, and ``n``.
    Empty with fewer than PEER_MIN_KINGDOMS. Plain function: the refresh passes the kingdoms it already holds."""
    rows = []
    for kd in kingdoms:
        if not kd or not kd.get("race") or str(kd.get("status", "")).lower() == "dead":
            continue
        try:
            rows.append(peer_measures(kd))
        except (KeyError, TypeError, ValueError):
            continue  # one odd kingdom must not stop the comparison for everyone
    if len(rows) < PEER_MIN_KINGDOMS:
        return {}
    ranges = {}
    for name in rows[0]:
        ordered = sorted(row[name] for row in rows)
        ranges[name] = {"low": _percentile(ordered, PEER_LOW), "median": _percentile(ordered, 0.5), "n": len(rows)}
    return ranges


# measure: (advice id, text, links). Only the low side: having more of any of these than most is a choice, not a risk.
PEER_ADVICE = {
    "income_per_star": (
        "peer_income_low",
        "Almost every kingdom earns more per star than yours. Income comes from mines and from people in homes: look "
        "at what your land holds, and keep your fuel up.",
        [("Structures", "/structures"), ("Spending", "/automation?tab=spending")],
    ),
    "defense_per_star": (
        "peer_defense_low",
        "Almost every kingdom keeps more defense per star at home than yours, which makes you one of the easier "
        "kingdoms to attack.",
        [("Train units", "/military"), ("Spending", "/automation?tab=spending")],
    ),
    "offense_per_star": (
        "peer_offense_low",
        "Almost every kingdom has more offense per star than yours. Offense takes stars from primitives and other "
        "kingdoms; without it your land comes only from settling.",
        [("Train units", "/military"), ("Primitives", "/primitives")],
    ),
    "drones_per_star": (
        "peer_drones_low",
        "Almost every kingdom has more drones per star than yours, so spying on you, robbing you and siphoning your "
        "income is easier than on most. Drone factories make drones.",
        [("Build drone factories", "/structures")],
    ),
    "bonuses_filled": (
        "peer_bonuses_low",
        "Almost every kingdom has fuller project bonuses than yours. Engineers fill them, and the bonuses add to your "
        "income, people and army.",
        [("Projects", "/projects")],
    ),
}


def _peer_check(measure):
    advice_id, text, links = PEER_ADVICE[measure]

    def check(ctx):
        spread = (ctx.peer_ranges or {}).get(measure)
        if not spread or measure not in (ctx.peer or {}):
            return None
        value = ctx.peer[measure]
        if value >= spread["low"] or value >= spread["median"] * PEER_GAP:
            return None
        return Advice(advice_id, "peer", text, links)

    check.__name__ = advice_id
    return check


PEER_CHECKS = [_peer_check(measure) for measure in PEER_ADVICE]
CHECKS.extend(PEER_CHECKS)
IDS.update({advice_id: "peer" for advice_id, _, _ in PEER_ADVICE.values()})


def advise(ctx, checks=None):
    """Every advice that applies, most serious kind first, then in the order of ``checks`` (``CHECKS`` by default)."""
    found = [advice for advice in (check(ctx) for check in (CHECKS if checks is None else checks)) if advice is not None]
    return sorted(found, key=lambda advice: KINDS.index(advice.kind))


def context_for(kd, state, mobis_queue, empires_inverted, empires, now=None, structures_queue=(),
                galaxy_id=None, galaxy_votes=None, cluster=None, universe_votes=None, targets=None, peer_ranges=None):
    """The context for ``kd``, from documents the route has read. ``cluster`` (the cluster document) is only needed
    for a galaxy leader, ``universe_votes`` while an election is open, ``targets`` (the empire's targets document)
    while its empire is at war: the route reads each only then. ``peer_ranges`` is the scores document's."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    game_start, game_end = uas.utc(state["state"]["game_start"]), uas.utc(state["state"]["game_end"])
    epochs = strategy.epochs_since(now, game_start)
    units = uag._calc_units(now, kd["units"], kd.get("generals_out", []), mobis_queue)
    max_hangar, used_hangar = uag._calc_hangar_capacity(kd, units)
    kd_id = str(kd.get("kdId"))
    empire = empires_inverted.get(kd_id)
    at_war = bool(empire and empires.get(empire, {}).get("war"))
    missing, active_count = [], None
    if galaxy_votes is not None:
        # The galaxy's policies as the tally has them now, for the policies this round plays (galaxypolicies.py).
        policies = uagp.round_policies(state["state"])
        galaxy = uagp.advance(galaxy_votes, policies, game_start, now)
        if kd_id not in ((galaxy_votes.get("votes") or {}).get("leader") or {}):
            missing.append("leader")
        if policies and all(kd_id not in galaxy["votes"].get(policy, {}) for policy in policies):
            missing.append("policies")
        active_count = len(galaxy["active"])
    galaxy_votes = galaxy_votes or {}
    is_leader = galaxy_votes.get("leader") == kd_id
    election_ends = election_open(state, now)
    cast = True
    if election_ends is not None:
        cast = any(kd_id in voters for options in (universe_votes or {}).get("votes", {}).values()
                   for voters in options.values())
    return Context(
        kd=kd, now=now, epochs=epochs, max_hangar=max_hangar, used_hangar=used_hangar, home_defense=home_defense(kd),
        peer=peer_measures(kd) if peer_ranges else {},
        peer_ranges=peer_ranges or {},
        at_war=at_war,
        epochs_left=max((game_end - now).total_seconds(), 0) / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"],
        progress=strategy.round_progress(now, game_start, game_end),
        structures_queued=uag._queue_total(structures_queue),
        galaxy_votes_missing=missing,
        galaxy_policies_active=active_count,
        is_leader=is_leader,
        cluster_voted=not is_leader or galaxy_id in ((cluster or {}).get("votes") or {}),
        in_empire=empire is not None,
        election_ends=election_ends,
        cast_universe_votes=cast,
        war_targets=len((targets or {}).get("targets") or {}) if at_war else 0,
    )


def election_open(state, now):
    """When the universe election that is open now closes, or None."""
    end = state["state"].get("election_end") or ""
    if end == "" or now >= uas.utc(end):
        return None
    return uas.utc(end)


def _peer_ranges_stored():
    """The comparison the refresh keeps in ``universe_stats``; none if it is missing (so no peer advice)."""
    return uag._get_universe_stats().get("peer_ranges") or {}


@bp.route("/api/advisors")
@flask_praetorian.auth_required
@alive_required
def get_advisors():
    """``{"enabled", "advice"}``: the caller's advice, most serious first, the hidden ones flagged ``hidden``. Nothing
    while the advisors are switched off, before the round starts, or without a kingdom."""
    import untitledapp.clusters as uacl  # clusters imports getters, which imports more; keep the import here
    import untitledapp.occ as occ

    user = flask_praetorian.current_user()
    preferences = uapr.read(user.id)
    if preferences["advisors"] == "off":
        return flask.jsonify({"enabled": False, "advice": []}), 200
    kd_id = user.kd_id
    state = uag._get_state()
    now = datetime.datetime.now(datetime.timezone.utc)
    if kd_id is None or now < uas.utc(state["state"]["game_start"]):
        return flask.jsonify({"enabled": True, "advice": []}), 200
    kd = uag._get_kd_info(kd_id)
    if not kd.get("race"):  # never set up
        return flask.jsonify({"enabled": True, "advice": []}), 200
    empires_inverted, empire_infos, _, galaxy_info = uag._get_empires_inverted()
    empires = empire_infos["empires"]
    galaxy_id = next((galaxy for galaxy, members in galaxy_info.items() if str(kd_id) in members), None)
    galaxy_votes = uag._get_galaxy_politics(kd_id, galaxy_id)[0] if galaxy_id else {}
    # The rest only when a check could use it.
    cluster = (uag._get_cluster_document(uacl.cluster_of(galaxy_id))
               if galaxy_id and galaxy_votes.get("leader") == str(kd_id) else None)
    universe_votes = uag._get_universe_politics() if election_open(state, now) else None
    empire = empires_inverted.get(str(kd_id))
    targets = (occ.read(f"/empire/{empire}/targets")
               if empire and empires.get(empire, {}).get("war") and empires[empire].get("targets") else None)
    ctx = context_for(
        kd, state, uag._get_mobis_queue(kd_id), empires_inverted, empires, now,
        structures_queue=uag._get_structures_queue(kd_id),
        galaxy_id=galaxy_id, galaxy_votes=galaxy_votes, cluster=cluster, universe_votes=universe_votes,
        targets=targets, peer_ranges=_peer_ranges_stored(),
    )
    hidden = set(preferences["hidden_advice"])
    advice = [item.view(hidden=item.id in hidden and item.kind in HIDEABLE_KINDS) for item in advise(ctx)]
    return flask.jsonify({"enabled": True, "advice": advice}), 200


@bp.route("/api/advisors/hide", methods=["POST"])
@flask_praetorian.auth_required
def hide_advice():
    """Body: ``{"id": <advice id>, "hidden": true|false}``. Hides an advice for good, or shows it again."""
    req = flask.request.get_json(force=True, silent=True)
    if not isinstance(req, dict) or not isinstance(req.get("hidden"), bool):
        return flask.jsonify({"message": "Say whether to hide the advice"}), 400
    advice_id = req.get("id")
    if advice_id not in IDS:
        return flask.jsonify({"message": "There is no such advice"}), 400
    if IDS[advice_id] not in HIDEABLE_KINDS:
        return flask.jsonify({"message": "Warnings about danger to your kingdom can not be hidden"}), 400
    if not uapr.set_advice_hidden(flask_praetorian.current_user().id, advice_id, req["hidden"]):
        return flask.jsonify({"message": "Your advisors could not be updated. Try again."}), 503
    message = "Advice hidden" if req["hidden"] else "Advice shown again"
    return flask.jsonify({"message": message, "status": "success"}), 200
