"""Folding build-queue entries that finish within moments of each other (funcapp/queues.py)."""
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from queues import coalesce  # noqa: E402

T0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def at(seconds):
    return (T0 + datetime.timedelta(seconds=seconds)).isoformat()


def test_entries_within_the_window_become_one_with_the_latest_time_and_summed_counts():
    merged = coalesce([{"time": at(0), "amount": 3}, {"time": at(10), "amount": 4}, {"time": at(20), "amount": 5}], 60)

    assert merged == [{"time": at(20), "amount": 12}]


def test_nothing_finishes_earlier_than_it_was_promised():
    entries = [{"time": at(5), "amount": 1}, {"time": at(50), "amount": 1}]
    assert all(merged["time"] >= max(e["time"] for e in entries) for merged in coalesce(entries, 60))


def test_entries_further_apart_than_the_window_stay_separate():
    entries = [{"time": at(0), "amount": 1}, {"time": at(61), "amount": 2}, {"time": at(500), "amount": 3}]

    assert coalesce(entries, 60) == entries


def test_a_chain_of_close_entries_never_makes_a_group_longer_than_the_window():
    entries = [{"time": at(s), "amount": 1} for s in range(0, 200, 20)]  # each 20 s after the last, 10 entries

    merged = coalesce(entries, 60)

    assert sum(entry["amount"] for entry in merged) == 10
    assert len(merged) == 3  # groups start at 0, 80 and 160


def test_unit_and_structure_queues_add_up_per_field():
    merged = coalesce([
        {"time": at(0), "homes": 5, "mines": 1},
        {"time": at(3), "homes": 2, "fuel_plants": 4},
    ], 60)

    assert merged == [{"time": at(3), "homes": 7, "mines": 1, "fuel_plants": 4}]


def test_input_order_does_not_matter_and_the_input_is_not_changed():
    entries = [{"time": at(30), "amount": 2}, {"time": at(0), "amount": 1}]
    snapshot = [dict(entry) for entry in entries]

    assert coalesce(entries, 60) == [{"time": at(30), "amount": 3}]
    assert entries == snapshot


def test_a_zero_window_turns_it_off_and_short_lists_are_untouched():
    entries = [{"time": at(0), "amount": 1}, {"time": at(1), "amount": 1}]

    assert coalesce(entries, 0) == entries
    assert coalesce(entries[:1], 60) == entries[:1]
    assert coalesce([], 60) == []


def test_times_with_and_without_fractions_of_a_second_compare_correctly():
    merged = coalesce([
        {"time": "2026-01-01T00:00:00+00:00", "amount": 1},
        {"time": "2026-01-01T00:00:00.500000+00:00", "amount": 1},
    ], 60)

    assert merged == [{"time": "2026-01-01T00:00:00.500000+00:00", "amount": 2}]
