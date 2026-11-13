# untitled-project

A long-running, real-time, team-based space strategy game played in the browser ("Cloud Web App Fun"). Players run a
**kingdom** inside a **galaxy** (their team), galaxies belong to an **empire**, and everyone shares one **universe**.
Kingdoms build, attack, spy, rob, trade and vote. The design tenets are in [untitled_project.txt](untitled_project.txt)
and summarized below. Solo-maintained personal project with no live users, so a broken deploy is low stakes, but still
fix it.

## Working here

- **Repo location:** `C:\dev\untitled-project`. An old copy in OneDrive is stale. Never read or edit it.
- **Workflow:** branch, commit, open a PR, merge. Each PR is squash-merged. Do not commit straight to `main`.
- **Every push to `main` deploys to production** (GitHub Actions to Azure App Service). Check the Actions run after
  merging and fix a failed deploy.
- **Never commit secrets.** `api/.flaskenv` and `funcapp/local.settings.json` hold real keys and are git-ignored, along
  with the SQLite and Azurite files. Do not print their values.
- **Tests are safe by default, destructive with `USE_EMULATOR=1`.** The default backend is in-memory
  ([tests/fake_backend.py](tests/fake_backend.py)). With `USE_EMULATOR=1` the `setup` fixture in
  [tests/conftest.py](tests/conftest.py) calls `/deleteall` on the function app before every test, wiping whatever Cosmos
  container it points at. Only do that when `COSMOS_ENDPOINT` in `funcapp/local.settings.json` is
  `https://localhost:8081` (the local emulator), never the Azure account.
- **Windows machine.** Use PowerShell. After installing tools, refresh `PATH` from the Machine and User environment
  variables, because older terminals will not see them. Python lives in Conda environments, and `conda`, `python` and
  `node` may not be on `PATH`.
- Dependencies were upgraded on 2026-11-10 (Flask 3, SQLAlchemy 2, flask-praetorian 1.6, wrapt 1.16, limits 3.13). The old `limits==3.5.0`/`wrapt==1.12.1` pairing is gone. If the Flask env is stale, recreate it from `requirements.txt`.
- Python is 3.10 everywhere (CI, Azure, local). Node is only used for the React build.

## Architecture

| Layer | Stack | Location | Local port |
|---|---|---|---|
| Frontend | React (Create React App), react-bootstrap, primereact, victory | `src/` | 3000 |
| API | Flask, SQLAlchemy, flask-praetorian (JWT), Flask-Sock, Flask-Limiter | `api/untitledapp/` | 8000 |
| Game state | Azure Functions (Python v2 model) over Cosmos DB | `funcapp/function_app.py` | 7071 |
| Infra | Terraform | `iac/` | n/a |
| Deploy | GitHub Actions, then Azure App Service | `.github/workflows/` | n/a |

**Request flow:** browser, then Flask `/api/*` (the React dev server proxies `/api` and `/ws` to port 8000 through
[src/setupProxy.js](src/setupProxy.js)), then the function app at `AZURE_FUNCTION_ENDPOINT` using
`requests` (`REQUESTS_SESSION`), then Cosmos DB.

- **Flask owns identity and rules.** `User` rows (login, roles, `kd_id`, `kd_death_date`) and a `Locks` table live in
  SQLite (`SQLALCHEMY_DATABASE_URI`). Game logic is in blueprints: `account`, `admin`, `build`, `conquer`, `getters`,
  `misc`, `politics`, `refresh` (about 109 routes). `refresh.py` is the real-time tick and scheduled-action logic.
  `shared.py` holds helpers shared by the blueprints. Decorators `alive_required`, `start_required` and
  `before_start_required` gate routes on kingdom and game state.
- **The function app owns game state.** It is a thin HTTP layer (69 routes) over a single Cosmos container, one
  document per item (`state`, `scores`, `galaxies`, `empires`, `kingdom_<id>`, `news_<id>`, `revealed_<id>`,
  `attack_history_<n>`, and so on). Partition key is `/id`. Database and container come from `COSMOS_DATABASE_NAME` and
  `COSMOS_CONTAINER_NAME`.
- **Startup coupling:** with the real config, `create_app` calls the function app's `/accounts` to sync users into
  SQLite, so **the function app must be running before Flask starts**.
