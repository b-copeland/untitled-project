# Testing

How to know a change works. Short version: run the three suites before every pull request, and add a test that would
have failed without your change.

## The suites

| Suite | Where | Needs | Command | Time |
|---|---|---|---|---|
| Backend | `tests/` | Nothing running. The function app's real handlers run in-process on an in-memory Cosmos stand-in (`tests/fake_backend.py`). | `python -m pytest tests -n 4` in the Flask environment | under a minute |
| Function app | `funcapp/tests/` | Nothing running | `python -m pytest funcapp/tests` in the function app environment | seconds |
| Frontend | `*.test.js` next to the code | Nothing running | `npm test -- --watchAll=false` with `CI=true` set | under a minute |
| All three | | | `.\scripts\check.ps1` (or `-Only backend`): Windows, PowerShell, conda | |

All commands run from the repository root. The two Python environments are described in
[development.md](development.md#2-install-dependencies); with conda, prefix the Python commands with
`conda run -n funcapp` and `conda run -n funcapp-worker`. In PowerShell, `CI=true` is `$env:CI = 'true'`.

CI runs all three on every push to `main`, and a failure stops the deploy. CI does **not** run on pull requests, so run
them yourself before merging.

Slower checks, when the change calls for them:

| Check | When | How |
|---|---|---|
| Against the real stack | A change to how Flask talks to the function app, or to Cosmos behaviour the fake may not copy | `$env:USE_EMULATOR=1` with the emulator and function app running. **It wipes the container the function app points at**, so only with `COSMOS_ENDPOINT` set to `https://localhost:8081`. About 11 minutes; reseed afterwards. |
| Rare races | A change to a concurrent path | `$env:STRESS_ROUNDS = 20` then `pytest tests/test_stress.py` |
| Concurrency against Cosmos | A change to `funcapp/concurrency.py` | `scripts/check_concurrency.py` against the running function app |
| In the browser | Any UI change | The local stack ([development.md](development.md)), at desktop and phone width |

## What to test, by kind of change

| You changed | Add or run |
|---|---|
| A formula or validation helper | A unit test of the function with plain inputs, including the edges (zero, the maximum, one over) |
| An action route | The success case, each rejection message, the documents afterwards, and a race test: several identical requests with `_run_together`, exactly one succeeds and the kingdom is charged once |
| A read route | The response for your own kingdom, and that hidden fields are absent for a kingdom you have not revealed |
| The refresh | Run it at two times and compare with one run at the later time; run it twice at the same time and check nothing is credited twice |
| A function app handler | In `funcapp/tests`: append and replace both land, and concurrent calls lose nothing |
| A page or component | A Jest test: what it shows for given data, the blocked reason on the button, the request body it sends |
| A doc | `tests/test_docs.py` checks that links and code paths exist and that the data model lists every kingdom field |
| Bot archetypes | `tests/test_bots.py` checks each archetype is legal by the same validators as the routes |

## Writing backend tests

- Fixtures in `tests/conftest.py`: `app`, `client`, `jwt1` and `jwt2` (tokens for `user1`, who owns kingdom `"1"`, and
  `user2`, who owns `"2"`). Every test starts with an empty container.
- Helpers in `tests/test_concurrency.py`: `_set_up_kingdom(money, kd_id="1", **overrides)` creates a started game and a
  kingdom; `_create_item(id, state)` writes any document; `_get(path)` reads one through the function app;
  `_run_together(app, count, request)` starts several requests at the same instant. `tests/test_attack.py` has
  `_set_up_two_kingdoms` and `_in_threads`. Import them; do not copy them.
- Assert on the stored documents, not only on the response: a response can say "success" while the write was lost.
- Do not set `FAKE_LATENCY=0`. The small delay is what makes requests overlap; without it a race test passes on code
  that has the race.

## Definition of done

A change is done when:

1. All three suites pass (`scripts/check.ps1`), with new tests for the new behaviour.
2. Rules that changed are reflected in the help page, and docs that describe the changed code are updated.
3. A UI change has been looked at in a browser at desktop and phone width, or the pull request says it has not.
4. The pull request says what was tested and what was not, and anything the maintainer must do (publish the function
   app, run a backfill, set a setting).
