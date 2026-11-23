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
import untitledapp.getters as uag
import untitledapp.preferences as uapr
import untitledapp.shared as uas
from untitledapp import alive_required

bp = flask.Blueprint("advisors", __name__)

KINDS = ("danger", "waste", "team")
HIDEABLE_KINDS = ("waste", "team")

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
    settles_queued: float = 0
    expansionist: bool = False  # the galaxy's Expansionist policy (cheaper settling)
    # Team: the galaxy's politics as the kingdom sees them on the Galaxy politics page.
    galaxy_votes: dict = dataclasses.field(default_factory=dict)
    is_leader: bool = False     # the galaxy's leader
    cluster_voted: bool = True  # the galaxy has a cluster vote in (only looked up for the leader)
    in_empire: bool = True
    election_ends: datetime.datetime = None  # when the universe election that is open closes; None if none is open
    cast_universe_votes: bool = True         # the kingdom has votes in the open election
    war_targets: int = 0        # targets its empire has marked, while at war


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


def hangars_full(ctx):
    if ctx.used_hangar <= ctx.max_hangar:
        return None
    return Advice(
        "hangars_full", "danger",
        f"Your units, with those in training, need {_number(ctx.used_hangar)} hangar space and your hangars hold "
        f"{_number(ctx.max_hangar)}. Units without a hangar take room in your homes, so your population shrinks. "
        "Build hangars.",
        [("Build hangars", "/structures"), ("Military", "/military")],
    )


def defense_under_break_even(ctx):
    """Below this line, hitting the kingdom pays an attacker more than sending the same army at primitives (bots.md,
    "what the simulations say", 2: bots that dropped to it were hunted at once)."""
    stars = ctx.kd.get("stars", 0)
    if stars <= 0:
        return None
    line = stars * strategy.break_even_per_star(ctx.epochs, war=ctx.at_war)
    if ctx.home_defense >= line:
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
# build are not.
EMPTY_STARS_SHARE = 0.05
EMPTY_STARS_MIN = 10
# Money and funding unspent for more than this many hours of income. Well-run bots keep about one hour's worth idle
# (bots.md, "what the simulations say", 3); twelve leaves room for saving up, and matches twice-a-day logins.
IDLE_MONEY_HOURS = 12
# Settling counts as slow under this share of the most the queue may hold (BASE_MAX_SETTLE_CAP of the stars).
SETTLE_SLOW_SHARE = 0.5
# Unassigned engineers worth a word: this share of them, and at least this many.
IDLE_ENGINEERS_SHARE = 0.05
IDLE_ENGINEERS_MIN = 10


def empty_stars(ctx):
    stars = ctx.kd.get("stars", 0)
    empty = stars - sum((ctx.kd.get("structures") or {}).values()) - ctx.structures_queued
    if empty < max(stars * EMPTY_STARS_SHARE, EMPTY_STARS_MIN):
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
    hours = _hours(idle / income)
    if hours <= IDLE_MONEY_HOURS:
        return None
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


def settling_slowly(ctx):
    """Settling is where most of a kingdom's stars come from (bots.md, "what the simulations say", 1), and
    ``settle_worth`` says whether a star still pays for itself before the round ends."""
    kd = ctx.kd
    stars = kd.get("stars", 0)
    if stars <= 0 or not kd.get("race"):
        return None
    cap = uas.GAME_FUNCS["BASE_MAX_SETTLE"](stars)
    if ctx.settles_queued >= cap * SETTLE_SLOW_SHARE:
        return None
    income = ((kd.get("income") or {}).get("money") or {}).get("net") or 0
    worth = strategy.settle_worth(kd, ctx.epochs_left, ctx.expansionist, income / stars if income > 0 else None)
    if worth <= 1:
        return None
    return Advice(
        "settling_slowly", "waste",
        f"You are settling {_number(ctx.settles_queued)} stars, and could have {_number(cap)} on the way. A new star "
        "still pays for itself before the round ends, and settling is where most kingdoms get most of their land.",
        [("Settle", "/settle"), ("Spending", "/automation?tab=spending")],
    )


def engineers_idle(ctx):
    kd = ctx.kd
    if kd.get("auto_assign_projects", True):
        return None
    engineers = (kd.get("units") or {}).get("engineers", 0)
    idle = engineers - sum((kd.get("projects_assigned") or {}).values())
    if idle < max(engineers * IDLE_ENGINEERS_SHARE, IDLE_ENGINEERS_MIN):
        return None
    return Advice(
        "engineers_idle", "waste",
        f"{_number(idle)} of your engineers are not working on a project. Assign them, or let them be assigned "
        "automatically.",
        [("Projects", "/projects")],
    )


