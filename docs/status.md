# Status: what is in flux

The one place for things that are unfinished, known to be wrong, or about to change. The other docs describe the rules
and the target; this says how far the code is from them. Date every entry you add, and remove it when it is done.

## Concurrency migration

From [concurrency.md](concurrency.md). Updated 2026-11-14.

| Area | Status |
|---|---|
| Function app: the single-document `update_*` handlers | Conditional and retried |
| Function app: multi-document admin handlers (`create_*`, `reset_state`, `delete_all`, `init`) | Not changed. They write several documents and cannot be re-run from the top. Admin and setup only. |
| Own-kingdom routes in `build.py` (structures, recruits, mobis and disband, settle, missiles, engineers, projects, targets, raze), shields, `/api/spending`, `/api/createkingdomchoices`, `/api/votes`, `/api/universepolitics/policies` | On `occ.update`. Still take the legacy lock too. |
| Attacks, primitives, spying, robbing, missiles, schedule add and cancel | Version-checked in steps ([decisions/0002](decisions/0002-attack-sequencing.md)). News, history, reveals and notifications are written the old way. |
| Shared intel, random reveal, galaxy votes, empire requests, invitations, joining and leaving, denounce, declare war | Version-checked |
| The refresh's kingdom write (`_refresh_kd`) | Version-checked, with `queues_resolved_until` cursors |
| **`_resolve_schedules` in `refresh.py`** | **Not migrated.** It reads the kingdom, runs due schedules, and writes the whole kingdom back with no version check, so a change that lands in between (a player action, an attack) can be overwritten. |
| Refresh sub-steps that write other documents (siphons, revealed and shared expiry, scores, empires, history, elections), surrender requests and offers, `create_empire`, kingdom reset, `pinned` | Not migrated. Each takes a legacy lock. |
| Legacy lock framework (`acquire_lock` in `misc.py`, the `Locks` table) | Still in place everywhere. Removable for a document once every writer of it checks its version. |
| Outbox and sweep (exactly-once effects, recovery after a crash between the steps of an action) | Not built |
| A write applied but its response lost, then retried | Can duplicate an append. Not seen; the outbox ids would fix it. |

## Parallelism gaps

Code must assume many web processes and instances ([architecture.md](architecture.md#1-design-for-many-processes-on-many-machines)).
These pieces do not yet:

| Piece | Problem | Direction |
|---|---|---|
| Users and locks in SQLite (2026-11-14: phase-out intended, replacement undecided, not started) | Each instance has its own file. Besides login, SQLite is read by `alive_required` (`kd_death_date`), `/api/kingdomid` (`kd_created`), `_refresh_kd` (`kd_created`), kingdom creation, reset and death (`misc.py`), `account.py`, `admin.py`, `bots.py`, and the lock functions. The `accounts` backup document is one list replaced whole, so two sign-ups at once can lose one. | Where users live is undecided (it must work with flask-praetorian); locks go with the concurrency migration ([architecture.md](architecture.md#target-no-sqlite)) |
| `SOCK_HANDLERS` (websocket registry) | A push only reaches sockets on the process that raised it. Each open socket also holds a server thread for its lifetime. | A pub/sub service, or polling notifications |
| Rate limiter (`memory://`) | Limits are per process | Shared storage for the limiter |
| The refresh | One request loops over every kingdom in turn; two overlapping refreshes are only safe where steps are version-checked | Finish the migration; split the tick per kingdom |
| Kingdom and empire ids | `create_kingdom` and `create_empire` in the function app pick `len(existing)` as the new id, so two creations at once can pick the same id | Conditional write on `kingdoms` / `empires` |

## Deployment and operations

- The function app is published by hand, not by CI. Intended to be automated ([deployment.md](deployment.md)).
- CI runs on pushes to `main` only, not on pull requests, so nothing checks a pull request before it merges. A pull
  request workflow running the same three suites would fix that.
- `scripts/check.ps1` is PowerShell and expects conda; there is no equivalent script for Linux or macOS, only the plain
  commands in [testing.md](testing.md#the-suites).
- The refresh is triggered by a WebJob configured in the portal; its script is not in the repo.
- The web app is on the Free plan with Always On off, which cron-triggered WebJobs need. Missed refreshes are possible.
- `iac/` is the Azure quickstart sample, not a description of production.
- No staging environment.

## Code health

- The function app's handlers catch everything with a bare `except` and answer `500`, which hides throttling (`429`) and
  real errors alike. Several `GET` handlers answer `201`.
- Function app write routes that cannot work (2026-11-14), all uncalled: `PATCH /empire/<id>/news` reads `empire_<id>`
  where the document is `empire_news_<id>`, so empire news is never written; `PATCH /kingdom/<id>/shared` adds a list to
  what is now an object; `/sharedrequests` reads a `shared_requests_<id>` document that is never created.
- `getters.py` and `conquer.py` are large and mix routes, formulas and storage calls.
- Over a hundred raw `REQUESTS_SESSION` calls across the blueprints; the target is one storage module
  ([architecture.md](architecture.md#target-one-storage-module)).
- Some pages keep their own copies of lists the server has (`STRUCTURES` in `src/pages/build/structures.js`).
- Python 3.10 reached end of life in October 2026. The Create React App toolchain is old. GitHub reports many
  Dependabot alerts on `main`.
- Unused leftovers: `/api/register` and `/api/finalize` in `account.py`; `adhoc/service_bus_testing.py`.

## Cost and efficiency

Measured with `scripts/profile_calls.py` on 2026-11-14 (24 bots, in-process backend). Not done, each for the reason given.

- **The legacy SQLite locks are most of the refresh's CPU** (about 70% of its Python time: each `acquire_lock` and
  `release_lock` is a SQLite commit, several per kingdom per tick). The web app's Free plan has a daily CPU quota.
  Removing a lock needs the maintainer's agreement and every writer of that document to be version-checked (see
  [Concurrency migration](#concurrency-migration)).
- **Lists that grow all round:** kingdom, galaxy and universe news, attack, spy and missile history, and the kingdom
  `history` are appended to and never trimmed (messages are capped at 100). Every append rewrites the whole document,
  so writes cost more as a round goes on. Capping them changes what players can see, so it needs a decision.
- **One read per kingdom shown:** the Galaxy page (`/api/galaxy/<id>`) and `/api/kingdomsinfo` read each kingdom with
  its own function app call. A batch read would make it one call, but the function app's rule is one document per
  route; this is what the storage module ([architecture.md](architecture.md#target-one-storage-module)) would allow.
- **Siphons are read on every tick for every kingdom** (`siphons_in` and `siphons_out`, two calls), almost always to
  find them empty. Skipping them needs a marker on the kingdom document, which is a document shape change.

## Frontend

- Not converted to check-before-sending: the politics forms.
- UX proposals not built: see [decisions/0003-ux-review.md](decisions/0003-ux-review.md#proposed-not-built).

## Bots

See [bots.md](bots.md) for what bots do not do yet and the open questions.
