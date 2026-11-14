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
  `delete_all`) and `create_item` are not retried and are admin or setup operations. Do not add new ones on a hot path.
- Kingdom routes are `kingdom/{kdId:int}/...`: kingdom ids are strings of integers.
- Do not import anything from `api/`; this app is deployed on its own.

## Known problems

Handlers catch everything with a bare `except` and answer `500`, which hides throttling (`429`). Some `GET`s answer
`201`. New handlers should let unexpected errors surface with their real status and log them. Three write routes do
not work with the current documents and nothing calls them (see [docs/data-model.md](../docs/data-model.md#how-the-function-app-writes)).

## Tests and running

- `conda run -n funcapp-worker python -m pytest funcapp/tests` (no stack needed).
- The Flask tests in `tests/` also run these handlers in-process on an in-memory container (`tests/fake_backend.py`).
- Locally: `func host start` in this folder, with `local.settings.json` pointing at the emulator. The host hot-reloads
  on file changes.
- Deploying: [docs/deployment.md](../docs/deployment.md#function-app). A change here must be live before the Flask
  change that depends on it.
