# Architecture

How the pieces fit, the rules every change must keep, and the direction the code is moving in. For what is unfinished
right now, see [status.md](status.md).

## The pieces

| Layer | Stack | Location | Local port |
|---|---|---|---|
| Frontend | React (Create React App), TanStack Query, react-bootstrap | `src/` | 3000 |
| API and game rules | Flask, SQLAlchemy, flask-praetorian (JWT), Flask-Sock, Flask-Limiter | `api/untitledapp/` | 8000 |
| Game state store | Azure Functions (Python v2 model), a thin HTTP layer over Cosmos DB | `funcapp/` | 7071 |
| Database | Cosmos DB (NoSQL API), one container, partition key `/id` | Azure, or the local emulator | 8081 |
| Deploy | GitHub Actions to Azure App Service | `.github/workflows/` | |

```
browser ──/api/*, /ws──▶ Flask (rules, identity) ──HTTP, x-functions-key──▶ function app (CRUD) ──▶ Cosmos DB
   ▲                        │
   └──── websocket push ────┘        a scheduler ──GET /api/refreshdata──▶ Flask (the game tick)
```

- **Flask owns the rules.** Every decision (can you afford it, does the attack win, what does the player see) is made in
  `api/untitledapp/`. Blueprints: `account`, `admin`, `build`, `conquer`, `getters`, `misc`, `politics`, `refresh`.
- **The function app owns storage, nothing else.** Each route reads or writes one Cosmos document. It does no game
  logic. Its `update_*` handlers merge or append into the newest version of the document (see [data-model.md](data-model.md)).