def generals_idle(ctx):
    """Primitives are a fifth to a third of a kingdom's stars in the simulations (bots.md, "what the simulations say",
    1): an army that never goes out leaves them to others."""
    kd = ctx.kd
    if kd.get("generals_out") or kd.get("auto_attack_enabled"):
        return None
    if any(str(entry.get("type", "")).startswith("attack") for entry in kd.get("schedule") or []):
        return None
    if strategy.raw_offense(kd.get("units") or {}) <= 0:
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
    votes = ctx.galaxy_votes.get("votes") or {}
    kd_id = str(ctx.kd.get("kdId"))
    missing = [kind for kind in ("leader", "policy_1", "policy_2") if kd_id not in (votes.get(kind) or {})]
    if not missing:
        return None
    what = "a galaxy leader" if missing == ["leader"] else "your galaxy's leader and policies" if "leader" in missing \
        else "your galaxy's policies"
    return Advice(
        "galaxy_votes_missing", "team",
        f"You have not voted for {what}. Your galaxy is your team: its leader speaks for it, and its policies help "
        "every kingdom in it.",
        [("Galaxy politics", "/galaxypolitics")],
    )


def galaxy_without_policies(ctx):
    if not ctx.galaxy_votes or ctx.galaxy_votes.get("active_policies"):
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
    settling_slowly,
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
    "settling_slowly": "waste",
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


def advise(ctx, checks=None):
    """Every advice that applies, most serious kind first, then in the order of ``checks`` (``CHECKS`` by default)."""
    found = [advice for advice in (check(ctx) for check in (CHECKS if checks is None else checks)) if advice is not None]
    return sorted(found, key=lambda advice: KINDS.index(advice.kind))


def context_for(kd, state, mobis_queue, empires_inverted, empires, now=None, structures_queue=(), settles_queue=(),
                galaxy_id=None, galaxy_votes=None, cluster=None, universe_votes=None, targets=None):
    """The context for ``kd``, from documents the route has read. ``cluster`` (the cluster document) is only needed
    for a galaxy leader, ``universe_votes`` while an election is open, ``targets`` (the empire's targets document)
    while its empire is at war: the route reads each only then."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    game_start, game_end = uas.utc(state["state"]["game_start"]), uas.utc(state["state"]["game_end"])
    epochs = strategy.epochs_since(now, game_start)
    units = uag._calc_units(now, kd["units"], kd.get("generals_out", []), mobis_queue)
    max_hangar, used_hangar = uag._calc_hangar_capacity(kd, units)
    home_defense = uag._calc_max_defense(
        {key: value for key, value in kd["units"].items() if key in uas.UNITS},
        military_bonus=uas.project_bonuses(kd)["military_bonus"],
        other_bonuses=0,
        shields=kd.get("shields", {}).get("military", 0),
        fuelless=kd.get("fuel", 0) <= 0,
        gaian=kd.get("race") == "Gaian",
    )
    kd_id = str(kd.get("kdId"))
    empire = empires_inverted.get(kd_id)
    at_war = bool(empire and empires.get(empire, {}).get("war"))
    galaxy_votes = galaxy_votes or {}
    is_leader = galaxy_votes.get("leader") == kd_id
    election_ends = election_open(state, now)
    cast = True
    if election_ends is not None:
        cast = any(kd_id in voters for options in (universe_votes or {}).get("votes", {}).values()
                   for voters in options.values())
    return Context(
        kd=kd, now=now, epochs=epochs, max_hangar=max_hangar, used_hangar=used_hangar, home_defense=home_defense,
        at_war=at_war,
        epochs_left=max((game_end - now).total_seconds(), 0) / uas.GAME_CONFIG["BASE_EPOCH_SECONDS"],
        progress=strategy.round_progress(now, game_start, game_end),
        structures_queued=uag._queue_total(structures_queue),
        settles_queued=uag._queue_total(settles_queue),
        expansionist="Expansionist" in (galaxy_votes.get("active_policies") or []),
        galaxy_votes=galaxy_votes,
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
        structures_queue=uag._get_structures_queue(kd_id), settles_queue=uag._get_settle_queue(kd_id),
        galaxy_id=galaxy_id, galaxy_votes=galaxy_votes, cluster=cluster, universe_votes=universe_votes,
        targets=targets,
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
