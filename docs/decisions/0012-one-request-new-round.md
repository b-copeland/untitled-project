# 0012: A new round is one request that pauses the game first and writes the state whole last

Date: 2026-11-21. Status: accepted.

## Context

Starting a round used to be three admin buttons: Reset State (`/api/resetstate`), Create State (galaxies) and Update
Game State (dates), typed as ISO text. Between them the game was half set up while the refresh ran every minute:

- after a reset the old dates stayed and `game_over` was cleared, but the scores' and empires' `last_update` were
  empty, so every tick failed (`fromisoformat("")`) until the dates were set;
- a fresh `/init` left the state empty, so every tick, `/api/state` and every action failed on `game_start`;
- `/init` failed part way on a container `/deleteall` had blanked, and `/resetstate` failed on blank documents;
- a time typed with a `Z` broke every route that parses it (Python 3.10's `fromisoformat`);
- keys from the last round (an open election, policies) carried over unless the admin overwrote each one;
- `max_galaxy_size` and `avg_size_new_galaxy` were asked for and stored but nothing read them.

## Decision

- **One route, `POST /api/admin/newround`, from any starting point**: `/init` (idempotent), pause, reset, galaxies,
  then the state. Rerunning it is the recovery from any failure.
- **Pause with `game_over` before deleting anything.** The engine and player writes already stop on `game_over`
  (`roundend.py`), so no new mechanism is needed; a round that has started is archived properly at the same time.
- **Write the inner state whole, last** (`round_state`), with every key the game reads. Nothing carries over, and
  clearing `game_over` is the switch that restarts the engine.
- **The function app's `/init` and `/resetstate` work on empty, blank or live containers**, from one table of core
  documents.
- **The server validates times and stores UTC ISO**; the page uses date-time pickers.
- **Dates of a set-up round change through their own validated route** (`POST /api/admin/round`), decided against the
  stored state.
- Bots are a second request, so a slow bot creation can not leave the round half set up.

## Rejected

- **Keep the three steps and make each one safe.** The gaps between them are the problem: the refresh runs in them.
- **Clear `game_over` straight after the reset (as before).** Restarts the engine before the round has dates.
- **A separate "maintenance" flag.** `game_over` already stops everything that matters; a second flag would need every
  check doubled.
- **Bots in the same request.** About twenty function app calls each; a hundred bots could outlast the request timeout
  and leave the game paused.
- **Merging into the state (`/updatestate`).** Cannot remove keys, so leftovers from the last round stay.