- **Identity is in SQLite, for now.** `User` rows (login, roles, `kd_id`) live in a SQLite file on the web server, and are
  copied to the `accounts` document as a backup. At startup Flask calls the function app's `/accounts` to fill SQLite, so
  the function app must be up before Flask starts. This is legacy and breaks rule 1 below; see
  [Target: no SQLite](#target-no-sqlite).
- **The game tick.** Nothing advances on its own. Something must call `GET /api/refreshdata` with the `Refresh-Secret`
  header (in production a scheduled job every minute). The refresh credits income and finished queues, runs scheduled
  actions and auto actions, updates scores, history and elections. See `refresh.py`.
- **The frontend** fetches each data key (`kingdom`, `structures`, ...) from its own `/api/<key>` route
  (`src/data/gameData.js`), polls the kingdom every 10 seconds, and refetches what an action changed. Game constants come
  from the server (`data.state.game_config`, `data.state.pretty_names`), not from copies in the browser.
- **Live notifications** use a websocket at `/ws/listen`. `SOCK_HANDLERS` maps a kingdom to its open socket.

## Rules every change keeps

### 1. Design for many processes on many machines

Assume several web processes and several function app instances are serving requests at the same moment, and any two
requests can overlap. Concretely:

- **No game state in process memory or on local disk.** No module-level dicts, caches or counters that hold game data,
  and nothing new in SQLite. Constants are fine. If something must be shared, it goes in a Cosmos document. The one
  cache is `request_cache.py`, and it lives on `flask.g` for a single request: the shared documents (`state`,
  `galaxies`, `empires`, `kingdoms`, galaxy politics) are read at most once per request, and the request's own writes
  drop its copy. Nothing in it outlives the request, so it holds no state between requests or processes.
- **Every change to a document is either conditional or commutative.** Conditional: decide against the document and
  write only if it is unchanged (`occ.update`, see [concurrency.md](concurrency.md)). Commutative: an append or a merge the
  function app applies to the newest version (`new_news`, `new_structures`, ...). A plain "read, change, write back" with
  no condition loses updates.
- **Background work is safe to run twice at once.** The refresh can overlap itself, and a retried request can run again.
  Use cursors and ids so nothing is credited twice (see `queues_resolved_until` in `refresh.py`).
- **Do not add new `acquire_lock` calls.** The SQLite locks only work inside one process. They remain on older routes until
  every writer of a document is migrated ([status.md](status.md)).

Pieces that still assume one process or one machine, and so are known gaps: SQLite (users and locks), `SOCK_HANDLERS`,
and the rate limiter's `memory://` storage. Do not build on them, and do not copy their pattern.

### 2. The server decides what a player can see

The game hides information on purpose (fog of war, reveal timers). Anything in an API response can be read by a script,
so hiding a field in the UI is not hiding it. A route that returns another kingdom's data must filter it through what the
caller has revealed: `_get_max_kd_info` in `getters.py` holds the whitelist of fields per reveal category. Calling it
with `max=True` returns the whole kingdom, which is for server-side calculations (an attack's real outcome) and must
never reach a response. Bots follow the same rule: they decide only from what a player in their position could see.

### 3. Rules live in one place

- Game numbers live in `shared.py` (`GAME_CONFIG`, `GAME_FUNCS`, `UNITS`, `PROJECTS`, ...). Never repeat a number in
  another file. The frontend reads them from `/api/state`.
- Forecasts (offense, losses, success chances, costs) are computed by the API and shown by the page. The browser does not
  re-derive game math. The one exception is `src/validation.js`, which repeats simple limits ("at most N") so a form can
  say no before sending. The server still decides.
- Formulas are plain functions of their inputs (dicts in, numbers or dicts out), with no Flask, HTTP or Cosmos inside.
  That keeps them testable and portable.

### 4. One action, one decision point

An action that spends or changes something picks the one document that holds what is at stake (usually
`kingdom_<id>`) and makes its decision there, with `occ.update`. Everything else it causes (news, history,
notifications, queue entries) is written after, as appends. See the tiers in [concurrency.md](concurrency.md).

## Portability

The project should be able to move to another cloud, database or web framework without rewriting the game. The seams:

| Concern | Today | Portable rule |
|---|---|---|
| Storage access | Blueprints call the function app directly through `REQUESTS_SESSION` (over a hundred call sites) | New code goes through a small number of helpers (`occ.read`, `occ.update`, and the getters in `getters.py`). The target is one storage module, see below. |
| Optimistic concurrency | Cosmos `_etag` with `If-Match` | Every serious store has the same thing: Postgres row versions, DynamoDB conditional writes, Firestore preconditions. Keep the `decide` pattern, never the Cosmos details, in game code. |
| Game rules | `shared.py` constants and formulas spread through the blueprints | Pure functions with no framework imports. |
| Azure SDKs | Only in `funcapp/` | Keep it that way. Nothing in `api/` imports `azure.*`. |
| Identity | flask-praetorian over a SQLAlchemy `User` in SQLite | Game code needs only `current_user().kd_id`. Keep it to that, so the user store can move. |
| Scheduling | An App Service WebJob calls `/api/refreshdata` (configured in the portal) | The tick is a plain authenticated HTTP call, so any scheduler works. |
| Configuration | Environment variables (`api/config.py`, function app settings) | Keep it that way. No settings in code, no cloud-specific config files read by game code. |
| Secrets | `api/.flaskenv`, `funcapp/local.settings.json`, App Service settings | Environment only. |

### Target: one storage module

A module (call it `store.py`) that is the only way Flask code reads or writes game state:

```python
store.get("/kingdom/1")                       # one document
store.update("/kingdom/1", decide)            # conditional, what occ.update does today
store.append("/kingdom/1/news", [item, ...])  # commutative append
```

Behind it sits one backend, today the function app over HTTP. This does not exist yet. Until it does, new code uses
`occ.read` and `occ.update` and the existing getters, and adds a raw `REQUESTS_SESSION` call only where no helper exists
(queue appends, news).

### Why there is a function app

Three responsibilities are kept apart on purpose: **Flask decides** (game rules), **Cosmos stores**, and a **storage
layer** between them knows how documents are read and written (merge, append, conditional write, queue folding). Either
side can then be replaced by changing only the storage layer. The function app is that layer, and it scales separately
from the web server. Keep to it: no game rules in `funcapp/`, no Cosmos details in `api/`.

Two things to know when working with it:

- **The separation comes from the interface, not from the network hop.** Today the interface is dozens of HTTP routes
  called from over a hundred places, each building its own URL and headers, so swapping the layer would mean reproducing
  every route or editing every call site. `store.py` is what makes the swap real: one module in front, any backend
  behind (the function app, a database SDK called in-process, another database). The in-memory test backend
  (`tests/fake_backend.py`) already shows a second backend is possible.
- **The hop has costs.** Each document read or write is a network round trip and a function execution; the Consumption
  plan has cold starts; `funcapp/` deploys separately and must go out first; and the handlers do merging and I/O, not
  game computation, so little CPU moves off the web server. This is why round trips are counted ([cost.md](cost.md)).

Whether the backend behind `store.py` stays the function app is the maintainer's call, best made by measuring once
`store.py` exists. Do not move storage calls into Flask without asking.

### Target: no SQLite

SQLite holds the `User` rows and the legacy `Locks` table, in a file on one machine. That contradicts rule 1, so it is
being phased out. Progress is in [status.md](status.md#parallelism-gaps).

- **Locks** go when the concurrency migration finishes.
- **Users: undecided.** The replacement must work with flask-praetorian (the login and JWT framework), which expects a
  user model backed by a database. Options to weigh: a shared SQL database that SQLAlchemy can use unchanged; or users
  in Cosmos behind a small user class (praetorian itself only calls `lookup`, `identify`, `identity`, `rolenames`,
  `password` and `is_valid` on it, but this has not been tried). Do not start either without asking.

Until then: add nothing to SQLite, and in game code take `kd_id` from `flask_praetorian.current_user()` and nothing else
new from `User`.

## Where things are

| Area | Files |
|---|---|
| Kingdom creation, shields, messages, spending, sharing, notifications | `misc.py` |
| Settling, building, training, projects, missiles | `build.py` |
| Attacks, spying, primitives, missiles launched, schedule, shared intel, pinned | `conquer.py` |
| Galaxy, empire and universe politics, votes, war, surrender | `politics.py` |
| Read routes (`/api/kingdom`, `/api/structures`, ...) and the calculations they share | `getters.py` |
| The tick | `refresh.py` (`refresh_data` calls `_refresh_kd` per kingdom) |
| Constants, formulas, initial kingdom | `shared.py` |
| Optimistic concurrency helper | `occ.py` |
| Bots (archetypes, also the quick starts on Create Kingdom) | `bots.py`, [bots.md](bots.md) |
| Route decorators `alive_required`, `start_required`, `before_start_required`, app factory, websocket | `api/untitledapp/__init__.py` |
| Email | `mailer.py`, [email.md](email.md) |
| Function app routes, conditional writes, queue folding | `funcapp/function_app.py`, `funcapp/concurrency.py`, `funcapp/queues.py` |

`getters.py` and `conquer.py` are large. Search them (and `shared.py`) for an existing helper before writing a new one.
