# api/: Flask, game rules and identity

Rules for working in the Flask app. The root `CLAUDE.md` and `docs/` still apply; the recipes for common changes are in
[docs/recipes.md](../docs/recipes.md).

## Layout

- `untitledapp/__init__.py`: app factory (`create_app`), `User` and `Locks` models, the route decorators
  (`alive_required`, `start_required`, `before_start_required`), the websocket, `REQUESTS_SESSION`.
- One blueprint per area: `account`, `admin`, `build`, `conquer`, `getters`, `misc`, `politics`, `refresh`. Which area
  holds what is in [docs/architecture.md](../docs/architecture.md#where-things-are).
- `shared.py`: every game constant and formula (`GAME_CONFIG`, `GAME_FUNCS`, `UNITS`, `PROJECTS`, policies,
  `INITIAL_KINGDOM_STATE`). `occ.py`: optimistic concurrency.
- `api/config.py`: `Config` reads environment variables; `TestingConfig` is what the tests use.

## Conventions

- Routes: `@bp.route(...)`, then `@flask_praetorian.auth_required` (or `roles_required('admin')`), then
  `@alive_required` and, if needed, `@start_required`. The player's kingdom is `flask_praetorian.current_user().kd_id`.
- Parse and type-check the request body first, and answer `400` with a message for bad input before touching state.
- Responses: `flask.jsonify({"message": "...", "status": "success"}), 200` on success; `{"message": "<why>"}` with `400`
  on a refusal. Messages are short sentences the player reads in a toast.
- State changes: `occ.update(path, decide)`; see [docs/concurrency.md](../docs/concurrency.md). Raise `occ.Rejected` for a
  refusal. Follow-up writes after `update` returns.
- Reads: `occ.read(path)` or the existing getters (`_get_kd_info`, `_get_state`, `_get_galaxies_inverted`, ...). Search
  `getters.py` and `shared.py` before writing a new helper; both are large and hold many. The shared documents are
  read at most once per request through the getters (`request_cache.py`); pass anything else you have already read
  down instead of reading it again, including to `occ.update(..., document=...)`. Count the calls with
  `scripts/profile_calls.py` ([docs/cost.md](../docs/cost.md#rules)).
- Calculations: plain functions of their inputs, no Flask or HTTP inside, so they can be unit tested and reused by the
  forecasts and the bots.
- Other kingdoms' data: through `_get_max_kd_info`, which keeps only the fields the caller has revealed. `max=True`
  skips the filter; never put that result in a response.
- SQLite (`User`, `Locks`, `db.session`) is being phased out. Add nothing to it; game code takes only
  `flask_praetorian.current_user().kd_id` from the user.
- Function app calls: `REQUESTS_SESSION` with the `x-functions-key` header from `AZURE_FUNCTION_KEY` and the base URL from
  `AZURE_FUNCTION_ENDPOINT`. Never inside a loop over kingdoms if a list can be read once.
- No new `acquire_lock` calls. Existing ones stay until [docs/status.md](../docs/status.md) says the document is fully
  migrated.
- Times: `datetime.datetime.now(datetime.timezone.utc)`, stored with `.isoformat()`.

## The refresh

`refresh.py`: `refresh_data` (the tick, called by a scheduler with `Refresh-Secret`) runs `_refresh_kd` for each
kingdom. In `_refresh_kd`, everything that changes the kingdom happens inside the attempt loop and is written once with a
version check; effects on other documents are deferred to `effects` and run after the write. Keep it that way: see
recipe 5 in [docs/recipes.md](../docs/recipes.md#5-a-step-in-the-refresh).

## Tests

`tests/` at the repo root, run with `conda run -n funcapp python -m pytest tests -n 4`. Helpers and patterns are in
[docs/testing.md](../docs/testing.md#writing-backend-tests).
