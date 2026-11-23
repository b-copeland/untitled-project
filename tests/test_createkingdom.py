"""Making a kingdom: quick starts from the bot archetypes, the player's own choices, and doing it in one request."""
import itertools

import pytest

import untitledapp.bots as bots
import untitledapp.shared as uas
from tests.test_bots import _kingdoms_starting_past_any_used_id
from tests.test_concurrency import _create_item, _get, _run_together, _set_up_kingdom
from tests.test_users import _add_user, _stored_user

_numbers = itertools.count(1)


@pytest.fixture
def world(app, client):
    """The game documents a new kingdom is made into: two empty galaxies."""
    _set_up_kingdom(money=0)
    _kingdoms_starting_past_any_used_id()
    _create_item("galaxies", {"galaxies": {"1:1": [], "1:2": []}})


@pytest.fixture
def player(app, client, world):
    """A signed-up account with no kingdom yet, signed in. Returns (username, auth headers)."""
    name = f"newplayer{next(_numbers)}"
    _add_user(app, name)
    token = client.post("/api/login", json={"username": name, "password": "pw"}).get_json()["accessToken"]
    return name, {"Authorization": f"Bearer {token}"}


def _kingdom_named(name):
    return next((kd_id for kd_id, kd_name in _get("/kingdoms")["kingdoms"].items() if kd_name == name), None)


def _user(app, name):
    user = _stored_user(app, name)
    return user.kd_id, user.kd_created


def test_the_creator_offers_every_bot_archetype_with_what_it_starts_with(client, player):
    _, headers = player
    data = client.get("/api/createkingdomdata", headers=headers).get_json()

    assert [preset["key"] for preset in data["presets"]] == list(bots.ARCHETYPES)
    attacker = next(preset for preset in data["presets"] if preset["key"] == "attacker")
    assert attacker["race"] == "Xo" and attacker["label"] == "Attacker" and attacker["autoAttack"] is True
    assert sum(attacker["unitsChoices"][unit] * data["selection_points"][unit] for unit in data["selection_points"]) == data["total_points"]
    assert sum(attacker["structuresChoices"].values()) == data["total_stars"]


@pytest.mark.parametrize("key", sorted(bots.ARCHETYPES))
def test_every_quick_start_makes_a_playable_kingdom_with_the_builder_off(client, player, app, key):
    name, headers = player
    archetype = bots.ARCHETYPES[key]

    response = client.post("/api/createkingdom", json={"kdName": f"{key} fan", "preset": key}, headers=headers)

    assert response.status_code == 200, response.get_json()
    kd_id, created = _user(app, name)
    assert kd_id and created is True
    kingdom = _get(f"/kingdom/{kd_id}")
    assert kingdom["name"] == f"{key} fan" and kingdom["race"] == archetype.race
    assert kingdom["units"]["attack"] == archetype.unit_choices["attack"]
    assert kingdom["structures"]["homes"] == archetype.structures_choices["homes"]
    # The plan is filled in exactly, but nothing is running.
    assert kingdom["auto_spending"] == archetype.auto_spending
    assert kingdom["structures_target"] == archetype.structures_target
    assert kingdom["auto_spending_enabled"] is False
    assert kingdom["auto_attack_enabled"] is False and kingdom["auto_rob_enabled"] is False
    assert kingdom["next_resolve"]["auto_spending"] == uas.DATE_SENTINEL
    if archetype.auto_attack:
        assert kingdom["auto_attack_settings"] == archetype.auto_attack
    if archetype.auto_rob:
        assert kingdom["auto_rob_settings"] == archetype.auto_rob


def test_choosing_the_auto_builder_switches_on_what_the_archetype_plays_by(client, player, app):
    name, headers = player
    client.post("/api/createkingdom", json={"kdName": "Raider", "preset": "attacker", "autoBuilder": True}, headers=headers)

    kingdom = _get(f"/kingdom/{_user(app, name)[0]}")
    assert kingdom["auto_spending_enabled"] is True and kingdom["auto_attack_enabled"] is True
    assert kingdom["auto_rob_enabled"] is True  # every quick start robs primitives with its drones
    assert kingdom["next_resolve"]["auto_spending"] < uas.DATE_SENTINEL
    assert kingdom["shields"]["military"] == bots.ARCHETYPES["attacker"].shields["military"]


