"""
Tests for funcapp/concurrency.py: conditional writes, retries, and If-Match.

They use an in-memory stand-in for the Cosmos container that enforces ETags the way Cosmos does, so they need no
emulator or function host. They need the function app's packages, so they are skipped where those are not installed
(for example the Flask environment). Run them from the repo root:

    conda run -n funcapp-worker pip install pytest
    conda run -n funcapp-worker python -m pytest funcapp/tests
"""
import copy
import json
import pathlib
import random
import sys
import threading
import time

import pytest

pytest.importorskip("azure.cosmos")
pytest.importorskip("azure.functions")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import azure.functions as func  # noqa: E402
from azure.cosmos.exceptions import CosmosAccessConditionFailedError  # noqa: E402

import concurrency  # noqa: E402
from concurrency import ConditionalContainer, retry_on_conflict  # noqa: E402




class FakeContainer:
    """Documents with ETags. replace_item honors etag/match_condition and raises 412 like Cosmos."""

    def __init__(self, jitter=0.0, always_conflict=False):
        self.docs = {}
        self.version = 0
        self.lock = threading.Lock()
        self.jitter = jitter
        self.always_conflict = always_conflict
        self.replace_kwargs = []

    def seed(self, doc):
        with self.lock:
            self.version += 1
            self.docs[doc["id"]] = {**copy.deepcopy(doc), "_etag": f'"{self.version}"'}

    def read_item(self, item, partition_key):
        with self.lock:
            doc = copy.deepcopy(self.docs[item])
        if self.jitter:
            time.sleep(random.uniform(0, self.jitter))  # widen the window between read and write
        return doc

    def replace_item(self, item, body, **kwargs):
        self.replace_kwargs.append(kwargs)
        with self.lock:
            if self.always_conflict and "etag" in kwargs:
                raise CosmosAccessConditionFailedError(message="conflict")
            if "etag" in kwargs and kwargs["etag"] != self.docs[item]["_etag"]:
                raise CosmosAccessConditionFailedError(message="conflict")
            self.version += 1
            stored = {**copy.deepcopy(body), "_etag": f'"{self.version}"'}
            self.docs[item] = stored
            return copy.deepcopy(stored)


def make_app(container):
    """Two handlers shaped like the real ones, including the bare except that swallows errors."""
    cond = ConditionalContainer(container)

    @retry_on_conflict
    def append(req: func.HttpRequest) -> func.HttpResponse:
        body = req.get_json()
        doc = cond.read_item(item="doc", partition_key="doc")
        try:
            doc["items"] = doc["items"] + [body["x"]]
            cond.replace_item("doc", doc)
            return func.HttpResponse("ok", status_code=200)
        except:  # noqa: E722  (this is what the real handlers do)
            return func.HttpResponse("not updated", status_code=500)

    @retry_on_conflict
    def patch(req: func.HttpRequest) -> func.HttpResponse:
        body = req.get_json()
        doc = cond.read_item(item="doc", partition_key="doc")
        try:
            cond.replace_item("doc", {**doc, **body})
            return func.HttpResponse("ok", status_code=200)
        except:  # noqa: E722
            return func.HttpResponse("not updated", status_code=500)

    return cond, append, patch


def request(body, headers=None):
    return func.HttpRequest(
        method="PATCH", url="/api/doc", body=json.dumps(body).encode(), headers=headers or {}, route_params={}
    )


def run_concurrently(count, target):
    threads = [threading.Thread(target=target, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_concurrent_appends_are_all_kept():
    container = FakeContainer(jitter=0.01)
    container.seed({"id": "doc", "items": []})
    _, append, _ = make_app(container)
    statuses = []

    run_concurrently(24, lambda i: statuses.append(append(request({"x": i})).status_code))

    assert statuses == [200] * 24
    assert sorted(container.docs["doc"]["items"]) == list(range(24))


def test_concurrent_patches_to_different_fields_are_all_kept():
    container = FakeContainer(jitter=0.01)
    container.seed({"id": "doc", "items": []})
    _, _, patch = make_app(container)

    run_concurrently(24, lambda i: patch(request({f"field_{i}": i})))

    assert all(container.docs["doc"].get(f"field_{i}") == i for i in range(24))


def test_without_the_wrapper_concurrent_appends_are_lost():
    """The failure this module exists to prevent, shown on the same fake container."""
    container = FakeContainer(jitter=0.01)
    container.seed({"id": "doc", "items": []})

    def unprotected(i):
        doc = container.read_item("doc", "doc")
        doc["items"] = doc["items"] + [i]
        container.replace_item("doc", doc)  # no etag: last write wins

    run_concurrently(24, unprotected)

    assert len(container.docs["doc"]["items"]) < 24


def test_if_match_with_the_current_etag_succeeds_and_returns_the_new_etag():
    container = FakeContainer()
    container.seed({"id": "doc", "items": []})
    _, _, patch = make_app(container)
    etag = container.docs["doc"]["_etag"]

    response = patch(request({"a": 1}, {"If-Match": etag}))

    assert response.status_code == 200
    assert response.headers["ETag"] == container.docs["doc"]["_etag"] != etag


def test_if_match_with_a_stale_etag_is_rejected_and_changes_nothing():
    container = FakeContainer()
    container.seed({"id": "doc", "items": []})
    _, _, patch = make_app(container)
    stale = container.docs["doc"]["_etag"]
    patch(request({"a": 1}))  # someone else writes first

    response = patch(request({"a": 2}, {"If-Match": stale}))

    assert response.status_code == 412
    assert container.docs["doc"]["a"] == 1


def test_only_one_of_two_spends_with_the_same_etag_wins():
    container = FakeContainer()
    container.seed({"id": "doc", "money": 100})
    _, _, patch = make_app(container)
    etag = container.docs["doc"]["_etag"]

    first = patch(request({"money": 40}, {"If-Match": etag}))
    second = patch(request({"money": 40}, {"If-Match": etag}))

    assert (first.status_code, second.status_code) == (200, 412)


def test_a_stale_etag_in_the_body_does_not_cause_a_conflict_loop():
    """Callers that send back a whole document they read must not pin the write to that old version."""
    container = FakeContainer()
    container.seed({"id": "doc", "items": []})
    _, _, patch = make_app(container)
    old_etag = container.docs["doc"]["_etag"]
    patch(request({"a": 1}))  # moves the document on

    response = patch(request({"b": 2, "_etag": old_etag, "_ts": 1}))

    assert response.status_code == 200
    assert container.docs["doc"]["b"] == 2 and container.docs["doc"]["a"] == 1
    assert container.docs["doc"]["_etag"] != old_etag


def test_gives_up_with_409_after_repeated_conflicts(monkeypatch):
    monkeypatch.setattr(concurrency.time, "sleep", lambda s: None)
    container = FakeContainer(always_conflict=True)
    container.seed({"id": "doc", "items": []})
    _, append, _ = make_app(container)

    response = append(request({"x": 1}))

    assert response.status_code == 409
    assert len(container.replace_kwargs) == concurrency.MAX_ATTEMPTS


def test_other_failures_are_not_retried():
    container = FakeContainer()
    container.seed({"id": "doc", "items": []})
    _, append, _ = make_app(container)

    response = append(request({"nope": 1}))  # handler raises KeyError inside its try

    assert response.status_code == 500
    assert container.replace_kwargs == []


def test_outside_a_wrapped_handler_writes_are_unchanged():
    container = FakeContainer()
    container.seed({"id": "doc", "items": []})
    cond = ConditionalContainer(container)
    doc = cond.read_item("doc", "doc")

    cond.replace_item("doc", doc)

    assert container.replace_kwargs == [{}]
