# 0015: Data migrations run on the refresh tick, behind code that reads both shapes

Date: 2026-11-22. Status: accepted.

## Context
Friends and family now play the deployed game, so a change to what documents hold must not lose their data. The
maintainer wants no manual step after a deploy. Any migration that runs separately from the code, before or after it,
leaves a window where one version of the code meets the other version of the data.

## Decision
- **The code that ships with a migration reads both shapes**, so the game is right before the migration has run, and
  an action in that window writes the new shape without losing anything (a galaxy vote carries the galaxy's old votes
  over with it).
- **The migration is a registered function** (`migrations.py`) that the refresh runs on its first tick after the
  deploy, before anything else, and records in `state.migrations_done` (decided on the state, so once). Each writes
  through `occ.update` and leaves a document in the new shape alone, so overlapping ticks and a tick that stops
  half-way are safe. One that raises is logged and tried again next tick; the tick goes on.
- A new round starts with every migration marked done.

## Rejected
- **An adhoc script the maintainer runs after the deploy**: a manual step, and a window between the deploy and the run.
- **A step in the deploy workflow**: the production Cosmos key in GitHub secrets, a second program writing to
  production, and still a window (before the step, new code on old data; or, run first, old code on new data).
- **Downtime during the deploy**: the window goes, but so does the game, and nothing in the stack can pause it yet.

## Consequences
- Every data-shape change ships its reading of the old shape and a migration with a test that runs it twice (recipe
  13). The old-shape reading can go once no environment has data from before it.
- A migration runs in every environment the code reaches, local and test ones included, which is how it gets tried
  before production.
