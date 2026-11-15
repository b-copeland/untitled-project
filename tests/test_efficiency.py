"""
How many function app calls the hot paths make, and the helpers that keep the number down: the per-request cache of
shared documents (request_cache.py), ``occ.update`` starting from a document the caller already read, and the refresh
reusing what it has read instead of asking again. See docs/cost.md.
"""
import collections
import datetime
import json

import pytest

import untitledapp.getters as uag
import untitledapp.occ as occ
import untitledapp.refresh as refresh
from untitledapp import REQUESTS_SESSION, request_cache
from tests.test_attack import _set_up_two_kingdoms
from tests.test_concurrency import FUNCTION_URL, KD_ID, no_shared_lock, _create_item, _get, _set_up_kingdom  # noqa: F401


@pytest.fixture
def calls(monkeypatch):
    """Every call to the function app from here on, as (method, path)."""
    recorded = []
    original = REQUESTS_SESSION.request

    def request(method, url, *args, **kwargs):
        recorded.append((method.upper(), url.split("/api", 1)[1].split("?")[0]))
        return original(method, url, *args, **kwargs)

    monkeypatch.setattr(REQUESTS_SESSION, "request", request)
    return recorded


def _count(calls, method, path):
    return sum(1 for call in calls if call == (method, path))


# --- the per-request cache -----------------------------------------------------------------------------------------


def test_shared_documents_are_read_once_per_request(app, calls):
    _set_up_kingdom(money=0)
    with app.app_context(), request_cache.scope():
        calls.clear()
        for _ in range(3):
            uag._get_state()
            uag._get_galaxy_info()
            uag._get_galaxy_politics(KD_ID)
    assert _count(calls, "GET", "/state") == 1
    assert _count(calls, "GET", "/galaxies") == 1
    assert _count(calls, "GET", "/galaxy/1/politics") == 1


def test_each_request_reads_afresh(app, calls):
    _set_up_kingdom(money=0)
    for _ in range(2):
        with app.app_context(), request_cache.scope():
            uag._get_state()
    assert _count(calls, "GET", "/state") == 2


def test_a_page_load_reads_each_shared_document_once(app, client, jwt1, calls):
    """Through a real request, so the app's before and after request hooks are what open and close the cache."""
    _set_up_two_kingdoms()
    calls.clear()
    response = client.get("/api/galaxy/1", headers={"Authorization": f"Bearer {jwt1}"})
    assert response.status_code == 200
    assert _count(calls, "GET", "/galaxies") == 1  # _get_galaxies_inverted is called twice on this route

    calls.clear()
    client.get("/api/galaxy/1", headers={"Authorization": f"Bearer {jwt1}"})
    assert _count(calls, "GET", "/galaxies") == 1  # and the next request reads it afresh


def test_nothing_is_cached_outside_a_request(app, calls):
    _set_up_kingdom(money=0)
    with app.app_context():
        uag._get_state()
        uag._get_state()
    assert _count(calls, "GET", "/state") == 2


def test_a_write_drops_the_cached_copy_of_what_it_wrote(app, calls):
    _set_up_kingdom(money=0)
    with app.app_context(), request_cache.scope():
        uag._get_galaxy_info()
        assert "next_history" not in uag._get_state()["state"]
        REQUESTS_SESSION.patch(f"{FUNCTION_URL}/updatestate", data=json.dumps({"next_history": "later"}))
        assert uag._get_state()["state"]["next_history"] == "later"
        uag._get_galaxy_info()
    assert _count(calls, "GET", "/state") == 2
    assert _count(calls, "GET", "/galaxies") == 1  # not what was written


def test_a_galaxy_vote_drops_only_that_galaxys_politics(app, calls):
    _set_up_two_kingdoms()
    with app.app_context(), request_cache.scope():
        uag._get_galaxy_politics(KD_ID, "1")
        uag._get_galaxy_politics(KD_ID, "2")
        occ.update("/galaxy/1/politics", lambda doc: ({"active_policies": ["Warlike"]}, None))
        assert uag._get_galaxy_politics(KD_ID, "1")[0]["active_policies"] == ["Warlike"]
        uag._get_galaxy_politics(KD_ID, "2")
    assert _count(calls, "GET", "/galaxy/2/politics") == 1


def test_any_other_write_empties_the_cache(app, calls):
    _set_up_kingdom(money=0)
    with app.app_context(), request_cache.scope():
        uag._get_galaxy_info()
        _create_item("galaxies", {"galaxies": {"1": [KD_ID], "9": []}})
        assert "9" in uag._get_galaxy_info()


def test_a_caller_can_change_what_it_was_given(app):
    _set_up_kingdom(money=0)
    with app.app_context(), request_cache.scope():
        uag._get_galaxy_info()["1"].append("intruder")
        assert uag._get_galaxy_info()["1"] == [KD_ID]


# --- occ.update with a document the caller has read ----------------------------------------------------------------