- **Email:** `untitledapp/mailer.py` (smtp, console or memory backend) and the account recovery routes in `account.py`. See [docs/email.md](docs/email.md).
- **Real-time push:** clients open a websocket at `/ws/listen` and register their JWT. `SOCK_HANDLERS` maps `kd_id` to
  the open socket.
- **Frontend:** pages in `src/pages/*`, auth in `src/auth`, shared components in `src/components`. In production, Flask
  serves the built frontend from `build/`. See "Frontend conventions" below.
- **Config:** [api/config.py](api/config.py) has `Config` (environment variables) and `TestingConfig` (SQLite
  `pytest.db`, function app at `http://localhost:7071/api`, SQLite users `admin`/`user1`/`user2`).

## Frontend conventions

- **Adding a page:** one entry in [src/routes.js](src/routes.js). The router and the sidebar both read it, so there is
  nothing else to wire. Game pages get `{data, loading, updateData}`; add `props: (context) => ({...})` for anything else.
- **Tables:** `GameTable` ([src/components/gametable.js](src/components/gametable.js)) from column definitions, not
  hand-written `<tr>`s. **Forms:** `useFormValues`, `NumberField`, `SubmitButton`
  ([src/components/forms.js](src/components/forms.js)). **Results of an action:** `ResultToasts`
  ([src/components/results.js](src/components/results.js)). **Numbers:** [src/format.js](src/format.js).
- **Check before sending:** [src/validation.js](src/validation.js) mirrors what the server enforces so the player sees why
  a request would fail, as a red message under the field and the button's tooltip, before it is sent. The server still
  decides. [src/pages/build/structures.js](src/pages/build/structures.js) is the model; military, projects, attack, spy,
  launch missiles, schedule and politics forms are not converted yet.
- **CSS:** shared layout classes and tokens are in [src/styles/shared.css](src/styles/shared.css) (`col-center`,
  `box-tight`, `game-table`, ...). Put a rule in a page stylesheet only if it is particular to that page. Before adding a
  rule, check it is not already a shared class.
- **Number inputs for amounts:** `AmountInput` (forms.js) is a slider with the number chosen on its left and the most on its right (press it to fill it in); give it the most that can be done. `box` adds a number box and a Max button, used on the planner pages where the exact number matters. **Planning pages** (Attack, Spy, Primitives, Share Intel, Schedule) are built from `Panel`, `FieldRow`, `Stats`, `VersusBar` and `Picker` in [src/components/planner.js](src/components/planner.js), with a forecast that follows the inputs and a confirm step before anything is sent.
- **Icons:** `react-icons`, shown through `IconButton` (name in the tooltip and the accessible label).
- **Tests:** Jest, next to the code (`npm test`). `src/setupTests.js` stubs `matchMedia`. Mock `components/header` and
  `components/helpbutton` when testing a page, and set mock implementations in `beforeEach` (Create React App resets mocks).
- [docs/ux-review.md](docs/ux-review.md) has the page-by-page UX review and proposals.

## Running locally

Start the pieces in this order. Each needs its own long-running process.

1. **Cosmos emulator:** `Microsoft.Azure.Cosmos.Emulator.exe /NoUI /NoExplorer` (installed under
   `C:\Program Files\Azure Cosmos DB Emulator`). Poll `/GetStatus` until it exits with code 2 (running).
2. **Azurite:** `azurite --silent --location C:\dev\azurite --skipApiVersionCheck`.
3. **Seed the emulator:** `python scripts/seed_cosmos_emulator.py` (report only), then `--apply` or
   `--apply --replace`. It reads the Azure container (read-only) and writes only to the emulator.
4. **Function app:** `func host start` from `funcapp/` (Azure Functions Core Tools 4).
5. **API:** `flask run -p 8000` from `api/` (needs `FLASK_APP=run` and the rest of `api/.flaskenv`).
6. **Frontend:** `npm start` from the repo root.

