"""Move a running round's galaxy politics to the galaxy policies of issue #168 (PR #190).

What changes in the data:

* The state gets ``galaxy_policies``, the policies the round plays. A round made before #190 has none and plays the
  first ``GALAXY_POLICIES_PER_ROUND`` (Growth, Tempo, Defense, Research Focus); this writes that list down, so the
  round keeps it whatever later code does with rounds that have none.
* Each ``galaxy_votes_<galaxy>`` gets ``policy_votes``, ``policy_active`` and ``policy_updated``. The old votes
  (``votes.policy_1``, ``votes.policy_2``, by option number) become votes for the same options, which now live in three
  policies: Expansionist (Growth Doctrine), Warlike (Tempo Doctrine), Intelligence and Conscription (Defense Doctrine).
  The options active by name (``active_policies``) stay active. The old fields are left as they are; nothing reads them.

Without it the deploy still works: galaxies keep their active options by name until a tally decides otherwise, but
every kingdom's old policy vote is gone until it votes again.

When: right after the web app with #190 is deployed (old code would keep writing the old vote fields). Running it
again changes nothing: a galaxy that already has ``policy_active`` is left alone.

Run it in the Flask environment (it needs azure-cosmos, from requirements-dev.txt). Credentials as
``adhoc/migrate_users_to_cosmos.py``: COSMOS_ENDPOINT, COSMOS_KEY, COSMOS_DATABASE_NAME, COSMOS_CONTAINER_NAME from the
environment or funcapp/local.settings.json. Never printed.

    python adhoc/migrate_168_galaxy_policies.py                        # dry run against the emulator
    python adhoc/migrate_168_galaxy_policies.py --apply                # write to the emulator
    python adhoc/migrate_168_galaxy_policies.py --production --apply   # a non-localhost endpoint: the maintainer only

Every write is conditional on the document's version, so a player voting at the same moment is not overwritten (the
script reports the conflict; run it again).
"""
import argparse
import datetime
import pathlib
import sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "adhoc"))

import untitledapp.galaxypolicies as galaxypolicies  # noqa: E402
import untitledapp.shared as uas  # noqa: E402

# Where each old vote goes: old policy, old option number -> (new policy, option).
OLD_VOTES = {
    "policy_1": {"1": ("growth_doctrine", "expansionist"), "2": ("tempo_doctrine", "warlike")},
    "policy_2": {"1": ("defense_doctrine", "intelligence"), "2": ("defense_doctrine", "conscription")},
}


def plan_state(state_inner):
    """The fields to add to the state's inner object, or {} if it has them."""
    if state_inner.get("galaxy_policies"):
        return {}
    return {"galaxy_policies": galaxypolicies.round_policies(state_inner)}


def plan_galaxy(document, policies, now):
    """The fields to add to one galaxy's politics document, or {} if it is moved already."""
    if "policy_active" in document:
        return {}
    galaxy = galaxypolicies.normalize(document, policies)  # takes the active options by name
    for old_policy, by_number in OLD_VOTES.items():
        for kd_id, number in ((document.get("votes") or {}).get(old_policy) or {}).items():
            policy, option = by_number.get(str(number), (None, None))
            if policy in policies:
                galaxy["votes"][policy][kd_id] = option
    galaxy["updated"] = now.isoformat()
    return galaxypolicies.written(galaxy)


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
    now = datetime.datetime.now(datetime.timezone.utc)
    conflicts = 0

    def write(document, fields, label):
        nonlocal conflicts
        print(f"{label}: {', '.join(sorted(fields))}" + ("" if args.apply else " (dry run)"))
        if not args.apply:
            return
        body = {key: value for key, value in document.items() if not key.startswith("_")}
        body.update(fields)
        try:
            container.replace_item(document["id"], body, etag=document["_etag"], match_condition=MatchConditions.IfNotModified)
        except ResourceModifiedError:
            conflicts += 1
            print(f"  {label} changed while this ran: left alone, run again")

    state = container.read_item("state", partition_key="state")
    inner = state.get("state") or {}
    fields = plan_state(inner)
    if fields:
        write(state, {"state": {**inner, **fields}}, f"state ({fields['galaxy_policies']})")
    policies = galaxypolicies.round_policies({**inner, **fields})

    galaxies = container.read_item("galaxies", partition_key="galaxies").get("galaxies", {})
    moved = 0
    for galaxy_id in sorted(galaxies):
        item_id = f"galaxy_votes_{galaxy_id}"
        document = container.read_item(item_id, partition_key=item_id)
        fields = plan_galaxy(document, policies, now)
        if fields:
            moved += 1
            votes = sum(len(v) for v in fields["policy_votes"].values())
            write(document, fields, f"{item_id}: {votes} votes, active {fields['policy_active']}")
    print(f"{moved} of {len(galaxies)} galaxies {'moved' if args.apply else 'to move'}; {conflicts} conflicts")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
