"""
What a request sends is checked before it is used, and only what the game uses is stored (issue #219).

The pages send sensible values; a script can send anything. Each case here once reached a document: an unknown key that
made the refresh fail on the kingdom every tick, NaN that passed every range check, a flag that was any JSON value, a
schedule or a pinned list stored as sent.
"""
import pytest

import untitledapp.inputs as uin
from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get, _set_up_kingdom
from tests.test_politics import _galaxy_politics


def _auth(jwt):
    return {"Authorization": f"Bearer {jwt}"}


def _set_up():
    _set_up_two_kingdoms()
    _create_item("kingdoms", {"kingdoms": {KD_ID: "Test Kingdom", TARGET_ID: "Target"}})


# --- the checks themselves -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [float("nan"), "nan", "inf", True, [1], {"a": 1}, "ten"])
def test_a_number_must_be_a_finite_number(value):
    with pytest.raises(uin.BadInput):
        uin.number(value)


def test_numbers_as_the_pages_send_them_pass():
    assert uin.number("12") == 12 and uin.number(12.5) == 12.5 and uin.number("", blank=0) == 0
    assert uin.number("7", integer=True) == 7
    with pytest.raises(uin.BadInput):
        uin.number("7.5", integer=True)


def test_keyed_values_must_use_known_keys():
    assert uin.keyed({"a": "1"}, ["a", "b"]) == {"a": 1}
    with pytest.raises(uin.BadInput):
        uin.keyed({"time": 1}, ["a"])


# --- build ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("body", [{"time": 5}, {"not_a_structure": 5}, {"homes": "nan"}, {"homes": [1]}])
def test_building_something_that_is_not_a_structure_is_refused_and_queues_nothing(app, client, jwt1, body):
    _set_up()
    before = _get(f"/kingdom/{KD_ID}/structures")

    response = client.post("/api/structures", json=body, headers=_auth(jwt1))

    assert response.status_code == 400
    assert _get(f"/kingdom/{KD_ID}/structures")["structures"] == before["structures"]


@pytest.mark.parametrize("body", [
    {"targets": {"engineers": 10}},
    {"targets": {"made_up": 10}},
    {"targets": {"attack": "nan"}},
    {"recruits_before_units": "yes"},
    {"targets": {"attack": 10}, "max_recruits": "nan"},
])
def test_unit_targets_take_only_trainable_units_finite_percentages_and_a_real_switch(app, client, jwt1, body):
    _set_up()
    before = _get(f"/kingdom/{KD_ID}")

    response = client.post("/api/mobis/target", json=body, headers=_auth(jwt1))

    assert response.status_code == 400
    after = _get(f"/kingdom/{KD_ID}")
    assert after["units_target"] == before["units_target"]
    assert after["recruits_before_units"] == before["recruits_before_units"]


def test_structure_targets_refuse_unknown_structures_and_nan(app, client, jwt1):
    _set_up()
    for body in ({"time": 10}, {"homes": "nan"}):
        assert client.post("/api/structures/target", json=body, headers=_auth(jwt1)).status_code == 400


def test_the_project_switch_must_be_true_or_false(app, client, jwt1):
    _set_up()
    response = client.post("/api/projects/target", json={"enabled": {"x" * 100: 1}}, headers=_auth(jwt1))
    assert response.status_code == 400
    assert _get(f"/kingdom/{KD_ID}")["auto_assign_projects"] in (True, False)


def test_auto_spending_refuses_nan_and_a_switch_that_is_not_true_or_false(app, client, jwt1):
    _set_up()
    assert client.post("/api/spending", json={"enabled": "on"}, headers=_auth(jwt1)).status_code == 400
    assert client.post("/api/spending", json={"settle": "nan"}, headers=_auth(jwt1)).status_code == 400


def test_shields_refuse_nan(app, client, jwt1):
    _set_up()
    assert client.post("/api/shields", json={"military": "nan"}, headers=_auth(jwt1)).status_code == 400


# --- conquer --------------------------------------------------------------------------------------------------------

def test_an_unknown_spy_operation_is_refused_before_anything_is_spent(app, client, jwt1):
    _set_up()
    before = _get(f"/kingdom/{KD_ID}")

    response = client.post(f"/api/spy/{TARGET_ID}", json={"drones": 100, "shielded": False, "operation": "made_up"},
                           headers=_auth(jwt1))

    assert response.status_code == 400
    after = _get(f"/kingdom/{KD_ID}")
    assert after["drones"] == before["drones"] and after["spy_attempts"] == before["spy_attempts"]


def test_a_schedule_keeps_only_the_options_its_kind_uses(app, client, jwt1):
    _set_up()
    body = {"type": "missiles", "time": "2999-01-01T00:00:00+00:00",
            "options": {"target": TARGET_ID, "planet_busters": "1", "star_busters": "", "galaxy_busters": "",
                        "junk": "x" * 1000}}
    _create_item("state", {"state": {"game_start": "2000-01-01T00:00:00+00:00",
                                     "game_end": "3000-01-01T00:00:00+00:00", "active_policies": []}})

    response = client.post("/api/schedule", json=body, headers=_auth(jwt1))

    assert response.status_code == 200, response.get_json()
    options = _get(f"/kingdom/{KD_ID}")["schedule"][-1]["options"]
    assert set(options) == {"target", "planet_busters", "star_busters", "galaxy_busters"}


