"""
Unit tests for the periodic refresh (api/untitledapp/refresh.py).

These patch out the function app, so they need neither it nor Azurite nor Cosmos, and never touch game data.
"""
import datetime
import json
import types

import pytest

import untitledapp.getters as getters
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

    def _respond(self, method, url, **kwargs):
        path = url.split("/api", 1)[1]
        self.calls.append((method, path, json.loads(kwargs["data"]) if kwargs.get("data") else None))
        body = json.dumps(self.kingdom) if method == "GET" and path.startswith("/kingdom/") and self.kingdom else "{}"
        return types.SimpleNamespace(text=body)

    def get(self, url, **kwargs):
        return self._respond("GET", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._respond("PATCH", url, **kwargs)

    def post(self, url, **kwargs):
        return self._respond("POST", url, **kwargs)

    def paths(self, method):
        return [path for m, path, _ in self.calls if m == method]


@pytest.fixture
def session(monkeypatch):
    fake = FakeSession()
    monkeypatch.setattr(refresh, "REQUESTS_SESSION", fake)
    monkeypatch.setattr(getters, "REQUESTS_SESSION", fake)
    # Locks live in SQLite and are not what is being tested here.
    monkeypatch.setattr(refresh.uam, "acquire_lock", lambda *a, **k: True)
    monkeypatch.setattr(refresh.uam, "release_lock", lambda *a, **k: None)
    monkeypatch.setattr(refresh.uam, "acquire_locks", lambda *a, **k: True)
    monkeypatch.setattr(refresh.uam, "release_locks_by_id", lambda *a, **k: None)
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
        "schedule": [
            {"time": PAST, "type": "attack"},
            {"time": FUTURE, "type": "attack"},
        ],
    }
    session.kingdom = kingdom
    ran_actions = []
    monkeypatch.setattr(refresh, "_resolve_schedule_attack", lambda kd, sched: (ran_actions.append, (sched["time"],)))

    with app.app_context():
        # The caller's copy says one is due, so the kingdom is read again under the lock before acting.
        ran = refresh._resolve_schedules(1, NOW, kingdom)

    assert ran is True
    assert ran_actions == [PAST]
    assert session.paths("GET") == ["/kingdom/1"]
    (patch_call,) = [c for c in session.calls if c[0] == "PATCH"]
    assert patch_call[1] == "/kingdom/1"
    assert patch_call[2]["schedule"] == [{"time": FUTURE, "type": "attack"}]


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
    _siphons(monkeypatch, siphons_out=[], siphons_in=[{"siphon": 5}, {"siphon": 7}])

    with app.app_context():
        _, income_in, _ = refresh._resolve_siphons(100, 1, NOW, 2.0)

    assert income_in == 6.0
    assert session.calls == [("PATCH", "/kingdom/1/siphonsin", {"siphons": []})]


def test_siphons_out_are_paid_to_the_receiver_and_the_remainder_kept(app, session, monkeypatch):
    _siphons(monkeypatch, siphons_out=[{"from": 2, "time": FUTURE, "siphon": 10.0}], siphons_in=[])

    with app.app_context():
        refresh._resolve_siphons(100, 1, NOW, 1.0)

    assert session.paths("PATCH") == ["/kingdom/2/siphonsin", "/kingdom/1/siphonsout"]
    kept = session.calls[1][2]["siphons"]
    assert len(kept) == 1 and kept[0]["from"] == 2


# --- _refresh_kd: when the kingdom is read again --------------------------------------------------------------------


def _kingdom_doc(**overrides):
    doc = {
        "kdId": 1,
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
        monkeypatch.setattr(refresh, "_kingdom_with_income", lambda kd, bonuses, st, now: dict(kd))
        with app.app_context():
            scores = refresh._refresh_kd(1, state, NOW, False, refresh._RefreshContext(state))
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


# --- refresh_data: one bad kingdom ----------------------------------------------------------------------------------


def test_one_failing_kingdom_does_not_stop_the_rest_and_keeps_its_old_score(app, client, monkeypatch):
    monkeypatch.setenv("REFRESH_SECRET", "secret")
    state = {
        "state": {
            "game_start": "2000-01-01T00:00:00+00:00",
            "election_start": "2999-01-01T00:00:00+00:00",
            "election_end": "",
            "next_history": "2999-01-01T00:00:00+00:00",
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
