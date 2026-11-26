"""POST /kingdomdocuments: many kingdoms' documents in one query, for the pages that show several kingdoms."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

URL = "http://funcapp/api/kingdomdocuments"


@pytest.fixture
def session():
    pytest.importorskip("azure.cosmos")
    pytest.importorskip("azure.functions")
    from tests import fake_backend
    container = fake_backend.FakeContainer()
    for kd_id in ("1", "2", "3"):
        container.create_item({"id": f"kingdom_{kd_id}", "name": f"Kingdom {kd_id}"})
    container.create_item({"id": "kingdom_1_news", "news": []})  # not a kingdom: never matched by an id
    return fake_backend.FakeSession(fake_backend.load_function_app(container))


def _read(session, body):
    return session.request("POST", URL, data=json.dumps(body))


def test_reads_the_kingdoms_asked_for_and_leaves_out_the_missing(session):
    response = _read(session, {"ids": ["3", "1", "9", "1"]})
    assert response.status_code == 200
    kingdoms = response.json()["kingdoms"]
    assert sorted(kingdoms) == ["1", "3"]
    assert kingdoms["1"]["name"] == "Kingdom 1" and "_etag" in kingdoms["1"]


def test_no_ids_reads_nothing(session):
    assert _read(session, {"ids": []}).json() == {"kingdoms": {}}


@pytest.mark.parametrize("body", [{}, {"ids": "1"}, {"ids": [1]}, {"ids": ["1_news"]}, {"ids": ["1?x"]}, ["1"]])
def test_only_a_list_of_kingdom_numbers(session, body):
    assert _read(session, body).status_code == 400


def test_a_bounded_number_at_once(session):
    import function_app
    too_many = [str(i) for i in range(function_app.MAX_KINGDOMS_PER_READ + 1)]
    assert _read(session, {"ids": too_many}).status_code == 400
    # Repeats count once, so a page's ids with duplicates still fit.
    assert _read(session, {"ids": ["1"] * (function_app.MAX_KINGDOMS_PER_READ + 1)}).status_code == 200
