# Recipes

Step-by-step checklists for the common changes. Follow the steps in order; each ends with the test that proves it. If a
change does not fit a recipe, read [architecture.md](architecture.md) and [concurrency.md](concurrency.md) first, and
ask if unsure.

Every recipe ends the same way: run the three test suites ([testing.md](testing.md#the-suites)), and in the pull request
say what you tested and what you could not.

## 1. An action: a route that spends or changes something

Example to read: `build_structures` in `api/untitledapp/build.py` (`POST /api/structures`). It still takes the legacy
lock (`acquire_locks`, `release_locks_by_id`); a new route leaves those lines out and follows the template below.

1. **Design.** Name the decision document (usually `kingdom_<id>`) and every other document the action writes, with
   its tier (strict, eventual, derived). See [concurrency.md](concurrency.md#which-documents-need-strict-handling).
2. **Pure helpers first.** Validation and calculation as plain functions of their inputs (`_validate_structures`,
   `_get_new_structures`), with no Flask or HTTP. Put game numbers in `GAME_CONFIG` in `shared.py`.
3. **The route.** In the right blueprint:
   ```python
   @bp.route('/api/<name>', methods=['POST'])
   @flask_praetorian.auth_required
   @alive_required            # and @start_required if it only works after the round starts
   def <name>():
       app = flask.current_app
       kd_id = flask_praetorian.current_user().kd_id
       req = flask.request.get_json(force=True)
       # parse and type-check the input here; reject bad input with a 400 before touching state

       def decide(kd_info):
           # read anything else needed with occ.read(...) here, so it is fresh on each attempt
           # validate against kd_info; raise occ.Rejected("why") if not allowed
           return {fields to write, full nested objects}, value_for_after

       try:
           result = occ.update(f'/kingdom/{kd_id}', decide)
       except occ.Rejected as rejection:
           return flask.jsonify({"message": rejection.message}), rejection.status
       except occ.Busy:
           return flask.jsonify({"message": "Server is busy"}), 400
       # follow-up writes, after the decision has landed: queue appends, news, notifications. For example:
       REQUESTS_SESSION.patch(
           app.config['AZURE_FUNCTION_ENDPOINT'] + f'/kingdom/{kd_id}/structures',
           headers={'x-functions-key': app.config['AZURE_FUNCTION_KEY']},
           data=json.dumps({"new_structures": result}),   # entries carry only "time" and counts
       )
       return flask.jsonify({"message": "Done", "status": "success"}), 200
   ```
   Body shapes for each function app route are in [data-model.md](data-model.md#how-the-function-app-writes).
   No `acquire_lock` in new routes. Messages are short, plain sentences the player will read.
4. **If it is something a player might want while offline,** add it to the Schedule (recipe 6) or the auto builder.
5. **Tests** in `tests/test_<blueprint>.py`:
   - the pure helpers, with plain asserts;
   - the route through `client.post(..., headers={"Authorization": f"Bearer {jwt1}"})`, after `_set_up_kingdom(...)`
     (from `tests/test_concurrency.py`): the success case, each rejection, and the document after;
   - a race: `_run_together(app, 6, ...)` with identical requests; exactly one succeeds and the kingdom is charged once.
6. **Frontend:** the form (recipe 7), with the limits mirrored in `src/validation.js`, and the help page updated.

## 2. A read route and a frontend data key

1. Add the route to `getters.py` (search first; there may be a helper that already reads what you need). Decorate with
   `@flask_praetorian.auth_required`.
2. **If it returns anything about another kingdom,** filter it through what the caller has revealed
   (`_get_max_kd_info`, without `max=True`). Never return a raw document of another kingdom.
3. Keep round trips down: one request per document, none inside a loop over kingdoms if you can read a list instead.
4. Add the key to `ENDPOINTS` and `initGlobalData` in `src/data/gameData.js`. If a `next_resolve` timer produces this
   data, add it to `RESOLVE_KEYS_MAP`.
5. Test the route in `tests/test_getters.py`, including that hidden fields are absent for an unrevealed kingdom.

## 3. A new field on the kingdom document

1. Add it with its starting value to `INITIAL_KINGDOM_STATE["kingdom"]` in `shared.py`.
2. **Existing kingdoms do not have it.** Read it with `kd_info.get("field", default)` everywhere, or write a one-off
   backfill in `adhoc/` and say in the pull request that it must be run. Prefer `.get`.
3. Add it to the table in [data-model.md](data-model.md#the-kingdom-document) (`tests/test_docs.py` checks this).
4. If another kingdom may see it, add it to the right reveal category in `_get_max_kd_info`, or decide it stays private.
5. If it is a nested object, remember the kingdom PATCH is a shallow merge: always write the whole object.

## 4. A new document type

1. **Function app** (`funcapp/function_app.py`): a `GET` and a `PATCH` route following the existing pairs (copy
   `get_structures` and `update_structures`). The `PATCH` handler must do exactly one `replace_item` and be decorated with
   `@retry_on_conflict`, below the route decorators. Use `new_<field>` to append and `<field>` to replace.
2. **Per-kingdom:** add the type to the list in `create_kingdom` (function app) and to `INITIAL_KINGDOM_STATE` (Flask).
   **Global:** create it in `init_state`, and decide whether `reset_state` keeps it (`RESET_KEEP_IDS`).
3. Existing games do not have it: handle a missing document, or backfill.
4. Add it to [data-model.md](data-model.md) with its writers and tier.
5. Tests: `funcapp/tests` for the handler (append and replace both land under concurrency), and a Flask test through
   the fake backend, which runs the real handlers.
6. Deploy the function app before the Flask change that needs it ([deployment.md](deployment.md)).

## 5. A step in the refresh

1. If it is timed, add a category to `next_resolve` in `INITIAL_KINGDOM_STATE` (with `DATE_SENTINEL`), and use
   `.get(category, DATE_SENTINEL)` for kingdoms made before the change.
2. Write it as a function of `(kd_info, time_update, ...)` that returns the new values and the next resolve time, and
   call it from `_refresh_kd` **inside the attempt loop, before the single kingdom write.** It must be correct when run
   twice and when the loop retries, so it does not write other documents. (The one exception in the code is expiry of
   `revealed` and `shared` entries, which gives the same result however often it runs.)
3. Effects on other documents go in `effects` (run after the write). Anything credited from a queue uses the
   `queues_resolved_until` cursor so it is credited once.
4. Compute from elapsed time, not from "one tick happened": the refresh may run late or twice.
5. Test in `tests/test_refresh.py`: run the refresh at two times and check the result is the same as one run at the
   later time.

## 6. A schedulable action

1. In `conquer.py`, a `_schedule_<type>(id, time, options, kd_info)` returning `(ok, entry, message)`; add it to
   `handler_funcs` in `add_schedule`.
2. In `refresh.py`, a `_resolve_schedule_<type>(kd_info, schedule)` that returns `(function, args)` to run after the
   kingdom is written; add it to `schedule_funcs` in `_resolve_schedules`. It must run through the same code as the route,
   so the action is checked again when it fires.
3. A card for it on the Schedule page (`src/pages/conquer/schedule.js`) and a line in its help page.
4. Test: schedule it, move time past it, run the refresh, check it happened once.

## 7. A page or a form

1. One entry in `src/routes.js`. The router and the sidebar both read it. Game pages get `{data, loading, updateData}`;
   add `props: (context) => ({...})` for anything else.
2. Build it from the shared components in [ux.md](ux.md#components). Copy `src/pages/build/structures.js` for a form,
   `src/pages/conquer/attack.js` for a planner.
3. Validate each field with `src/validation.js`, set `SubmitButton`'s `blocked` to the first error, and send with
   `updateData([changed keys], [request])`.
4. A help topic in `src/pages/help/` and a `HelpButton` pointing to it.
5. A Jest test next to the page. Mock `components/header` and `components/helpbutton`; set mock implementations in
   `beforeEach`.
6. Look at it at desktop and phone width.

## 8. A game number

1. Add or change it in `GAME_CONFIG` (or `UNITS`, `PROJECTS`, ...) in `shared.py`. Never put the number anywhere else;
   the frontend reads `data.state.game_config`.
2. **Balance numbers are the maintainer's call.** Propose the value in the pull request and say why.
3. If it changes what players see, update the help page.
4. If `funcapp/queues.py` depends on it (the epoch length), keep them equal; `tests/test_queue_batching.py` checks it.

## 9. A new unit, structure or missile

This touches many places; search for an existing name (for example `drone_factories`) across `api/`, `src/` and
`funcapp/` and handle every hit. At least: `UNITS` or `STRUCTURES` or `MISSILES`, `INITIAL_KINGDOM_STATE` (counts and
targets), `NETWORTH_VALUES`, `PRETTY_NAMES`, the formulas that use the others, the frontend lists (some pages still have
their own, such as `STRUCTURES` in `structures.js`), the help pages, and a backfill for existing kingdoms.