def test_a_player_can_make_their_own_choices(client, player, app):
    name, headers = player
    body = {
        "kdName": "Homebody",
        "race": "Gaian",
        "unitsChoices": {"drones": 20000},
        "structuresChoices": {"homes": int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"])},
    }
    assert client.post("/api/createkingdom", json=body, headers=headers).status_code == 200

    kingdom = _get(f"/kingdom/{_user(app, name)[0]}")
    assert kingdom["drones"] == 20000 and kingdom["race"] == "Gaian"
    assert kingdom["auto_spending_enabled"] is False


@pytest.mark.parametrize("change", [
    {"race": ""},
    {"race": "Klingon"},
    {"unitsChoices": {"drones": 100}},
    {"unitsChoices": {"drones": "lots"}},
    {"unitsChoices": {"cannons": 20000}},
    {"structuresChoices": {"palaces": 300}},
    {"structuresChoices": {"homes": 10}},
    {"preset": "wizard"},
])
def test_a_request_that_would_not_work_makes_nothing(client, player, app, change):
    name, headers = player
    body = {"kdName": "Nobody", "race": "Gaian", "unitsChoices": {"drones": 20000},
            "structuresChoices": {"homes": int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"])}, **change}

    response = client.post("/api/createkingdom", json=body, headers=headers)

    assert response.status_code == 400 and response.get_json()["message"]
    assert _user(app, name) == (None, False)  # not even a half-made kingdom
    assert _kingdom_named("Nobody") is None


def test_a_taken_or_bad_name_is_refused_and_points_at_the_name(client, player):
    _, headers = player
    assert client.post("/api/createkingdom", json={"kdName": "Taken", "preset": "explorer"}, headers=headers).status_code == 200

    for name in ("taken", "", "   ", "x" * 25):
        # a second player trying the same name
        other = f"other{next(_numbers)}"
        _add_user(client.application, other)
        token = client.post("/api/login", json={"username": other, "password": "pw"}).get_json()["accessToken"]
        response = client.post("/api/createkingdom", json={"kdName": name, "preset": "explorer"},
                               headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 400 and response.get_json()["field"] == "name", name


def test_a_second_kingdom_is_refused(client, player):
    _, headers = player
    assert client.post("/api/createkingdom", json={"kdName": "Once", "preset": "explorer"}, headers=headers).status_code == 200
    again = client.post("/api/createkingdom", json={"kdName": "Twice", "preset": "explorer"}, headers=headers)
    assert again.status_code == 400 and _kingdom_named("Twice") is None


def test_a_kingdom_left_half_made_by_the_old_flow_is_finished_without_a_name(client, player, app):
    name, headers = player
    # What the old name-only step left behind: a kingdom with an id, never set up.
    with app.app_context():
        _stored_user(app, name).save(kd_id="1")

    response = client.post("/api/createkingdom", json={"preset": "intel"}, headers=headers)

    assert response.status_code == 200, response.get_json()
    assert _get("/kingdom/1")["race"] == "Lumina" and _user(app, name) == ("1", True)


def test_a_double_click_makes_one_kingdom(app, client, player):
    """The claim on the user document is what stops it (there is no lock)."""
    name, headers = player
    body = {"kdName": "Eager", "preset": "thief"}

    responses = _run_together(app, 6, lambda c, i: c.post("/api/createkingdom", json=body, headers=headers))

    assert sorted(r.status_code for r in responses).count(200) == 1, [r.get_json() for r in responses]
    kingdoms = _get("/kingdoms")["kingdoms"]
    assert list(kingdoms.values()).count("Eager") == 1
    assert _user(app, name)[1] is True


# --- the login token follows the kingdom (docs/decisions/0005-kingdom-in-the-token.md) ---------------------------

def _claims(app, token):
    return app.extensions["praetorian"].extract_jwt_token(token)


def test_creating_a_kingdom_returns_tokens_that_name_it(app, client, player):
    name, headers = player
    before = _claims(app, headers["Authorization"].split()[1])
    assert (before["kd"], before["kc"]) == ("", False)

    body = client.post("/api/createkingdom", json={"kdName": "Token Realm", "preset": "attacker"}, headers=headers).get_json()

    kd_id, _ = _user(app, name)
    claims = _claims(app, body["accessToken"])
    assert (claims["kd"], claims["kc"]) == (kd_id, True)
    assert _claims(app, body["refreshToken"])["kd"] == kd_id
    new_headers = {"Authorization": f"Bearer {body['accessToken']}"}
    assert client.get("/api/kingdomid", headers=new_headers).get_json() == {"kd_id": kd_id, "created": True}


def test_resetting_a_kingdom_returns_tokens_that_say_it_is_not_created(app, client, player):
    name, headers = player
    body = client.post("/api/createkingdom", json={"kdName": "Resettable", "preset": "attacker"}, headers=headers).get_json()
    headers = {"Authorization": f"Bearer {body['accessToken']}"}
    _create_item("state", {"state": {"game_start": "2999-01-01T00:00:00+00:00"}})  # the game has not started

    response = client.post("/api/resetkingdom", headers=headers)

    assert response.status_code == 200, response.get_json()
    assert _claims(app, response.get_json()["accessToken"])["kc"] is False


def test_a_refresh_rebuilds_the_kingdom_claims_from_the_user(app, client, player, monkeypatch):
    import pendulum
    name, _ = player
    guard = app.extensions["praetorian"]
    monkeypatch.setattr(guard, "access_lifespan", pendulum.duration(seconds=-5))  # born expired, so it can refresh
    old = client.post("/api/login", json={"username": name, "password": "pw"}).get_json()["refreshToken"]
    monkeypatch.undo()
    with app.app_context():
        _stored_user(app, name).save(kd_id="77", kd_created=True)  # changed behind the token's back

    refreshed = client.post("/api/refresh", headers={"Authorization": f"Bearer {old}"}).get_json()["accessToken"]

    claims = _claims(app, refreshed)
    assert (claims["kd"], claims["kc"]) == ("77", True)


def test_a_token_from_before_a_round_reset_stops_working(app, client, player, monkeypatch):
    import pendulum
    name, headers = player
    _create_item("state", {"state": {"game_start": "2000-01-01T00:00:00+00:00"}, "round": "round-1"})
    token = client.post("/api/login", json={"username": name, "password": "pw"}).get_json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/kingdomid", headers=headers).status_code == 200
    monkeypatch.setattr(app.extensions["praetorian"], "access_lifespan", pendulum.duration(seconds=-5))  # can refresh
    expired = client.post("/api/login", json={"username": name, "password": "pw"}).get_json()["refreshToken"]
    monkeypatch.undo()

    _create_item("state", {"state": {"game_start": "2000-01-01T00:00:00+00:00"}, "round": "round-2"})  # a reset

    assert client.get("/api/kingdomid", headers=headers).status_code == 401
    assert client.post("/api/shields", json={"military": 0}, headers=headers).status_code == 401
    assert client.post("/api/refresh", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    fresh = client.post("/api/login", json={"username": name, "password": "pw"}).get_json()["accessToken"]
    assert client.get("/api/kingdomid", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200


def test_a_disabled_player_keeps_a_token_already_issued(app, client, player):
    """The accepted trade-off of decision 0005: disabling takes effect when the token is renewed."""
    name, headers = player
    with app.app_context():
        _stored_user(app, name).save(is_active=False)
    assert client.get("/api/kingdomid", headers=headers).status_code == 200


def test_a_new_kingdom_shows_its_income_before_the_first_tick(client, player, app):
    """The Status and Shields pages read the income breakdown: a new player needs their fuel surplus to set shields."""
    name, headers = player
    assert client.post("/api/createkingdom", json={"kdName": "Fresh", "preset": "explorer"}, headers=headers).status_code == 200

    kingdom = _get(f"/kingdom/{_user(app, name)[0]}")
    income = kingdom["income"]
    mines = int(kingdom["structures"]["mines"])
    assert income["money"]["mines"] == mines * uas.GAME_CONFIG["BASE_MINES_INCOME_PER_EPOCH"]
    assert income["money"]["net"] > 0
    plants = int(kingdom["structures"]["fuel_plants"])
    assert income["fuel"]["fuel_plants"] == plants * uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"]
    assert "net" in income["fuel"] and "drones" in income and "population" in income
    # Only the breakdown is seeded: nothing is credited.
    assert kingdom["money"] == uas.INITIAL_KINGDOM_STATE["kingdom"]["money"]
