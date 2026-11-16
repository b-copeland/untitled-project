# Status: what is in flux

The one place for things that are unfinished, known to be wrong, or about to change. The other docs describe the rules
and the target; this says how far the code is from them. Date every entry you add, and remove it when it is done.

## Concurrency migration

From [concurrency.md](concurrency.md). Updated 2026-11-14.

| Area | Status |
|---|---|
| Function app: the single-document `update_*` handlers | Conditional and retried |
| Function app: `create_kingdom`, `create_empire` | The new id, and joining the galaxy, are conditional writes on `kingdoms`, `empires` and `galaxies` (`change_document`); the documents they then create are new. |
| Function app: other multi-document admin handlers (`create_galaxy`, `reset_state`, `delete_all`, `init`) | Not changed. Admin and setup only. |
| Every action route (build, shields, spending, kingdom setup, votes, attacks, primitives, spying, robbing, missiles, schedules, shared intel, politics, empires, surrender, auto attack and rob settings) | Conditional (`occ.update`) or commutative (appends and merges). |
| The refresh: the kingdom write, schedules, siphons, revealed and shared expiry, scores, empires, queue trims | Conditional, with `queues_resolved_until` cursors. Schedules are taken off the kingdom with a version-checked write before they run. |
| The refresh: elections and the history mark | Decided on `/state` (`_claim_state`), so an overlapping tick does not open, close or record twice. |
| Kingdom reset (`/api/resetkingdom`) | Overwrites the kingdom's documents with the initial state on purpose (before the game starts). |
| Legacy locks | **Removed** (2026-11-14). `acquire_lock` and the `Locks` model are gone. |
| Outbox and sweep (exactly-once effects, recovery after a crash between the steps of an action) | Not built |
| A write applied but its response lost, then retried | Can duplicate an append. Not seen; the outbox ids would fix it. |

## Parallelism gaps

Code must assume many web processes and instances ([architecture.md](architecture.md#1-design-for-many-processes-on-many-machines)).
These pieces do not yet:

| Piece | Problem | Direction |
|---|---|---|
| The `accounts` document (2026-11-14) | The last copy of the SQLite users. Nothing writes it since users moved to `user_` documents; `adhoc/migrate_users_to_cosmos.py` reads it. `/resetstate` still clears kingdom fields in it, and `GET`/`PATCH /accounts` still exist. | Kept as a backup until the migration has run in production and been checked, then remove the document, the routes, and its place in `/init` and `/resetstate` |
| `SOCK_HANDLERS` (websocket registry) | A push only reaches sockets on the process that raised it. Each open socket also holds a server thread for its lifetime. | A pub/sub service, or polling notifications |
| Rate limiter (`memory://`) | Limits are per process | Shared storage for the limiter |
| The refresh | One request loops over every kingdom in turn. Two overlapping refreshes are safe (every step is version-checked), but one long tick is still one request | Split the tick per kingdom |

## Deployment and operations

- The function app is published by CI (2026-11-14) but the workflow is untested until the maintainer adds the
  `AZUREFUNCTIONS_PUBLISHPROFILE` secret and a merge to `main` runs it ([deployment.md](deployment.md)).
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
- Unused leftovers: `adhoc/service_bus_testing.py`.

## Cost and efficiency

Measured with `scripts/profile_calls.py` on 2026-11-14 (24 bots, in-process backend). Not done, each for the reason given.

- **One user read per authenticated request** (2026-11-14, [decisions/0004](decisions/0004-users-in-cosmos.md) D3):
  `current_user()` reads `user_<id>`, once per request. That doubles the function app calls of the 10-second kingdom
  and notification polls (one call each to two). Removing it means putting the kingdom id in the JWT as a claim, with
  new tokens when it changes and old ones invalid after a round reset; optional, and only with the maintainer's
  agreement.
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
