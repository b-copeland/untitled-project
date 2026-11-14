# Concurrency: writing actions that are safe when requests overlap

Two requests can always overlap: a double click, two browser tabs, two web processes, the refresh running while a player
acts. If both read the same state, both decide the action is allowed, and both write, the player gets the action twice
for one payment, or one of the writes is lost. This page is how to write code so that cannot happen. Why it is done
this way, and what was measured, is in [decisions/0001-versions-not-locks.md](decisions/0001-versions-not-locks.md).
What is not migrated yet is in [status.md](status.md#concurrency-migration).

## The mechanism in one paragraph

Cosmos DB gives every document a version (`_etag`) that changes on every write. A write sent with
`If-Match: <version>` only lands if the document still has that version; otherwise it is refused (`412`). Cosmos
checks the condition as part of the write, on the server, so nothing can slip in between. On top of that:

- **The function app** (`funcapp/concurrency.py`): every `update_*` handler is wrapped in `@retry_on_conflict`. Its one
  `replace_item` is conditional on the version it read, and on a conflict the handler runs again on the newer document
  (up to 12 times, then `409`). So merges and appends from different requests never lose each other.
- **Flask** (`api/untitledapp/occ.py`): `occ.update(path, decide)` reads the document, calls `decide(document)`, and
  writes the result with `If-Match`. If the document changed in between, `decide` runs again on the new version.

## Writing an action

```python
def decide(kingdom):                          # the kingdom as it is right now
    if kingdom["money"] < cost:
        raise occ.Rejected("Not enough money")   # becomes a 400 with this message
    return {"money": kingdom["money"] - cost}, new_items   # (fields to write, value to return)

try:
    new_items = occ.update(f"/kingdom/{kd_id}", decide)
except occ.Rejected as rejection:
    return flask.jsonify({"message": rejection.message}), rejection.status
except occ.Busy:
    return flask.jsonify({"message": "Server is busy"}), 400
# now the follow-up writes: queue entries, news, notifications
```

Rules:

1. **Pick the one document that holds what is being spent or changed.** For most actions that is `kingdom_<id>`. That
   document is where the decision is made; whichever request commits to it first wins, and the others decide again.
2. **Validate inside `decide`,** against the document passed in. Read anything else it needs inside `decide` too, so it
   is fresh on every attempt.
3. **`decide` has no side effects.** It can run several times. Compute, do not act: no writes, no notifications, no
   random numbers whose result you then rely on outside.
4. **Do the follow-up writes after `update` returns,** as appends or merges (`new_structures`, news items). These are
   safe to land a moment later.
5. **Never read the document before `update` and use that copy inside `decide`.** That is the stale read this replaces.
6. **Return the full nested object** for any nested field you change (`next_resolve`, `units`, ...). The kingdom PATCH is a
   shallow merge, so a partial nested object replaces the whole one ([data-model.md](data-model.md#how-the-function-app-writes)).
7. **Do not add `acquire_lock` to new code.** Routes that already take a legacy lock keep it until every writer of that
   document is migrated, because an unconditional writer could otherwise overwrite a conditional one.

`occ.update` also takes `write_path` (for documents read and written at different routes, such as `GET /universevotes`
and `PATCH /universepolitics`) and `method="post"` (for `/kingdom/<id>/shared`).

## Which documents need strict handling

One question sorts them: **does any later decision read this document to decide whether something is allowed, or how
big an outcome is?**

| Tier | Documents | How they are written |
|---|---|---|
| **Strict** | The documents holding what is at stake: the actor's and the target's kingdom, votes, empire membership, `shared` offers being accepted | Conditional writes with `occ.update`. Keep this set small: most actions have one strict document, an attack has two. |
| **Eventual** | News, history, notifications, messages, `revealed`, pinned | Appends or merges applied by the function app to the newest version. Order does not matter. Timers on the kingdom that these depend on are only ever lowered (`_lower_timer` in `conquer.py` keeps the sooner time), which is safe in any order. |
| **Derived** | `scores`, galaxy networth, empire aggregates | Actions never write them. The refresh recomputes them from the kingdom documents. |

## Actions that touch several documents

Nothing is atomic across two documents. The pattern is **one atomic decision, then effects that are safe to repeat**:

1. Decide against the actor's document and commit (as above).
2. Apply each effect to its own document as an append, a merge, or its own conditional write.
3. A crash between 1 and 2 can leave an effect unapplied. The planned fix is an outbox: the decision write also records
   the effects owed, each with an id; each target remembers the ids it has applied, so applying twice is a no-op; and a
   periodic sweep finishes anything left over. **Not built yet** ([status.md](status.md)).

**Attacks** have two strict documents: the attacker (units leave, cost paid) and then the target (losses, computed from
the target as it is at that moment and written with `If-Match`). Two attacks on one target therefore resolve one after
another, each seeing the other's losses. Details in [decisions/0002-attack-sequencing.md](decisions/0002-attack-sequencing.md).

**The refresh** computes completed queue items without removing them, writes the kingdom once with a version check,
records `queues_resolved_until` per queue so nothing is credited twice, and trims the queues only after the write.
Follow the same shape for any new refresh step.

## Limits to keep in mind

- **Hot documents.** About 100 simultaneous writers to one document can exhaust the retries and get `409`. That is
  deliberate. If a real document sees that load (`scores` or `universe_news` are the likeliest), split it rather than
  raising the retry count.
- **Throttling.** Cosmos answers `429` when the account's request units run out. The function app's bare `except` blocks
  turn that into a `500`, so a burst of 500s under load may be throttling, not a bug.
- **A lost response.** If a write lands but its response is lost and the caller retries, an append can be applied twice.
  Not seen in practice; the outbox ids would fix it.

## Testing concurrency

The backend tests run the real function app handlers on an in-memory container that adds a few milliseconds of latency
to every call, so concurrent requests really overlap. No running stack is needed.

```powershell
conda run -n funcapp python -m pytest tests/test_concurrency.py tests/test_attack.py tests/test_occ.py
$env:STRESS_ROUNDS = 20; conda run -n funcapp python -m pytest tests/test_stress.py   # hunt for rare races
conda run -n funcapp-worker python -m pytest funcapp/tests
```

For a new action that spends something, write a race test: start several identical requests at once with
`_run_together` (in `tests/test_concurrency.py`) and assert exactly one succeeds and the kingdom is charged once.
Do not set `FAKE_LATENCY=0`; without the latency the race tests pass on code that has the race.

`scripts/check_concurrency.py` hammers a running function app (writes to the emulator) and reports lost updates.
