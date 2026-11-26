# Keeping the cost down

This is an unfunded personal project. The target is to run a round for free or close to it. Any change that adds a paid
service, moves to a paid tier, or noticeably raises usage needs the maintainer's agreement first.

## What it runs on

Read from Azure on 2026-11-10; check [deployment.md](deployment.md) for detail. Prices and free allowances change, so check
the Azure pricing pages before relying on a number here.

| Piece | Plan | Cost model | Limit that bites first |
|---|---|---|---|
| Web app (Flask and the built frontend) | App Service **Basic (B1)**, one instance (since 2026-11-21, for the custom domain; was Free F1) | Paid per instance, about $13 a month for one | 1 core and 1.75 GB; stays at one instance. Issue #173 plans a cheaper host. |
| Function app | **Linux Consumption (Y1)** | Free monthly grant of executions and GB-seconds, then pay per execution and per GB-second | Executions: every Flask request makes several function calls |
| Cosmos DB | **Free tier**, 1000 RU/s shared by the database, manual | Free up to 1000 RU/s and 25 GB per account | Request units per second. **All four containers, including production, share the 1000 RU/s.** |
| Email | SendGrid | Free tier | Daily send limit |
| Storage (function app requirement) | Standard storage | Cents | |

## Where the usage comes from

Every player action and every page load is: browser to Flask, then **several** Flask-to-function-app calls, each of which
is one function execution and at least one Cosmos operation. So the cost of a feature is roughly
`(requests per player per day) x (function calls per request) x (players)`.

Measured on the emulator (check the real account's request charge before relying on them): reading a typical document is
about 1 RU; a conditional write is about 10 RU for a small document and 13 RU for a 3 KB kingdom document. An attack
writing about ten documents is 120 to 150 RU.

The steady load, without anyone acting:

| Source | Rate |
|---|---|
| Each open game tab polls the kingdom and notifications | every 10 s, so about 12 requests a minute per player, each reaching the function app |
| Each open game tab polls scores | every 60 s |
| Opening the Status page fetches the advisors | nine reads each time (up to twelve for a galaxy leader, during an election or at war), one with the advisors off ([advisors.md](advisors.md)); not polled |
| The refresh | every minute, reading and writing every kingdom and its due queues, plus scores, history and elections; once per history mark, `universe_stats` for the advisors |
| Bots | as many function calls as a player, on the refresh |
| Repeating spy operations | nothing until one is due and a spy attempt is free (found in the kingdom the tick already read). Then two kingdom writes (claim, record), one revealed read for intel, and the spy operation itself (what a player clicking Spy costs). At most one spy attempt's worth per epoch per kingdom, since attempts come back once an epoch |
| Reactive rules | nothing to check: they run on the kingdom the tick is about to write. A war rule makes the tick read the empires once (for every kingdom together); a hangars rule reads the kingdom's training queue, which the tick's population step shares instead of reading it again. A firing rule adds one news write and a notification; a reaction against the sender adds a schedule entry to that write, and then costs what the action does. Every spy operation now writes the target once more (its `events`), about 10 RU |

## Rules

1. **Count round trips.** Before adding a route or a refresh step, count the function app calls it makes. Never call the
   function app inside a loop over kingdoms when one read of a list would do. Read a document once per request and pass
   it down:
   - The shared documents (`state`, `galaxies`, `empires`, `kingdoms`, a galaxy's politics) are read through the getters
     (`_get_state`, `_get_galaxy_info`, ...), which read each at most once per request (`request_cache.py`). Do not read
     them with a raw `REQUESTS_SESSION.get`.
   - The page getters (`_get_settle`, `_get_structures_info`, `_get_mobis`, `_get_engineers`) take the kingdom, its
     queue, the state or the galaxy's politics when the caller already has them. The refresh passes what it has read.
   - If a route reads a document and then decides on it, pass the copy to `occ.update(..., document=copy)` instead of
     letting it read again ([concurrency.md](concurrency.md#writing-an-action), rule 5).
   - A list from the request that turns into reads (ids to look up) is checked against what exists and de-duplicated
     first, so a request costs at most one read per real item, however long the list a script sends
     (`/api/kingdomsinfo`). Such a route also gets a tighter rate limit in `create_app`.
   - Measure, do not guess: `python scripts/profile_calls.py` runs a game of bots in-process (no stack, no Azure) and
     prints the function app calls, Cosmos reads and writes, and bytes written per route and per refresh tick;
     `--sites` shows which function made each call. `tests/test_efficiency.py` pins the counts for the hot paths.
2. **Write less.** Writes cost ten times reads. Batch eventual writes (several news lines in one append). Do not write a
   document that did not change. Derived data (scores, aggregates) is computed by the refresh, never written by actions.
3. **Keep documents small.** A write costs more the bigger the document. Trim lists that grow forever (news, history),
   and do not put large blobs in the kingdom document. Build queues are folded for this reason.
4. **Poll less, push more.** Prefer a websocket push or refetching after an action over a new polling interval. Do not
   shorten an existing interval.
5. **Keep dev and test traffic off Azure.** Local work and tests use the emulator or the in-memory fake. Nothing local
   points at the Azure account, because it shares production's request units.
6. **No new paid services or tier changes without asking.** That includes Service Bus, Redis, SignalR or Web PubSub,
   Application Insights beyond the free allowance, a paid App Service plan, autoscale, or more Cosmos throughput. When one
   is needed, write down the monthly cost and the free alternative considered.
7. **Say the cost in the pull request.** One line: "No new calls", or "Adds 2 function calls per Attack page load", or
   "Adds a write per kingdom per refresh".

## Cheaper directions worth knowing

- One storage module in Flask ([architecture.md](architecture.md#target-one-storage-module)) makes it possible to batch
  reads, and to measure a backend without the function app's network hop and execution per call. Whether to change the
  backend is the maintainer's call ([why there is a function app](architecture.md#why-there-is-a-function-app)).
- Fewer, larger reads: a single route that returns what a page needs, instead of a page firing many keys.
- Linux Consumption is being retired by Azure (announced for 2028-09-30); its replacement (Flex Consumption) is priced
  differently. Check it before the move.
