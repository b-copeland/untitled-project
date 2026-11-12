"""
The bot brain (issue #76, second half): the part of a bot that *decides*.

``bots.py`` sets a bot kingdom up and the game's auto builder then builds, settles and trains for it. This module makes
it act on other kingdoms: attack, spy, reveal and share intel, rob, launch missiles, vote. The strategy comes from the
in-game guide and help pages, and is written as a few small rules per action:

* **Know before you hit.** Never attack without military intel. If nothing with intel is beatable, send spies for it
  first (the guide: "gather Military intel on the target prior to attempting an attack").
* **Hit what you can beat, near the top.** Of the targets the bot can beat with the buffer it asks for, prefer the one
  with the most stars (a successful attack takes a share of the target's stars), with a little noise.
* **Keep a home guard.** Only some generals go out and only some of the army, so a bot is not wide open while away.
* **Share what you learn.** Intel bots offer what their spies reveal to their galaxy, the others now and then.
* **Spy attempts are a resource**: thieves keep back what their auto rob needs, and nobody spends its last.
* **Vote for the playstyle**: each archetype has the galaxy and universe policies that suit it.

How it acts, and why it does not all happen at once (BEN COMMENT in docs/bots.md): the brain never calls an action
directly. Every ``think`` it **queues scheduled actions** on the bot's own kingdom, the same schedule a player fills in on
the Schedule page, at times spread at random over the coming interval. The refresh then runs them when they fall due,
through the same functions the routes use. So bots do different things at different moments, and the check that an
attack is still winnable happens when it is sent, not when it was planned. The schedule holds ten, and the brain stays
well under that so it never crowds out a player-style use.

When a bot thinks is also randomised: each has its own ``next_think``, set at random when it is created and again,
within the personality's range, after every think. A hundred bots therefore think a few at a time, tick after tick.

Everything the brain looks at is what a player could see (names, galaxies, the intel the bot has revealed), never
another kingdom's hidden state. Every decision is logged on the bot (``bot["log"]``, the last ``LOG_SIZE``).

**All numbers are first guesses marked ``TUNE``.** ``problems(personality)`` checks them, ``tests/test_bot_brain.py``
runs it.
"""
import copy
import dataclasses
import datetime
import random
import uuid

import flask

import untitledapp.conquer as uac
import untitledapp.getters as uag
import untitledapp.misc as uam
import untitledapp.occ as occ
import untitledapp.politics as uap
import untitledapp.shared as uas

LOG_SIZE = 40
SCHEDULE_LIMIT = 10  # what the game allows
EPOCH = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]


@dataclasses.dataclass(frozen=True)
class Personality:
    """How one playstyle behaves. Times are in epochs (``BASE_EPOCH_SECONDS``, half an hour by default)."""
    # TUNE: how often it thinks, as a range in epochs; each gap is drawn at random from it.
    think_epochs: tuple = (1.0, 3.0)
    # TUNE: the most scheduled actions the brain adds in one think, and the most it lets sit in the schedule.
    max_new: int = 2
    max_pending: int = 4

    # TUNE: chance per think of trying each kind of action.
    attack_chance: float = 0.0
    intel_chance: float = 0.3
    aggressive_chance: float = 0.0
    missiles_chance: float = 0.0

    # TUNE: attacks. How much more offense than their defense it asks for, how many generals it sends, and the most of
    # its army it will have out at once.
    attack_buffer: tuple = (3.0, 12.0)     # percent
    attack_generals: tuple = (1, 2)
    attack_army_out: float = 0.5           # the most of each unit (fraction) away on generals at once

    # TUNE: intel. Which reveal operations it likes, the share of its drones to send, tries, and the chance that it
    # shares what it learns with its galaxy.
    intel_ops: tuple = ("spymilitary", "spykingdom", "spyshields")
    intel_drones: tuple = (20.0, 50.0)     # percent
    intel_tries: tuple = (2, 4)
    share_chance: float = 0.3
    # Spy attempts to leave unspent (the thief's auto rob uses its own).
    keep_spy_attempts: int = 2

    # TUNE: aggressive spying (thieves).
    aggressive_ops: tuple = ("siphonfunds",)
    aggressive_drones: tuple = (15.0, 35.0)
    aggressive_attempts: tuple = (1, 2)

    # TUNE: the share of its missiles it fires at once.
    missiles_share: tuple = (0.3, 0.6)

    # Politics: the option (as the vote route takes it) it votes for in each galaxy and universe policy.
    galaxy_votes: dict = dataclasses.field(default_factory=dict)
    universe_votes: dict = dataclasses.field(default_factory=dict)