@pytest.mark.parametrize("options, type_", [
    ({"target": "999", "planet_busters": 1}, "missiles"),
    ({"target": TARGET_ID, "operation": "made_up", "attempts": 1, "drones_pct": 10}, "aggressivespy"),
    ({"target": TARGET_ID, "planet_busters": "nan"}, "missiles"),
    ({"target": TARGET_ID, "planet_busters": 1}, "made_up"),
])
def test_a_schedule_with_an_unknown_target_operation_type_or_nan_is_refused(app, client, jwt1, options, type_):
    _set_up()
    response = client.post("/api/schedule", json={"type": type_, "time": "2999-01-01T00:00:00+00:00", "options": options},
                           headers=_auth(jwt1))
    assert response.status_code == 400


def test_pinning_keeps_only_kingdoms_that_exist(app, client, jwt1):
    _set_up()

    assert client.post("/api/pinned", json={"pinned": ["999"]}, headers=_auth(jwt1)).status_code == 400
    assert client.post("/api/pinned", json={"junk": "x"}, headers=_auth(jwt1)).status_code == 400
    response = client.post("/api/pinned", json={"pinned": [TARGET_ID, TARGET_ID], "junk": "x"}, headers=_auth(jwt1))

    assert response.status_code == 200
    pinned = _get(f"/kingdom/{KD_ID}/pinned")
    assert pinned["pinned"] == [TARGET_ID] and "junk" not in pinned


def test_an_attack_sends_only_units_that_fight(app, client, jwt1):
    """Engineers are dropped (so nothing is sent), as is the page's own suggestion margin."""
    _set_up()
    before = _get(f"/kingdom/{KD_ID}")["units"]
    response = client.post(f"/api/attack/{TARGET_ID}",
                           json={"attackerValues": {"engineers": 5, "generals": 1, "buffer": "1.0"}}, headers=_auth(jwt1))
    assert response.status_code == 400
    assert _get(f"/kingdom/{KD_ID}")["units"] == before


def test_an_attack_as_the_page_sends_it_still_goes(app, client, jwt1):
    _set_up()
    response = client.post(f"/api/attack/{TARGET_ID}",
                           json={"attackerValues": {"attack": "1000", "generals": "1", "buffer": "1.0"}}, headers=_auth(jwt1))
    assert response.status_code == 200, response.get_json()


# --- misc and politics -----------------------------------------------------------------------------------------------

def test_a_message_gets_the_servers_time_and_must_be_text(app, client, jwt1):
    _set_up()

    assert client.post(f"/api/messages/{TARGET_ID}", json={"message": ["x"] * 5}, headers=_auth(jwt1)).status_code == 400
    response = client.post(f"/api/messages/{TARGET_ID}", json={"message": "hello", "time": {"big": "x" * 1000}},
                           headers=_auth(jwt1))

    assert response.status_code == 200
    sent = _get(f"/kingdom/{TARGET_ID}/messages")["messages"][0]
    assert isinstance(sent["time"], str) and sent["time"].startswith("20")


def test_a_galaxy_can_only_elect_one_of_its_own(app, client, jwt1):
    _set_up_kingdom(money=0)
    _set_up_kingdom(money=0, kd_id="2")
    _create_item("galaxies", {"galaxies": {"1:1": [KD_ID], "1:2": ["2"]}})
    _create_item("galaxy_votes_1:1", _galaxy_politics())

    response = client.post("/api/galaxypolitics/leader", json={"selected": "2"}, headers=_auth(jwt1))

    assert response.status_code == 400
    assert _get("/galaxy/1:1/politics")["leader"] == ""


def test_a_route_about_an_empire_or_galaxy_that_does_not_exist_is_a_404(app, client, jwt1):
    _set_up()
    _create_item("empires", {"empires": {}})
    assert client.post("/api/empire/e9/denounce", headers=_auth(jwt1)).status_code == 404
    assert client.post("/api/galaxy/9:9/invite", headers=_auth(jwt1)).status_code == 404
    assert client.get("/api/galaxy/9:9", headers=_auth(jwt1)).status_code == 404


# --- sign-up --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("username", ["bot_fake", "Bot_fake", "BOT_x", "name​", " spaced", "x" * 33])
def test_a_sign_up_with_a_bot_name_or_hidden_characters_is_refused(app, client, username):
    response = client.post("/api/signup", json={"username": username, "password": "pw"})
    assert response.status_code == 400


def test_an_ordinary_sign_up_still_works(app, client):
    assert client.post("/api/signup", json={"username": "robot_fan", "password": "pw"}).status_code == 201
