"""
Universe policies: what every kingdom's bought votes decide, one election at a time.

Each election puts ``UNIVERSE_POLICIES_PER_ELECTION`` policies of ``shared.UNIVERSE_POLICIES`` on the **ballot**. The
first ballot of a round is drawn when the admin makes the round, and always has the policies marked
``first_election_only`` (Primitives, which matters most early) and never again; each later ballot is drawn when the
election before it closes, from the policies that were not on that one, so players see what comes up next for days.

While an election is open, the result of the last one still applies. When it closes, each ballot policy's option
with the most votes becomes active, a tie (no votes at all included) is decided at random, and the policies of the
last ballot end. The state keeps the active options' ids in ``active_policies``, and the ballot in ``ballot``.

Every option punishes a playstyle (``shared.EFFECTS``). Most hit every kingdom; Wealth's hit the leaders by networth
(``applies_to``), from the scores the refresh keeps.
"""
import random

import untitledapp.shared as uas

# The names the old universe policies were stored by, for a round from before the ballot.
_LEGACY_NAMES = {"Treatied": "treatied"}


def _ordered(keys):
    order = list(uas.UNIVERSE_POLICIES)
    return sorted(set(keys), key=order.index)


def draw_ballot(rng=random, first=False, previous=()):
    """
    The policies of the next ballot. The first of a round has every ``first_election_only`` policy; the others never
    do, nor any policy of the ``previous`` ballot while there are enough without them.
    """
    count = uas.GAME_CONFIG["UNIVERSE_POLICIES_PER_ELECTION"]
    firsts = [key for key, entry in uas.UNIVERSE_POLICIES.items() if entry.get("first_election_only")]
    others = [key for key in uas.UNIVERSE_POLICIES if key not in firsts]
    ballot = list(firsts[:count]) if first else []
    pool = [key for key in others if key not in previous]
    if len(pool) < count - len(ballot):
        pool = others
    ballot += rng.sample(pool, min(max(count - len(ballot), 0), len(pool)))
    return _ordered(ballot)


def ballot_of(state_inner):
    """The ballot of the coming or open election, from the state's inner object (empty if none is drawn yet)."""
    return _ordered(key for key in ((state_inner or {}).get("ballot") or []) if key in uas.UNIVERSE_POLICIES)


def active_options(state_inner):
    """The universe options in force now. A round from before the ballot keeps the one old option that is still here."""
    found = []
    for value in (state_inner or {}).get("active_policies") or []:
        option = value if value in uas.UNIVERSE_POLICY_OF_OPTION else _LEGACY_NAMES.get(value)
        if option and option not in found:
            found.append(option)
    return found


def empty_votes(ballot):
    """The vote tally of a new election: each ballot policy's options with no votes."""
    return {policy: {option: {} for option in uas.UNIVERSE_POLICIES[policy]["options"]} for policy in ballot}


def tally(votes, ballot, seed):
    """
    The options the votes make active: for each ballot policy, the option with the most votes, a tie decided at random
    (``seed`` makes the draw the same however often the close is decided).
    """
    rng = random.Random(str(seed))
    winners = []
    for policy in ballot:
        options = list(uas.UNIVERSE_POLICIES[policy]["options"])
        totals = {option: sum(((votes or {}).get(policy) or {}).get(option, {}).values()) for option in options}
        best = max(totals.values())
        tied = [option for option in options if totals[option] == best]
        winners.append(tied[0] if len(tied) == 1 else rng.choice(tied))
    return winners


def vote_problem(ballot, policy, option, election_open):
    """Why votes can not be cast for ``option`` of ``policy`` now, or None."""
    if not election_open:
        return "Votes can only be cast while an election is open"
    if policy not in ballot:
        if policy in uas.UNIVERSE_POLICIES:
            return f"{uas.UNIVERSE_POLICIES[policy]['name']} is not on this election's ballot"
        return "Choose one of the policies on the ballot"
    if option not in uas.UNIVERSE_POLICIES[policy]["options"]:
        return f"Choose one of the options of {uas.UNIVERSE_POLICIES[policy]['name']}"
    return None


def leaders(scores):
    """``(top kingdoms, top galaxies)`` by networth, as many as Wealth's options hit, from the scores document."""
    networth = (scores or {}).get("networth") or {}
    galaxy_networth = (scores or {}).get("galaxy_networth") or {}
    kingdoms = sorted(networth, key=lambda kd: (-networth[kd], kd))[:uas.GAME_CONFIG["UNIVERSE_WEALTH_TOP_KINGDOMS"]]
    galaxies = sorted(galaxy_networth, key=lambda g: (-galaxy_networth[g], g))[:uas.GAME_CONFIG["UNIVERSE_WEALTH_TOP_GALAXIES"]]
    return set(kingdoms), set(galaxies)


def applies(option, kd_id, galaxy_id, scores):
    """Whether ``option`` hits ``kd_id`` (of ``galaxy_id``)."""
    applies_to = uas.UNIVERSE_POLICIES[uas.UNIVERSE_POLICY_OF_OPTION[option]]["options"][option]["applies_to"]
    if applies_to == "everyone":
        return True
    top_kingdoms, top_galaxies = leaders(scores)
    if applies_to == "top_kingdoms":
        return str(kd_id) in top_kingdoms
    return galaxy_id in top_galaxies


def needs_scores(active):
    """Whether any active option depends on who leads (so the scores must be read)."""
    return any(
        uas.UNIVERSE_POLICIES[uas.UNIVERSE_POLICY_OF_OPTION[option]]["options"][option]["applies_to"] != "everyone"
        for option in active
    )


def modifiers(active, kd_id=None, galaxy_id=None, scores=None):
    """What the active universe options do to ``kd_id``: effect to signed value (``shared.EFFECTS``)."""
    return uas.add_modifiers(*(
        uas.UNIVERSE_POLICIES[uas.UNIVERSE_POLICY_OF_OPTION[option]]["options"][option]["effects"]
        for option in active
        if applies(option, kd_id, galaxy_id, scores)
    ))


def describe(option):
    """An option for the pages: its key, name, sentence, and policy."""
    policy = uas.UNIVERSE_POLICY_OF_OPTION[option]
    entry = uas.UNIVERSE_POLICIES[policy]["options"][option]
    return {"key": option, "policy": policy, "policy_name": uas.UNIVERSE_POLICIES[policy]["name"],
            "name": entry["name"], "desc": entry["desc"]}