PERSONALITIES = {
    "explorer": Personality(
        think_epochs=(2.0, 5.0),
        attack_chance=0.0, intel_chance=0.2, aggressive_chance=0.0,
        share_chance=0.5,
        galaxy_votes={"policy_1": "1", "policy_2": "2"},     # Expansionist, Conscription
        universe_votes={"policy_1": "2", "policy_2": "1"},    # Treatied (it defends), Free trade
    ),
    "attacker": Personality(
        think_epochs=(1.0, 3.0),
        attack_chance=0.75, intel_chance=0.5, missiles_chance=0.2,
        attack_buffer=(2.0, 10.0), attack_generals=(1, 3), attack_army_out=0.6,
        share_chance=0.2,
        galaxy_votes={"policy_1": "2", "policy_2": "2"},     # Warlike, Conscription
        universe_votes={"policy_1": "1", "policy_2": "1"},    # Unregulated, Free trade
    ),
    "intel": Personality(
        think_epochs=(1.0, 2.5),
        attack_chance=0.0, intel_chance=0.8, max_new=3, max_pending=6,
        intel_ops=("spymilitary", "spykingdom", "spyshields", "spystructures", "spyprojects", "spydrones"),
        intel_drones=(20.0, 45.0), share_chance=0.9, keep_spy_attempts=1,
        galaxy_votes={"policy_1": "1", "policy_2": "1"},     # Expansionist, Intelligence
        universe_votes={"policy_1": "2", "policy_2": "1"},
    ),
    "thief": Personality(
        think_epochs=(1.5, 4.0),
        attack_chance=0.0, intel_chance=0.4, aggressive_chance=0.5,
        share_chance=0.2, keep_spy_attempts=5,   # the auto rob keeps this many for itself
        galaxy_votes={"policy_1": "1", "policy_2": "1"},
        universe_votes={"policy_1": "2", "policy_2": "1"},
    ),
}


def problems(personality):
    """Everything wrong with a personality, as sentences. Empty if fine."""
    found = []
    for name in ("think_epochs", "attack_buffer", "attack_generals", "intel_drones", "intel_tries",
                 "aggressive_drones", "aggressive_attempts", "missiles_share"):
        low, high = getattr(personality, name)
        if low > high or low < 0:
            found.append(f"{name} must be a range from low to high, not {low}..{high}")
    for name in ("attack_chance", "intel_chance", "aggressive_chance", "missiles_chance", "share_chance",
                 "attack_army_out"):
        if not 0 <= getattr(personality, name) <= 1:
            found.append(f"{name} is a chance from 0 to 1")
    if personality.attack_generals[0] < 1 or personality.attack_generals[1] > 4:
        found.append("generals are 1 to 4")
    if personality.intel_tries[0] < 1 or personality.intel_tries[1] > 10:
        found.append("intel tries are 1 to 10")
    if personality.aggressive_attempts[0] < 1 or personality.aggressive_attempts[1] > 10:
        found.append("aggressive attempts are 1 to 10")
    if personality.max_pending > SCHEDULE_LIMIT - 2:
        found.append(f"max_pending must leave room in the schedule of {SCHEDULE_LIMIT}")
    for operation in personality.intel_ops:
        if operation not in uas.REVEAL_OPERATIONS:
            found.append(f"{operation} is not an intel operation")
    for operation in personality.aggressive_ops:
        if operation not in uas.AGGRO_OPERATIONS:
            found.append(f"{operation} is not an aggressive operation")
    for policy, option in personality.galaxy_votes.items():
        if option not in uas.GALAXY_POLICIES.get(policy, {}).get("options", {}):
            found.append(f"galaxy {policy} has no option {option}")
    for policy, option in personality.universe_votes.items():
        if option not in uas.UNIVERSE_POLICIES.get(policy, {}).get("options", {}):
            found.append(f"universe {policy} has no option {option}")
    return found


@dataclasses.dataclass
class Decision:
    """One thing the bot has decided to do. ``kind`` is a schedule type, or ``vote_galaxy`` / ``vote_universe``."""
    kind: str
    options: dict
    why: str
    delay: float = 0.0   # seconds from now


# ------------------------------------------------------------------------------------------------ what a bot can see