Conda environments under `C:\Users\bcope\miniconda3\envs\`:
- `funcapp`: Python 3.10 with `requirements.txt`, for Flask and pytest.
- `funcapp-worker`: Python 3.10 with `funcapp/requirements.txt`, for the function app worker and the seed script. It is
  kept separate from the Flask environment's pinned packages.

The admin login password is `ADMIN_PASSWORD` in `api/.flaskenv`. It is only applied when no `admin` row exists, so
after copying an old `database.db` it may not match, and the hash in SQLite must be updated.

## Tests

`python -m pytest tests -n 4` from the repo root, in the `funcapp` environment after `pip install -r requirements-dev.txt`.
The backend tests run the function app's real handlers in-process on an in-memory Cosmos stand-in
([tests/fake_backend.py](tests/fake_backend.py)), so no emulator, function host or Azurite is needed (about 30 seconds).
`USE_EMULATOR=1` runs them against the real stack instead (slow, and it wipes the emulator; see "Tests are destructive").

- **Function app tests:** `python -m pytest funcapp/tests` in the `funcapp-worker` environment (no stack needed).
- **Frontend tests:** `CI=true npm test -- --watchAll=false`. CI runs these before every build, so a failure blocks the
  deploy. CI does not run the Python tests.
- **Concurrency check:** `python scripts/check_concurrency.py` against the running function app (writes to the emulator).
- Race tests (`test_concurrency`, `test_attack`, ...) rely on the fake container's small random latency to make requests overlap. Do not set `FAKE_LATENCY=0`.

## Design philosophy

From [untitled_project.txt](untitled_project.txt). Use these to judge whether a feature belongs.

- Games are long term (rounds can run a day, a week, or a month). Strategy beats activity: one login every 12 hours
  with a good plan should stay competitive.
- Real time, with ticks of at most one second or continuous formulas.
- Several playstyles (attacker, defender/expander, thief, support, leader). Teams outperform individuals.
- Three tiers of politics: local (galaxy), regional (empire) and universal (all players, with votes that can be
  bought).
- Clear, relevant information at every decision point, but moderate obscurity (fog of war, reveal timers) so outside
  tools cannot beat human judgment. If information is only reachable through an external program, make it available to
  everyone or no one.
- Minor comeback mechanics, plus early game-end if someone runs away with it. Leaderboards reward mid-round
  contribution over end-of-round snapshots.
- Simplicity over complexity: only add a feature if it is a net positive for the other tenets.
- Not for v1.0: a graphical UI and built-in chat.

## Code conventions and gotchas

- Mirror the existing style: blueprint routes use `@bp.route`, `@flask_praetorian.auth_required`, and usually
  `@alive_required`/`@start_required`. State reads and writes go through `REQUESTS_SESSION` calls to the function
  app, with the `x-functions-key` header taken from `AZURE_FUNCTION_KEY`.
- `getters.py` and `conquer.py` are large (1300 and 3000 lines). Search before adding a helper, since `shared.py` and
  `getters.py` already hold many.
- Most routes make several round trips to the function app, so avoid adding more inside loops.
- **Actions that spend or change state must not use read-then-write.** Use `occ.update(path, decide)` from
  `api/untitledapp/occ.py`: validate inside `decide` (which can run more than once, so no side effects), and the write
  only lands if the document is unchanged since it was read. The old SQLite locks (`acquire_lock`) are per server and
  being phased out; migrated routes keep them for now. Read [docs/concurrency.md](docs/concurrency.md) first.
- Function app `update_*` handlers must stay single-write (one `replace_item`) so `@retry_on_conflict` can re-run them.
  `funcapp/` is published by hand, not by CI.
- Build queues are folded on every append (`funcapp/queues.py`): finish times are rounded up to a grid of 0.1% of the epoch
  (`QUEUE_MERGE_FRACTION` of `EPOCH_SECONDS`, 1.8 s) and entries sharing a time are summed. Nothing finishes early, nothing is
  more than one window late, and re-folding never moves anything. Queue entries have no identity beyond their time, and
  must not carry extra keys (the refresh treats every key but `time` as a unit or structure name).
- `adhoc/` is for one-off scripts. Reusable tooling goes in `scripts/`.
- `iac/terraform.tfstate` and `funcapp/__azurite_*` are local state, not source.
- Known tech debt: Python 3.10 is end-of-life, the CRA toolchain is old, and GitHub reports many Dependabot alerts on `main`.
