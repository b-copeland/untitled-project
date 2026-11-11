# Concurrency: how game-state changes avoid duplicate and lost actions

Issue [#64](https://github.com/b-copeland/untitled-project/issues/64) asked for the lock framework to be documented, and
for something better. This describes what exists today, why it breaks, what replaces it, what is already done, and the
plan for the rest.

**In one paragraph.** Two requests that overlap (a double click, two browser tabs, two web app instances, a refresh
running while a player acts) could both read the same state, both decide the action was allowed, and both apply it. The
old defense was a lock row in a SQLite file on the web server, which only works while there is exactly one server and
only for code that bothers to take it. The replacement does not use locks. Cosmos DB gives every document a version
(`_etag`); a change is written with "only if the version is still the one I read", and if it is not, the action is
decided again against the new state. That works for any number of servers, holds no state, and cannot leave a stuck lock
behind.

## 1. How it works today (the lock framework)

Defined in `api/untitledapp/misc.py` (`acquire_lock`, `acquire_locks`, `release_lock`, `release_locks_by_id`) and used by
about 70 call sites in `build`, `conquer`, `misc`, `politics` and `refresh`.

- A lock is a row in the `Locks` table (`lock_name`, `request_id`, `expires_at`) in the web app's SQLite database.
- Names mirror the documents they guard: `/kingdom/{id}`, `/kingdom/{id}/structures`, `/scores`, `/galaxies`, ...
- `acquire_locks([...])` inserts the missing rows, takes over expired ones, and polls every 10 ms for the rest until a
  timeout (10 s for requests, 999 s for the refresh). If it times out it releases what it took and the route answers
  "Server is busy".
- A lock expires after 10 to 20 seconds. That is the lease.
- A route takes its locks, reads documents from the function app, decides, writes, and releases in a `finally`.

### Why it does not hold up

| Problem | Effect |
|---|---|
| The lock table is in **one server's SQLite file** | With two web app instances there are two lock tables and no mutual exclusion at all. This is what blocks scaling out. |
| Only code that takes the lock is protected | The refresh writes **other kingdoms'** documents (`siphonsin` of the kingdom it takes from) without a lock, and many routes write documents they never locked. |
| The lease is time-based | If a request takes longer than its lease (a slow call to the function app), the lock expires while it is still working and a second request walks in. Nothing detects it. |
| Taking a lock is not atomic | `acquire_lock` does a read, then a write; the takeover of an expired lock is a plain merge, not a compare-and-swap. |
| Nothing protects the data itself | The function app's writes were unconditional read-modify-writes, so two overlapping requests lose one update **even if every caller held a lock** (measured below). |
| Bugs | Six routes in `build.py` called `acquire_lock` in their `finally` block instead of `release_lock`, so the lock was never released and the player's next action got "Server is busy" for up to 10 seconds. Fixed. |

### Measured, before

`scripts/check_concurrency.py` fires 24 concurrent requests at one kingdom through the function app (old code):

| check | expected | applied |
|---|---|---|
| appends to one list (e.g. news, siphons) | 24 | **7** |
| patches to different fields of one document | 24 | **5** |
| spends (read balance, write balance minus 1) | 24 | **2** |

And through the real routes, with the lock switched off to simulate a second web app instance (the end-to-end tests in
`tests/test_concurrency.py`, run against the old route code): **6 identical "build 100 structures" requests all
succeeded**, so one payment queued the structures six times, and four simultaneous shield changes lost updates (one of the
four shields stayed at 0).

## 2. The replacement: check the version, not a lock

Two parts, one per layer. Neither keeps any state outside Cosmos.

### The function app: writes are conditional on the version read

`funcapp/concurrency.py`. Every `update_*` handler (31 of them) is wrapped in `@retry_on_conflict`:

1. Its `replace_item` is sent with `If-Match: <the _etag it read>`.
2. If another request wrote the document first, Cosmos refuses (HTTP 412). The handler is run again from the top on the
   newer document, with a short random backoff, up to 12 times, then answers `409` ("try again").
3. So appends and patches to different fields can no longer lose each other.
4. A caller can also send its own `If-Match`, and gets `412` if the document changed since it read it. Successful writes
   return the new version in the `ETag` header.

It is invisible to existing callers: the Cosmos system fields (`_etag`, `_ts`, ...) that callers send back when they
`PATCH` a whole document they read are stripped, and `If-Match` is only enforced when sent.

### The web app: decide against the current state, commit only if it is still current

`api/untitledapp/occ.py`:

```python
def decide(kingdom):                       # sees the document as it is right now
    if kingdom["money"] < cost:
        raise occ.Rejected("Not enough money")
    return {"money": kingdom["money"] - cost}, new_items

new_items = occ.update(f"/kingdom/{kd_id}", decide)
# ...then do whatever must happen once, using new_items
```

`update` reads the document, calls `decide`, and writes with `If-Match`. If the document changed in between, `decide`
runs again on the new version. The second of two identical requests therefore finds the money gone and is rejected by
the route's own validation, instead of both passing. `Rejected` becomes a 400 with the message; `Busy` (the document
kept changing for 12 attempts) becomes "Server is busy".

