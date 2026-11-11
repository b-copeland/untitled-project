"""
Keeping the build queues (settles, mobis, structures, missiles, engineers) small.

Auto spending queues something on every tick, and several of those land within seconds of each other, so a queue
collects many entries that finish at practically the same moment. Each one is a few hundred bytes in a document that is
read and rewritten on every append, and each one is a row for the player to read on the queue page.

``coalesce`` folds entries whose times are close together into one. The merged entry takes the *latest* time of the
group, so nothing finishes earlier than it was promised; the cost to the player is that an entry can finish up to
``window`` seconds later than it would have. Counts are added together. A group is anchored at its first entry, so one
never spans more than ``window`` seconds however many entries chain together.

It is a sort and one pass over a list of a few dozen items, far cheaper than the write it saves.
"""
import datetime
import os

DEFAULT_WINDOW_SECONDS = 60


def window_seconds():
    return float(os.environ.get("QUEUE_MERGE_SECONDS", DEFAULT_WINDOW_SECONDS))


def _when(entry):
    return datetime.datetime.fromisoformat(entry["time"]).astimezone(datetime.timezone.utc)


def _is_count(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _merge(group):
    merged = {"time": max((entry["time"] for entry in group), key=lambda t: _when({"time": t}))}
    for entry in group:
        for key, value in entry.items():
            if key == "time":
                continue
            if _is_count(value) and (key not in merged or _is_count(merged[key])):
                merged[key] = merged.get(key, 0) + value
            else:
                merged.setdefault(key, value)
    return merged


def coalesce(entries, window=None):
    """Fold queue entries whose times are within ``window`` seconds (default ``QUEUE_MERGE_SECONDS``) into one."""
    window = window_seconds() if window is None else window
    if window <= 0 or len(entries) < 2:
        return list(entries)

    groups = []
    for entry in sorted(entries, key=_when):
        if groups and (_when(entry) - _when(groups[-1][0])).total_seconds() <= window:
            groups[-1].append(entry)
        else:
            groups.append([entry])
    return [group[0] if len(group) == 1 else _merge(group) for group in groups]
