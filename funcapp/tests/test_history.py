"""
Tests for a kingdom's history (``history_<kd_id>``): a series the document does not have yet starts empty, and ``keep``
trims a series to its newest points.

They run the real handlers on the in-memory container (tests/fake_backend.py). Run them from the repo root:

    conda run -n funcapp-worker python -m pytest funcapp/tests
"""
import json
import pathlib
import sys

import pytest

pytest.importorskip("azure.cosmos")
pytest.importorskip("azure.functions")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tests import fake_backend  # noqa: E402

ENDPOINT = "http://funcapp/api"


@pytest.fixture
def session():
    container = fake_backend.FakeContainer()
    container.create_item({"id": "history_1", "history": {"stars": []}})
    return fake_backend.FakeSession(fake_backend.load_function_app(container))


def _patch(session, body):
    return session.request("PATCH", f"{ENDPOINT}/kingdom/1/history", data=json.dumps(body))


def _history(session):
    return json.loads(session.request("GET", f"{ENDPOINT}/kingdom/1/history").text)["history"]


def test_a_new_series_starts_on_an_old_document(session):
    response = _patch(session, {"history": {"stars": {"time": "t1", "value": 1}, "units": {"time": "t1", "value": {"attack": 2}}}})

    assert response.status_code == 200
    assert _history(session) == {"stars": [{"time": "t1", "value": 1}], "units": [{"time": "t1", "value": {"attack": 2}}]}


def test_keep_trims_only_the_series_it_names(session):
    for i in range(4):
        _patch(session, {"history": {"stars": {"time": f"t{i}", "value": i}, "units": {"time": f"t{i}", "value": {}}},
                         "keep": {"units": 2}})

    history = _history(session)
    assert [point["time"] for point in history["units"]] == ["t2", "t3"]
    assert len(history["stars"]) == 4