class World:
    """
    What a player would see from this kingdom, read once per think: names, galaxies, the intel that is revealed to it.
    The attack evaluator is a method so tests can stand in for it.
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

    @property
    def my_galaxy(self):
        return self.galaxy_of.get(self.kd_id)

    def outsiders(self):
        """Kingdoms in other galaxies, the only ones worth acting against."""
        return [kd for kd in self.names if kd != self.kd_id and self.galaxy_of.get(kd) != self.my_galaxy]

    def seconds_left(self, target, category):
        """How long ``category`` of ``target`` stays revealed to us, in seconds (0 if it is not)."""
        until = self.revealed.get(target, {}).get(category)
        if until is None:
            return 0.0
        until = datetime.datetime.fromisoformat(until).astimezone(datetime.timezone.utc)
        return max((until - self.now).total_seconds(), 0.0)

    def revealed_with(self, category, at_least=0.0):
        return [kd for kd in self.outsiders() if self.seconds_left(kd, category) > at_least]

    def target_info(self, target):
        """What we are allowed to know about ``target``."""
        return uag._get_max_kd_info(target, self.kd_id, self.revealed_info, galaxies_inverted=self.galaxy_of)

    def evaluate_attack(self, target, generals, buffer_percent):
        """Offense against defense for an attack on ``target`` that uses everything, as the Attack page's autofill does.
        Returns ``(offense, defense)`` or None if it can not be worked out."""
        payload, status = uac._autofill_attack({
            "defenderValues": {**{unit: 0 for unit in uas.UNITS}, "military_bonus": 25, "shields": 10},
            "buffer": buffer_percent,
            "generals": generals,
        }, self.kd_id, target)
        if status != 200 or "attacker_offense" not in payload:
            return None
        return payload["attacker_offense"], payload["defender_defense"]


# ------------------------------------------------------------------------------------------------------- the rules

def _between(rng, span):
    low, high = span
    return rng.uniform(low, high)


def _whole_between(rng, span):
    low, high = span
    return rng.randint(int(low), int(high))


def _spare_attempts(world, personality, wanted=1):
    return (world.me.get("spy_attempts") or 0) - personality.keep_spy_attempts >= wanted


def plan_attack(world, personality, rng):
    """Attack the best target the bot has intel to beat; else start getting the intel."""
    me = world.me
    if me.get("generals_available", 0) < 1 or rng.random() >= personality.attack_chance:
        return []
    offense_units = [unit for unit, count in me["units"].items() if count > 0 and uas.UNITS[unit].get("offense", 0) > 0]
    if not offense_units:
        return []
    generals = min(_whole_between(rng, personality.attack_generals), me["generals_available"])
    buffer = _between(rng, personality.attack_buffer)
    # The intel must outlast the wait before the action runs, with room to spare.
    window = personality.think_epochs[1] * EPOCH
    candidates = world.revealed_with("military", at_least=window + EPOCH)

    scored = []
    for target in rng.sample(candidates, min(len(candidates), 6)):
        info = world.target_info(target)
        if str(info.get("status", "")).lower() == "dead":
            continue
        result = world.evaluate_attack(target, generals, buffer)
        if result is None or result[0] <= result[1]:
            continue
        # More stars to take is better; a little noise so bots do not all pile onto one kingdom.
        scored.append(((info.get("stars") or info.get("networth") or 0) * rng.uniform(0.8, 1.2), target, result))
    if scored:
        _, target, (offense, defense) = max(scored, key=lambda item: item[0])
        return [Decision("attack", {
            "target": target, "generals": generals, "prefer_autofill": True, "autofill_buffer": buffer,
            # Only used if the intel has gone by the time it runs, and then nothing is sent.
            "pure_offense": 0, "flex_offense": 0,
        }, f"attack {world.names[target]}: {offense:,.0f} offense vs {defense:,.0f} defense with a {buffer:.0f}% buffer")]
    # Nothing beatable with intel: get military intel on somebody for next time.
    return plan_intel(world, personality, rng, force=True, military_only=True)


def plan_intel(world, personality, rng, force=False, military_only=False):
    """Send spies for intel on a kingdom it has none (or little) on, sharing it with the galaxy sometimes."""
    if not force and rng.random() >= personality.intel_chance:
        return []
    if not _spare_attempts(world, personality) or (world.me.get("drones") or 0) < 100:
        return []
    window = personality.think_epochs[1] * EPOCH
    operation = "spymilitary" if military_only else rng.choice(personality.intel_ops)
    # Somebody whose intel of this kind is missing or about to run out.
    lacking = [kd for kd in world.outsiders() if world.seconds_left(kd, _category(operation)) <= window + EPOCH]
    if not lacking:
        return []
    target = rng.choice(lacking)
    return [Decision("intelspy", {
        "target": target, "operation": operation,
        "drones_pct": _between(rng, personality.intel_drones),
        "max_tries": min(_whole_between(rng, personality.intel_tries), max(world.me["spy_attempts"] - personality.keep_spy_attempts, 1)),
        "shielded": False,
        "share_to_galaxy": rng.random() < personality.share_chance,
    }, f"{operation} on {world.names[target]}")]


def _category(operation):
    """The revealed category an operation fills in."""
    return {"spymilitary": "military", "spykingdom": "kingdom", "spyshields": "shields", "spyprojects": "projects",
            "spystructures": "structures", "spydrones": "drones"}[operation]


def plan_aggressive(world, personality, rng):
    """Thieves: siphon funds from the richest kingdom it has seen the money of."""
    if rng.random() >= personality.aggressive_chance:
        return []
    attempts = _whole_between(rng, personality.aggressive_attempts)
    if not _spare_attempts(world, personality, wanted=attempts) or (world.me.get("drones") or 0) < 100:
        return []
    window = personality.think_epochs[1] * EPOCH
    seen = world.revealed_with("kingdom", at_least=window)
    richest = []
    for target in seen:
        info = world.target_info(target)
        if str(info.get("status", "")).lower() != "dead" and info.get("money"):
            richest.append((info["money"], target))
    if not richest:
        # Nothing known about anybody's money: find out first.
        return plan_intel(world, dataclasses.replace(personality, intel_ops=("spykingdom",)), rng, force=True)
    _, target = max(richest)
    return [Decision("aggressivespy", {
        "target": target, "operation": rng.choice(personality.aggressive_ops), "attempts": attempts,
        "drones_pct": _between(rng, personality.aggressive_drones), "shielded": False,
    }, f"{personality.aggressive_ops[0]} against {world.names[target]}")]


def plan_missiles(world, personality, rng):
    """Fire some of the stock at the biggest kingdom it has intel on."""
    stock = {kind: count for kind, count in (world.me.get("missiles") or {}).items() if count > 0}
    if not stock or rng.random() >= personality.missiles_chance:
        return []
    window = personality.think_epochs[1] * EPOCH
    known = [(world.target_info(kd).get("stars") or 0, kd) for kd in world.revealed_with("kingdom", at_least=window)]
    known = [(stars, kd) for stars, kd in known if stars]
    if not known:
        return []
    _, target = max(known)
    share = _between(rng, personality.missiles_share)
    options = {kind: int(stock.get(kind, 0) * share) for kind in ("planet_busters", "star_busters", "galaxy_busters")}
    if sum(options.values()) < 1:
        return []
    return [Decision("missiles", {"target": target, **options}, f"missiles at {world.names[target]}")]


def plan_politics(world, personality, rng):
    """Vote for the policies that suit the playstyle, only where its vote is not already that."""
    decisions = []
    galaxy_votes, _ = uag._get_galaxy_politics(world.kd_id)
    for policy, option in personality.galaxy_votes.items():
        if galaxy_votes["votes"].get(policy, {}).get(world.kd_id) != option:
            decisions.append(Decision("vote_galaxy", {"policy": policy, "option": option},
                                      f"vote {uas.GALAXY_POLICIES[policy]['options'][option]['name']} in the galaxy"))
    # The universe: spend the votes it has (it does not buy any) during an election, half on each doctrine.
    election_on = world.state["state"].get("election_end", "") not in ("", None)
    votes = int(world.me.get("votes") or 0)
    if election_on and votes > 0 and personality.universe_votes:
        policies = list(personality.universe_votes.items())
        share, extra = divmod(votes, len(policies))
        for index, (policy, option) in enumerate(policies):
            amount = share + (extra if index == 0 else 0)
            if amount > 0:
                decisions.append(Decision("vote_universe", {"policy": policy, "option": option, "votes": amount},
                                          f"cast {amount} votes for {uas.UNIVERSE_POLICIES[policy]['options'][option]['name']}"))
    return decisions


def plan(world, personality, rng):
    """Everything the bot wants to do this think, with the times spread over the coming interval."""
    pending = len(world.me.get("schedule", []))
    room = max(min(personality.max_pending - pending, SCHEDULE_LIMIT - pending, personality.max_new), 0)
    decisions = []
    if room > 0:
        for rule in (plan_attack, plan_intel, plan_aggressive, plan_missiles):
            if len(decisions) >= room:
                break
            decisions.extend(rule(world, personality, rng)[: room - len(decisions)])
    decisions.extend(plan_politics(world, personality, rng))

    # Spread the actions over the coming interval so bots (and one bot's own actions) do not land together. Intel goes
    # first within it, as the refresh does too.
    interval = personality.think_epochs[1] * EPOCH
    game_end = datetime.datetime.fromisoformat(world.state["state"]["game_end"]).astimezone(datetime.timezone.utc)
    for decision in decisions:
        decision.delay = rng.uniform(EPOCH * 0.05, interval)
    # The schedule refuses a time outside the round.
    return [d for d in decisions if d.kind.startswith("vote_") or world.now + datetime.timedelta(seconds=d.delay) < game_end]


# --------------------------------------------------------------------------------------------------- carrying it out

# The same handlers the Schedule page's route uses. They take percents the way the form sends them (and scale them
# down), so the options in a Decision are in percent.
_SCHEDULERS = {
    "attack": uac._schedule_attack,
    "intelspy": uac._schedule_intelspy,
    "aggressivespy": uac._schedule_aggressivespy,
    "missiles": uac._schedule_missiles,
}


def next_think_time(personality, rng, now):
    low, high = personality.think_epochs
    return now + datetime.timedelta(seconds=rng.uniform(low, high) * EPOCH)


def first_think_time(personality, rng, now):
    """When a new bot first thinks: somewhere in its first interval, so a hundred new bots are spread out."""
    return now + datetime.timedelta(seconds=rng.uniform(0, personality.think_epochs[1] * EPOCH))


def _log_entry(now, decision, outcome):
    return {"time": now.isoformat(), "kind": decision.kind, "why": decision.why, "outcome": outcome}


def _queue(kd_id, decisions, personality, rng, now, log_extra):
    """Add the scheduled decisions to the bot's schedule and move its next think on, in one write."""
    scheduled = [decision for decision in decisions if decision.kind in _SCHEDULERS]
    refused = []

    def decide(kd_info):
        refused.clear()
        schedule = list(kd_info["schedule"])
        entries = []
        for decision in scheduled:
            if len(schedule) >= SCHEDULE_LIMIT:
                refused.append((decision, "schedule full"))
                continue
            when = (now + datetime.timedelta(seconds=decision.delay)).isoformat()
            ok, entry, message = _SCHEDULERS[decision.kind](
                id=str(uuid.uuid4()), time=when, options=copy.deepcopy(decision.options), kd_info=kd_info)
            if ok:
                schedule.append(entry)
                entries.append(_log_entry(now, decision, f"scheduled for {when}"))
            else:
                refused.append((decision, message))
        schedule.sort(key=lambda item: item["time"])
        bot = dict(kd_info.get("bot", {}))
        bot["next_think"] = next_think_time(personality, rng, now).isoformat()
        bot["log"] = (bot.get("log", []) + log_extra + entries
                      + [_log_entry(now, d, f"not scheduled: {m}") for d, m in refused])[-LOG_SIZE:]
        return {"schedule": schedule, "bot": bot}, None

    occ.update(f'/kingdom/{kd_id}', decide)


