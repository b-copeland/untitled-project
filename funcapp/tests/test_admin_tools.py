"""
The function app's side of the admin tools (issue #219): removing fields from a kingdom, and messages from a list.
Run from the repo root: conda run -n funcapp-worker python -m pytest funcapp/tests
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
def backend():
    container = fake_backend.FakeContainer()
    return container, fake_backend.FakeSession(fake_backend.load_function_app(container))


def test_named_fields_come_out_of_the_kingdom_but_never_its_ids(backend):
    container, session = backend
    container.create_item({"id": "kingdom_4", "kdId": "4", "money": 5, "junk": "x", "more": 1})

    response = session.request("POST", ENDPOINT + "/kingdom/4/removefields",
                               data=json.dumps({"fields": ["junk", "more", "id", "kdId", "_etag", "absent"]}))

    assert response.status_code == 200
    assert sorted(json.loads(response.text)["removed"]) == ["junk", "more"]
    kingdom = container.docs["kingdom_4"]
    assert kingdom["money"] == 5 and kingdom["kdId"] == "4" and "junk" not in kingdom and "more" not in kingdom


def test_removing_fields_needs_a_list_of_names_and_a_kingdom(backend):
    container, session = backend
    assert session.request("POST", ENDPOINT + "/kingdom/4/removefields", data=json.dumps({"fields": "junk"})).status_code == 400
    assert session.request("POST", ENDPOINT + "/kingdom/9/removefields", data=json.dumps({"fields": []})).status_code == 404


def test_listed_messages_come_out_and_new_ones_still_go_in_front(backend):
    container, session = backend
    old = {"time": "t1", "with": "2", "from": True, "message": "rude"}
    keep = {"time": "t2", "with": "2", "from": True, "message": "fine"}
    container.create_item({"id": "messages_4", "messages": [keep, old]})

    assert session.request("PATCH", ENDPOINT + "/kingdom/4/messages", data=json.dumps({"remove": [old]})).status_code == 200
    assert container.docs["messages_4"]["messages"] == [keep]
    new = {"time": "t3", "with": "2", "from": True, "message": "new"}
    assert session.request("PATCH", ENDPOINT + "/kingdom/4/messages", data=json.dumps(new)).status_code == 200
    assert container.docs["messages_4"]["messages"] == [new, keep]
