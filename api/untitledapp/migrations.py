"""
Data migrations, run by the refresh: a change to what documents hold is applied by the deployed game itself, on the
first tick after the deploy, in every environment, with nobody running anything ([decisions/0015]).

The rule that makes this safe: **the code that ships with a migration reads both the old and the new shape**, so the
game is right in the minute between the deploy and the tick, and a vote or an action in that minute writes the new
shape without losing anything. The migration only writes the data into its final shape; nothing depends on it having
run yet.

Each migration is a function of the state (``state["state"]``) that changes documents through ``occ.update`` (so it
never overwrites a player's write) and is idempotent (it leaves a document already in the new shape alone), because two
ticks can overlap and a tick can stop half-way. Once it has finished, the tick adds its id to
``state.migrations_done`` (decided on the state, so only once). A migration that raises is logged and tried again on the
next tick; the rest of the tick goes on. A new round starts with every migration marked done
(``admin.round_state``): its documents are made in the new shape.

To add one: a function decorated with ``@migration("<issue>_<what>")``, a test that runs it twice on old documents and
checks the second run changes nothing, and a line in the pull request. Remove it, with its old-shape reading, once
no environment has data from before it (a new round in each).
"""
import datetime
import logging

import untitledapp.galaxypolicies as uagp
import untitledapp.getters as uag
import untitledapp.occ as occ

MIGRATIONS = []  # (id, function), in the order they run


def migration(migration_id):
    def register(function):
        MIGRATIONS.append((migration_id, function))
        return function
    return register


def all_ids():
    return [migration_id for migration_id, _ in MIGRATIONS]


def pending(state_inner):
    """The migrations this game has not run, in order."""
    done = set((state_inner or {}).get("migrations_done") or [])
    return [(migration_id, function) for migration_id, function in MIGRATIONS if migration_id not in done]


def run_pending(state, claim_state):
    """
    Run every pending migration for the game in ``state`` and mark each done once it has finished. ``claim_state`` is
    ``refresh._claim_state``. Returns the ids that ran. Nothing is read or written when none is pending.
    """
    ran = []
    for migration_id, function in pending(state.get("state")):
        try:
            function(state)
        except Exception:  # a migration must not stop the game: it is tried again on the next tick
            logging.exception("Migration %s failed; it will run again on the next tick", migration_id)
            continue

        def mark(stored, migration_id=migration_id):
            done = list(stored.get("migrations_done") or [])
            if migration_id in done:
                return None
            return {"migrations_done": done + [migration_id]}

        claim_state(mark)
        state["state"]["migrations_done"] = list(state["state"].get("migrations_done") or []) + [migration_id]
        ran.append(migration_id)
    return ran


def _set_state_field(field, value_of):
    """Write ``field`` into the state, with ``value_of(stored)``, unless it is there already."""
    def decide(document):
        inner = document["state"]
        if inner.get(field):
            return None, None
        return {field: value_of(inner)}, None
    occ.update('/state', decide, write_path='/updatestate')


# --- the migrations ---------------------------------------------------------------------------------------------------

@migration("168_galaxy_policies")
def galaxy_policies(state):
    """
    Issue #168: the round writes down the galaxy policies it plays (a round from before has none and plays the first
    ones), and every galaxy's politics gets ``policy_votes``, ``policy_active`` and ``policy_updated`` from its old
    votes and its options active by name (``galaxypolicies.LEGACY_VOTES``, ``normalize``).
    """
    _set_state_field("galaxy_policies", uagp.round_policies)
    stored_state = uag._get_state()  # read again: it may just have been written
    policies = uagp.round_policies(stored_state.get("state"))
    round_start = uag._round_start(stored_state)
    now = datetime.datetime.now(datetime.timezone.utc)
    _, galaxies = uag._get_galaxies_inverted()
    for galaxy_id in sorted(galaxies):
        def decide(document):
            if "policy_active" in document:
                return None, None  # in the new shape already (a vote, or an earlier run)
            return uagp.written(uagp.advance(document, policies, round_start, now)), None
        occ.update(f'/galaxy/{galaxy_id}/politics', decide)


@migration("168_cluster_benefits")
def cluster_benefits(state):
    """
    Issue #168: the round writes down the cluster benefits it plays. A round from before has none and plays the first
    ``CLUSTER_BENEFITS_PER_ROUND``, which start with the three it had; cluster documents keep their keys.
    """
    import untitledapp.clusters as uacl  # clusters imports getters, as this module does; imported here to keep it light

    _set_state_field("cluster_benefits", uacl.round_benefits)


_OLD_UNIVERSE_POLICIES = ("policy_1", "policy_2")


def universe_refunds(votes, election_open):
    """Kingdom to the votes it spent on the old doctrines in the open election (none between elections)."""
    if not election_open:
        return {}
    refunds = {}
    for policy in _OLD_UNIVERSE_POLICIES:
        for cast in ((votes or {}).get(policy) or {}).values():
            for kd_id, count in (cast or {}).items():
                refunds[str(kd_id)] = refunds.get(str(kd_id), 0) + int(count or 0)
    return {kd_id: count for kd_id, count in refunds.items() if count > 0}


@migration("168_universe_policies")
def universe_policies(state):
    """
    Issue #168: the options in force stored by key (old names: Treatied stays, the other three end), the ballot written
    down (the one ``universepolicies.ballot_of`` already reads), and the votes document without the old two doctrines.
    Votes spent on those in an election open at the deploy go back to the kingdoms that spent them: each refund is
    recorded, then taken off the record before it is paid, so a refund is never paid twice.
    """
    import untitledapp.universepolicies as uaup

    def state_fields(document):
        inner = document["state"]
        fields = {}
        if "ballot" not in inner:
            fields["ballot"] = uaup.ballot_of(inner)
        if (inner.get("active_policies") or []) != uaup.active_options(inner):
            fields["active_policies"] = uaup.active_options(inner)
        return fields or None, None

    occ.update('/state', state_fields, write_path='/updatestate')
    inner = uag._get_state()["state"]
    ballot = uaup.ballot_of(inner)
    election_open = bool(inner.get("election_end"))

    def votes_fields(document):
        votes = document.get("votes") or {}
        if not any(policy in votes for policy in _OLD_UNIVERSE_POLICIES):
            return None, None
        kept = {policy: cast for policy, cast in votes.items() if policy not in _OLD_UNIVERSE_POLICIES}
        for policy, options in uaup.empty_votes(ballot).items():
            kept.setdefault(policy, options)  # votes cast before this ran stay
        pending = dict(document.get("refunds_pending") or {})
        for kd_id, count in universe_refunds(votes, election_open).items():
            pending[kd_id] = pending.get(kd_id, 0) + count
        return {"votes": kept, "refunds_pending": pending}, None

    occ.update('/universevotes', votes_fields, write_path='/universepolitics')

    while True:
        claimed = {}

        def claim(document):
            pending = dict(document.get("refunds_pending") or {})
            if not pending:
                return None, None
            kd_id = sorted(pending)[0]
            claimed["kd_id"], claimed["votes"] = kd_id, pending.pop(kd_id)
            return {"refunds_pending": pending}, None

        occ.update('/universevotes', claim, write_path='/universepolitics')
        if not claimed:
            break

        def pay(kingdom):
            return {"votes": int(kingdom.get("votes") or 0) + claimed["votes"]}, None

        occ.update(f'/kingdom/{claimed["kd_id"]}', pay)
