# 0009: Last-known intel in one document per kingdom

Date: 2026-11-20. Status: accepted.

## Context

Issue #27: players keep spreadsheets of what they saw while intel was active, because the game forgets it the moment a
reveal expires. Tenet 2 says information reachable only through an outside tool goes to everyone or no one. So when a
reveal ends, the kingdom that had it keeps a snapshot of what that reveal showed, and the pages that show other kingdoms
show it where nothing is revealed now, coloured by age. Active intel always wins.

That is up to one entry per (holder, target, category): kingdom-squared in the worst case. Two questions decide the
design: where the entries live, and how the values at the moment of expiry are read without a read per expiry.

### Measurements

A simulated round (`scripts/simulate_round.py`, 40 bots in 4 galaxies, 3 game days, on the in-memory backend),
counting the writes and measuring the documents at the end:

| | Value |
|---|---|
| Pairs with at least one snapshot | 947 of 1,560 possible (61%): sparse early, filling as a round goes on |
| Targets per holder | mean 23.7, max 30 |
| One document per kingdom | mean 10.8 KB, max 15.1 KB |
| One document per pair | mean 0.5 KB, max 1.3 KB |
| Entry size by category | stats 0.09 KB, drones 0.1 KB, kingdom 0.23 KB, military 0.76 KB |
| Snapshot writes | 954 (40 creates), against 2,510 writes of `revealed_` documents in the same round |

Bots never spy on structures, shields or projects. Sized from a kingdom document: structures 0.19 KB, shields 0.13 KB,
projects about 3 KB (after dropping zero entries and the derived bonuses). A holder that has every category on every
other kingdom of a 100-kingdom round would have about 99 x 5 KB = 500 KB, a quarter of Cosmos's 2 MB item limit. A
realistic round is far below that: the measured 11 to 15 KB, perhaps several times more for a heavy spy.

### What reads and writes each layout costs

| | One document per kingdom (`lastknown_<kd>`) | One document per pair (`lastknown_<kd>_<target>`) |
|---|---|---|
| Galaxy page (about 10 kingdoms) | 1 read | 10 point reads (10 function executions), or one cross-partition query |
| Kingdom view | 1 read | 1 read |
| Revealed and Pinned tables (N kingdoms) | 1 read | N reads |
| The tick, per holder with expiries | 1 merge write | 1 write per target that expired |
| Bytes per write | the whole document (8 KB mean in the run) | 0.5 KB |

Page loads far outnumber expiries (a page loads on every visit; a reveal expires once per spy), and the cost that
bites first on the Consumption plan is function executions, which scale with the number of calls, not their size.

## Decision

- **One `lastknown_<kd_id>` document per kingdom**, `known: {target: {category: {ended, values}}}`, merged by the
  function app keeping the later `ended` per category, so writes commute and a repeat changes nothing. A kingdom with
  no snapshots has no document; a read answers empty without writing.
- **Snapshot after the tick, from what it already has.** `_resolve_revealed` reports each expired reveal; the tick keeps
  every kingdom document it read or wrote in its context, and once every kingdom is done (`_record_ended_intel`) writes
  one merge per holder from those. A target the tick refreshed costs no read; only a target it did not read (gone) is
  read. The values are the target as the tick left it, at most one tick after the expiry; `ended` is the exact expiry.
- **Unshare is an end too.** A galaxymate who stops sharing leaves the other a snapshot of every category.
- **The server filters.** `_get_max_kd_info` adds `last_known` only for categories not revealed now, only from the
  caller's own document, and only on the three display routes (`/api/kingdom/<id>`, `/api/galaxy/<id>`,
  `/api/kingdomsinfo`). Attack, spy and bot code never reads it.
- **Small entries.** A snapshot holds only the category's stored fields; projects drop zero entries and their bonuses
  (worked out again when read).

## Rejected

- **One document per pair.** Smaller writes, but every page that lists kingdoms pays one call per kingdom, and those
  pages are the most frequent reads. A cross-partition query would avoid the calls but costs more RU per page load and
  is a pattern the project keeps off hot paths.
- **Snapshots inside `revealed_<id>`.** No extra read on the pages (they read it already), but that document is
  written on every spy, purchase and share (2.6 times as often as snapshots in the run), and is sent to the browser as
  the `revealed` data key, so every one of those writes and polls would carry the whole snapshot history.
- **Reading each target at expiry.** One read per expired target per tick, when the tick has just read and written
  that target anyway.
- **Recording at reveal time.** The values would be from the start of the reveal, not its end.

## Consequences

- Each display route makes one more read (the caller's `lastknown_` document). The tick makes one write per holder
  whose intel ended in it, and no extra reads.
- A heavy spy's document grows through the round: its writes cost more as it grows. If that shows in the request
  charge, the next step is excluding `/known/*` from the container's indexing policy (an Azure change, so ask first),
  or splitting the document by the target's galaxy.
- A reset deletes the documents with everything else; kingdom ids are not reused, so nothing carries over.
- Open: kingdoms leaving a galaxy and the end of the round leave no snapshots (see [status.md](../status.md)).
