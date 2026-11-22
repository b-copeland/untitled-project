"""
Galaxy policies: what a galaxy's kingdoms vote for, and which option holds when.

A round plays ``GALAXY_POLICIES_PER_ROUND`` of the policies in ``shared.GALAXY_POLICIES``, drawn when the admin makes
the round and stored in the state (``galaxy_policies``); they hold for the whole round. Each has two options. Every
kingdom of a galaxy may vote for one option of each, or none.

Votes do not switch a policy at once. The galaxy's votes are **tallied** every ``GALAXY_POLICY_TALLY_EPOCHS``, at fixed
times counted from the round's start (the first at the start itself). A tally weighs each vote by how long it was held
since the last tally, so a vote switched just before a tally counts for little and the galaxymates who log in most
can not flip a policy at the last moment. The option with the most weight is active until the next tally; a tie, or
no votes at all, keeps the one that was active (none, at first). So a kingdom never has a vote cooldown on policies:
changing a vote only changes how its time is counted.

Like cluster levels, the tally is a pure function of the stored document and the clock (``advance``): between writes
the votes are constant, so anyone reading the document works out every tally since it was written. Only a vote writes.
The fields, on the galaxy's politics document ``galaxy_votes_<galaxy>`` (each read with a default):

* ``policy_votes``: policy to kingdom to the option it votes for.
* ``policy_held``: policy to option to the seconds votes for it have been held since the last tally, as of
  ``policy_updated``.
* ``policy_active``: policy to its active option. A policy with none is absent.
* ``policy_updated``: when ``policy_held`` was last brought up to date.

Galaxies made before this kept their active policies by name in ``active_policies``; those still count until the
first tally after their next vote, where they are in this round's draw.
"""
import datetime
import math
import random

import untitledapp.shared as uas

_EPSILON = 1e-6


def draw(rng=random, count=None):
    """The policies a new round plays: ``count`` of them at random, in the order ``GALAXY_POLICIES`` lists them."""
    count = uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"] if count is None else count
    keys = list(uas.GALAXY_POLICIES)
    chosen = rng.sample(keys, min(max(count, 0), len(keys)))
    return [key for key in keys if key in chosen]


def round_policies(state_inner):
    """
    The policies this round plays, from the state's inner object. A round made before the draw existed plays the
    first ``GALAXY_POLICIES_PER_ROUND``, which keep the doctrines it had.
    """
    drawn = [key for key in ((state_inner or {}).get("galaxy_policies") or []) if key in uas.GALAXY_POLICIES]
    if drawn:
        return drawn
    return list(uas.GALAXY_POLICIES)[:uas.GAME_CONFIG["GALAXY_POLICIES_PER_ROUND"]]


def tally_seconds():
    return uas.GAME_CONFIG["GALAXY_POLICY_TALLY_EPOCHS"] * uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]


def tally_after(round_start, moment):
    """The first tally strictly after ``moment``: the round's start, or a whole number of tally periods after it."""
    if moment < round_start:
        return round_start
    periods = math.floor((moment - round_start).total_seconds() / tally_seconds()) + 1
    return round_start + datetime.timedelta(seconds=periods * tally_seconds())


def _options(policy):
    return uas.GALAXY_POLICIES[policy]["options"]


def normalize(document, policies):
    """The policy fields of a galaxy's politics document, each with its default, for ``policies``, as a private copy."""
    document = document or {}
    stored_votes = document.get("policy_votes") or {}
    stored_held = document.get("policy_held") or {}
    votes = {
        policy: {kd: option for kd, option in (stored_votes.get(policy) or {}).items() if option in _options(policy)}
        for policy in policies
    }
    held = {
        policy: {option: float(value) for option, value in (stored_held.get(policy) or {}).items()
                 if option in _options(policy)}
        for policy in policies
    }
    if "policy_active" in document:
        stored_active = document.get("policy_active") or {}
        active = {policy: option for policy, option in stored_active.items()
                  if policy in policies and option in _options(policy)}
    else:
        # A galaxy from before the tally: its active options were stored by name.
        names = set(document.get("active_policies") or [])
        active = {}
        for policy in policies:
            for option, entry in _options(policy).items():
                if entry["name"] in names:
                    active[policy] = option
    return {"votes": votes, "held": held, "active": active, "updated": document.get("policy_updated")}


