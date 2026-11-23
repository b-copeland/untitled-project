# 0017: Unread counts as a sequence and a read cursor

Date: 2026-11-23. Status: accepted.

## Context

The side navigation shows unread counts for kingdom news, galaxy news, messages, the galaxy board and the intel
market, kept on `notifs_<kd_id>`. Each new item added one to a counter, and opening the page set it to 0. Anything
that arrived between the page loading its list and the reset was marked read without ever being shown, and a page
open when something arrived kept its badge until the next visit.

The usual design is a read cursor: the user has seen everything up to a point, and unread is whatever is past it.
Chat apps keep the last message read in each channel.

## Decision

Per category, `notifs_<kd_id>` keeps `<category>_total` (one more for each item) and `<category>_read` (how many have
been seen), and still `<category>` = total - read, the count the pages show (`funcapp/notifs.py`). A page that shows
the items notes the total from the last notifs it fetched, refetches its list, then asks to mark read up to that
total (`src/data/notifs.js`). The cursor never moves back or past the total, so a repeated request changes nothing,
and items that came in after the page loaded stay unread. Pages mark read again when more arrive while they are open.

## Rejected

- **A cursor on time** (read up to the newest item's time). Needs the time each counted item was written to match its
  item exactly: the call sites write the news and the count separately, and messages carry the sender's browser clock.
  A sequence needs no time at all.
- **Counting unread from the lists on every poll.** Removes the counters, but the page polls notifs every 10 seconds
  and the news lists grow all round, so it would read the largest documents most often.
- **Subtracting what the page saw from the counter.** Same effect, but a request sent twice subtracts twice.

## Consequences

- Nothing to migrate: a document with only `<category>` reads as that many unread out of that many, and the first
  write adds the rest. The count fields keep their meaning, so an API from before this reads them unchanged.
- The API sends `clear_categories` alongside `read`, so a function app from before this still clears the category.
- Still one write per kingdom per item, as before: an attack writes the count for every member of both galaxies.
