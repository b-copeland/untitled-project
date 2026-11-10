"""
Unit tests for api/untitledapp/occ.py: read, decide, write with If-Match, decide again on conflict.

The function app is replaced by an in-memory one that enforces ETags the way funcapp/concurrency.py does, so these
need no stack and never touch game data.
"""
import json
import random
import threading
import time
import types

import pytest

import untitledapp.occ as occ


@pytest.fixture(autouse=True)
def setup():
    """Replaces the autouse fixture in conftest.py that wipes the function app: nothing here uses it."""
    yield


class FakeFunctionApp:
    """Documents with ETags. PATCH merges the payload and returns 412 if If-Match is stale, like the real thing."""

    def __init__(self, jitter=0.0, forced_status=None):
        self.docs = {}
        self.version = 0
        self.lock = threading.Lock()
        self.jitter = jitter
        self.forced_status = forced_status
        self.patches = []

    def seed(self, path, doc):
        with self.lock:
            self.version += 1
            self.docs[path] = {**doc, "_etag": f'"{self.version}"'}

    @staticmethod
    def _path(url):
        return url.split("/api", 1)[1]

    def get(self, url, **kwargs):
        path = self._path(url)
        with self.lock:
            body = json.dumps(self.docs[path])
        if self.jitter:
            time.sleep(random.uniform(0, self.jitter))
        return types.SimpleNamespace(text=body, status_code=200)

    def patch(self, url, headers=None, data=None, **kwargs):
        path = self._path(url)
        payload = json.loads(data)
        with self.lock:
            self.patches.append((path, payload, (headers or {}).get("If-Match")))
            if self.forced_status:
                return types.SimpleNamespace(text="forced", status_code=self.forced_status)
            if_match = (headers or {}).get("If-Match")
            if if_match and if_match != self.docs[path]["_etag"]:
                return types.SimpleNamespace(text="changed", status_code=412)
            self.version += 1
            self.docs[path] = {**self.docs[path], **payload, "_etag": f'"{self.version}"'}
            return types.SimpleNamespace(text="ok", status_code=200)


@pytest.fixture
def fake(monkeypatch):
    fake_app = FakeFunctionApp()
    monkeypatch.setattr(occ, "REQUESTS_SESSION", fake_app)
    monkeypatch.setattr(occ.time, "sleep", lambda seconds: None)
    return fake_app


def test_update_writes_the_decided_change_with_the_etag_it_read(app, fake):
    fake.seed("/kingdom/1", {"money": 100})
    etag = fake.docs["/kingdom/1"]["_etag"]

    with app.app_context():
        result = occ.update("/kingdom/1", lambda kd: ({"money": kd["money"] - 30}, "done"))

    assert result == "done"
    assert fake.docs["/kingdom/1"]["money"] == 70
    assert fake.patches == [("/kingdom/1", {"money": 70}, etag)]


def test_update_with_no_payload_changes_nothing(app, fake):
    fake.seed("/kingdom/1", {"money": 100})

    with app.app_context():
        assert occ.update("/kingdom/1", lambda kd: (None, "unchanged")) == "unchanged"

    assert fake.patches == []


def test_a_rejection_propagates_and_writes_nothing(app, fake):
    fake.seed("/kingdom/1", {"money": 5})

    def decide(kd):
        raise occ.Rejected("Not enough money")

    with app.app_context(), pytest.raises(occ.Rejected) as caught:
        occ.update("/kingdom/1", decide)

    assert caught.value.message == "Not enough money" and caught.value.status == 400
    assert fake.patches == []


def test_decide_runs_again_on_the_new_document_after_a_conflict(app, fake):
    fake.seed("/kingdom/1", {"money": 100})
    seen = []

    def decide(kd):
        seen.append(kd["money"])
        if len(seen) == 1:
            # somebody else spends 60 after we read, before we write
            fake.patch("http://x/api/kingdom/1", headers={}, data=json.dumps({"money": 40}))
        return {"money": kd["money"] - 30}, None

    with app.app_context():
        occ.update("/kingdom/1", decide)

    assert seen == [100, 40]
    assert fake.docs["/kingdom/1"]["money"] == 10


