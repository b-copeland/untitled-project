"""
Unread counts on ``notifs_<kd_id>``, as a sequence and a read cursor per category:

* ``<category>_total``: how many items have ever been counted (one more for each new item),
* ``<category>_read``: how many of those the player has seen,
* ``<category>``: ``total - read``, the unread count the pages show, kept so that readers need not know the rest.

Marking read moves the cursor to the total the page saw, never back and never past the total, so items that arrived
after the page loaded stay unread and sending the same request twice changes nothing. A document from before the
cursor has only ``<category>``: it reads as that many unread out of that many.
"""


def counter(notifs, category):
    """``(total, read)`` for ``category``."""
    if f"{category}_total" in notifs:
        return int(notifs[f"{category}_total"]), int(notifs.get(f"{category}_read", 0))
    return int(notifs.get(category, 0) or 0), 0


def _store(notifs, category, total, read):
    notifs[f"{category}_total"] = total
    notifs[f"{category}_read"] = read
    notifs[category] = total - read


def add(notifs, category):
    """One more unread item."""
    total, read = counter(notifs, category)
    _store(notifs, category, total + 1, read)


def mark_read(notifs, category, seen_total=None):
    """Seen up to ``seen_total`` items (all of them if None)."""
    total, read = counter(notifs, category)
    seen = total if seen_total is None else min(max(int(seen_total), read), total)
    _store(notifs, category, total, seen)
