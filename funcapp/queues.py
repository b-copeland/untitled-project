"""
Keeping the build queues (settles, mobis, structures, missiles, engineers) small.

Auto spending queues something on every tick, and several of those land within seconds of each other, so a queue
collects many entries that finish at practically the same moment. Each one is a few hundred bytes in a document that is
read and rewritten on every append, and each one is a row for the player to read on the queue page.

``coalesce`` rounds every entry's finish time *up* to the next multiple of ``window`` seconds and adds together the
entries that land on the same time. So:

* nothing finishes early, and nothing is late by more than ``window``;
* it cannot drift: rounding a time that is already rounded changes nothing, so an entry is never pushed back again by
  later appends, however many there are;
* entries carry no extra fields (the refresh treats every key but ``time`` as a unit or structure name);
* it is one pass with a dictionary, plus a sort of the (already merged) distinct times, so a queue of tens of thousands
  of entries costs milliseconds.

The window is a fraction of the game's epoch: ``QUEUE_MERGE_FRACTION`` (0.1% by default) of ``EPOCH_SECONDS`` (1800 s,
so 1.8 s). It scales with the round speed.
"""
import datetime
import os

# Keep EPOCH_SECONDS equal to BASE_EPOCH_SECONDS in api/untitledapp/shared.py (tests/test_queue_batching.py checks it).
DEFAULT_EPOCH_SECONDS = 30 * 60
DEFAULT_FRACTION = 0.001

_ORIGIN = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
_MS = datetime.timedelta(milliseconds=1)


def window_seconds():
    epoch = float(os.environ.get("EPOCH_SECONDS", DEFAULT_EPOCH_SECONDS))
    return epoch * float(os.environ.get("QUEUE_MERGE_FRACTION", DEFAULT_FRACTION))


def _millis(text):
    return (datetime.datetime.fromisoformat(text).astimezone(datetime.timezone.utc) - _ORIGIN) // _MS


def _is_count(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def coalesce(entries, window=None):
    """Round entry times up to a ``window``-second grid and add together entries that share a time."""
    window = window_seconds() if window is None else window
    window_ms = int(round(window * 1000))
    if window_ms <= 0 or len(entries) < 2:
        return list(entries)

    slots = {}
    for entry in entries:
        slot = -(-_millis(entry["time"]) // window_ms)  # ceiling division
        merged = slots.get(slot)
        if merged is None:
            slots[slot] = merged = {"time": (_ORIGIN + slot * window_ms * _MS).isoformat()}
        for key, value in entry.items():
            if key == "time":
                continue
            if _is_count(value) and (key not in merged or _is_count(merged[key])):
                merged[key] = merged.get(key, 0) + value
            else:
                merged.setdefault(key, value)
    return [slots[slot] for slot in sorted(slots)]
