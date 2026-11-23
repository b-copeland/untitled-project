# funcapp/: the storage layer

An Azure Functions app (Python v2 programming model) that is a thin HTTP layer over one Cosmos DB container. The root
`CLAUDE.md` and `docs/` still apply.

## What belongs here

Reading and writing documents, nothing else. **No game rules**: no validation of whether an action is allowed, no
formulas. Those live in Flask. If a handler needs to know game rules to work, the design is wrong.

## Rules for handlers

- A route reads or writes **one document** (`<type>_<kd_id>` or a global id; see [docs/data-model.md](../docs/data-model.md)).
- Every write handler (`update_*`) does **exactly one `replace_item`** and is decorated with `@retry_on_conflict`
  (from `concurrency.py`) below the `@APP.route` decorator. The decorator re-runs the whole handler on a conflict, so it
  must be safe to run again from the top: read, change, one write, nothing else.
- Body conventions: `new_<field>` appends to a list, `<field>` replaces it; whole-document routes shallow-merge
  (`{**document, **body}`). Follow the existing pair for the closest document type (`get_structures`,
  `update_structures`).
- Build queues are folded with `coalesce` from `queues.py` on every append. Queue entries carry only `time` and counts.
- `auth_level=func.AuthLevel.ADMIN` on every route: only Flask, with the host key, calls this app.
- Multi-document handlers (`create_kingdom`, `create_galaxy`, `create_empire`, `reset_state`, `init_state`,
  `delete_all`) and `create_item` are not retried as a whole. Do not add new ones on a hot path. Where one changes a
  shared document that other requests also change (`kingdoms`, `galaxies`, `empires`), it does so with
  `change_document` from `concurrency.py`: a conditional write retried on conflict, which can refuse with `Refused`.
  `create_kingdom` and `create_empire` choose their new id that way.
- Create-only routes (`create_user`, `create_username`) do one `create_item` and answer `409` when the id exists: that
  is how uniqueness is enforced, so do not turn them into create-or-merge.
- Users outlive a round: `reset_state` keeps `user_` and `username_` documents (`is_user_document`), and `delete_all`
  removes them instead of blanking them.
- `init_state` and `reset_state` share one table of core documents (`_core_documents`) and must work on an empty
  container, a blanked one and a live game: the admin's new round calls both every time ([docs/admin.md](../docs/admin.md)).
- The user handlers (end of `function_app.py`) are the model for new ones: no bare `except`, real status codes
  (`404` missing, `400` bad body), and a `CosmosAccessConditionFailedError` caught inside a retried handler so
  `retry_on_conflict` can see it.
- Kingdom routes are `kingdom/{kdId:int}/...`: kingdom ids are strings of integers.
- Do not import anything from `api/`; this app is deployed on its own.

## Known problems

Handlers catch everything with a bare `except` and answer `500`, which hides throttling (`429`). Some `GET`s answer
`201`. New handlers should let unexpected errors surface with their real status and log them.

## Tests and running

- `conda run -n funcapp-worker python -m pytest funcapp/tests` (no stack needed).
- The Flask tests in `tests/` also run these handlers in-process on an in-memory container (`tests/fake_backend.py`).
- Locally: `func host start` in this folder, with `local.settings.json` pointing at the emulator. The host hot-reloads
  on file changes.
- Deploying: [docs/deployment.md](../docs/deployment.md#function-app). A change here must be live before the Flask
  change that depends on it.