### Rules for writing an action

1. **Pick the one document that holds what is being spent or changed** (for most actions, `kingdom_{id}`). That
   document is the *linearization point*: whichever request commits to it first wins, and the rest re-decide.
2. Do all the validation **inside `decide`**, against the document passed in (and fresh reads of anything else it needs).
3. `decide` can run several times, so it must have **no side effects**. Compute, do not act.
4. Do the follow-up writes after `update` returns (queue entries, news, notifications).
5. Do not read the kingdom before `update` and use it inside: that is exactly the stale read this removes.

### Measured, after

| check (function app, same tool) | 24 threads | 64 threads | 96 threads, one document |
|---|---|---|---|
| appends | 24/24 | 64/64 | 84 applied, 12 told `409` |
| patches to different fields | 24/24 | 64/64 | 94 applied, 2 told `409` |
| spends with `If-Match` | 24/24 | 64/64 | 96/96 |

The guarantee is **every request either applies exactly once or is told to retry**; none disappears. Through the routes
(`tests/test_concurrency.py`, lock off): 6 identical builds give exactly one success, the kingdom is charged once and the
structures are queued once; four simultaneous shield changes are all kept.

### What the guarantee covers, and what it does not

"Read, decide, then write only if unchanged" is not a check followed by a write. The condition travels **with** the write
and Cosmos evaluates it on the server as part of the same operation, so there is no gap between the check and the write
for something else to slip into. The database serializes writes to one document: if two conditional writes race, the
second sees the new version and is refused. A stale read is harmless: it carries an old version, so the write is refused
and costs one retry. This was confirmed against the Cosmos emulator (96 concurrent spends, all exactly once), and the
production account has one write region (East US), so the same holds there.

Limits to keep in mind:

1. **One document at a time.** Nothing is atomic across documents. That is what the tiers and the outbox below are for.
2. **Every writer has to send the condition.** An unconditional write is atomic too, but it does not compare, so it can
   overwrite a checked write. This is why the legacy locks stay until all writers of a document are migrated.
3. **A lost response is not yet handled.** If a write is applied but its response is lost (a timeout) and something
   retries it with the old version, the retry gets a `412` as if someone else had written, and the handler would apply the
   change again. For an append that is a duplicate. I have not seen it happen, and I do not know whether the Cosmos Python
   SDK retries writes after a timeout. The fix is the one the attack design already uses: give each change an id that the
   document remembers, so a repeat is recognized and skipped. The 31 `update_*` handlers do not do this yet.

## 3. What is done and what is not

| | Status |
|---|---|
| Function app: 31 single-document handlers conditional and retried | Done (merged) |
| Function app: 7 multi-document admin handlers (`create_*`, `reset_state`, `delete_all`, `init`) | Not changed. They write several documents and can not be re-run from the top. They are admin and setup operations, not hot paths. |
| `occ.py` helper, with unit tests that need no stack | Done |
| Routes migrated to `occ.update`: every own-kingdom route in `build.py` (structures, recruits, mobis and disband, settle, missiles, engineers, projects, targets, raze), shields, `/api/spending`, `/api/createkingdomchoices`, `/api/votes`, `/api/universepolitics/policies` | Done. **They still take the legacy lock as well** (see below). |
| Attacks (`POST /api/attack/<kd>`, primitives), spying, robbing primitives, missiles, schedule add/cancel | Done. Attacks are committed in three versioned steps (depart, resolve against the target as it is, credit). Spy and missiles charge the attacker up front under a version check and apply damage to the target's latest document. Reveal timers are min-merged and aggression is an increment on the latest `/empires`. News, history, reveal documents and notifications are still written the old way (eventual tier, not yet exactly-once), and the lock lists in these routes are unchanged. |
| Six `acquire_lock`-in-`finally` bugs | Fixed |
| The other lock call sites (politics other than votes, messages, shared intel, pinned, `reveal_random_galaxy`, kingdom reset, the refresh) | Not migrated. Recipe above; do them by module. |
| The refresh (`refresh.py`) | Not migrated. It needs the saga below, because it consumes queue documents before writing the kingdom. |
| Multi-document actions other than the attack (spy, trade, politics) | Design below, not built. |

