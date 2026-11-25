"""
Ids from a request can not reach a document other than the one they name (issue #219).

Flask decodes the URL before a route sees it, so ``/api/messages/2%3Fx`` hands the route the id ``2?x``. Pasted into a
function app URL that cut the path short, and a write meant for kingdom 2's messages landed on kingdom 2's own document.
"""
import json

import pytest

from untitledapp import UnsafePath, check_function_url

from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get

ENDPOINT = "http://localhost:7071/api"


def _set_up():
    _set_up_two_kingdoms()
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Test Kingdom", TARGET_ID: "Target"}})


@pytest.mark.parametrize("path", [
    "/kingdom/2?x/messages",
    "/kingdom/2#x/messages",
    "/kingdom/2%3Fx/messages",
    "/kingdom/../state",
    "/kingdom/2 x/messages",
])
def test_a_function_app_url_must_be_plain_segments(path):
    with pytest.raises(UnsafePath):
        check_function_url(ENDPOINT + path)


def test_plain_function_app_urls_pass():
    check_function_url(ENDPOINT + "/kingdom/2/messages")
    check_function_url(ENDPOINT + "/username/6162")
    check_function_url(ENDPOINT + "/galaxy/1:2/news")


def test_a_kingdom_write_with_a_field_kingdoms_do_not_have_is_refused_under_test(app):
    with app.app_context():
        with pytest.raises(UnsafePath):
            check_function_url(ENDPOINT + "/kingdom/2", "PATCH", json.dumps({"money": 1, "message": "x" * 1000}))
        body = json.dumps({"money": 1, "_etag": "e"})
        assert check_function_url(ENDPOINT + "/kingdom/2", "PATCH", body) == body
        # Other documents of a kingdom have fields of their own.
        body = json.dumps({"message": "hi"})
        assert check_function_url(ENDPOINT + "/kingdom/2/messages", "PATCH", body) == body


def test_outside_tests_a_field_kingdoms_do_not_have_is_dropped_from_the_write(app, monkeypatch):
    """So a kingdom that already carries a stray field can still be written whole."""
    monkeypatch.setitem(app.config, "STRICT_KINGDOM_FIELDS", False)
    with app.app_context():
        body = check_function_url(ENDPOINT + "/kingdom/2", "PATCH", json.dumps({"money": 1, "message": "x"}))
    assert json.loads(body) == {"money": 1}


def test_a_message_to_an_id_with_a_query_in_it_changes_no_kingdom(app, client, jwt1):
    _set_up()
    before = _get(f"/kingdom/{TARGET_ID}")

    response = client.post(
        f"/api/messages/{TARGET_ID}%3Fx",
        json={"message": "hello", "time": {"big": "x" * 1000}},
        headers={"Authorization": f"Bearer {jwt1}"},
    )

    assert response.status_code == 404
    after = _get(f"/kingdom/{TARGET_ID}")
    assert {key: value for key, value in after.items() if not key.startswith("_")} == {
        key: value for key, value in before.items() if not key.startswith("_")
    }


def test_a_message_to_a_kingdom_that_does_not_exist_is_refused(app, client, jwt1):
    _set_up()

    response = client.post("/api/messages/999", json={"message": "hello"}, headers={"Authorization": f"Bearer {jwt1}"})

    assert response.status_code == 400


def test_a_spy_operation_on_an_id_with_a_query_in_it_is_refused_before_anything_is_spent(app, client, jwt1):
    _set_up()
    attacker0, target0 = _get(f"/kingdom/{KD_ID}"), _get(f"/kingdom/{TARGET_ID}")

    response = client.post(
        f"/api/spy/{TARGET_ID}%3Fx",
        json={"drones": 100, "shielded": False, "operation": "suicidedrones"},
        headers={"Authorization": f"Bearer {jwt1}"},
    )

    assert response.status_code == 404
    assert _get(f"/kingdom/{KD_ID}")["drones"] == attacker0["drones"]
    assert _get(f"/kingdom/{TARGET_ID}")["fuel"] == target0["fuel"]


def test_a_spy_operation_on_a_kingdom_outside_every_galaxy_is_refused(app, client, jwt1):
    """The id reaches ``_spy`` unchecked from a schedule's options too, so ``_spy`` checks it itself."""
    import untitledapp.conquer as uac

    _set_up()
    with app.test_request_context():
        _, payload, status, success = uac._spy(
            {"drones": 100, "shielded": False, "operation": "suicidedrones"}, KD_ID, "999"
        )

    assert status == 400 and not success
    assert _get(f"/kingdom/{KD_ID}")["spy_attempts"] > 0