def _accumulate(galaxy, seconds):
    if seconds <= 0:
        return
    for policy, votes in galaxy["votes"].items():
        for option in votes.values():
            galaxy["held"][policy][option] = galaxy["held"][policy].get(option, 0.0) + seconds


def _tally(galaxy):
    for policy in galaxy["votes"]:
        weights = galaxy["held"][policy]
        best = max(weights.values(), default=0.0)
        leaders = [option for option, weight in weights.items() if abs(weight - best) < _EPSILON]
        if best > _EPSILON and len(leaders) == 1:
            galaxy["active"][policy] = leaders[0]
        galaxy["held"][policy] = {}


def advance(document, policies, round_start, now):
    """
    The galaxy's policies as of ``now``: every tally since the document was last written applied, and the time since
    the last tally counted. ``round_start`` is the round's ``game_start`` as a datetime.
    """
    galaxy = normalize(document, policies)
    if galaxy["updated"] is None:
        galaxy["updated"] = now.isoformat()
        return galaxy
    moment = uas.utc(galaxy["updated"])
    if now <= moment:
        return galaxy
    while True:
        tally_time = tally_after(round_start, moment)
        if tally_time > now:
            break
        _accumulate(galaxy, (tally_time - moment).total_seconds())
        _tally(galaxy)
        moment = tally_time
    _accumulate(galaxy, (now - moment).total_seconds())
    galaxy["updated"] = now.isoformat()
    return galaxy


def active_options(galaxy):
    """The options active in the galaxy now (from ``advance``)."""
    return [option for option in galaxy["active"].values()]


def modifiers(galaxy):
    """What the galaxy's active options are worth to its kingdoms: effect to signed value (see ``shared.EFFECTS``)."""
    return uas.add_modifiers(*(
        _options(policy)[option]["effects"] for policy, option in galaxy["active"].items()
    ))


def written(galaxy):
    """The fields a write stores, from ``advance``."""
    return {
        "policy_votes": galaxy["votes"],
        "policy_held": galaxy["held"],
        "policy_active": galaxy["active"],
        "policy_updated": galaxy["updated"],
    }


def vote_problem(policies, policy, option):
    """Why a vote for ``option`` of ``policy`` can not be cast this round, or None. ``option`` None withdraws."""
    if policy not in policies:
        if policy in uas.GALAXY_POLICIES:
            return f"{uas.GALAXY_POLICIES[policy]['name']} is not one of this round's policies"
        return "Choose one of this round's policies"
    if option is not None and option not in _options(policy):
        return f"Choose one of the options of {uas.GALAXY_POLICIES[policy]['name']}"
    return None


def cast(galaxy, kd_id, policy, option):
    """Put ``kd_id``'s vote for ``policy`` as ``option`` (None withdraws it) in ``galaxy`` (from ``advance``). Returns
    whether anything changed."""
    votes = galaxy["votes"][policy]
    if votes.get(kd_id) == option:
        return False
    if option is None:
        votes.pop(kd_id, None)
    else:
        votes[kd_id] = option
    return True


def view(galaxy, policies, round_start, now, kd_id):
    """
    What the Policies tab shows a kingdom of the galaxy: each of the round's policies with its options, the active
    one, the votes for each, how much weight each has gathered towards the next tally, and this kingdom's vote.
    ``galaxy`` is from ``advance`` at ``now``.
    """
    shown = []
    for policy in policies:
        entry = uas.GALAXY_POLICIES[policy]
        votes = galaxy["votes"][policy]
        held = galaxy["held"][policy]
        total_held = sum(held.values())
        shown.append({
            "key": policy,
            "name": entry["name"],
            "active": galaxy["active"].get(policy),
            "my_vote": votes.get(kd_id),
            "options": [
                {
                    "key": option,
                    "name": option_entry["name"],
                    "desc": option_entry["desc"],
                    "effects": option_entry["effects"],
                    "votes": sum(1 for chosen in votes.values() if chosen == option),
                    # The share of the weight so far towards the next tally (0 when nothing is held yet).
                    "weight": (held.get(option, 0.0) / total_held) if total_held > 0 else 0.0,
                }
                for option, option_entry in entry["options"].items()
            ],
        })
    return {
        "policies": shown,
        "next_tally": tally_after(round_start, now).isoformat(),
        "tally_hours": tally_seconds() / 3600,
    }