def test_update_starts_from_the_callers_document_without_reading_it_again(app, calls):
    _set_up_kingdom(money=100)
    with app.app_context():
        document = occ.read(f"/kingdom/{KD_ID}")
        calls.clear()
        occ.update(f"/kingdom/{KD_ID}", lambda kd: ({"money": kd["money"] - 40}, None), document=document)
    assert calls == [("PATCH", f"/kingdom/{KD_ID}")]
    assert _get(f"/kingdom/{KD_ID}")["money"] == 60


def test_update_with_an_out_of_date_document_decides_again_on_the_current_one(app, calls):
    _set_up_kingdom(money=100)
    seen = []

    def spend(kd):
        seen.append(kd["money"])
        kd["next_resolve"]["generals"] = "changed in place"  # decide may change what it is given
        return {"money": kd["money"] - 40}, None

    with app.app_context():
        stale = occ.read(f"/kingdom/{KD_ID}")
        occ.update(f"/kingdom/{KD_ID}", lambda kd: ({"money": 70}, None))  # someone else spends meanwhile
        occ.update(f"/kingdom/{KD_ID}", spend, document=stale)

    assert seen == [100, 70]  # the stale copy was refused, and the decision made again on the current one
    assert _get(f"/kingdom/{KD_ID}")["money"] == 30
    assert stale["money"] == 100 and stale["next_resolve"]["generals"] != "changed in place"


# --- the refresh -----------------------------------------------------------------------------------------------------


def _auto_spending_kingdom():
    """Kingdom 1 with auto spending due, money in every fund, and targets to build towards."""
    _set_up_two_kingdoms()
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Spender", "2": "Target"}})
    kd = _get(f"/kingdom/{KD_ID}")
    long_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    _create_item(f"kingdom_{KD_ID}", {
        **kd,
        "auto_spending_enabled": True,
        "funding": {"settle": 1_000_000, "structures": 1_000_000, "military": 1_000_000, "engineers": 1_000_000},
        "structures_target": {"homes": 0.5, "mines": 0.5},
        "units_target": {"attack": 0.5, "defense": 0.5},
        "units": {**kd["units"], "recruits": 100},
        "last_income": long_ago,
        "next_resolve": {**kd["next_resolve"], "auto_spending": long_ago},
    })


def test_auto_spending_reads_each_document_once(app, calls):
    _auto_spending_kingdom()
    with app.app_context(), request_cache.scope():
        state = uag._get_state()
        calls.clear()
        refresh._refresh_kd(KD_ID, state, datetime.datetime.now(datetime.timezone.utc), False)

    reads = collections.Counter(path for method, path in calls if method == "GET")
    assert reads[f"/kingdom/{KD_ID}"] == 1, reads
    assert reads["/state"] == 0, reads  # the refresh passes the state it read
    for queue in ("settles", "structures", "mobis", "engineers"):
        assert reads[f"/kingdom/{KD_ID}/{queue}"] == 1, (queue, reads)
    assert reads["/galaxies"] <= 1 and reads["/galaxy/1/politics"] <= 1, reads
    # and it still spends: something was queued in every queue it had money and room for
    assert _get(f"/kingdom/{KD_ID}/settles")["settles"]
    assert _get(f"/kingdom/{KD_ID}/mobis")["mobis"]


def test_auto_spending_with_nothing_to_train_writes_no_mobis(app, calls):
    _auto_spending_kingdom()
    kd = _get(f"/kingdom/{KD_ID}")
    _create_item(f"kingdom_{KD_ID}", {**kd, "funding": {**kd["funding"], "military": 0}})
    with app.app_context(), request_cache.scope():
        state = uag._get_state()
        calls.clear()
        refresh._refresh_kd(KD_ID, state, datetime.datetime.now(datetime.timezone.utc), False)
    assert ("PATCH", f"/kingdom/{KD_ID}/mobis") not in calls


def test_a_finished_queue_is_read_once_and_trimmed_without_reading_it_again(app, calls):
    _set_up_kingdom(money=0)
    kd = _get(f"/kingdom/{KD_ID}")
    now = datetime.datetime.now(datetime.timezone.utc)
    past, future = (now - datetime.timedelta(minutes=5)).isoformat(), (now + datetime.timedelta(hours=1)).isoformat()
    _create_item(f"settles_{KD_ID}", {"settles": [{"time": past, "amount": 3}, {"time": future, "amount": 2}]})
    _create_item(f"kingdom_{KD_ID}", {**kd, "last_income": past, "next_resolve": {**kd["next_resolve"], "settles": past}})
    with app.app_context(), request_cache.scope():
        state = uag._get_state()
        calls.clear()
        refresh._refresh_kd(KD_ID, state, now, False)

    assert _count(calls, "GET", f"/kingdom/{KD_ID}/settles") == 1
    assert _count(calls, "PATCH", f"/kingdom/{KD_ID}/settles") == 1
    assert _get(f"/kingdom/{KD_ID}/settles")["settles"] == [{"time": future, "amount": 2}]
    assert _get(f"/kingdom/{KD_ID}")["stars"] == kd["stars"] + 3
