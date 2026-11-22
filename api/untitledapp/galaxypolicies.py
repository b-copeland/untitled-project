"""
Galaxy policies: what a galaxy's kingdoms vote for, and which option holds when.

A round plays ``GALAXY_POLICIES_PER_ROUND`` of the policies in ``shared.GALAXY_POLICIES``, drawn when the admin makes
the round and stored in the state (``galaxy_policies``); they hold for the whole round. Each has two options. Every
kingdom of a galaxy may vote for one option of each, or none.

Votes do not switch a policy at once. The galaxy's votes are **tallied** every ``GALAXY_POLICY_TALLY_EPOCHS``, at fixed
times counted from the round's start (the first at the start itself). At each tally the option with the most votes
then becomes active until the next tally; a tie, or no votes at all, keeps the one that was active (none, at first).
So policies hold between tallies, and a kingdom has no vote cooldown on them.

Like cluster levels, the tally is a pure function of the stored document and the clock (``advance``): between writes
the votes are constant, so anyone reading the document works out every tally since it was written. Only a vote writes.
The fields, on the galaxy's politics document ``galaxy_votes_<galaxy>`` (each read with a default):

* ``policy_votes``: policy to kingdom to the option it votes for.
* ``policy_active``: policy to its active option. A policy with none is absent.
* ``policy_updated``: the moment the document was last brought up to date (every tally up to it applied).

Galaxies made before this kept their votes in ``votes.policy_1``/``votes.policy_2`` (by option number) and their
active options by name in ``active_policies``. Until a galaxy is written in the new shape, both are read as the new
fields (``LEGACY_VOTES``), so nothing is lost whether a vote or the refresh's migration (``migrations.py``) moves it.
"""
import datetime
import math
import random

import untitledapp.shared as uas

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


# Where each old vote goes: old policy, old option number -> (new policy, option).
LEGACY_VOTES = {
    "policy_1": {"1": ("growth_doctrine", "expansionist"), "2": ("tempo_doctrine", "warlike")},
    "policy_2": {"1": ("defense_doctrine", "intelligence"), "2": ("defense_doctrine", "conscription")},
}


def normalize(document, policies):
    """The policy fields of a galaxy's politics document, each with its default, for ``policies``, as a private copy."""
    document = document or {}
    stored_votes = document.get("policy_votes") or {}
    votes = {
        policy: {kd: option for kd, option in (stored_votes.get(policy) or {}).items() if option in _options(policy)}
        for policy in policies
    }
    if "policy_active" in document:
        stored_active = document.get("policy_active") or {}
        active = {policy: option for policy, option in stored_active.items()
                  if policy in policies and option in _options(policy)}
    else:
        # A galaxy from before the tally: its active options were stored by name, its votes by option number.
        names = set(document.get("active_policies") or [])
        active = {}
        for policy in policies:
            for option, entry in _options(policy).items():
                if entry["name"] in names:
                    active[policy] = option
        for old_policy, by_number in LEGACY_VOTES.items():
            for kd_id, number in ((document.get("votes") or {}).get(old_policy) or {}).items():
                policy, option = by_number.get(str(number), (None, None))
                if policy in votes:
                    votes[policy].setdefault(kd_id, option)
    return {"votes": votes, "active": active, "updated": document.get("policy_updated")}


def counts(galaxy, policy):
    """The votes each option of ``policy`` has now."""
    found = {option: 0 for option in _options(policy)}
    for option in galaxy["votes"][policy].values():
        found[option] += 1
    return found


def _tally(galaxy):
    for policy in galaxy["votes"]:
        votes = counts(galaxy, policy)
        best = max(votes.values(), default=0)
        leaders = [option for option, count in votes.items() if count == best]
        if best > 0 and len(leaders) == 1:
            galaxy["active"][policy] = leaders[0]


def advance(document, policies, round_start, now):
    """
    The galaxy's policies as of ``now``: every tally since the document was last written applied (the votes have not
    changed since, so each counts the same votes). ``round_start`` is the round's ``game_start`` as a datetime.
    """
    galaxy = normalize(document, policies)
    if galaxy["updated"] is None:
        galaxy["updated"] = now.isoformat()
        return galaxy
    moment = uas.utc(galaxy["updated"])
    if now <= moment:
        return galaxy
    if tally_after(round_start, moment) <= now:
        _tally(galaxy)  # one tally or many, the votes are the same, so is the result
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
    one, the votes for each, and this kingdom's vote.
    ``galaxy`` is from ``advance`` at ``now``.
    """
    shown = []
    for policy in policies:
        entry = uas.GALAXY_POLICIES[policy]
        votes = counts(galaxy, policy)
        shown.append({
            "key": policy,
            "name": entry["name"],
            "active": galaxy["active"].get(policy),
            "my_vote": galaxy["votes"][policy].get(kd_id),
            "options": [
                {
                    "key": option,
                    "name": option_entry["name"],
                    "desc": option_entry["desc"],
                    "effects": option_entry["effects"],
                    "votes": votes[option],
                }
                for option, option_entry in entry["options"].items()
            ],
        })
    return {
        "policies": shown,
        "next_tally": tally_after(round_start, now).isoformat(),
        "tally_hours": tally_seconds() / 3600,
    }
