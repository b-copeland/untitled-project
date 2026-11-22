"""
``/init`` and ``/resetstate`` (funcapp/function_app.py): they must work on an empty container, on one ``/deleteall``
has blanked, and on a live game, because the admin's new round (api/untitledapp/admin.py) calls both every time.
"""
import pathlib
import sys

import pytest

pytest.importorskip("azure.cosmos")
pytest.importorskip("azure.functions")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tests import fake_backend  # noqa: E402

ENDPOINT = "http://funcapp/api"
CORE = ("state", "kingdoms", "galaxies", "empires", "universe_news", "universe_votes", "accounts", "scores")


@pytest.fixture
def backend():
    container = fake_backend.FakeContainer()
    session = fake_backend.FakeSession(fake_backend.load_function_app(container))
    return container, session


def _post(session, path):
    return session.request("POST", ENDPOINT + path)


def _strip(document):
    return {key: value for key, value in document.items() if not key.startswith("_")}


def test_init_on_an_empty_container_creates_every_core_document(backend):
    container, session = backend
    response = _post(session, "/init")

    assert response.status_code == 201
    assert set(container.docs) == set(CORE)
    assert container.docs["state"]["round"] and container.docs["state"]["state"] == {}
    assert container.docs["scores"]["last_update"] == "" and container.docs["empires"]["last_update"] == ""


def test_init_fills_in_blanked_documents_and_never_touches_a_live_one(backend):
    container, session = backend
    _post(session, "/init")
    container.blank()  # what /deleteall leaves
    container.docs["galaxies"] = {"id": "galaxies", "galaxies": {"1:1": ["0"]}}  # this one has content

    assert _post(session, "/init").status_code == 201

    assert container.docs["galaxies"]["galaxies"] == {"1:1": ["0"]}
    assert container.docs["kingdoms"]["kingdoms"] == {} and container.docs["state"]["state"] == {}
    before = {item: _strip(doc) for item, doc in container.docs.items()}
    assert _post(session, "/init").status_code == 201
    assert {item: _strip(doc) for item, doc in container.docs.items()} == before  # a second call is a no-op


def test_reset_works_on_a_blanked_or_empty_container(backend):
    container, session = backend
    assert _post(session, "/resetstate").status_code == 200  # nothing there at all
    assert set(CORE) <= set(container.docs)

    container.blank()
    assert _post(session, "/resetstate").status_code == 200
    assert container.docs["universe_votes"]["votes"]["policy_1"] == {"option_1": {}, "option_2": {}}
    assert container.docs["scores"]["galaxy_kingdoms_alive"] == {}


def test_reset_empties_the_round_and_keeps_what_outlives_it(backend):
    container, session = backend
    _post(session, "/init")
    docs = container.docs
    docs["state"]["state"] = {"game_start": "x", "rounds_archived": 2}
    old_round = docs["state"]["round"]
    docs["kingdoms"].update({"kingdoms": {"0": "a", "7": "b"}, "next_id": 3})
    docs["galaxies"]["galaxies"] = {"1:1": ["0", "7"]}
    docs["scores"].update({"stars": {"0": 1}, "galaxy_kingdoms_alive": {"1:1": 2}, "last_update": "then"})
    docs["accounts"]["accounts"] = [{"username": "old", "kd_id": "0", "kd_created": True, "kd_death_date": "x"}]
    for item in ("kingdom_0", "galaxy_votes_1:1", "galaxy_intel_1:1", "cluster_1", "empire_politics_0",
                 "user_1", "username_61", "user_counter", "preferences_1", "archive_1", "archive_2"):
        docs[item] = {"id": item, "something": 1}

    assert _post(session, "/resetstate").status_code == 200

    assert set(docs) == set(CORE) | {"user_1", "username_61", "user_counter", "preferences_1", "archive_1", "archive_2"}
    assert docs["state"]["state"] == {"game_start": "x", "rounds_archived": 2}  # Flask rewrites it
    assert docs["state"]["round"] != old_round
    assert docs["kingdoms"]["kingdoms"] == {} and docs["kingdoms"]["next_id"] == 8
    assert docs["galaxies"]["galaxies"] == {} and docs["scores"]["stars"] == {}
    assert docs["scores"]["galaxy_kingdoms_alive"] == {} and docs["scores"]["last_update"] == ""
    assert docs["accounts"]["accounts"] == [{"username": "old", "kd_id": None, "kd_created": False, "kd_death_date": None}]
    assert docs["user_1"]["something"] == 1 and docs["archive_2"]["something"] == 1
