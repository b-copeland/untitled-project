# 0001: Document versions instead of locks

Date: 2026-11-09 (PR #86, issue #64). Status: accepted; migration in progress ([status.md](../status.md#concurrency-migration)).

## Context

Players got duplicate actions in the beta round (one payment, the structures queued several times) and lost updates.
The defense was a lock table (`Locks`) in the web app's SQLite file: `acquire_locks` inserted rows named after documents,
polled until it had them, and released them in a `finally`. It failed in several ways:

| Problem | Effect |
|---|---|
| The lock table is in one server's SQLite file | No mutual exclusion between two web processes or instances at all |
| Only code that takes the lock is protected | The refresh wrote other kingdoms' documents without a lock, and many routes wrote documents they never locked |
| Locks are time-based leases (10 to 20 s) | A request slower than its lease lost the lock while still working, and nothing noticed |
| Taking a lock was a read then a write | Two requests could both take an expired lock |
| The function app's writes were unconditional read-modify-writes | Overlapping requests lost updates even when every caller held a lock |
| Six routes called `acquire_lock` instead of `release_lock` in `finally` | The player's next action got "Server is busy" for 10 s (fixed) |

Measured with `scripts/check_concurrency.py`, 24 concurrent requests at one kingdom through the old function app: 7 of 24
appends applied, 5 of 24 patches to different fields, 2 of 24 spends. Through the old routes with the lock switched off
(as on a second instance): 6 identical "build 100 structures" requests all succeeded.

## Decision

Optimistic concurrency on the document version (`_etag`):

- The function app's single-write handlers are retried on conflict (`@retry_on_conflict`), so merges and appends never
  lose each other.
- Flask actions decide inside `occ.update(path, decide)`, which writes with `If-Match` and re-decides on a conflict.
- Documents are sorted into strict, eventual and derived tiers so only the few that gate decisions need conditional
  writes.

After: 24/24 and 64/64 for appends, patches and spends; 96 concurrent spends on one document all applied exactly once
(against the emulator). Through the routes, 6 identical builds give exactly one success. The production Cosmos account
has one write region, which is what makes the conditional write a true compare-and-swap.

The legacy locks stay on migrated routes until every writer of a document checks its version, because a writer that
does not check can overwrite one that does.

## Rejected

| Option | Why not |
|---|---|
| Service Bus, one queue per document, act when first in every queue (the proposal in #64) | Serializes everything on a document, including actions that never conflict; keeps a coordination service in the path of every action; one queue per document hits the namespace limit around 500 players; sessions cost money; peek-lock durations bring back lease expiry |
| Move the lock table to Cosmos (lease documents with ETags) | Fixes multi-instance, but keeps time-based leases, stuck locks and unprotected writers |
| Redis or Redlock | New infrastructure and cost; leases still expire, so it needs fencing tokens to be safe |
| Durable Entities (one actor per kingdom) | Clean model, but ties the game to the Durable runtime and its latency. Worth revisiting if one document becomes a hot spot |
| Cosmos stored procedures or transactional batch | Atomic only within one partition key; attacks cross kingdoms whatever the key |

## Consequences

- Works with any number of web and function instances, holds no state outside the database, cannot leave a stuck lock.
- Costs one extra read and write only when two writers actually collide.
- Nothing is atomic across documents. Multi-document actions need the outbox pattern ([concurrency.md](../concurrency.md)),
  which is not built.
- Every writer must send the condition; the migration is not finished.
