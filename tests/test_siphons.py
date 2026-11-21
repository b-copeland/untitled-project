"""Siphons in the refresh, against the function app's real handlers (the unit tests in test_refresh.py fake them)."""
import datetime

import pytest

import untitledapp.refresh as refresh
import untitledapp.shared as shared
from tests.test_concurrency import KD_ID, _create_item, _get, _set_up_kingdom  # noqa: F401

THIEF = "2"


def test_a_siphon_is_paid_once_per_tick_and_what_is_left_of_it_is_kept(app):
    """Regression: the refresh read the siphon lists under a key the documents do not have, so it raised after paying
    the thief and never wrote back what was left: the thief was paid the same siphon again on every tick."""
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id=THIEF)
    now = datetime.datetime.now(datetime.timezone.utc)
    until = (now + datetime.timedelta(hours=5)).isoformat()
    _create_item(f"siphons_out_{KD_ID}", {"siphons_out": [{"from": THIEF, "time": until, "siphon": 100.0}]})

    with app.app_context():
        pool, _, _ = refresh._resolve_siphons(1000, KD_ID, now, 1.0)

    assert pool > 0
    left = _get(f"/kingdom/{KD_ID}/siphonsout")["siphons_out"]
    assert len(left) == 1 and left[0]["from"] == THIEF and left[0]["siphon"] == 100.0 - pool
    paid = _get(f"/kingdom/{THIEF}/siphonsin")["siphons_in"]
    assert [entry["from"] for entry in paid] == [KD_ID]


def test_collected_siphons_are_cleared(app):
    _set_up_kingdom(money=0)
    _create_item(f"siphons_in_{KD_ID}", {"siphons_in": [{"from": THIEF, "siphon": 5.0, "time": "x", "remaining_siphon": 0}]})

    with app.app_context():
        _, income_in, _ = refresh._resolve_siphons(1000, KD_ID, datetime.datetime.now(datetime.timezone.utc), 1.0)

    assert income_in == 5.0
    assert _get(f"/kingdom/{KD_ID}/siphonsin")["siphons_in"] == []


def test_a_cut_is_stored_on_the_oldest_siphon_and_the_newer_one_is_paid_in_full(app):
    for kd_id in (KD_ID, THIEF, "3"):
        _set_up_kingdom(money=0, kd_id=kd_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    oldest = {"from": THIEF, "time": (now + datetime.timedelta(hours=1)).isoformat(), "siphon": 100.0, "rate": 50.0}
    newest = {"from": "3", "time": (now + datetime.timedelta(hours=5)).isoformat(), "siphon": 500.0, "rate": 50.0}
    _create_item(f"siphons_out_{KD_ID}", {"siphons_out": [oldest, newest]})
    income = 80 / shared.GAME_CONFIG["BASE_MAX_SIPHON"]  # room for the newest and 30 of the oldest

    with app.app_context():
        out_per_epoch, _, _ = refresh._resolve_siphons(income, KD_ID, now, 1.0)

    assert out_per_epoch == pytest.approx(80)
    left = {entry["from"]: entry for entry in _get(f"/kingdom/{KD_ID}/siphonsout")["siphons_out"]}
    assert left[THIEF]["rate"] == pytest.approx(30) and left["3"]["rate"] == 50.0
    assert left["3"]["siphon"] == pytest.approx(450)
    assert [entry["siphon"] for entry in _get(f"/kingdom/{THIEF}/siphonsin")["siphons_in"]] == [pytest.approx(30)]
    assert [entry["siphon"] for entry in _get("/kingdom/3/siphonsin")["siphons_in"]] == [pytest.approx(50)]


def test_a_siphon_from_a_dead_kingdom_ends_and_pays_nothing(app):
    """#57: a dead siphoner's siphon is taken off the list without paying, and frees its share of the cap."""
    for kd_id in (KD_ID, THIEF, "3"):
        _set_up_kingdom(money=0, kd_id=kd_id)
    _create_item(f"kingdom_{THIEF}", {**_get(f"/kingdom/{THIEF}"), "status": "Dead"})
    now = datetime.datetime.now(datetime.timezone.utc)
    dead = {"from": THIEF, "time": (now + datetime.timedelta(hours=1)).isoformat(), "siphon": 100.0, "rate": 50.0}
    alive = {"from": "3", "time": (now + datetime.timedelta(hours=5)).isoformat(), "siphon": 500.0, "rate": 50.0}
    _create_item(f"siphons_out_{KD_ID}", {"siphons_out": [dead, alive]})
    income = 50 / shared.GAME_CONFIG["BASE_MAX_SIPHON"]  # room for one siphon only: the live one gets all of it

    with app.app_context():
        context = refresh._RefreshContext(state=None)
        out_per_epoch, _, _ = refresh._resolve_siphons(
            income, KD_ID, now, 1.0, is_dead=lambda kd: refresh._is_dead(context.kingdom(kd)))

    assert out_per_epoch == pytest.approx(50)
    assert [entry["from"] for entry in _get(f"/kingdom/{KD_ID}/siphonsout")["siphons_out"]] == ["3"]
    assert _get(f"/kingdom/{THIEF}/siphonsin")["siphons_in"] == []
    assert [entry["siphon"] for entry in _get("/kingdom/3/siphonsin")["siphons_in"]] == [pytest.approx(50)]


def test_the_refresh_ends_siphons_from_a_dead_kingdom(app):
    """Through a kingdom's tick: the target's refresh drops the dead siphoner's siphon."""
    now = datetime.datetime.now(datetime.timezone.utc)
    for kd_id in (KD_ID, THIEF):
        _set_up_kingdom(money=0, kd_id=kd_id, race="Xo", last_income=(now - datetime.timedelta(minutes=5)).isoformat())
    _create_item(f"kingdom_{THIEF}", {**_get(f"/kingdom/{THIEF}"), "status": "Dead"})
    until = (now + datetime.timedelta(hours=5)).isoformat()
    _create_item(f"siphons_out_{KD_ID}", {"siphons_out": [{"from": THIEF, "time": until, "siphon": 100.0, "rate": 10.0}]})

    with app.app_context():
        state = _get("/state")
        refresh._refresh_kd(KD_ID, state, now, False)

    assert _get(f"/kingdom/{KD_ID}/siphonsout")["siphons_out"] == []
    assert _get(f"/kingdom/{THIEF}/siphonsin")["siphons_in"] == []
    assert _get(f"/kingdom/{KD_ID}")["income"]["money"]["siphons_out"] == 0