def _vote(kd_id, world, decision):
    """Cast one vote decision now. Returns the outcome for the log."""
    try:
        if decision.kind == "vote_galaxy":
            uap.cast_galaxy_vote(kd_id, world.my_galaxy, decision.options["policy"], decision.options["option"])
            return "voted"
        payload, status = uap.cast_universe_votes(
            kd_id, decision.options["policy"], decision.options["option"], decision.options["votes"])
        return "voted" if status == 200 else f"refused: {payload.get('message')}"
    except (occ.Busy, KeyError) as problem:
        return f"failed: {problem!r}"


def think(kd_id, now=None, rng=None, state=None):
    """
    One think for one bot: look, decide, queue. Returns the decisions. Does nothing for a kingdom that is not a bot or
    is dead. Safe to call at any time; ``maybe_think`` is the one the refresh uses.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    rng = rng or random.Random()
    me = uag._get_kd_info(kd_id)
    bot = me.get("bot")
    if not bot or str(me.get("status", "")).lower() == "dead":
        return []
    personality = PERSONALITIES[bot["type"]]

    world = World(kd_id, me, now, state=state)
    decisions = plan(world, personality, rng)

    voted = [_log_entry(now, decision, _vote(kd_id, world, decision))
             for decision in decisions if decision.kind.startswith("vote_")]
    _queue(kd_id, [d for d in decisions if not d.kind.startswith("vote_")], personality, rng, now, voted)
    return decisions


def maybe_think(kd_info, now, state=None):
    """Called by the refresh for every kingdom: thinks if this is a bot whose time has come. Never raises."""
    bot = kd_info.get("bot")
    if not bot or str(kd_info.get("status", "")).lower() == "dead":
        return False
    try:
        if datetime.datetime.fromisoformat(bot["next_think"]).astimezone(datetime.timezone.utc) > now:
            return False
        think(kd_info["kdId"], now=now, state=state)
        return True
    except Exception:
        flask.current_app.logger.exception("Bot %s failed to think", kd_info.get("kdId"))
        return False
