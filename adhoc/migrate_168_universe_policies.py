"""Move a running round's universe politics to the ballots of issue #168 (the universe policies PR).

What changes in the data:

* ``state.active_policies`` held option *names* (Unregulated, Treatied, Free Trade, Isolationist); it now holds keys.
  Treatied becomes ``treatied``; the other three no longer exist and end.
* ``state.ballot``: the policies of the next (or open) election. Drawn here as the code would: a round with nothing in
  force yet gets a first ballot, with Primitives.
* ``universe_votes`` held votes under ``policy_1``/``policy_2`` and ``option_1``/``option_2``. It is written empty for
  the ballot. **If an election is open**, the votes kingdoms cast in it were spent on policies that no longer exist, so
  each kingdom gets them back to spend on the ballot. The refunds are recorded in ``universe_votes.refunds_pending``
  first and each is crossed off as it lands, so a run that stops half-way, run again, finishes without paying anyone
  twice.

Without it the deploy still works: old names are read as above, and a round with no ballot draws one when its next
election opens. But votes cast in an election that is open at the deploy are lost.

When: right after the web app is deployed. Same environment, credentials and flags as
``adhoc/migrate_168_galaxy_policies.py`` (dry run by default, ``--apply`` to write, ``--production`` for a
non-localhost endpoint: the maintainer only). Every write is conditional on the document's version.
"""
import argparse
import pathlib
import random
import sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "adhoc"))

import untitledapp.universepolicies as up  # noqa: E402

OLD_POLICIES = ("policy_1", "policy_2")


def is_old_votes(votes_doc):
    """Whether the votes document still has the old two-doctrine shape."""
    return any(key in OLD_POLICIES for key in ((votes_doc or {}).get("votes") or {}))


def plan_state(state_inner, rng=None):
    """The fields to set on the state's inner object, or {} if it is moved already."""
    if "ballot" in state_inner:
        return {}
    active = up.active_options(state_inner)
    rng = rng or random.Random(state_inner.get("election_start") or "migration")
    return {"active_policies": active, "ballot": up.draw_ballot(rng, first=not active)}


def plan_refunds(votes_doc, election_open):
    """Kingdom to the votes it spent in the open election, from the old shape (nothing between elections)."""
    if not election_open or not is_old_votes(votes_doc):
        return {}
    refunds = {}
    for policy in OLD_POLICIES:
        for cast in (((votes_doc.get("votes") or {}).get(policy)) or {}).values():
            for kd_id, votes in (cast or {}).items():
                refunds[str(kd_id)] = refunds.get(str(kd_id), 0) + int(votes)
    return {kd_id: votes for kd_id, votes in refunds.items() if votes > 0}


def main(argv=None):
    from migrate_users_to_cosmos import _container, _settings, LOCAL_HOSTS
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceModifiedError

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write; without it, only say what would change")
    parser.add_argument("--production", action="store_true", help="allow an endpoint that is not this machine")
    args = parser.parse_args(argv)
    settings = _settings()
    if urlparse(settings["COSMOS_ENDPOINT"]).hostname not in LOCAL_HOSTS and not args.production:
        sys.exit("The endpoint is not this machine: pass --production to run against it.")
    container = _container(settings)
    dry = "" if args.apply else " (dry run)"

    def replace(document, body):
        clean = {key: value for key, value in body.items() if not key.startswith("_")}
        container.replace_item(document["id"], clean, etag=document["_etag"], match_condition=MatchConditions.IfNotModified)

    state = container.read_item("state", partition_key="state")
    inner = state.get("state") or {}
    fields = plan_state(inner)
    ballot = fields.get("ballot") or up.ballot_of(inner)
    votes_doc = container.read_item("universe_votes", partition_key="universe_votes")

    # 1. The votes document: the new empty shape, and the refunds owed, in one write.
    if is_old_votes(votes_doc):
        refunds = plan_refunds(votes_doc, bool(inner.get("election_end")))
        print(f"universe_votes: empty for {ballot}; refunds owed to {len(refunds)} kingdoms ({sum(refunds.values())} votes){dry}")
        if args.apply:
            try:
                replace(votes_doc, {**votes_doc, "votes": up.empty_votes(ballot), "refunds_pending": refunds})
            except ResourceModifiedError:
                print("universe_votes changed while this ran: run it again")
                return 1
            votes_doc = container.read_item("universe_votes", partition_key="universe_votes")

    # 2. Each refund, crossed off once it has landed.
    pending = dict(votes_doc.get("refunds_pending") or {})
    for kd_id, votes in sorted(pending.items()):
        print(f"kingdom {kd_id}: +{votes} votes back{dry}")
        if not args.apply:
            continue
        for _ in range(5):
            kingdom = container.read_item(f"kingdom_{kd_id}", partition_key=f"kingdom_{kd_id}")
            try:
                replace(kingdom, {**kingdom, "votes": int(kingdom.get("votes") or 0) + votes})
                break
            except ResourceModifiedError:
                continue
        else:
            print(f"kingdom {kd_id} kept changing: run it again")
            return 1
        for _ in range(5):
            votes_doc = container.read_item("universe_votes", partition_key="universe_votes")
            left = {k: v for k, v in (votes_doc.get("refunds_pending") or {}).items() if k != kd_id}
            try:
                replace(votes_doc, {**votes_doc, "refunds_pending": left})
                break
            except ResourceModifiedError:
                continue

    # 3. The state, last: what is in force by key, and the ballot.
    if fields:
        print(f"state: active_policies {inner.get('active_policies')} -> {fields['active_policies']}, ballot {fields['ballot']}{dry}")
        if args.apply:
            try:
                replace(state, {**state, "state": {**inner, **fields}})
            except ResourceModifiedError:
                print("The state changed while this ran (a tick): run it again")
                return 1
    else:
        print("state: moved already")
    return 0


if __name__ == "__main__":
    sys.exit(main())