def test_the_second_of_two_overlapping_spends_is_rejected_by_its_own_validation(app, fake):
    fake.seed("/kingdom/1", {"money": 100})
    attempts = []

    def spend_80(kd):
        attempts.append(kd["money"])
        if kd["money"] < 80:
            raise occ.Rejected("Not enough money")
        if len(attempts) == 1:
            # a duplicate request lands between our read and our write
            fake.patch("http://x/api/kingdom/1", headers={}, data=json.dumps({"money": 20}))
        return {"money": kd["money"] - 80}, None

    with app.app_context(), pytest.raises(occ.Rejected):
        occ.update("/kingdom/1", spend_80)

    assert attempts == [100, 20]
    assert fake.docs["/kingdom/1"]["money"] == 20  # charged once, by the other request


def test_gives_up_with_busy_when_the_document_never_stops_changing(app, monkeypatch):
    fake_app = FakeFunctionApp(forced_status=412)
    fake_app.seed("/kingdom/1", {"money": 100})
    monkeypatch.setattr(occ, "REQUESTS_SESSION", fake_app)
    monkeypatch.setattr(occ.time, "sleep", lambda seconds: None)

    with app.app_context(), pytest.raises(occ.Busy):
        occ.update("/kingdom/1", lambda kd: ({"money": 1}, None))

    assert len(fake_app.patches) == occ.MAX_ATTEMPTS


def test_a_409_from_the_function_app_is_retried_like_a_412(app, monkeypatch):
    fake_app = FakeFunctionApp(forced_status=409)
    fake_app.seed("/kingdom/1", {"money": 100})
    monkeypatch.setattr(occ, "REQUESTS_SESSION", fake_app)
    monkeypatch.setattr(occ.time, "sleep", lambda seconds: None)

    with app.app_context(), pytest.raises(occ.Busy):
        occ.update("/kingdom/1", lambda kd: ({"money": 1}, None))

    assert len(fake_app.patches) == occ.MAX_ATTEMPTS


def test_other_errors_are_raised_not_retried(app, monkeypatch):
    fake_app = FakeFunctionApp(forced_status=500)
    fake_app.seed("/kingdom/1", {"money": 100})
    monkeypatch.setattr(occ, "REQUESTS_SESSION", fake_app)

    with app.app_context(), pytest.raises(RuntimeError, match="500"):
        occ.update("/kingdom/1", lambda kd: ({"money": 1}, None))

    assert len(fake_app.patches) == 1


def test_many_overlapping_identical_spends_charge_exactly_once(app, monkeypatch):
    """The scenario from the bug report: duplicate requests racing. Money for one purchase, 32 requests."""
    fake_app = FakeFunctionApp(jitter=0.005)
    fake_app.seed("/kingdom/1", {"money": 100, "purchases": 0})
    monkeypatch.setattr(occ, "REQUESTS_SESSION", fake_app)

    def buy(kd):
        if kd["money"] < 100:
            raise occ.Rejected("Not enough money")
        return {"money": kd["money"] - 100, "purchases": kd["purchases"] + 1}, None

    outcomes = []

    def request(_):
        with app.app_context():
            try:
                occ.update("/kingdom/1", buy)
                outcomes.append("bought")
            except occ.Rejected:
                outcomes.append("rejected")
            except occ.Busy:
                outcomes.append("busy")

    threads = [threading.Thread(target=request, args=(i,)) for i in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("bought") == 1
    assert outcomes.count("bought") + outcomes.count("rejected") + outcomes.count("busy") == 32
    assert fake_app.docs["/kingdom/1"]["money"] == 0
    assert fake_app.docs["/kingdom/1"]["purchases"] == 1


def test_many_overlapping_spends_that_all_fit_are_all_applied_once(app, monkeypatch):
    fake_app = FakeFunctionApp(jitter=0.005)
    fake_app.seed("/kingdom/1", {"money": 1000})
    monkeypatch.setattr(occ, "REQUESTS_SESSION", fake_app)
    done = []

    def request(_):
        with app.app_context():
            occ.update("/kingdom/1", lambda kd: ({"money": kd["money"] - 10}, None))
            done.append(1)

    threads = [threading.Thread(target=request, args=(i,)) for i in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(done) == 24
    assert fake_app.docs["/kingdom/1"]["money"] == 1000 - 24 * 10
