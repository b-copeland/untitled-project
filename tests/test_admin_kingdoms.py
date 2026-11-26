"""The admin's tools for one kingdom (issue #219, api/untitledapp/adminkingdoms.py): rename, delete a message or a board
post, clear stray fields."""
from tests.test_admin_accounts import _admin
from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get


def _set_up():
    _set_up_two_kingdoms()
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Test Kingdom", TARGET_ID: "Target"}})


def _player(jwt):
    return {"Authorization": f"Bearer {jwt}"}


def test_a_player_can_not_use_the_tools(app, client, jwt1):
    _set_up()
    for path in (f"/api/admin/kingdom/{TARGET_ID}/rename", f"/api/admin/kingdom/{TARGET_ID}/clearfields"):
        assert client.post(path, json={"name": "Mine now"}, headers=_player(jwt1)).status_code in (401, 403)


def test_renaming_changes_the_list_and_the_kingdom_and_refuses_a_name_in_use(app, client):
    _set_up()

    response = client.post(f"/api/admin/kingdom/{TARGET_ID}/rename", json={"name": "Polite Name"}, headers=_admin(client))

    assert response.status_code == 200, response.get_json()
    assert _get("/kingdoms")["kingdoms"][TARGET_ID] == "Polite Name"
    assert _get(f"/kingdom/{TARGET_ID}")["name"] == "Polite Name"
    taken = client.post(f"/api/admin/kingdom/{TARGET_ID}/rename", json={"name": "test kingdom"}, headers=_admin(client))
    assert taken.status_code == 400
    assert client.post("/api/admin/kingdom/999/rename", json={"name": "X"}, headers=_admin(client)).status_code == 404


def test_deleting_a_message_takes_it_out_of_both_kingdoms(app, client, jwt1):
    _set_up()
    assert client.post(f"/api/messages/{TARGET_ID}", json={"message": "rude"}, headers=_player(jwt1)).status_code == 200
    assert client.post(f"/api/messages/{TARGET_ID}", json={"message": "fine"}, headers=_player(jwt1)).status_code == 200
    details = client.get(f"/api/admin/kingdom/{KD_ID}", headers=_admin(client)).get_json()
    rude = next(entry for entry in details["messages"] if entry["message"] == "rude")

    response = client.post(f"/api/admin/kingdom/{KD_ID}/messages/delete", json={"message": rude}, headers=_admin(client))

    assert response.status_code == 200, response.get_json()
    assert [entry["message"] for entry in _get(f"/kingdom/{KD_ID}/messages")["messages"]] == ["fine"]
    assert [entry["message"] for entry in _get(f"/kingdom/{TARGET_ID}/messages")["messages"]] == ["fine"]


def test_deleting_a_board_post_of_the_kingdom(app, client, jwt1):
    _set_up()
    assert client.post("/api/galaxyboard", json={"text": "spam"}, headers=_player(jwt1)).status_code == 200
    details = client.get(f"/api/admin/kingdom/{KD_ID}", headers=_admin(client)).get_json()
    post = details["board_posts"][0]

    response = client.post(f"/api/admin/kingdom/{KD_ID}/board/{post['id']}/delete", headers=_admin(client))

    assert response.status_code == 200, response.get_json()
    assert client.get(f"/api/admin/kingdom/{KD_ID}", headers=_admin(client)).get_json()["board_posts"] == []


def test_clearing_stray_fields_keeps_every_field_kingdoms_have(app, client):
    _set_up()
    before = _get(f"/kingdom/{TARGET_ID}")
    _create_item(f"kingdom_{TARGET_ID}", {"message": "x" * 1000, "with": "1"})
    assert client.get(f"/api/admin/kingdom/{TARGET_ID}", headers=_admin(client)).get_json()["stray_fields"] == ["message", "with"]

    response = client.post(f"/api/admin/kingdom/{TARGET_ID}/clearfields", headers=_admin(client))

    assert response.status_code == 200, response.get_json()
    assert sorted(response.get_json()["removed"]) == ["message", "with"]
    after = _get(f"/kingdom/{TARGET_ID}")
    assert "message" not in after and "with" not in after
    assert {k: v for k, v in after.items() if not k.startswith("_")} == {k: v for k, v in before.items() if not k.startswith("_")}
    again = client.post(f"/api/admin/kingdom/{TARGET_ID}/clearfields", headers=_admin(client))
    assert again.status_code == 200 and again.get_json()["removed"] == []
