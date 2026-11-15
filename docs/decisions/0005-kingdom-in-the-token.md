# 0005: The kingdom id travels in the login token

Date: 2026-11-14. Status: proposed, to be accepted by the maintainer before the code is written.

## Context

[0004](0004-users-in-cosmos.md) made every authenticated request read the caller's `user_<id>` document, because
flask-praetorian's `current_user()` calls `User.identify` and almost every route needs `kd_id`. That is one extra
function app call per request, and it roughly doubled the cost of the 10-second kingdom and notification polls (D3 of
0004 named the fix as a separate step).

The login token (a JWT, 24 hours for access and for refresh, so a session is capped at 24 hours) already carries the
user id and roles. If it also carried the kingdom id, a poll would need no user read.

Two facts make this less simple than adding a claim:

- Kingdom ids are not unique across rounds: the function app takes `str(len(kingdoms))`, and a round reset empties
  `kingdoms`. A token from before a reset would then name a kingdom that now belongs to another player.
- A token cannot be revoked. Whatever it says stays true until it expires.

## Decision

- **D1. Which values go in the token.** The existing `id` and `rls` (roles), plus `kd` (the kingdom id, or empty),
  `kc` (whether the kingdom was created, which the front end uses to choose between the create page and the game) and
  `rnd` (the id of the round the token was issued in). Nothing else: not `is_active`, not the death date, not email.
  `alive_required` and the action routes keep reading the user document (writes are rare next to polls), so death needs
  no token change. The user document stays the source of truth; the token is a copy for reads.
- **D2. A fresh token when the kingdom changes.** The routes that change `kd_id` or `kd_created` (creating a
  kingdom, resetting one) return a new `accessToken` and `refreshToken` built from the user as just saved, and the
  front end stores them. `refresh` also rebuilds the claims from the user document instead of copying the old ones
  (praetorian copies custom claims by default), so a refresh is where a token catches up with anything missed. The
  refresh already reads the user, so this adds no call.
- **D3. Tokens from before a round reset stop working.** The state document gets a `round` id, a new random value
  whenever the round is reset (`/resetstate`, `/init`), and a missing one counts as the empty id. Tokens carry it as
  `rnd`. A mismatch is a 401 with a message that the round has ended, which the front end already treats as "log in
  again". It is checked where a state read is already paid for or is rare, not on polls:
  every action (`start_required` reads the state), `kingdomid` (called when the app loads), and `refresh`.
  A poll with a stale token does not leak anything, because the kingdom ids of a new round are never reused: the
  function app keeps a `next_id` in the `kingdoms` document, which `/resetstate` keeps, and takes
  `max(len(kingdoms), next_id)`. A stale token then names a kingdom that does not exist and its polls return nothing
  until the app next loads or refreshes. This is a function app change, so it is published first.
- **D4. Disabling a player takes effect when their token is renewed.** `disable_user` sets `is_active` false;
  praetorian refuses to refresh or log in a disabled user, but a token already issued keeps working until it expires,
  at most 24 hours. Accepted: disabling is rare and an admin action, and the game has no money or private data at
  stake beyond the kingdom. Not accepted for roles: an `admin` removed from `rls` keeps admin routes for the same
  window, so admin routes (rare) keep reading the user document.

## Rejected

- **Read the state document on every request to check `rnd`.** It is one call per request, which is what this
  decision removes.
- **Keep the user read and cache it in the process.** State in one process (architecture rule 1).
- **Put `is_active` in the token and check a revocation list.** A revocation list is a shared read per request again.
- **Shorter tokens (an hour) to bound the disable delay.** Doubles the refresh traffic and the frontend refreshes only
  inside the last hour of a token anyway.
- **Kingdom ids with the round in them.** Changes every stored id, the front end's routes and the data.

## Consequences

- Reads that need only `kd_id` cost one call fewer per request. `current_user()` stays for routes that need more of
  the user, so nothing changes for them.
- The `kingdoms` document gains `next_id` and the state document gains `round`: both read with `.get(field, default)`,
  so old data needs no migration, but the function app must be published before the web app.
- Disabling a player is delayed by up to a day, and a removed role likewise (admin routes excepted).
- Every route that changes the user's kingdom fields must return a new token. A test lists them.
