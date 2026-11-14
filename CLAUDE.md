# untitled-project

A long-running, real-time, team-based space strategy game in the browser. Players run a **kingdom** inside a **galaxy**
(their team); galaxies form **empires**; everyone shares one **universe**. Kingdoms build, attack, spy, rob, trade and
vote. Solo-maintained personal project with no live users and no funding: a broken deploy is low stakes but still gets
fixed, and anything that costs money needs the maintainer's agreement.

This file is the rules and the map. The detail is in `docs/`. Read the doc for your task before you start.

## Read first

| Task | Read |
|---|---|
| Any change | This file, then [docs/architecture.md](docs/architecture.md) |
| Designing a feature or changing a rule | [docs/game-design.md](docs/game-design.md): tenets in priority order, glossary, "does it belong" checklist |
| A route, a refresh step, a page, a document, a constant | [docs/recipes.md](docs/recipes.md): step-by-step checklists |
| Anything that writes game state | [docs/concurrency.md](docs/concurrency.md) |
| Document shapes and how the function app writes them | [docs/data-model.md](docs/data-model.md) |
| A page or form | [docs/ux.md](docs/ux.md) |
| Testing, and when a change is done | [docs/testing.md](docs/testing.md) |
| Anything that adds requests, writes or services | [docs/cost.md](docs/cost.md) |
| What is unfinished or known broken | [docs/status.md](docs/status.md) |
| Why something is the way it is | [docs/decisions/](docs/decisions/README.md) |
| Running locally, deploying, bots, email | [docs/development.md](docs/development.md), [docs/deployment.md](docs/deployment.md), [docs/bots.md](docs/bots.md), [docs/email.md](docs/email.md) |

`api/`, `funcapp/` and `src/` each have their own `CLAUDE.md` with the rules for that layer.

## The architecture in brief

Browser → Flask `/api/*` (rules, identity, `api/untitledapp/`) → function app over HTTP (storage only, `funcapp/`) →
Cosmos DB (one container, one document per item). A scheduled call to `/api/refreshdata` is the game tick. The React
frontend (`src/`) gets each data key from its own route and reads game constants from `/api/state`.

## Hard rules

1. **Never commit secrets.** `api/.flaskenv` and `funcapp/local.settings.json` hold real keys and are git-ignored. Never
   print their values.
2. **Never point local work or tests at the Azure Cosmos account.** It shares request units with production. Use the
   emulator or the in-memory test backend.
3. **Branch, pull request, squash-merge.** Never commit to `main`: every push to `main` deploys to production.
4. **Design for many processes on many machines.** No game state in process memory or on local disk, and no new
   `acquire_lock` calls. SQLite is legacy and being phased out: add nothing to it (no tables, no columns, no new
   queries of `User` in game logic).
5. **Decide against the current document.** An action that spends or changes state uses `occ.update(path, decide)`,
   never read-then-write.
6. **The server decides what a player sees.** Never return another kingdom's data without filtering it by what the
   caller has revealed.
7. **One home per rule.** Game numbers live in `shared.py`; forecasts come from the API. Do not copy them elsewhere.
8. **Ask before** changing balance numbers or the tenets, adding a paid service or tier, changing a document's shape in
   a way existing data must migrate to, removing legacy locks, or touching anything in Azure.

## Top 10 pitfalls

1. **Read, decide, write without a condition.** Two overlapping requests both pass the check: one payment, two builds.
   Use `occ.update`. Validation goes inside `decide`, and `decide` has no side effects because it can run several times.
2. **Partial nested objects.** The kingdom PATCH is a shallow merge: sending `{"next_resolve": {"structures": t}}`
   replaces all of `next_resolve`. Write the whole nested object.
3. **State in one process.** A dict or cache only exists in the process that wrote it, and a SQLite row only on the
   machine that wrote it. Shared state goes in a Cosmos document.
4. **Leaking hidden information.** A field in an API response is visible to scripts even if the UI hides it. Filter with
   `_get_max_kd_info` in `getters.py`. Its `max=True` skips the filter: use that only for server-side calculations,
   never for data that goes into a response.
5. **Game math in two places.** The frontend reads `data.state.game_config` and asks the API for forecasts.
   `src/validation.js` mirrors only simple limits, and must change when the server's limits change.
6. **Function app calls in loops.** Each call is a function execution and Cosmos request units on a free tier shared
   with production. Count the round trips a change adds.
7. **New fields on old kingdoms.** Kingdoms created before a change do not have the new field. Read it with
   `.get(field, default)`; a `KeyError` in the refresh skips that kingdom on every tick.
8. **Extra keys on queue entries.** The refresh credits every key except `time`. Entries carry only `time` and counts.
9. **Counting ticks.** The refresh can run late, or twice. Compute from elapsed time and use cursors
   (`queues_resolved_until`) so nothing is credited twice.
10. **`USE_EMULATOR=1` wipes data.** The test setup calls `/deleteall` on whatever container the function app points at.
    Only with `COSMOS_ENDPOINT` set to `https://localhost:8081`.

## Workflow

- Before a pull request, run the three test suites (backend, function app, frontend; no stack needed):
  `.\scripts\check.ps1` on Windows, or the plain commands in [docs/testing.md](docs/testing.md#the-suites) anywhere.
  CI runs the same suites only after merge, on `main`, and a failure stops the deploy.
- A change is done when the definition of done in [docs/testing.md](docs/testing.md#definition-of-done) is met: tests
  added, help page and docs updated, UI checked in a browser (or the pull request says it was not).
- After merging, check the GitHub Actions run and fix a failed deploy.
- The function app is published separately from the web app (see [docs/deployment.md](docs/deployment.md)). Say in
  the pull request when a `funcapp/` change must go out first.
- Pull request descriptions say what was tested, what was not, the cost impact (one line), and anything the maintainer
  must do.

## Environment

- Python 3.10 everywhere, in two separate environments because their pins conflict: one for Flask and pytest
  (`requirements.txt` plus `requirements-dev.txt`), one for the function app (`funcapp/requirements.txt`). Node is only
  for the React build and its tests.
- The docs write commands for the maintainer's setup: Windows, PowerShell, and conda environments named `funcapp` and
  `funcapp-worker`. CI is Ubuntu with pip and virtual environments. On another setup, run the same `pytest` and `npm`
  commands in your own two environments. Anything particular to one machine (paths, where tools are installed) does not
  belong in this file or in `docs/`.
- Running locally needs, in order: Cosmos emulator, Azurite, the function app (`func host start` in `funcapp/`), Flask
  (`flask run -p 8000` in `api/`), `npm start`. Nothing advances game time locally unless you call `/api/refreshdata`.
  Full steps and troubleshooting: [docs/development.md](docs/development.md).
- `adhoc/` is for one-off scripts; reusable tooling goes in `scripts/`. `iac/terraform.tfstate` and
  `funcapp/__azurite_*` are local state, not source.

## Keeping the docs true

The docs are how the next person, or model, learns the rules, so a wrong doc is a bug.

- When you change behaviour a doc describes, update the doc in the same pull request.
- Rules go in the topic docs; anything unfinished or temporary goes in [docs/status.md](docs/status.md), dated. No
  counts or dates in rule docs: they go stale.
- A significant decision with rejected alternatives gets a record in `docs/decisions/`.
- `tests/test_docs.py` fails when a doc links to or names a file that does not exist, or when the data model misses a
  kingdom field.
