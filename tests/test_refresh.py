"""
Unit tests for the periodic refresh (api/untitledapp/refresh.py).

These patch out the function app, so they need neither it nor Azurite nor Cosmos, and never touch game data.
"""
import datetime
import json
import types

import pytest

import untitledapp.getters as getters
import untitledapp.migrations as migrations
import untitledapp.refresh as refresh
import untitledapp.shared as shared

NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
PAST = (NOW - datetime.timedelta(hours=1)).isoformat()
FUTURE = (NOW + datetime.timedelta(hours=1)).isoformat()


@pytest.fixture(autouse=True)
def setup():
    """Replaces the autouse fixture in conftest.py that wipes the function app: nothing here uses it."""
    yield


class FakeSession:
    """Stands in for REQUESTS_SESSION and records every call to the function app as (method, path, payload)."""

    def __init__(self, kingdom=None):
        self.calls = []
        self.kingdom = kingdom
        self.failures = []
        self.docs = {}  # other documents by path, versioned like the function app's
        self.versions = 0

    def _respond(self, method, url, **kwargs):
        path = url.split("/api", 1)[1]
        self.calls.append((method, path, json.loads(kwargs["data"]) if kwargs.get("data") else None))
        body = json.dumps(self.kingdom) if method == "GET" and path.startswith("/kingdom/") and self.kingdom else "{}"
        if path in self.docs:
            if method == "GET":
                body = json.dumps(self.docs[path])
            elif method == "PATCH":
                if_match = (kwargs.get("headers") or {}).get("If-Match")
                if if_match and if_match != self.docs[path]["_etag"]:
                    return types.SimpleNamespace(text="changed", status_code=412)
                self.versions += 1
                self.docs[path] = {**self.docs[path], **json.loads(kwargs["data"]), "_etag": f'"{self.versions}"'}
        return types.SimpleNamespace(text=body, status_code=self.status_for(method, path, kwargs))

    def status_for(self, method, path, kwargs):
        """200 unless a test queued a failure for this kind of call, e.g. 412 for the kingdom write."""
        for i, (queued_method, queued_prefix, status) in enumerate(self.failures):
            if queued_method == method and path.startswith(queued_prefix):
                del self.failures[i]
                return status
        return 200

    def get(self, url, **kwargs):
        return self._respond("GET", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._respond("PATCH", url, **kwargs)

    def post(self, url, **kwargs):
        return self._respond("POST", url, **kwargs)

    def paths(self, method):
        return [path for m, path, _ in self.calls if m == method]


def _context(state):
    """
    A refresh context that already holds the galaxies, as a tick has after its first kingdom: they and the cluster
    documents are read once per tick, not per kingdom, so the per-kingdom call counts below leave them out. Kingdom 1
    is in no galaxy here, so its cluster benefits are none.
    """
    context = refresh._RefreshContext(state)
    context._galaxies_inverted, context._galaxies = {}, {}
    return context


@pytest.fixture
def session(monkeypatch):
    fake = FakeSession()
    monkeypatch.setattr(refresh, "REQUESTS_SESSION", fake)
    monkeypatch.setattr(refresh.occ, "REQUESTS_SESSION", fake)
    monkeypatch.setattr(getters, "REQUESTS_SESSION", fake)
    return fake


# --- _RefreshContext -------------------------------------------------------------------------------------------------


def test_context_fetches_shared_data_once(app, monkeypatch):
    calls = {"galaxies": 0, "politics": []}

    def fake_galaxies_inverted():
        calls["galaxies"] += 1
        return {"1": "1:1", "2": "1:1", "3": "1:2"}, {}

    def fake_politics(kd_id, galaxy_id):
        calls["politics"].append(galaxy_id)
        return {"active_policies": [galaxy_id]}, {}

    monkeypatch.setattr(getters, "_get_galaxies_inverted", fake_galaxies_inverted)
    monkeypatch.setattr(getters, "_get_galaxy_politics", fake_politics)
    context = refresh._RefreshContext(state={})

    assert context.galaxies_inverted["3"] == "1:2"
    assert context.galaxies_inverted["1"] == "1:1"
    assert context.galaxy_politics("1", "1:1") == {"active_policies": ["1:1"]}
    assert context.galaxy_politics("2", "1:1") == {"active_policies": ["1:1"]}
    assert context.galaxy_politics("3", "1:2") == {"active_policies": ["1:2"]}

    assert calls["galaxies"] == 1
    assert calls["politics"] == ["1:1", "1:2"]


# --- _resolve_schedules ----------------------------------------------------------------------------------------------


def test_schedules_not_due_cost_nothing(app, session):
    with app.app_context():
        ran = refresh._resolve_schedules(1, NOW, {"schedule": [{"time": FUTURE, "type": "attack"}]})

    assert ran is False
    assert session.calls == []


def test_no_schedules_at_all_cost_nothing(app, session):
    with app.app_context():
        assert refresh._resolve_schedules(1, NOW, {"schedule": []}) is False
    assert session.calls == []


def test_due_schedule_runs_and_is_removed(app, session, monkeypatch):
    kingdom = {
        "kdId": 1,
        "_etag": '"1"',
        "money": 5,
        "schedule": [
            {"time": PAST, "type": "attack"},
            {"time": FUTURE, "type": "attack"},
        ],
    }
    session.kingdom = kingdom
    ran_actions = []
    monkeypatch.setattr(refresh, "_resolve_schedule_attack", lambda kd, sched: (ran_actions.append, (sched["time"],)))

    with app.app_context():
        # The caller's copy says one is due, so the kingdom is read again and the due one taken off it before acting.
        ran = refresh._resolve_schedules(1, NOW, kingdom)

    assert ran is True
    assert ran_actions == [PAST]
    assert session.paths("GET") == ["/kingdom/1"]
    (patch_call,) = [c for c in session.calls if c[0] == "PATCH"]
    assert patch_call[1] == "/kingdom/1"
    # Only the schedule is written: the rest of the kingdom is never sent back from a copy that may be old.
    assert patch_call[2] == {"schedule": [{"time": FUTURE, "type": "attack"}]}


def test_schedules_without_a_snapshot_always_read(app, session):
    session.kingdom = {"kdId": 1, "schedule": []}
    with app.app_context():
        # Callers that have no fresh copy keep the old behavior.
        refresh._resolve_schedules(1, NOW)
    assert session.paths("GET") == ["/kingdom/1"]


# --- _resolve_siphons ------------------------------------------------------------------------------------------------


def _siphons(monkeypatch, siphons_out, siphons_in):
    monkeypatch.setattr(getters, "_get_siphons_out", lambda kd_id: siphons_out)
    monkeypatch.setattr(getters, "_get_siphons_in", lambda kd_id: siphons_in)


def test_empty_siphons_are_not_rewritten(app, session, monkeypatch):
    _siphons(monkeypatch, siphons_out=[], siphons_in=[])

    with app.app_context():
        pool, income_in, siphons_in = refresh._resolve_siphons(100, 1, NOW, 1.0)

    assert (pool, income_in, siphons_in) == (0, 0.0, [])
    assert session.calls == []


def test_siphons_in_are_cleared_after_being_collected(app, session, monkeypatch):
    siphons_in = [{"siphon": 5}, {"siphon": 7}]
    _siphons(monkeypatch, siphons_out=[], siphons_in=siphons_in)
    session.docs["/kingdom/1/siphonsin"] = {"siphons_in": list(siphons_in), "_etag": '"s0"'}

    with app.app_context():
        _, income_in, _ = refresh._resolve_siphons(100, 1, NOW, 2.0)

    assert income_in == 6.0
    assert session.docs["/kingdom/1/siphonsin"]["siphons"] == []


def test_siphons_added_while_collecting_are_not_cleared(app, session, monkeypatch):
    collected = [{"siphon": 5}]
    _siphons(monkeypatch, siphons_out=[], siphons_in=collected)
    session.docs["/kingdom/1/siphonsin"] = {"siphons_in": collected + [{"siphon": 9}], "_etag": '"s0"'}

    with app.app_context():
        refresh._resolve_siphons(100, 1, NOW, 2.0)

    assert session.docs["/kingdom/1/siphonsin"]["siphons"] == [{"siphon": 9}]


def test_siphons_out_are_paid_to_the_receiver_and_the_remainder_kept(app, session, monkeypatch):
    out = [{"from": 2, "time": FUTURE, "siphon": 10.0}]
    _siphons(monkeypatch, siphons_out=out, siphons_in=[])
    session.docs["/kingdom/1/siphonsout"] = {"siphons_out": list(out), "_etag": '"s0"'}

    with app.app_context():
        refresh._resolve_siphons(100, 1, NOW, 1.0)

    assert session.paths("PATCH") == ["/kingdom/2/siphonsin", "/kingdom/1/siphonsout"]
    kept = session.docs["/kingdom/1/siphonsout"]["siphons"]
    assert len(kept) == 1 and kept[0]["from"] == 2 and kept[0]["siphon"] < 10.0


def test_a_siphon_payment_carries_the_rate_of_what_is_left(app, session, monkeypatch):
    out = [{"from": 2, "time": FUTURE, "siphon": 10.0}]
    _siphons(monkeypatch, siphons_out=out, siphons_in=[])
    session.docs["/kingdom/1/siphonsout"] = {"siphons_out": list(out), "_etag": '"s0"'}

    with app.app_context():
        refresh._resolve_siphons(100, 1, NOW, 1.0)

    (payment,) = [body["new_siphons"] for method, path, body in session.calls if path == "/kingdom/2/siphonsin"]
    epochs_left = 3600 / shared.GAME_CONFIG["BASE_EPOCH_SECONDS"]
    assert payment["rate"] == pytest.approx(payment["remaining_siphon"] / epochs_left)


def test_the_siphons_running_keep_each_rate_between_payments_and_drop_ended_ones():
    later = (NOW + datetime.timedelta(hours=2)).isoformat()
    ended = (NOW - datetime.timedelta(minutes=1)).isoformat()
    previous = {f"3|{later}": {"from": 3, "until": later, "rate": 4.0}, f"4|{ended}": {"from": 4, "until": ended, "rate": 9.0}}
    payments = [{"from": 2, "siphon": 1.0, "time": FUTURE, "remaining_siphon": 6.0, "rate": 3.0}]
    running = refresh._siphons_running(previous, payments, NOW)
    # Siphon 3 paid nothing this tick but keeps its rate; siphon 4 has ended; siphon 2 is added.
    assert {entry["from"]: entry["rate"] for entry in running.values()} == {3: 4.0, 2: 3.0}
    # A payment from before the rate was sent: what is left over the time left (an hour here).
    old = refresh._siphons_running({}, [{"from": 5, "siphon": 1.0, "time": FUTURE, "remaining_siphon": 6.0}], NOW)
    assert list(old.values())[0]["rate"] == pytest.approx(6.0 / (3600 / shared.GAME_CONFIG["BASE_EPOCH_SECONDS"]))
    # A second payment from the same siphon replaces its entry.
    again = refresh._siphons_running(running, [{**payments[0], "rate": 2.5}], NOW)
    assert len(again) == 2 and again[f"2|{FUTURE}"]["rate"] == 2.5


def test_siphon_payments_wait_for_the_kingdom_to_be_written_and_are_not_repeated_when_the_tick_restarts(app, session, monkeypatch):
    out = [{"from": 2, "time": FUTURE, "siphon": 10.0}]
    _siphons(monkeypatch, siphons_out=out, siphons_in=[])
    session.docs["/kingdom/1/siphonsout"] = {"siphons_out": list(out), "_etag": '"s0"'}
    effects = []

    with app.app_context():
        refresh._resolve_siphons(100, 1, NOW, 1.0, effects)
        refresh._resolve_siphons(100, 1, NOW, 1.0, effects)  # the tick restarted after a conflict
        assert session.paths("PATCH") == []  # nothing paid yet
        effects.clear()
        refresh._resolve_siphons(100, 1, NOW, 1.0, effects)
        for effect in effects:
            effect()

    assert session.paths("PATCH").count("/kingdom/2/siphonsin") == 1


# --- _settle_siphons: how much each siphon pays ----------------------------------------------------------------------

EPOCH = shared.GAME_CONFIG["BASE_EPOCH_SECONDS"]
PER_DRONE = shared.GAME_CONFIG["BASE_DRONES_SIPHON_PER_DRONE"]
SIPHON_EPOCHS = shared.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"]
MAX_SIPHON = shared.GAME_CONFIG["BASE_MAX_SIPHON"]
RICH = 10**9  # an income whose cap no test reaches


def _at(epochs):
    """The time ``epochs`` epochs after NOW."""
    return NOW + datetime.timedelta(seconds=epochs * EPOCH)


def _new_siphon(drones, from_kd=2, started=0.0):
    """An entry as a successful Siphon Funds stores it, ``started`` epochs after NOW."""
    total = drones * PER_DRONE
    return {"from": from_kd, "time": _at(started + SIPHON_EPOCHS).isoformat(), "siphon": total, "rate": total / SIPHON_EPOCHS}


def _run_siphon(siphons, income, ticks, start=0.0):
    """Settle the siphons tick by tick from ``start`` epochs after NOW, each tick ``elapsed`` epochs long. Returns the
    money paid per sender and what is left."""
    paid_to = {}
    clock = start
    for elapsed in ticks:
        clock += elapsed
        paid, siphons = refresh._settle_siphons(siphons, income, _at(clock), elapsed)
        for entry, money, _ in paid:
            paid_to[entry["from"]] = paid_to.get(entry["from"], 0) + money
    return paid_to, siphons


def test_one_siphon_pays_its_share_each_epoch_and_stops_at_its_total():
    siphon = _new_siphon(drones=300)

    paid, kept = refresh._settle_siphons([siphon], RICH, _at(1), 1.0)

    rate = 300 * PER_DRONE / SIPHON_EPOCHS
    assert [(entry["from"], money) for entry, money, _ in paid] == [(2, pytest.approx(rate))]
    assert kept == [{**siphon, "siphon": pytest.approx(300 * PER_DRONE - rate)}]

    paid_to, kept = _run_siphon([siphon], RICH, [1.0] * (SIPHON_EPOCHS + 3))
    assert paid_to[2] == pytest.approx(300 * PER_DRONE)
    assert kept == []


def test_a_late_tick_pays_for_the_time_elapsed_but_never_more_than_the_siphon_has_left():
    siphon = _new_siphon(drones=300)

    paid, kept = refresh._settle_siphons([siphon], RICH, _at(2.5), 2.5)
    assert paid[0][1] == pytest.approx(2.5 * siphon["rate"])

    # A tick long after the end pays what was left, for the time it was still running, and drops it.
    paid, kept = refresh._settle_siphons(kept, RICH, _at(SIPHON_EPOCHS + 10), SIPHON_EPOCHS + 10 - 2.5)
    assert paid[0][1] == pytest.approx(siphon["siphon"] - 2.5 * siphon["rate"])
    assert kept == []


def test_no_time_elapsed_pays_nothing_and_changes_nothing():
    siphon = _new_siphon(drones=300)

    paid, kept = refresh._settle_siphons([siphon], RICH, NOW, 0.0)

    assert paid == []
    assert kept == [siphon]


def test_siphons_under_the_cap_all_pay_in_full():
    siphons = [_new_siphon(drones=100, from_kd=2), _new_siphon(drones=200, from_kd=3, started=-1)]
    income = sum(s["rate"] for s in siphons) / MAX_SIPHON + 1

    paid_to, _ = _run_siphon(siphons, income, [1.0, 1.0])

    assert paid_to == {2: pytest.approx(2 * siphons[0]["rate"]), 3: pytest.approx(2 * siphons[1]["rate"])}


def test_over_the_cap_the_oldest_siphon_is_cut_first_and_newer_ones_pay_in_full():
    oldest = _new_siphon(drones=600, from_kd=2, started=-3)
    middle = _new_siphon(drones=600, from_kd=3, started=-2)
    newest = _new_siphon(drones=600, from_kd=4, started=-1)
    rate = oldest["rate"]
    # The cap leaves room for the two newer siphons and a quarter of the oldest.
    income = 2.25 * rate / MAX_SIPHON

    paid, kept = refresh._settle_siphons([newest, oldest, middle], income, _at(1), 1.0)

    by_sender = {entry["from"]: money for entry, money, _ in paid}
    assert by_sender == {2: pytest.approx(0.25 * rate), 3: pytest.approx(rate), 4: pytest.approx(rate)}
    assert sum(by_sender.values()) == pytest.approx(income * MAX_SIPHON)
    # The list keeps its order; the cut is stored on the oldest, and what it has left is what that rate can still pay.
    assert [entry["from"] for entry in kept] == [4, 2, 3]
    cut = kept[1]
    assert cut["rate"] == pytest.approx(0.25 * rate)
    epochs_left = SIPHON_EPOCHS - 3 - 1
    assert cut["siphon"] == pytest.approx(0.25 * rate * epochs_left)


def test_when_the_cut_is_bigger_than_the_oldest_siphon_the_next_oldest_is_cut_too():
    oldest = _new_siphon(drones=600, from_kd=2, started=-2)
    middle = _new_siphon(drones=600, from_kd=3, started=-1)
    newest = _new_siphon(drones=600, from_kd=4)
    rate = oldest["rate"]
    income = 1.5 * rate / MAX_SIPHON

    paid, kept = refresh._settle_siphons([oldest, middle, newest], income, _at(1), 1.0)

    by_sender = {entry["from"]: money for entry, money, _ in paid}
    assert by_sender == {3: pytest.approx(0.5 * rate), 4: pytest.approx(rate)}
    assert sum(by_sender.values()) == pytest.approx(income * MAX_SIPHON)
    # Cut to nothing, the oldest has nothing left to pay and is dropped.
    assert [entry["from"] for entry in kept] == [3, 4]


def test_a_cut_is_permanent_when_the_income_recovers():
    oldest = _new_siphon(drones=600, from_kd=2, started=-1)
    newest = _new_siphon(drones=600, from_kd=3)
    rate = oldest["rate"]

    _, kept = refresh._settle_siphons([oldest, newest], 1.5 * rate / MAX_SIPHON, _at(1), 1.0)
    paid, kept = refresh._settle_siphons(kept, RICH, _at(2), 1.0)

    by_sender = {entry["from"]: money for entry, money, _ in paid}
    assert by_sender == {2: pytest.approx(0.5 * rate), 3: pytest.approx(rate)}
    assert kept[0]["rate"] == pytest.approx(0.5 * rate)


def test_a_cut_does_not_compound_when_the_income_stays_low():
    oldest = _new_siphon(drones=600, from_kd=2, started=-1)
    newest = _new_siphon(drones=600, from_kd=3)
    income = 1.5 * oldest["rate"] / MAX_SIPHON

    paid_to, _ = _run_siphon([oldest, newest], income, [1.0, 1.0, 1.0])

    assert sum(paid_to.values()) == pytest.approx(3 * income * MAX_SIPHON)


def test_no_income_means_nothing_is_siphoned():
    paid, kept = refresh._settle_siphons([_new_siphon(drones=300)], -50, _at(1), 1.0)

    assert paid == [] and kept == []


def test_an_entry_made_before_the_rate_was_stored_pays_what_it_has_left_evenly_until_it_ends():
    old = {"from": 2, "time": _at(4).isoformat(), "siphon": 400.0}

    paid, kept = refresh._settle_siphons([old], RICH, _at(1), 1.0)

    # Four epochs from the start of the tick to its end: a quarter of it each epoch, and the rate is stored from now on.
    assert paid[0][1] == pytest.approx(100.0)
    assert kept == [{**old, "siphon": pytest.approx(300.0), "rate": pytest.approx(100.0)}]
    paid_to, kept = _run_siphon(kept, RICH, [1.0] * 5, start=1.0)
    assert paid_to[2] == pytest.approx(300.0) and kept == []


def test_an_old_entry_is_cut_like_any_other():
    old = {"from": 2, "time": _at(4).isoformat(), "siphon": 400.0}
    newest = _new_siphon(drones=600, from_kd=3)
    income = newest["rate"] / MAX_SIPHON

    paid, kept = refresh._settle_siphons([newest, old], income, _at(1), 1.0)

    assert {entry["from"]: money for entry, money, _ in paid} == {3: pytest.approx(newest["rate"])}
    assert [entry["from"] for entry in kept] == [3]


def test_resolve_siphons_reports_the_money_siphoned_per_epoch(app, session, monkeypatch):
    siphon = _new_siphon(drones=300)
    _siphons(monkeypatch, siphons_out=[siphon], siphons_in=[])
    session.docs["/kingdom/1/siphonsout"] = {"siphons_out": [siphon], "_etag": '"s0"'}

    with app.app_context():
        out_per_epoch, _, _ = refresh._resolve_siphons(RICH, 1, _at(2), 2.0)

    assert out_per_epoch == pytest.approx(siphon["rate"])
    (payment,) = [data for method, path, data in session.calls if path == "/kingdom/2/siphonsin"]
    assert payment["new_siphons"]["siphon"] == pytest.approx(2 * siphon["rate"])
    assert payment["new_siphons"]["remaining_siphon"] == pytest.approx(siphon["siphon"] - 2 * siphon["rate"])


def test_a_tick_with_no_time_elapsed_writes_nothing(app, session, monkeypatch):
    _siphons(monkeypatch, siphons_out=[_new_siphon(drones=300)], siphons_in=[{"siphon": 5}])

    with app.app_context():
        out_per_epoch, in_per_epoch, _ = refresh._resolve_siphons(RICH, 1, NOW, 0.0)

    assert (out_per_epoch, in_per_epoch) == (0, 0)
    assert session.paths("PATCH") == []


# --- _refresh_kd: when the kingdom is read again --------------------------------------------------------------------


def _kingdom_doc(**overrides):
    doc = {
        "kdId": 1,
        "race": "Xo",  # set up: the refresh skips a kingdom with no race
        "_etag": "\"1\"",
        "status": "Active",
        "projects_points": {project: 0 for project in shared.PROJECTS},
        "projects_max_points": {project: 1 for project in shared.PROJECTS},
        "next_resolve": {},
        "auto_assign_projects": False,
        "units": {"engineers": 0},
        "projects_assigned": {},
        "stars": 7,
        "networth": 70,
        "schedule": [],
        "auto_attack_enabled": False,
        "auto_rob_enabled": False,
        "generals_available": 0,
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def refresh_one(app, session, monkeypatch):
    """Refresh one kingdom with the income maths stubbed out, returning (scores, session)."""
    state = {"state": {}}

    def run(**doc_overrides):
        doc = _kingdom_doc(**doc_overrides)
        session.kingdom = doc
        monkeypatch.setattr(refresh, "_kingdom_with_income", lambda kd, bonuses, st, now, *effects: dict(kd))
        with app.app_context():
            scores = refresh._refresh_kd(1, state, NOW, False, _context(state))
        return scores, session

    return run


def test_quiet_kingdom_is_read_once_and_written_once(refresh_one):
    scores, session = refresh_one()

    assert scores == (7, 70)
    assert session.calls[0][:2] == ("GET", "/kingdom/1")
    assert session.calls[1][:2] == ("PATCH", "/kingdom/1")
    assert len(session.calls) == 2


def test_due_schedule_causes_exactly_one_extra_read(refresh_one, monkeypatch):
    monkeypatch.setattr(refresh, "_resolve_schedule_attack", lambda kd, sched: (lambda: None, ()))

    _, session = refresh_one(schedule=[{"time": PAST, "type": "attack"}])

    # initial read, income write, then the schedule's own read and write, then one read of the result
    assert session.paths("GET") == ["/kingdom/1", "/kingdom/1", "/kingdom/1"]
    assert session.paths("PATCH") == ["/kingdom/1", "/kingdom/1"]


def test_auto_attack_and_rob_each_cause_one_extra_read(refresh_one, monkeypatch):
    attacked, robbed = [], []
    monkeypatch.setattr(refresh, "_resolve_auto_attack", lambda kd: attacked.append(kd["kdId"]) or True)
    monkeypatch.setattr(refresh, "_resolve_auto_rob", lambda kd: robbed.append(kd["kdId"]) or True)

    _, session = refresh_one(auto_attack_enabled=True, generals_available=2, auto_rob_enabled=True)

    assert attacked == [1] and robbed == [1]
    assert session.paths("GET") == ["/kingdom/1"] * 3
    assert session.paths("PATCH") == ["/kingdom/1"]


def test_auto_rob_that_does_not_rob_causes_no_extra_read(refresh_one, monkeypatch):
    monkeypatch.setattr(refresh, "_resolve_auto_rob", lambda kd: False)

    _, session = refresh_one(auto_rob_enabled=True)

    assert session.paths("GET") == ["/kingdom/1"]


# --- _resolve_scores ------------------------------------------------------------------------------------------------


def test_scores_count_each_galaxys_kingdoms_still_alive(app, session):
    session.docs["/scores"] = {"points": {}, "stars": {}, "networth": {}, "galaxy_networth": {},
                               "last_update": NOW.isoformat(), "_etag": '"s0"'}
    context = refresh._RefreshContext(state={})
    context._galaxies_inverted = {"1": "1:1", "2": "1:1", "3": "1:2"}
    # Kingdom 2 is dead: the refresh scores a dead kingdom (0, 0).
    scores = {"stars": {"1": 10, "2": 0, "3": 5}, "networth": {"1": 100, "2": 0, "3": 50}}
    with app.app_context():
        refresh._resolve_scores(scores, NOW, context)
    written = session.docs["/scores"]
    assert written["galaxy_kingdoms_alive"] == {"1:1": 1, "1:2": 1}
    assert written["galaxy_networth"] == {"1:1": 100, "1:2": 50}


# --- refresh_data: one bad kingdom ----------------------------------------------------------------------------------


def test_one_failing_kingdom_does_not_stop_the_rest_and_keeps_its_old_score(app, client, monkeypatch):
    monkeypatch.setenv("REFRESH_SECRET", "secret")
    state = {
        "state": {
            "game_start": "2000-01-01T00:00:00+00:00",
            "election_start": "2999-01-01T00:00:00+00:00",
            "election_end": "",
            "next_history": "2999-01-01T00:00:00+00:00",
            "migrations_done": migrations.all_ids(),  # this test is about kingdoms, not migrations
        }
    }
    monkeypatch.setattr(getters, "_get_state", lambda: state)
    monkeypatch.setattr(getters, "_get_kingdoms", lambda: ["1", "2", "3"])
    monkeypatch.setattr(
        getters, "_get_scores", lambda: {"stars": {"2": 55}, "networth": {"2": 555}}
    )

    visited = []

    def fake_refresh_kd(kd_id, state, time_update, update_history, context=None):
        visited.append(kd_id)
        if kd_id == "2":
            raise ValueError("bad legacy data")
        return {"1": (10, 100), "3": (30, 300)}[kd_id]

    resolved = {}
    monkeypatch.setattr(refresh, "_refresh_kd", fake_refresh_kd)
    monkeypatch.setattr(refresh, "_resolve_scores", lambda scores, now, context=None: resolved.update(scores=scores))
    monkeypatch.setattr(refresh, "_resolve_empires", lambda scores, now: None)
    monkeypatch.setattr(refresh, "_resolve_clusters", lambda empires, now, context: None)

    response = client.get("/api/refreshdata", headers={"Refresh-Secret": "secret"})

    assert response.status_code == 200
    assert "failed" in response.get_data(as_text=True)
    assert visited == ["1", "2", "3"]
    assert resolved["scores"] == {
        "stars": {"1": 10, "2": 55, "3": 30},
        "networth": {"1": 100, "2": 555, "3": 300},
    }


def test_refresh_still_requires_the_secret(app, client, monkeypatch):
    monkeypatch.setenv("REFRESH_SECRET", "secret")
    assert client.get("/api/refreshdata").status_code == 401
    assert client.get("/api/refreshdata", headers={"Refresh-Secret": "wrong"}).status_code == 401


# --- _refresh_kd: queues are credited once, and trimmed only after the kingdom is written -----------------------------


def _settling(session, kingdom=None):
    session.kingdom = _kingdom_doc(next_resolve={"settles": PAST}, **(kingdom or {}))
    session.kingdom["_etag"] = '"k1"'
    session.docs["/kingdom/1/settles"] = {
        "settles": [{"time": PAST, "amount": 3}, {"time": FUTURE, "amount": 2}], "_etag": '"q0"'}


def _refresh(app, monkeypatch, when=NOW):
    state = {"state": {}}
    monkeypatch.setattr(refresh, "_kingdom_with_income", lambda kd, bonuses, st, now, *effects: dict(kd))
    with app.app_context():
        return refresh._refresh_kd(1, state, when, False, _context(state))


def _kingdom_writes(session):
    return [payload for method, path, payload in session.calls if method == "PATCH" and path == "/kingdom/1"]


def test_finished_settles_are_credited_and_the_queue_is_trimmed_after_the_kingdom_is_written(app, session, monkeypatch):
    _settling(session)

    scores = _refresh(app, monkeypatch)

    assert scores[0] == 10  # 7 stars + 3 settled
    order = [(m, p) for m, p, _ in session.calls if m == "PATCH"]
    assert order.index(("PATCH", "/kingdom/1")) < order.index(("PATCH", "/kingdom/1/settles"))
    assert session.docs["/kingdom/1/settles"]["settles"] == [{"time": FUTURE, "amount": 2}]


def test_the_old_shared_timer_is_retired_without_reading_anything_for_it(app, session, monkeypatch):
    # Kingdoms made before the intel market have a "shared" timer. It is set to never, and no shared document is read.
    session.kingdom = _kingdom_doc(next_resolve={"shared": PAST})
    session.kingdom["_etag"] = '"k1"'

    _refresh(app, monkeypatch)

    (written,) = _kingdom_writes(session)
    assert written["next_resolve"]["shared"].startswith("2099")
    assert not any("/shared" in path for _, path, _ in session.calls)


def test_the_kingdom_is_written_with_the_version_it_was_read_at(app, session, monkeypatch):
    _settling(session)
    seen = []
    original = session.patch

    def patch(url, **kwargs):
        if url.endswith("/kingdom/1"):
            seen.append(kwargs["headers"].get("If-Match"))
        return original(url, **kwargs)

    monkeypatch.setattr(session, "patch", patch)
    _refresh(app, monkeypatch)

    assert seen == ['"k1"']


def test_a_conflicting_write_makes_the_tick_start_again_without_crediting_twice(app, session, monkeypatch):
    _settling(session)
    session.failures.append(("PATCH", "/kingdom/1", 412))

    scores = _refresh(app, monkeypatch)

    assert scores[0] == 10
    assert session.paths("GET").count("/kingdom/1") >= 2  # read again after the conflict
    assert len(_kingdom_writes(session)) == 2
    # nothing was trimmed until a write landed, and then once
    assert session.paths("PATCH").count("/kingdom/1/settles") == 1


def test_a_lost_trim_does_not_credit_the_same_settles_on_the_next_tick(app, session, monkeypatch):
    _settling(session)
    original_queue = json.loads(json.dumps(session.docs["/kingdom/1/settles"]))
    _refresh(app, monkeypatch)
    after_first = _kingdom_writes(session)[-1]
    assert after_first["queues_resolved_until"]["settles"] == NOW.isoformat()

    # the trim never happened (the process died after writing the kingdom), and a minute later the tick runs again
    session.kingdom = {**after_first, "next_resolve": {"settles": PAST}, "_etag": '"k2"'}
    session.docs["/kingdom/1/settles"] = original_queue
    scores = _refresh(app, monkeypatch, when=NOW + datetime.timedelta(minutes=1))

    assert scores[0] == 10  # still 10, not 13
    assert session.docs["/kingdom/1/settles"]["settles"] == [{"time": FUTURE, "amount": 2}]


def test_settles_queued_while_the_tick_runs_survive_the_trim(app, session, monkeypatch):
    _settling(session)
    original = session.patch

    def patch(url, **kwargs):
        response = original(url, **kwargs)
        if url.endswith("/kingdom/1"):
            # the player queues more settling right after the kingdom is written, before the trim
            session.docs["/kingdom/1/settles"]["settles"].append({"time": FUTURE, "amount": 5})
            session.docs["/kingdom/1/settles"]["_etag"] = '"q-new"'
        return response

    monkeypatch.setattr(session, "patch", patch)
    _refresh(app, monkeypatch)

    assert [entry["amount"] for entry in session.docs["/kingdom/1/settles"]["settles"]] == [2, 5]


def test_a_scheduled_spy_shares_its_intel_for_the_cut_asked(monkeypatch):
    sent = []
    monkeypatch.setattr(refresh.uag, "_get_kd_info", lambda kd_id: {"drones": 1000})
    monkeypatch.setattr(refresh.uac, "_spy", lambda req, kd_id, target: (sent.append(req) or ({}, {}, 200, True)))
    options = {"drones_pct": 0.5, "max_tries": 1, "operation": "spymilitary", "target": "2", "share_to_galaxy": True}

    func, args = refresh._resolve_schedule_intelspy({"kdId": "1"}, {"options": {**options, "cut": 10.0}})
    func(*args)
    func, args = refresh._resolve_schedule_intelspy({"kdId": "1"}, {"options": options})  # the Schedule page sends none
    func(*args)

    assert [req["cut"] for req in sent] == [10.0, 0]
    assert all(req["share_to_galaxy"] for req in sent)


# --- reactive rules in the tick --------------------------------------------------------------------------------------


def _rob_off_rule(kind):
    import untitledapp.rules as rules
    rule, problem = rules.make_rule({"when": {"kind": kind}, "then": {"kind": "settings", "hours": 2,
                                                                    "settings": {"auto_rob_enabled": False}}})
    assert problem is None
    return rule


def test_a_rule_on_something_done_to_the_kingdom_costs_no_call(refresh_one):
    _, session = refresh_one(rules=[_rob_off_rule("attacked")])
    assert session.paths("GET") == ["/kingdom/1"] and session.paths("PATCH") == ["/kingdom/1"]


def test_a_war_rule_fires_in_the_tick_write(refresh_one, monkeypatch):
    monkeypatch.setattr(refresh._RefreshContext, "at_war", lambda self, kd_id: True)
    told = []
    monkeypatch.setattr(refresh, "_tell_rule", lambda kd_id, message: told.append(message))
    _, session = refresh_one(rules=[_rob_off_rule("at_war")], auto_rob_enabled=True)
    written = next(payload for method, path, payload in session.calls if method == "PATCH" and path == "/kingdom/1")
    assert written["auto_rob_enabled"] is False
    assert written["rules"][0]["state"]["fires"] == 1
    assert "went to war" in told[0]


def test_a_hangars_rule_reads_the_training_queue_once(refresh_one, session, monkeypatch):
    session.docs["/kingdom/1/mobis"] = {"mobis": [], "_etag": '"0"'}
    monkeypatch.setattr(refresh.uag, "_calc_units", lambda *args: {})
    monkeypatch.setattr(refresh.uag, "_calc_hangar_capacity", lambda kd, units: (100, 50))  # room to spare
    _, session = refresh_one(rules=[_rob_off_rule("hangars_full")], generals_out=[])
    assert session.paths("GET").count("/kingdom/1/mobis") == 1


# --- bots and players ------------------------------------------------------------------------------------------------


def _bot_gate(app, session, target_doc, kingdom=None, schedule_type="attack"):
    session.docs["/kingdom/9"] = {"kdId": "9", "_etag": '"0"', **target_doc}
    bot = kingdom if kingdom is not None else {"kdId": "1", "bot": {"type": "attacker"}}
    with app.app_context():
        return refresh._bot_may_act_on(bot, {"type": schedule_type, "options": {"target": "9"}}, NOW)


def test_bots_may_hit_a_player_three_times_then_not(app, session):
    session.docs["/kingdom/9"] = {"kdId": "9", "_etag": '"0"'}
    results = []
    with app.app_context():
        for _ in range(5):
            results.append(refresh._bot_may_act_on(
                {"kdId": "1", "bot": {"type": "attacker"}}, {"type": "attack", "options": {"target": "9"}}, NOW))
    assert results == [True, True, True, False, False]


def test_bots_are_not_held_back_from_bots_and_players_are_not_held_back_at_all(app, session):
    assert all(_bot_gate(app, session, {"bot": {"type": "thief"}}) for _ in range(6))
    assert all(_bot_gate(app, session, {}, kingdom={"kdId": "2"}) for _ in range(6))
    assert all(_bot_gate(app, session, {}, schedule_type="intelspy") for _ in range(6))
