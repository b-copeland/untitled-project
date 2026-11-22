"""Write down the cluster benefits a running round plays (issue #168, PR #191).

A round made before #191 has no ``cluster_benefits`` in its state and plays the first ``CLUSTER_BENEFITS_PER_ROUND`` of
``CLUSTER_BENEFITS``, which start with the three it had (Drone Production, Cheaper Units, Cheaper Settling). This writes
that list into the state, so the round keeps it whatever later code does with rounds that have none. Nothing else in
the data changes: cluster documents keep their votes and levels by the same keys.

Without it the deploy still works the same way. Run it after the deploy; running it again changes nothing.
Same environment, credentials and flags as ``adhoc/migrate_168_galaxy_policies.py`` (dry run by default, ``--apply``
to write, ``--production`` for a non-localhost endpoint: the maintainer only). The write is conditional on the state's
version; on a conflict, run it again.
"""
import argparse
import pathlib
import sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "adhoc"))

import untitledapp.clusters as clusters  # noqa: E402


def plan_state(state_inner):
    """The fields to add to the state's inner object, or {} if it has them."""
    if state_inner.get("cluster_benefits"):
        return {}
    return {"cluster_benefits": clusters.round_benefits(state_inner)}


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
    state = container.read_item("state", partition_key="state")
    inner = state.get("state") or {}
    fields = plan_state(inner)
    if not fields:
        print("The state has its cluster benefits already: nothing to do")
        return 0
    print(f"state: cluster_benefits = {fields['cluster_benefits']}" + ("" if args.apply else " (dry run)"))
    if args.apply:
        body = {key: value for key, value in state.items() if not key.startswith("_")}
        body["state"] = {**inner, **fields}
        try:
            container.replace_item("state", body, etag=state["_etag"], match_condition=MatchConditions.IfNotModified)
        except ResourceModifiedError:
            print("The state changed while this ran: run it again")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
