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
    assert answer["theme"] == "twilight"
    assert [option["value"] for option in answer["options"]["theme"]][:3] == ["gray", "dark", "light"]


def test_a_theme_is_saved_for_that_player_only(app, client, jwt1, jwt2):
    response = _post(client, jwt1, {"theme": "nebula"})
    assert response.status_code == 200, response.get_json()
    assert _get(client, jwt1).get_json()["theme"] == "nebula"
    assert _get(client, jwt2).get_json()["theme"] == "twilight"


def test_a_choice_that_is_not_offered_is_refused(app, client, jwt1):
    assert _post(client, jwt1, {"theme": "plaid"}).status_code == 400
    assert _post(client, jwt1, {"font": "big"}).status_code == 400
    assert _post(client, jwt1, {}).status_code == 400
    assert _get(client, jwt1).get_json()["theme"] == "twilight"


def test_preferences_need_a_login(app, client):
    assert client.get("/api/preferences").status_code == 401


def test_the_answer_names_the_player_for_the_user_menu(app, client, jwt1, jwt2):
    assert _get(client, jwt1).get_json()["username"] == "user1"
    assert _get(client, jwt2).get_json()["username"] == "user2"


def test_nothing_is_muted_until_the_player_says_so_and_every_kind_is_offered(app, client, jwt1):
    answer = _get(client, jwt1).get_json()
    assert answer["muted"] == []
    kinds = [option["value"] for option in answer["options"]["muted"]]
    assert {"settles", "structures", "military", "spy_attempts", "generals"} <= set(kinds)
    assert "dead" not in kinds
    assert all(option["label"] and option["group"] for option in answer["options"]["muted"])


def test_muted_notifications_are_saved_for_that_player_only_and_keep_the_theme(app, client, jwt1, jwt2):
    assert _post(client, jwt1, {"theme": "nebula"}).status_code == 200
    response = _post(client, jwt1, {"muted": ["generals", "settles", "settles"]})
    assert response.status_code == 200, response.get_json()
    answer = _get(client, jwt1).get_json()
    assert answer["muted"] == ["settles", "generals"]  # in the Settings page's order, once each
    assert answer["theme"] == "nebula"
    assert _get(client, jwt2).get_json()["muted"] == []
    assert _post(client, jwt1, {"muted": []}).status_code == 200
    assert _get(client, jwt1).get_json()["muted"] == []


def test_a_notification_kind_that_does_not_exist_or_cannot_be_muted_is_refused(app, client, jwt1):
    assert _post(client, jwt1, {"muted": ["weather"]}).status_code == 400
    assert _post(client, jwt1, {"muted": ["dead"]}).status_code == 400
    assert _post(client, jwt1, {"muted": "settles"}).status_code == 400
    assert _get(client, jwt1).get_json()["muted"] == []


def test_the_tour_is_offered_until_the_player_answers_and_the_answer_is_kept(app, client, jwt1, jwt2):
    assert _get(client, jwt1).get_json()["tour"] == "offer"
    for answer in ("later", "declined", "done"):
        assert _post(client, jwt1, {"tour": answer}).status_code == 200
        assert _get(client, jwt1).get_json()["tour"] == answer
    assert _get(client, jwt2).get_json()["tour"] == "offer"
    assert _post(client, jwt1, {"tour": "maybe"}).status_code == 400
    assert _get(client, jwt1).get_json()["tour"] == "done"
