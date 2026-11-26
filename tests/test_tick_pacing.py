"""The tick spreads its kingdoms over TICK_SPREAD_SECONDS, so their writes do not land in one burst (refresh._paced)."""
import pytest

from untitledapp import refresh


class Clock:
    """A clock that moves only when something sleeps, or when the work between kingdoms takes ``work`` seconds."""

    def __init__(self, work=0.0):
        self.now = 100.0
        self.work = work
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 6))
        self.now += seconds


def _run(items, spread, clock):
    started = []
    for item in refresh._paced(items, spread, clock=clock.time, sleep=clock.sleep):
        started.append(round(clock.now - 100.0, 6))
        clock.now += clock.work
    return started


def test_kingdoms_start_evenly_over_the_spread():
    clock = Clock()
    assert _run(["1", "2", "3", "4"], 20, clock) == [0, 5, 10, 15]
    assert clock.sleeps == [5, 5, 5]  # never after the last kingdom


def test_work_that_takes_time_waits_only_for_the_rest():
    clock = Clock(work=2)
    assert _run(["1", "2", "3", "4"], 20, clock) == [0, 5, 10, 15]
    assert clock.sleeps == [3, 3, 3]


def test_work_slower_than_the_spread_never_waits():
    clock = Clock(work=10)
    assert _run(["1", "2", "3"], 6, clock) == [0, 10, 20]
    assert clock.sleeps == []


@pytest.mark.parametrize("spread, items", [(0, ["1", "2"]), (-1, ["1", "2"]), (30, ["1"]), (30, [])])
def test_no_spread_or_one_kingdom_never_waits(spread, items):
    clock = Clock()
    assert _run(items, spread, clock) == [0] * len(items)
    assert clock.sleeps == []


def test_production_spreads_and_the_tests_do_not(app):
    import config
    assert 0 < config.Config.TICK_SPREAD_SECONDS < 60
    assert app.config["TICK_SPREAD_SECONDS"] == 0
