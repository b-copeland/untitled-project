# The admin page

How the maintainer runs a round: what each operation on `/admin` does, in what order, and what to do when one fails.
The routes are in `api/untitledapp/admin.py` (and `roundend.py` for ending a round, `adminaccounts.py` for
accounts); the page is `src/pages/admin.js` with `adminround.js`, `adminuniverse.js` and `adminaccounts.js`. Why a new round works the way it does:
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
| Accounts | `GET /api/admin/accounts` | Every account (bots hidden unless asked for) with its kingdom, email, ban, last login and the accounts it shares a login signal with. One query over the users and the cached `kingdoms` document. See [Accounts](#accounts). |
| Set a password | `POST /api/admin/accounts/<id>/password` | `{"password"}`. For a player without a confirmed email, who can not use the email reset. |
| Ban, unban | `POST /api/admin/accounts/<id>/ban`, `/unban` | `{"reason"}` (optional, at most 200 characters, shown to the player when they try to log in). |

Times on the page are in the admin's time zone; the page sends them to the server as UTC ISO times, and the server
stores them as `datetime.isoformat()` in UTC.

## Starting a new round

The form asks for the start, the end, the first election (left empty, it opens `BASE_FIRST_ELECTION_START_MULTIPLIER` epochs after the start, or none in a round too short for it; or tick "No elections"), the number of galaxies, galaxies per cluster, and
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
   whole (`round_state`): the dates, `election_end: ""`, `next_history` = the start, no policies, the drawn
   `galaxy_policies`, `cluster_benefits` and first `ballot`, `game_over: ""`,
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

## Accounts

The list is for spotting trouble and helping a player who is locked out. Open an account by its name to set its
password or ban it.

- **Setting a password** stores the new one at once; the admin tells the player. Any email reset link the player had
  stops working, as after every password change. A login token the player already has keeps working until it expires.
- **A ban** sets `is_active` false with `banned_at` and `ban_reason` on the user. The player can not log in (the login
  page shows the reason, but only to someone who typed the right password) or renew their token. A token they already
  have stops working at once: every action reads the account (`refuse_banned` in `api/untitledapp/__init__.py`), and
  the ban marks their kingdom `banned` so the kingdom poll (also made when the app loads) answers 401 within seconds.
  A 401 signs them out. Their notification sockets are closed. Their kingdom stays in the round. Banning again
  changes only the reason. An account with the `admin` role can not be banned here, so the admin can not lock
  themselves out. Unbanning clears all three and the kingdom's mark.
- **Login signals.** Each player login (not bots, not `/api/adminlogin`) stores in the user's `seen` list a keyed
  hash of the address it came from and of the browser's device id: a random id the login page keeps in local storage
  (`deviceId` in `src/auth/index.js`). The address is the last entry of `X-Forwarded-For`, which App Service's front
  end adds (earlier entries are whatever the client sent), without its port; an IPv6 address counts as its /64. This holds while nothing else sits in front of the app (the
Cloudflare record is DNS only, [deployment.md](deployment.md)): turning on Cloudflare's proxy or moving host makes the
last entry the proxy's, and every account would share one address, so check `client_address` in
`api/untitledapp/adminaccounts.py` then.
  The hash is an HMAC with the app's `SECRET_KEY`, so the stored values say only "same" or "different": the admin
  never sees an address. Changing `SECRET_KEY` makes every stored signal match nothing.
- **Keeping them short.** A signal is rewritten only when it is new or was last written a day ago, so most logins add
  no write. Each account keeps the newest `SEEN_PER_KIND` of each kind, and a signal not seen for `SEEN_DAYS` is
  ignored by the list and dropped at the account's next login or the next new round. Recording never fails a login.
- **Reading them.** Two accounts that share a signal are listed together, saying whether it was the address, the
  device or both. A shared device is the stronger sign; a shared address can be a household, a school or a phone
  network. Why it is built this way: [decisions/0016](decisions/0016-login-signals.md).

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
`tests/test_admin_accounts.py` covers the accounts routes and the login signals, `src/pages/adminaccounts.test.js` the
accounts section.
