# 0016: Login signals are keyed hashes on the user document, kept for 90 days

Date: 2026-11-22. Status: accepted.

## Context
Issue #172 asks for a way to spot one person playing several accounts. That needs something recorded per login that
two of one person's accounts would share. The maintainer agreed to storing addresses and device identifiers. They are
personal data under GDPR for any player in the EU or UK, so what is kept should be the least that does the job, for
a limited time. Rule 4 (many processes) and the free tier rule out anything held in a process or written on every
request.

## Decision
- **Two signals per login:** the address the request came from (the last `X-Forwarded-For` entry, an IPv6 address as
  its /64) and a random device id the login page keeps in the browser's local storage. Bots and the admin login
  record nothing.
- **Stored as keyed hashes** (HMAC-SHA256 with `SECRET_KEY`, cut to 24 hex characters). Equal values give equal
  hashes, which is all the grouping needs; the admin never sees an address, and a leaked user document does not give
  one away.
- **On the user document** (`seen`), which login already reads, with a first and last time per signal. Rewritten only
  when a signal is new or a day old, so most logins add no write.
- **90 days**, and the newest 10 of each kind: older ones are ignored by the list and dropped at the next login or new
  round.

## Rejected
- **Storing the raw address.** It would let the admin judge a shared address (a school, a phone network) by looking
  it up, but it keeps more personal data than "same or not" needs. The page's note says a shared address is only a
  reason to look.
- **A browser fingerprint** (screen, fonts, user agent). More invasive, needs consent under the ePrivacy rules in the
  same way, and less stable than an id the page stores itself.
- **A document per login, or a log.** One write per login, unbounded growth, and another query to group them.
- **Recording on every request or token refresh.** A write, or a read, per request, which decision 0005 removed.

## Consequences
- Changing `SECRET_KEY` makes every stored signal match nothing new: grouping starts again from the next logins.
- Clearing browser storage, or a private window, gives a new device id; the address still links the accounts.
- A player behind a VPN or a shared network can be listed with strangers, or not with their own second account. The
  list is a lead, not proof: a ban is still the admin's judgement.
- The app has no privacy notice yet ([status.md](../status.md)); one should say what is kept, why and for how long.
