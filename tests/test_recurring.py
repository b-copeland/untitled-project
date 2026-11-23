"""Recurring spy operations (issue #137): standing orders that use spy attempts as they come back."""
import datetime

import pytest

import untitledapp.conquer as uac
import untitledapp.recurring as rec
import untitledapp.shared as uas
from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get

NOW = datetime.datetime(2026, 6, 1, 12, tzinfo=datetime.timezone.utc)
EPOCH = datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"])
SIPHON_TIME = EPOCH * uas.GAME_CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"]


def _entry(**overrides):
    entry, problem = rec.make_entry({"type": "siphon", "target": TARGET_ID, "drones_pct": 50, **overrides}, KD_ID, NOW)
    assert problem is None, problem
    return entry


# --- the entry -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("request_, problem", [
    ({"type": "rob"}, "Choose a siphon or an intel operation"),
    ({"type": "siphon", "target": KD_ID, "drones_pct": 50}, "You can not spy on yourself"),
    ({"type": "intel", "target": TARGET_ID, "drones_pct": 50, "operation": "siphonfunds"}, "Choose an intel operation"),
    ({"type": "siphon", "target": TARGET_ID, "drones_pct": 0}, "Send between 1% and 100% of your drones"),
    ({"type": "siphon", "target": TARGET_ID, "drones_pct": 50, "stop_after_fails": 11}, "Stop after 0 to 10 failures in a row (0 never stops)"),
    ({"type": "siphon", "target": TARGET_ID, "drones_pct": 50, "until": "2026-06-01T11:00:00+00:00"}, "The end time has passed"),
])
def test_a_bad_request_is_refused_with_a_reason(request_, problem):
    assert rec.make_entry(request_, KD_ID, NOW) == (None, problem)


def test_a_new_entry_is_due_at_once_and_stops_after_three_failures_by_default():
    entry = _entry()
    assert entry["operation"] == "siphonfunds" and entry["drones_pct"] == 0.5
    assert rec.is_due(entry, NOW) and entry["stop_after_fails"] == 3


def test_a_siphon_that_worked_repeats_when_it_has_run_its_course():
    entry, stop = rec.outcome(_entry(), ("success", "Success!"), NOW)
    assert stop is None and entry["fails"] == 0 and entry["runs"] == 1
    assert uas.utc(entry["next"]) == NOW + SIPHON_TIME


def test_a_failed_run_tries_again_at_the_next_attempt_and_stops_after_enough_in_a_row():
    entry = _entry(stop_after_fails=2)
    entry, stop = rec.outcome(entry, ("failure", "Failure!"), NOW)
    assert stop is None and uas.utc(entry["next"]) == NOW
    entry, stop = rec.outcome(entry, ("failure", "Failure!"), NOW)
    assert stop == "it failed 2 times in a row"


def test_zero_never_stops_on_failures_but_refusals_stop_it_and_a_dead_target_ends_it():
    entry = _entry(stop_after_fails=0)
    for _ in range(20):
        entry, stop = rec.outcome(entry, ("failure", "Failure!"), NOW)
        assert stop is None
    for _ in range(rec.REFUSALS_TO_STOP - 1):
        entry, stop = rec.outcome(entry, ("refused", "Not enough drones"), NOW)
        assert stop is None and uas.utc(entry["next"]) == NOW + EPOCH
    assert rec.outcome(entry, ("refused", "Not enough drones"), NOW)[1].startswith("it was refused")
    assert rec.outcome(_entry(), ("dead", "They are dead"), NOW)[1] == "its target is dead"


def test_intel_waits_for_what_it_reveals_to_run_out():
    entry = _entry(type="intel", operation="spymilitary")
    later = NOW + EPOCH * 3
    held = {"revealed": {TARGET_ID: {"military": later.isoformat()}}, "revealed_galaxymates": []}
    assert rec._revealed_until(held, entry, NOW) == later
    assert rec._revealed_until(held, entry, later) is None
    assert rec._revealed_until({"revealed": {}, "revealed_galaxymates": []}, entry, NOW) is None
    entry, stop = rec.outcome(entry, ("waited", later), NOW)
    assert stop is None and uas.utc(entry["next"]) == later and entry["runs"] == 0


# --- in the refresh --------------------------------------------------------------------------------------------------


def test_nothing_due_costs_nothing(app, monkeypatch):
    # Any call to storage would fail the test.
    monkeypatch.setattr(rec.occ, "update", lambda *a, **k: pytest.fail("wrote"))
    monkeypatch.setattr(rec.uag, "_get_kd_info", lambda *a, **k: pytest.fail("read"))
    entry = {**_entry(), "next": (NOW + EPOCH).isoformat()}
    with app.app_context():
        assert rec.resolve_recurring(KD_ID, NOW, {"recurring": [entry], "spy_attempts": 5}) is False
        assert rec.resolve_recurring(KD_ID, NOW, {"recurring": [_entry()], "spy_attempts": 0}) is False
        assert rec.resolve_recurring(KD_ID, NOW, {"spy_attempts": 5}) is False  # a kingdom made before


