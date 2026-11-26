# Security: what a hostile player can send

The pages only send sensible requests, but every route is public and a script can send anything: any id, any key, any
value, as often as the rate limits allow, from as many accounts as it can sign up. A review before the first round with
strangers (issue #219) found each of the holes below in working code. The rules here are what closed them. Read this
before adding a route, a field, a list or anything a player can repeat.

## The rules

### 1. An id from the request reaches only the document it names

Flask decodes the path before the route sees it, so `/api/spy/5%3Fx` hands the route the id `5?x`. Pasted into a
function app URL, `/kingdom/5?x/news` became a write to `/kingdom/5` itself: one player could write into another
kingdom's main document, and spy on a kingdom while the news, the radar reveal and the aggression went nowhere.

- Check every id from the path or the body against the list it belongs to (`uag._get_kingdoms()`,
  `_get_galaxies_inverted()`, `_get_empire_info()`), and use the checked string from then on.
- `REQUESTS_SESSION` refuses a function app URL that is not plain path segments (`check_function_url` in
  `api/untitledapp/__init__.py`), and API routes refuse a path id that is not a plain id with a 404. Those are the
  backstop; the check in the route is the rule.
- Query strings go in `params=`, never in the path.

### 2. Every value is checked, and only what the game uses is stored

A key that is not a structure went into a build queue and stopped the kingdom's refresh on every tick. `NaN` passed
every `<` and `>` check. A switch stored whatever JSON was sent. A schedule and a pinned list were stored as sent.

- Read each value through `api/untitledapp/inputs.py`: `number` (finite, optionally whole, in range), `flag`
  (true or false only), `one_of`, `text` (with a length), `keyed` (keys from the game's own lists), `ids`.
- Keys come from the game's lists: `uas.STRUCTURES`, `TRAINABLE_UNITS`, `MISSILES`, `PROJECTS`, the spy operations,
  `SCHEDULE_OPTION_KEYS`. Never trust `uas.UNITS.get(key)` to mean "a unit that can do this": it includes engineers and
  recruits.
- Build what you store from the checked values, never from the request's own dict. Drop keys the game does not use
  (the attack page sends its own `buffer`), or refuse them when no page sends them.
- Check before anything is spent. An unknown spy operation used to fail after the drones were gone.
- A kingdom write may only carry known fields (`KINGDOM_FIELDS` in `shared.py`). Under the tests an unknown field
  raises; in production it is dropped and logged. A new kingdom field goes in `INITIAL_KINGDOM_STATE` or
  `KINGDOM_FIELDS_ADDED_LATER` (recipe 3 in [recipes.md](recipes.md)).

### 3. Nothing a player can repeat for free grows without end

Asking to join an empire and cancelling cost nothing and each posted a line of empire news; founding and leaving an
empire made a new set of documents each time; news and histories had no cap. A Cosmos item is at most 2 MB, and every
read and write of a big one costs more request units, on the free tier production shares.

- Every list in a document has a cap where it is written: in the function app (`NEWS_LENGTH`, `HISTORY_LENGTH`,
  `PINNED_LENGTH`, messages) or in the Flask code that decides it (the intel market's `HISTORY_LENGTH`, the board, the
  schedule, recurring operations).
- Every free action that writes is bounded by one of: a cooldown on the document (the galaxy leader vote), an
  allowance over time (`GALAXY_DIPLOMACY_ACTIONS_PER_HOUR` with `spend_diplomacy`), a refusal of the repeat (asking
  twice, inviting twice), or a route limit (`ROUTE_LIMITS`). Ask "what if a script does this a million times?"
- Each entry's size is bounded too: text has a length, and fields the server can set (a message's time) are set by
  the server.

### 4. A request costs at most what it is worth

`/api/kingdomsinfo` read one document per id in the request, so one request could cost thousands of function app
executions and Cosmos reads.

- A list from the request that turns into reads is checked against what exists and de-duplicated, so the cost is at
  most one read per real item ([cost.md](cost.md), rule 1).
- A route that is expensive, creates accounts, sends email or hashes a password gets a line in `ROUTE_LIMITS`
  ([architecture.md](architecture.md#rate-limits)).
- Anything that holds a server thread (the notification sockets) is capped before the caller has proven who they are
  (`PENDING`, `PER_ADDRESS` in `sockets.py`).

### 5. Limits count against the caller, not what the caller sends

The limiter was keyed on the token string, and anyone can make one up. Limits key on the user of a valid token, else
the address (`_limit_key`). A new per-caller limit of any kind (a cooldown, an allowance) is stored on a document the
caller can not choose: their kingdom, their galaxy, their user.

### 6. Accounts are cheap, and one person may hold many

Signing up is free (issue #262). Assume any rule can be worked by several accounts at once.

- Names starting `bot_` belong to the game's bots and are refused at sign-up: the admin page and the login signals
  treat bots apart. Usernames and kingdom names have no hidden characters, so one can not be made to look like another.
- A ban takes effect at once: actions read the account, and the kingdom poll sees the kingdom marked `banned`
  ([admin.md](admin.md#accounts)).

### 7. The server decides what a player sees

Unchanged, and still the most important: another kingdom's data goes through `_get_max_kd_info`, never `max=True`, into
a response ([architecture.md](architecture.md)).

## Checklist for a new route

1. Which ids does it take, and is each checked against its list before use?
2. Is every value read through `inputs.py`? Is anything stored that the request made up?
3. Can a player repeat it for free? What bounds it, and what does each repeat add to a document?
4. How many function app calls can one request make, at most? Does it need a line in `ROUTE_LIMITS`?
5. Does it return anything about another kingdom, and is it filtered?
6. Does it work when the player has several accounts in the same galaxy?

## Testing the hostile request

Test the request a script would send, not only the one the page sends (`tests/test_inputs.py`,
`tests/test_path_ids.py` show the patterns): an unknown key, `"nan"`, a list where a number belongs, a string where a
switch belongs, an id with `%3F` in it, an id that does not exist, the same request a hundred times. Assert the status,
and that the documents are unchanged after a refusal.

## What is still open

The open items are in [status.md](status.md): sign-up checks (issue #262), and the rate limits and socket caps being
per process.
