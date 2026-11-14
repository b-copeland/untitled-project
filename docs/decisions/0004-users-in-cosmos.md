# 0004: Users in Cosmos, through the function app

Date: 2026-11-14. Status: accepted; migration in progress ([status.md](../status.md#parallelism-gaps)).

## Context

Users (login, roles, `kd_id`, email) and the legacy locks live in a SQLite file on one App Service machine, which breaks
the rule that code works on many processes on many machines ([architecture.md](../architecture.md#target-no-sqlite)).
A full copy of the users is pushed to the `accounts` document after every change, and SQLite is refilled from it at
startup. flask-praetorian (login and JWTs) needs a user class, but version 1.6.2 only calls `lookup(username)`,
`identify(id)`, `identity`, `rolenames`, `password` and `is_valid()` on it, so the class does not have to be SQLAlchemy.

The SQLite lock commits are also most of the refresh's CPU time, and the locks only work inside one process.

## Decision

- **D1. Users move to Cosmos, through the function app.** One document per user (`user_<id>`), one per username
  (`username_<hex of the UTF-8 username>`, holding the user id; creating it is the uniqueness check) and a counter for
  the next id (`user_counter`, taken with `occ.update`). Flask gets a plain `User` class that praetorian can use.
- **D2. The numeric user ids stay.** They are already in JWTs (the `id` claim) and in email verify and reset tokens, so
  existing sessions and links keep working.
- **D3. One user read per authenticated request, memoised per request.** praetorian calls `identify()` every time
  `current_user()` is called; that becomes a function-app call, read once per request and kept on `flask.g`. This
  adds about one call per authenticated request, which roughly doubles the cost of the 10-second kingdom and
  notification polls. Removing it (the kingdom id as a JWT claim) is a separate, optional step.
- **D4. Locks are removed document by document,** once every writer of that document checks its version. (Done
  2026-11-14.)

## Rejected

- **A shared SQL database (Azure SQL or Postgres).** SQLAlchemy and praetorian would work unchanged, but it adds a
  second database and probably a paid service, for a project with no funding.
- **The existing `accounts` document as the store.** Every login and request would read the whole user list, it grows
  with the number of users, and two sign-ups at once conflict on the one document.
- **Usernames as document ids directly.** Cosmos ids cannot contain `/ \ ? #`, and the names are case-sensitive today.
  Lowercase hex of the UTF-8 bytes is always a valid id and keeps lookups case-sensitive.

## Consequences

- Sign-up is several documents (counter, username claim, user), so it is not atomic: a crash between the username claim
  and the user write leaves the name taken by nobody. Rare and low stakes; an admin can delete the claim.
- Listing users by email, kingdom or name prefix is a cross-partition query (`GET /users`). It is kept to admin and
  rare paths (email recovery, bot names, round reset), never per request or per tick.
- The `accounts` backup document stays for a while after the switch, then goes ([status.md](../status.md)).
- The function app routes come first (phase 1); the Flask store and a migration script follow, and the maintainer runs
  the migration against production.