def _kingdom_with(entries, attempts=5, drones=10_000):
    _set_up_two_kingdoms()
    _create_item(f"kingdom_{KD_ID}", {"recurring": entries, "spy_attempts": attempts, "drones": drones})


def test_a_due_siphon_runs_once_takes_one_attempt_and_is_set_to_repeat(app, monkeypatch):
    monkeypatch.setattr(uac.random, "uniform", lambda a, b: 0.0)  # every roll succeeds
    with app.app_context():
        _kingdom_with([_entry()])
        assert rec.resolve_recurring(KD_ID, NOW, _get(f"/kingdom/{KD_ID}")) is True
        kingdom = _get(f"/kingdom/{KD_ID}")
        assert kingdom["spy_attempts"] == 4
        [entry] = kingdom["recurring"]
        assert entry["last"]["status"] == "success" and uas.utc(entry["next"]) == NOW + SIPHON_TIME
        # Running the tick again at the same time does nothing: it is not due.
        assert rec.resolve_recurring(KD_ID, NOW, kingdom) is False
        assert _get(f"/kingdom/{KD_ID}")["spy_attempts"] == 4


def test_with_fewer_attempts_than_due_entries_the_first_added_go_first(app, monkeypatch):
    monkeypatch.setattr(uac.random, "uniform", lambda a, b: 0.0)
    with app.app_context():
        first, second = _entry(), _entry(type="intel", operation="spykingdom")
        _kingdom_with([first, second], attempts=1)
        rec.resolve_recurring(KD_ID, NOW, _get(f"/kingdom/{KD_ID}"))
        kingdom = _get(f"/kingdom/{KD_ID}")
        by_id = {entry["id"]: entry for entry in kingdom["recurring"]}
        assert by_id[first["id"]]["runs"] == 1 and by_id[second["id"]]["runs"] == 0
        assert kingdom["spy_attempts"] == 0


def test_an_entry_past_its_end_time_is_dropped_and_the_player_told(app):
    with app.app_context():
        entry = {**_entry(), "until": (NOW - EPOCH).isoformat(), "next": (NOW + EPOCH).isoformat()}
        _kingdom_with([entry], attempts=0)
        rec.resolve_recurring(KD_ID, NOW, _get(f"/kingdom/{KD_ID}"))
        assert _get(f"/kingdom/{KD_ID}")["recurring"] == []
        assert "reached its end time" in _get(f"/kingdom/{KD_ID}/news")["news"][-1]["news"]


def test_a_dead_target_ends_the_entry(app):
    with app.app_context():
        _kingdom_with([_entry()])
        _create_item(f"kingdom_{TARGET_ID}", {"status": "Dead"})
        rec.resolve_recurring(KD_ID, NOW, _get(f"/kingdom/{KD_ID}"))
        assert _get(f"/kingdom/{KD_ID}")["recurring"] == []
        assert "target is dead" in _get(f"/kingdom/{KD_ID}/news")["news"][-1]["news"]


# --- the routes ------------------------------------------------------------------------------------------------------


def _post(client, jwt, path, body):
    return client.post(path, json=body, headers={"Authorization": f"Bearer {jwt}"})


def _set_up_two_named_kingdoms():
    _set_up_two_kingdoms()
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Attacker", TARGET_ID: "Target"}})


def test_adding_and_cancelling_through_the_routes(app, client, jwt1):
    _set_up_two_named_kingdoms()
    body = {"type": "siphon", "target": TARGET_ID, "drones_pct": 40}
    assert _post(client, jwt1, "/api/recurring", body).status_code == 200
    duplicate = _post(client, jwt1, "/api/recurring", body)
    assert duplicate.status_code == 400 and "already repeats" in duplicate.get_json()["message"]
    [entry] = _get(f"/kingdom/{KD_ID}")["recurring"]
    assert entry["drones_pct"] == 0.4 and entry["target"] == TARGET_ID and entry["target_name"] == "Target"
    assert _post(client, jwt1, "/api/recurring/cancel", {"id": entry["id"]}).status_code == 200
    assert _get(f"/kingdom/{KD_ID}")["recurring"] == []
    assert _post(client, jwt1, "/api/recurring/cancel", {"id": entry["id"]}).status_code == 400


def test_a_galaxymate_can_not_be_a_target(app, client, jwt1):
    _set_up_two_named_kingdoms()
    _create_item("galaxies", {"galaxies": {"1": [KD_ID, TARGET_ID]}})
    response = _post(client, jwt1, "/api/recurring", {"type": "siphon", "target": TARGET_ID, "drones_pct": 40})
    assert response.status_code == 400 and "galaxymate" in response.get_json()["message"]


def test_the_number_of_entries_is_capped(app, client, jwt1, monkeypatch):
    monkeypatch.setitem(uas.GAME_CONFIG, "BASE_MAX_RECURRING_ENTRIES", 1)
    _set_up_two_named_kingdoms()
    assert _post(client, jwt1, "/api/recurring", {"type": "siphon", "target": TARGET_ID, "drones_pct": 40}).status_code == 200
    response = _post(client, jwt1, "/api/recurring", {"type": "intel", "operation": "spykingdom", "target": TARGET_ID, "drones_pct": 40})
    assert response.status_code == 400 and "more than 1" in response.get_json()["message"]
