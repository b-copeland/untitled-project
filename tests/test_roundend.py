"""The end of a round (issue #17): archive, freeze, engine stopped, everything public."""
import datetime
import json

import pytest

import untitledapp.roundend as roundend
from tests.test_attack import TARGET_ID, _attack, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, no_shared_lock, _create_item, _get  # noqa: F401
from untitledapp import REQUESTS_SESSION

NOW = datetime.datetime.now(datetime.timezone.utc)


def _archive(app, number):
    response = REQUESTS_SESSION.get(app.config["AZURE_FUNCTION_ENDPOINT"] + "/item", data=json.dumps({"item": f"archive_{number}"}))
    return json.loads(response.text)


def _two_kingdoms_with_scores():
    _set_up_two_kingdoms()
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Alpha", TARGET_ID: "Beta"}})
    _create_item("scores", {
        "last_update": NOW.isoformat(),
        "stars": {KD_ID: 300, TARGET_ID: 250}, "networth": {KD_ID: 9, TARGET_ID: 8},
        "points": {KD_ID: 5, TARGET_ID: 7}, "galaxy_networth": {"1": 9, "2": 8},
    })


def _end(app, **kwargs):
    with app.app_context():
        state = roundend.uag._get_state()
        return roundend.end_round(state, NOW, **kwargs)


def test_ending_the_round_archives_the_final_standings_and_marks_the_game_over(app, client):
    _two_kingdoms_with_scores()
    state = _end(app, reason="because")["state"]

    assert state["game_over"] and state["rounds_archived"] == 1
    archive = _archive(app, 1)
    assert archive["reason"] == "because" and archive["number"] == 1
    assert archive["ranking"] == [TARGET_ID, KD_ID]  # by points
    assert archive["kingdoms"][KD_ID]["name"] == "Alpha" and archive["kingdoms"][KD_ID]["galaxy"] == "1"
    assert archive["scores"]["stars"] == {KD_ID: 300, TARGET_ID: 250}


def test_ending_twice_archives_once(app, client):
    _two_kingdoms_with_scores()
    _end(app)
    _end(app)
    assert _get("/state")["state"]["rounds_archived"] == 1


def test_nothing_that_changes_a_kingdom_works_after_the_round_ends(app, client, jwt1):
    _two_kingdoms_with_scores()
    before = _get(f"/kingdom/{TARGET_ID}")
    _end(app)

    response = _attack(client, jwt1)

    assert response.status_code == 400 and response.get_json()["message"] == roundend.OVER_MESSAGE
    assert _get(f"/kingdom/{TARGET_ID}")["stars"] == before["stars"]
    # Reading still works, and so does signing in.
    assert client.get("/api/scores", headers={"Authorization": f"Bearer {jwt1}"}).status_code == 200
    assert client.post("/api/login", json={"username": "user1", "password": "user1"}).status_code == 200


def test_before_the_end_nothing_is_frozen(app, client, jwt1):
    _two_kingdoms_with_scores()
    assert _attack(client, jwt1).status_code == 200


def test_the_scores_name_every_kingdom_once_the_round_is_over(app, client, jwt1):
    _two_kingdoms_with_scores()
    _create_item(f"revealed_{KD_ID}", {"revealed": {}, "galaxies": {}, "revealed_galaxymates": [], "revealed_to_galaxymates": []})
    headers = {"Authorization": f"Bearer {jwt1}"}
    during = client.get("/api/scores", headers=headers).get_json()
    assert ["", 250] in during["stars"]  # the other galaxy is hidden

    _end(app)
    after = client.get("/api/scores", headers=headers).get_json()
    assert [name for name, _ in after["stars"]] == [KD_ID, TARGET_ID]


def test_the_refresh_closes_the_round_once_the_end_time_has_passed_and_then_does_nothing(app, client, monkeypatch):
    _two_kingdoms_with_scores()
    _create_item("empires", {"empires": {}, "last_update": NOW.isoformat()})
    _create_item("kingdoms", {"kingdoms": {}})  # the made-up kingdoms are not built to be refreshed; the tick is about the round
    monkeypatch.setenv("REFRESH_SECRET", "s")
    past = (NOW - datetime.timedelta(minutes=1)).isoformat()
    _create_item("state", {"state": {**_get("/state")["state"], "game_end": past, "election_start": (NOW + datetime.timedelta(days=9)).isoformat(), "election_end": "",
                                    "next_history": (NOW + datetime.timedelta(days=1)).isoformat()}})
    headers = {"Refresh-Secret": "s"}

    first = client.get("/api/refreshdata", headers=headers)
    assert first.status_code == 200 and _get("/state")["state"].get("game_over")
    assert client.get("/api/refreshdata", headers=headers).get_data(as_text=True) == "Round over"


def test_the_admin_can_end_a_round_early_and_a_reset_opens_the_next_one(app, client):
    _two_kingdoms_with_scores()
    token = client.post("/api/login", json={"username": "admin", "password": "admin"}).get_json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/admin/endround", headers=headers).status_code == 200
    assert client.post("/api/admin/endround", headers=headers).status_code == 400  # already over
    assert _get("/state")["state"]["game_over"]

    client.post("/api/resetstate", headers=headers)  # still allowed: it is how the next round starts
    state = _get("/state")["state"]
    assert not state["game_over"] and state["rounds_archived"] == 1
    assert _archive(app, 1)["number"] == 1