**Where the remaining lock sites are** (69 call sites, counted by which documents each locks; the grouping is
approximate, a few routes in the first group also touch other kingdoms):

| Group | Sites | Examples | Approach |
|---|---|---|---|
| Own kingdom, plus one of its sub-documents | 39 | build, train, disband, projects, settle, missiles, schedules, pinned, shields, shared intel | Section 2 recipe. Mechanical, one route at a time. |
| Several documents of different owners | 19 | politics (invites, requests, surrender, denounce, policies), election, auto spending, history | Section 4 outbox pattern, or section 2 where the "other" document is only appended to. |
| Lock list built at runtime | 6 | attack, spy, offer/accept shared intel, surrender acceptance, kingdom reset | Section 4. Attacks follow the sequencing design below. |
| Shared documents only | 5 | create kingdom, create empire, declare war, resolve scores, resolve empires | Mostly merge or append semantics that the function app now handles; a few need a decision step. |

**Why the legacy lock is still there.** Until *every* writer of a document checks its version, a writer that does not
check can overwrite a checked one (it reads, a checked write lands, then it writes its stale copy over it). While both
kinds exist, a migrated route keeps the lock so the two kinds still exclude each other on one server, and the version
check adds protection across servers and against the writers that never locked. Once all writers of a document are
migrated, the locks for it can be deleted.

**Deploy order matters:** the function app is published manually, not by CI. Publish `funcapp/` before relying on the
Flask side. A Flask route that sends `If-Match` to an *old* function app still works (the header is ignored), it is just
not protected.

## 4. Multi-document actions: the plan

Most actions touch more than one document: an attack changes the attacker, the target, both sides' news and history; a
build changes the kingdom and its structure queue. Cosmos can only commit several documents atomically if they share a
partition key, and here every document is its own partition (`/id`), and an attack spans two kingdoms whatever the key.

The pattern to use: **one atomic decision, then idempotent effects** (the transactional outbox).

1. **Decide** against the actor's document, as above, and in the *same* conditional write record the effects that must
   follow, each with an id: `outbox: [{id, target, change}, ...]`. The decision and the promise of the effects are one
   atomic write, because they are in one document.
2. **Apply** each effect to its target document idempotently: the target remembers the ids it has applied (a small
   bounded list), so applying twice is a no-op. Then remove the entry from the outbox (conditional write again).
3. **Recover**: if the process dies between 1 and 2, the outbox still lists what is owed. The request that finishes
   normally does the work; a periodic sweep (an Azure Functions timer trigger, which the function app can host) finishes
   anything left over.

This gives exactly-once effects without a transaction coordinator. The trade-off: effects on other kingdoms land a moment
after the decision, rather than in the same instant.

### Which documents need strict handling: three tiers

