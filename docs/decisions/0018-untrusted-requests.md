# 0018: Every request is untrusted: checked ids, checked values, bounded growth

Date: 2026-11-25. Status: accepted.

## Context

Before the first round with strangers, a review (issue #219) found that the API trusted its callers in many places. An
id with an encoded `?` cut a function app URL short and wrote into another kingdom's document. Keys from the request
went into queues and targets and stopped kingdoms' refreshes. `NaN` passed range checks. Lists grew without a cap from
actions that cost nothing. The rate limit counted made-up tokens separately. Sockets that never sent a token took every
server thread.

## Decision

- **D1. Ids are checked in the route, with a backstop in the session.** Each route checks the ids it takes against
  their list. `REQUESTS_SESSION` also refuses any function app URL that is not plain path segments, and API paths with
  such an id get a 404, so a route that forgets is still safe.
- **D2. Kingdom writes carry only known fields** (`KINGDOM_FIELDS`). An unknown field is dropped and logged in
  production, and raises under the tests.
- **D3. One module checks values** (`inputs.py`), and routes store what it returns.
- **D4. Lists are capped where they are written**, and free repeatable actions are bounded: by a cooldown, an allowance
  over time, a refusal of the repeat, or a route limit.
- **D5. Rate limits key on the user of a valid token, else the address**, with a total per address across routes.

## Rejected

- **An allow-list of kingdom fields in the function app.** Every new kingdom field would need a function app publish
  first, and the list would live in two places. The Flask session sees every write anyway.
- **Refusing a kingdom write with an unknown field in production.** A kingdom that already carried one (written by the
  hole itself) could never be written whole again, which would freeze it. Dropping and logging keeps it working, and
  the admin's tools clear the field.
- **Encoding ids into URLs (`urllib.parse.quote`) instead of checking them.** It stops the path from being cut, but a
  made-up id would still reach the function app, and the route still would not know the kingdom exists.
- **A shared limiter store (Redis).** It is a paid service (docs/cost.md rule 6), and production runs one process.
- **Per-token limits with token revocation.** Revocation needs a shared read per request, which decision 0005 removed.
