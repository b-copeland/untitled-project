"""Folding build-queue entries that finish within moments of each other (funcapp/queues.py)."""
import datetime
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from queues import coalesce, window_seconds  # noqa: E402

T0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def at(seconds):
    return (T0 + datetime.timedelta(seconds=seconds)).isoformat()


def when(text):
    return datetime.datetime.fromisoformat(text)


def test_the_window_is_a_tenth_of_a_percent_of_the_epoch():
    assert window_seconds() == 1.8  # 1800 s epoch


def test_entries_in_the_same_slot_become_one_with_summed_counts():
    merged = coalesce([{"time": at(0.2), "amount": 3}, {"time": at(0.9), "amount": 4}, {"time": at(1.5), "amount": 5}], 2)

    assert merged == [{"time": at(2), "amount": 12}]


def test_nothing_finishes_early_and_nothing_is_late_by_more_than_the_window():
    entries = [{"time": at(s / 7), "amount": 1} for s in range(0, 700)]

    assert sum(e["amount"] for e in coalesce(entries, 3.6)) == 700
    for entry in entries:
        slot = min(m for m in (when(x["time"]) for x in coalesce(entries, 3.6)) if m >= when(entry["time"]))
        assert (slot - when(entry["time"])).total_seconds() < 3.6


def test_appending_again_never_pushes_an_entry_back():
    """The failure to avoid: a steady stream of appends chaining one entry later and later."""
    queue = []
    for step in range(200):
        queue = coalesce(queue + [{"time": at(1000 + step), "amount": 1}], 3.6)
        # the very first entry (due at 1000 s) can never end up later than the end of its slot
        assert min(when(e["time"]) for e in queue) <= when(at(1000 + 3.6))
    assert sum(e["amount"] for e in queue) == 200


def test_coalescing_twice_changes_nothing():
    entries = [{"time": at(s * 0.3), "amount": 1} for s in range(50)]
    once = coalesce(entries, 1.8)

    assert coalesce(once, 1.8) == once


def test_entries_further_apart_than_the_window_stay_separate():
    entries = [{"time": at(0), "amount": 1}, {"time": at(10), "amount": 2}, {"time": at(500), "amount": 3}]

    assert coalesce(entries, 1.8) == [{"time": at(0), "amount": 1}, {"time": at(10.8), "amount": 2}, {"time": at(500.4), "amount": 3}]


def test_unit_and_structure_queues_add_up_per_field():
    merged = coalesce([
        {"time": at(0.1), "homes": 5, "mines": 1},
        {"time": at(0.3), "homes": 2, "fuel_plants": 4},
    ], 2)

    assert merged == [{"time": at(2), "homes": 7, "mines": 1, "fuel_plants": 4}]


def test_input_order_does_not_matter_and_the_input_is_not_changed():
    entries = [{"time": at(1), "amount": 2}, {"time": at(0.5), "amount": 1}]
    snapshot = [dict(entry) for entry in entries]

    assert coalesce(entries, 2) == [{"time": at(2), "amount": 3}]
    assert entries == snapshot


def test_a_zero_window_turns_it_off_and_short_lists_are_untouched():
    entries = [{"time": at(0), "amount": 1}, {"time": at(1), "amount": 1}]

    assert coalesce(entries, 0) == entries
    assert coalesce(entries[:1], 2) == entries[:1]
    assert coalesce([], 2) == []


def test_times_with_and_without_fractions_of_a_second_and_other_offsets():
    merged = coalesce([
        {"time": "2026-01-01T00:00:00+00:00", "amount": 1},
        {"time": "2026-01-01T01:00:00.500000+01:00", "amount": 1},
    ], 2)

    # 01:00:00.5+01:00 is 00:00:00.5 UTC, which rounds up to 2 s; 00:00:00 is already on the grid
    assert merged == [{"time": at(0), "amount": 1}, {"time": at(2), "amount": 1}]


def test_a_queue_of_tens_of_thousands_folds_quickly():
    entries = [{"time": at(i * 0.05), "homes": 1} for i in range(50000)]
    start = time.perf_counter()
    merged = coalesce(entries, 1.8)

    assert time.perf_counter() - start < 1.5
    assert sum(m["homes"] for m in merged) == 50000
    assert len(merged) < 1500
