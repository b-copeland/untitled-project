"""Siphons in the refresh, against the function app's real handlers (the unit tests in test_refresh.py fake them)."""
import datetime

import untitledapp.refresh as refresh
from tests.test_concurrency import KD_ID, no_shared_lock, _create_item, _get, _set_up_kingdom  # noqa: F401

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
