"""
A player's preferences (``/api/preferences``): the defaults for a player who has set nothing, saving a choice to their
own document only, and refusing what is not one of the choices.
"""
import json


def _get(client, jwt):
    return client.get("/api/preferences", headers={"Authorization": f"Bearer {jwt}"})


def _post(client, jwt, body):
    return client.post("/api/preferences", headers={"Authorization": f"Bearer {jwt}"}, data=json.dumps(body))


def test_a_player_who_has_set_nothing_gets_the_defaults_and_the_choices(app, client, jwt1):
    answer = _get(client, jwt1).get_json()
    assert answer["theme"] == "gray"
    assert [option["value"] for option in answer["options"]["theme"]][:3] == ["gray", "dark", "light"]


def test_a_theme_is_saved_for_that_player_only(app, client, jwt1, jwt2):
    response = _post(client, jwt1, {"theme": "nebula"})
    assert response.status_code == 200, response.get_json()
    assert _get(client, jwt1).get_json()["theme"] == "nebula"
    assert _get(client, jwt2).get_json()["theme"] == "gray"


def test_a_choice_that_is_not_offered_is_refused(app, client, jwt1):
    assert _post(client, jwt1, {"theme": "plaid"}).status_code == 400
    assert _post(client, jwt1, {"font": "big"}).status_code == 400
    assert _post(client, jwt1, {}).status_code == 400
    assert _get(client, jwt1).get_json()["theme"] == "gray"


def test_preferences_need_a_login(app, client):
    assert client.get("/api/preferences").status_code == 401
