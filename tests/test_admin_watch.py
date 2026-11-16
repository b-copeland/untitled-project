"""The admin's view of a round: every kingdom at a glance, and one kingdom in full."""
from tests.test_concurrency import KD_ID, _create_item, _set_up_kingdom  # noqa: F401


def _admin(client):
    token = client.post("/api/login", json={"username": "admin", "password": "admin"}).get_json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _universe():
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2", name="bot_thief_1", bot={"type": "thief", "log": [{"kind": "plan", "why": "x"}]})
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Test Kingdom", "2": "bot_thief_1"}})
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"]}})
    _create_item("empires", {"empires": {"0": {"name": "Reds", "galaxies": ["1:2"], "war": []}}})
    _create_item("scores", {"stars": {KD_ID: 300, "2": 900}, "networth": {KD_ID: 10, "2": 50}, "points": {"2": 4.25},
                            "galaxy_networth": {}})


def test_players_can_not_watch_the_universe(app, client, jwt1):
    headers = {"Authorization": f"Bearer {jwt1}"}
    assert client.get("/api/admin/universe", headers=headers).status_code in (401, 403)
    assert client.get("/api/admin/kingdom/2", headers=headers).status_code in (401, 403)


def test_the_admin_sees_every_kingdom_strongest_first(app, client):
    _universe()

    response = client.get("/api/admin/universe", headers=_admin(client))

    assert response.status_code == 200, response.get_data(as_text=True)
    first, second = response.get_json()["kingdoms"]
    assert first == {"kd_id": "2", "name": "bot_thief_1", "playstyle": "thief", "galaxy": "1:2", "empire": "Reds",
                     "stars": 900, "networth": 50, "points": 4.2}
    assert second["playstyle"] == "player" and second["empire"] is None


def test_the_admin_sees_a_kingdom_in_full_with_its_bot(app, client):
    _universe()

    response = client.get("/api/admin/kingdom/2", headers=_admin(client))

    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["kingdom"]["bot"]["log"][0]["why"] == "x" and "units" in body["kingdom"]
    assert not any(key.startswith("_") for key in body["kingdom"]) and "news" in body