An attack touches many documents (`_attack` writes four kingdom documents, the attack history, kingdom news twice, galaxy
news twice and a reveal, and adds aggression and notifications; its lock list also covers `/empires`, and for a
cross-galaxy attack a `revealed` and a kingdom document for every member of the defender's galaxy). Most of those do not
need to be consistent with each other at the same instant. One question sorts them: **does any later decision read this
document to decide whether something is allowed, or how big an outcome is?**

| Tier | Documents | How they are written |
|---|---|---|
| **Strict** | the kingdom documents that hold what is at stake: the actor's and the target's (including the target's death state) | Conditional writes, sequenced by version, as designed here. An attack has at most two decision points: the attacker, then the target. |
| **Eventual, exactly-once** | news, attack and spy history, notifications, `revealed`, galaxy news, messages | Applied from the outbox with ids, so a repeat is a no-op, normally within seconds. Appends commute, so their order does not matter. `revealed` is "set if newer". |
| **Derived** | scores, galaxy networth, empire aggregates | Actions do not write them. The refresh already recomputes them from the kingdom documents every tick. |

So the strict part of an attack is two documents, not dozens, and the rest lands a moment later without ever being able
to disagree about the money or the land. Eventual writes can also be batched (for example, several news lines in one
write), which saves Request Units (see section 5).

Not yet read: why the lock list includes every defender-galaxy member's kingdom document, and what `_add_aggression`
writes to `/empires`. Both need a look before they are assigned a tier.

### Attacks: concurrent attacks on one target resolve one after another

Requirement (from the maintainer): an attack is resolved against the target roughly as it was when the attacker decided,
but if two players attack the same kingdom at the same time, the attacks must resolve **sequentially**, because each
outcome depends on the other.

The target's own document is the sequencer, so no queue or lock is needed:

1. **Commit the attacker's side.** In one conditional write to the attacker's document: the units and generals leave, the
   cost is paid, and an attack record with an id (`attack_id`) is added to its outbox. This is the same single-document
   decision as everywhere else, so an attacker can not send the same units twice.
2. **Resolve against the target.** Read the target document (and its version), compute the outcome from the target as it
   is *now*, and write the target's losses with `If-Match`, recording `attack_id` in the target's list of applied attacks.
   If another attack, or any other write, landed on the target in between, the write is refused, the target is read
   again, and the outcome is recomputed. Attacks on the same target therefore resolve one after another, each seeing the
   previous one's losses, in the order they commit to the target. The outcome calculators are pure functions of
   (attacker forces, target state), so recomputing is safe; messages and notifications are sent only after the commit.
3. **Report back.** Apply the result to the attacker (land and gains, casualties, return time) and write the news and
   history entries, idempotently keyed by `attack_id`. The outbox sweep finishes any that a crash left behind.

"Roughly as it was when the attacker decided" holds because steps 1 and 2 are normally milliseconds apart. If the target
also spent money or built something in that gap, the attack sees that too, which is closer to real-time play than a
snapshot. Scheduled attacks and auto attacks go through the same path.

**Reveals are eventual and min-merged** (maintainer's decision). An attack across galaxies reveals the attacker's galaxy
to every defender-galaxy member by writing their `revealed` document and lowering `next_resolve.revealed` on their
kingdom document. That is why the attack's lock list contains the whole defender galaxy, but nothing about the combat
depends on it. Taking the sooner of the stored and the new timestamp is idempotent and order-independent, so it can run
after the strict steps, on its own, with a version-checked write per member and a sweep for any that fail. The aggression
counter in `/empires` (`_add_aggression`) should become an increment applied to the freshest document for the same reason.

**What is built so far:** steps 1 to 3 above for the attack itself, using the target's version as the sequencer, plus the
min-merged reveal timers and the aggression increment. Not built: the `attack_id` outbox and sweep, so a crash between
the steps leaves the attacker's units out with no result applied (the attacker side is compensated if the target step
fails, but not if the process dies). News and history writes are unchanged.

Open question: the order is the order attacks *reach the target document*, which is the only order that exists across
several servers. If the order players *clicked* must win over the order requests arrived, a per-target queue would be
needed. I would not build that unless it matters in play.

**The refresh** is the hardest case, because it consumes queue documents (`settles`, `mobis`, `structures`, ...) *before*
it writes the kingdom, so a conflict on the kingdom would either lose the completed items or credit them twice. It needs
the same shape: compute completed items without removing them, write the kingdom once with the credit, then trim the
queues as idempotent effects keyed by item id. The refresh also needs to be safe to run twice at once; per-kingdom
version checks give that for free once it is converted.

### Why not the Service Bus design in #64

The proposal queues one message per document per action and lets an action start only when its request is first in every
queue it needs. It would work, but:

- It serializes **everything** on a document, including actions that could never conflict, and keeps a coordination
  service in the critical path of every action.
- One queue per document hits the namespace limit (10,000 queues), which the issue itself estimates at about 500
  players, and the Standard-tier alternative (sessions) adds a monthly cost and a second system to operate.
- Peek-lock messages have lock durations and redelivery, which brings back the lease-expiry problem it was meant to remove.
- The version check needs no new infrastructure, adds no cost, and only does extra work when two writers actually collide.

### Other options considered

| Option | Verdict |
|---|---|
| Move the lock table to Cosmos (lease documents with ETags) | Fixes multi-instance, keeps time-based leases, stuck locks and the unprotected writers. |
| Redis / Redlock | New infrastructure; leases still expire, so it needs fencing tokens to be safe. |
| Durable Entities (one actor per kingdom, serializes everything) | The cleanest model for per-kingdom state, but ties the project to the Durable runtime and its latency. Worth revisiting if hot-document contention becomes a problem. |
| Cosmos stored procedures / transactional batch | Atomic only within one partition key; would need `/kingdom` partitioning, and attacks still cross it. |

## 5. Other things that stop the web app from scaling out

The locks were one of four per-server pieces of state. Removing them does not make a second instance safe by itself.

Production runs `gunicorn -k gthread --threads=100 --timeout 600`: one process, 100 threads, requests allowed ten
minutes. So today's duplicate actions did **not** need a second server. Up to 100 requests run at once in the same
process, and the lock leases are 10 to 20 seconds, so a request that takes longer than its lease (the function app being
slow, with a timeout this generous) loses its lock while still working. That, plus writers that never took the lock, is
the likeliest source of the duplicates seen in the beta round. I have not reproduced that exact case.

The web app is also on the **Free (F1) App Service plan**, which is limited to one instance, so scaling out starts with
changing the plan. The same plan allows only 5 concurrent WebSocket connections, so live notifications reach few players.
Separately, the `/ws/listen` handler loops for as long as a player is connected, so each connection occupies one of the
100 gunicorn threads for its whole lifetime; with enough players online, sockets alone would use up the threads that
serve ordinary requests. (That second point is from reading the code, not from a measurement.) The function app is different: it runs on a Linux Consumption plan, which scales out on its own, so
several function app instances can already run at once. See "What Azure actually runs" in
[deployment.md](deployment.md).

| State | Where | What breaks with two instances | Direction |
|---|---|---|---|
| Users and locks | SQLite file (`SQLALCHEMY_DATABASE_URI`) | Each instance has its own users; the lock table is covered above | Move users to Cosmos, or a shared SQL database |
| Websocket registry | `SOCK_HANDLERS` dict in `untitledapp/__init__.py` | A notification only reaches players whose socket is on the instance that raised it | Azure Web PubSub / SignalR, or Redis pub/sub |
| Rate limiter | `Limiter(storage_uri="memory://")` | Limits are per instance | Shared storage for the limiter |
| The refresh | `/api/refreshdata`, called every minute by the `refreshapp` WebJob (not in the repo) | Two overlapping refreshes must not both resolve a kingdom | Covered by per-kingdom version checks once converted |

### The Cosmos budget

All four containers in the `dev` database share **1000 RU/s**, the free-tier allowance. Writes are what cost: measured on
the emulator, a read of a typical document is about 1 RU, and a conditional write is about 10 RU for a small document
and about 13 RU for a 3 KB kingdom document. These are emulator figures; they should be close to Azure's, but check the
request charge on the real account before relying on them.

| | Roughly |
|---|---|
| Kingdom writes the whole game can sustain | about 75 per second |
| One attack with about ten document writes | about 120 to 150 RU, so a handful of attacks per second at most, before the refresh and everything else |
| A throttled request (`429`) | surfaces as a 500, because the handlers' bare `except` swallows it |

Practical consequences: keep the strict tier small, batch and coalesce the eventual tier, avoid retry storms on hot
documents, and keep dev and test traffic off the production database (the local emulator exists for that).

## 6. Reproducing and testing

```powershell
# Function app, against the Cosmos emulator (writes to it, so reseed afterwards)
conda run -n funcapp-worker python scripts/check_concurrency.py --threads 24

# Mechanism tests (no Azure needed)
conda run -n funcapp-worker python -m pytest funcapp/tests
conda run -n funcapp python -m pytest tests/test_occ.py

# End to end through the real routes (needs the stack running, like the other tests in tests/)
conda run -n funcapp python -m pytest tests/test_concurrency.py tests/test_attack.py

# Mixed actions with exact bookkeeping checks; raise STRESS_ROUNDS to hunt for rare races
$env:STRESS_ROUNDS = 20; conda run -n funcapp python -m pytest tests/test_stress.py
```

To see the original bug, run the same checks against the code from before these changes: the end-to-end tests fail on the
old routes (six successful duplicate builds), and `check_concurrency.py` loses most of its updates against the old
`function_app.py`. The function app host hot-reloads on file changes, so wait a few seconds after switching code.

Under very heavy contention on a single document (about 100 simultaneous writers) a request can run out of retries and gets
`409`. That is deliberate. If a real document ever sees that load (`scores` or `universe_news` are the likeliest), split
it rather than raising the retry count.

The Cosmos emulator defaults to 400 RU/s and answers `429` under this kind of load, which the handlers' bare `except`
turns into a 500. The seed script now creates the container with 4000 RU/s; for an existing container, raise it with
`replace_throughput`.
