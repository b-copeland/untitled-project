# The admin page

How the maintainer runs a round: what each operation on `/admin` does, in what order, and what to do when one fails.
The routes are in `api/untitledapp/admin.py` (and `roundend.py` for ending a round); the page is
`src/pages/admin.js` with `adminround.js` and `adminuniverse.js`. Why a new round works the way it does:
[decisions/0012](decisions/0012-one-request-new-round.md).

## Signing in

`/admin` signs in through `POST /api/adminlogin`, which only accepts a user with the `admin` role. Flask creates the
`admin` user at startup when there is none, with `ADMIN_PASSWORD` ([deployment.md](deployment.md#required-app-service-settings)); it is
an ordinary user document after that, so changing the setting does not change the password.

Admin routes are under `/api/admin/` and need the `admin` role. They stay open when a round is over
(`roundend._STILL_OPEN`), and they do not check the round id in the token, so an admin token survives a new round.

## The operations

| On the page | Route | What it does |
|---|---|---|
| The round | `GET /api/admin/round` | The phase (`not set up`, `not started`, `running`, `over`), the dates, galaxies, clusters, players, bots and rounds archived. It first calls the function app's `/init`, so a container that was never set up gets its empty documents. |
| Start a new round | `POST /api/admin/newround` | Deletes the current round and sets up the next one, in one request (below). |
| Change the dates | `POST /api/admin/round` | Moves `game_end`, the next `election_start` (`""` for no more elections), and `game_start` while the round has not started. Decided against the stored state with `occ.update`. |
| Add bots | `POST /api/admin/bots` | `{"total": n}` in the default mix (`bots.mix_for`), or counts per type. At most 200 per call. Needs galaxies. See [bots.md](bots.md#creating-them). |
| End the round now | `POST /api/admin/endround` | Archives the round and makes the game read only, as when `game_end` passes. Only a new round undoes it. |
| Watch the round | `GET /api/admin/universe`, `/api/admin/kingdom/<id>` | Every kingdom at a glance, and one in full with its bot's decisions. See [bots.md](bots.md). |

Times on the page are in the admin's time zone; the page sends them to the server as UTC ISO times, and the server
stores them as `datetime.isoformat()` in UTC.

## Starting a new round

The form asks for the start, the end, the first election (or none), the number of galaxies, galaxies per cluster, and
how many bots to add. "Players expected" is not sent: it only shows how many kingdoms each galaxy would get. A
confirmation says what will be deleted.

Rules, checked by `check_new_round` (and mirrored by the page so it can say no before sending):

- the end is in the future and after the start; the start may be in the past (the round runs straight away);
- the first election, if any, is between the start and the end;
- 1 to `MAX_GALAXIES` galaxies; at least one galaxy per cluster (`CLUSTER_SIZE` if left out).

The number of galaxies is fixed for the round: a new kingdom joins the galaxy with the fewest kingdoms, and no
galaxies are added later. Galaxies are dealt in order into clusters (`1:1` to `1:5`, then `2:1`, ...), and a galaxy
never changes cluster ([decisions/0007](decisions/0007-cluster-politics.md)).

`POST /api/admin/newround` then, in this order:

1. **`/init`**: creates any core document that is missing or blank (`/deleteall` leaves them blank). A no-op on a set-up
   game.
2. **Pause**: sets `game_over` in the state, so from here a refresh does nothing and every player write is refused.
   If a round has started, has kingdoms and `archive` is true (the default), it is ended properly instead
   (`roundend.end_round`), which archives it as `archive_<n>`.
3. **`/resetstate`** in the function app: deletes every per-round document (kingdoms and all their documents, galaxy
   and empire documents, clusters, intel markets), writes the core documents back to empty, and gives the state a new
   `round` id. Users, preferences, archives and `kingdoms.next_id` stay. Then every user loses their kingdom
   (`kd_id`, `kd_created`, `kd_death_date`).
4. **Galaxies**: one `POST /galaxy/<id>` each, which also makes the galaxy's news and votes documents.
5. **Clocks and state**: the scores' and empires' `last_update` are set to the start, then the inner `state` is written
   whole (`round_state`): the dates, `election_end: ""`, `next_history` = the start, no policies, `game_over: ""`,
   `rounds_archived` carried over, `cluster_size`. Clearing `game_over` comes last, so the engine restarts only once
   everything is ready.

The page then calls `POST /api/admin/bots` if bots were asked for. A player's old login token is from another round:
the app signs them out when it next loads, and they sign in again and make a new kingdom.

### When it fails

A refused request (a bad date, too many galaxies) changes nothing. A failure after the pause answers 500 with "the
game is paused": the refresh and players are stopped, and **starting the new round again is the fix**. Every step
can run again from any point.

A refresh already running when the pause lands can still finish its tick: there are no locks. The pause stops every
tick that starts after it, and the last step writes the state whole, so what such a tick wrote to the state is
replaced. See [status.md](status.md).

## Running it from a script

`scripts/simulate_bots.py`, `simulate_round.py` and `profile_calls.py` start their rounds with the same route. The
body is the same as the page's:

```
POST /api/admin/newround  {"game_start": "...", "game_end": "...", "election_start": "", "num_galaxies": 4, "cluster_size": 5, "archive": false}
POST /api/admin/bots      {"total": 20}
```

## Tests

`tests/test_admin_rounds.py` walks rounds through the real routes: from an empty container, from a blanked one, a
round that is played, ended and followed by the next, archiving or not, leftovers in the state, a failure part way,
and the refresh during a reset. `funcapp/tests/test_round_reset.py` covers `/init` and `/resetstate` on empty, blanked
and live containers. `src/pages/adminround.test.js` covers the page.
