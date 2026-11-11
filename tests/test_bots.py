"""Bots: every archetype is legal, differs per bot, and ends up as a working kingdom with its auto builder on."""
import random

import pytest

import untitledapp.bots as bots
import untitledapp.refresh as refresh
import untitledapp.shared as uas
from tests.test_concurrency import _create_item, _get, _set_up_kingdom

_next_start = [5000]


def _kingdoms_starting_past_any_used_id():
    """The next kingdom id is how many kingdoms exist, and the test backend keeps ids from earlier tests (blanked, as
    /deleteall leaves them), so start each test's bots at an id nothing has used."""
    _next_start[0] += 100
    _create_item("kingdoms", {"kingdoms": {f"filler{i}": "filler" for i in range(_next_start[0])}})


@pytest.mark.parametrize("key", sorted(bots.ARCHETYPES))
def test_every_archetype_is_legal(app, key):
    with app.app_context():
        assert bots.problems(bots.ARCHETYPES[key]) == []


def test_the_four_playstyles_have_their_races():
    assert {key: archetype.race for key, archetype in bots.ARCHETYPES.items()} == {
        "explorer": "Gaian", "attacker": "Xo", "intel": "Lumina", "thief": "Vult"}


def test_an_illegal_edit_is_caught(app):
    import dataclasses

    too_much = dataclasses.replace(bots.ARCHETYPES["explorer"], auto_spending={"settle": 0.8, "structures": 0.5})
    with app.app_context():
        assert any("auto spending" in problem for problem in bots.problems(too_much))


def test_variation_keeps_each_total_and_makes_bots_differ():
    base = bots.ARCHETYPES["attacker"].auto_spending
    one, two = bots.vary(base, random.Random(1), 0.2), bots.vary(base, random.Random(2), 0.2)

    assert round(sum(one.values()), 3) == round(sum(base.values()), 3)
    assert one != two and one != base


def test_a_created_bot_is_a_playable_kingdom_with_the_builder_on(app, client):
    _set_up_kingdom(money=0)  # the game state, kingdoms and galaxies documents
    _kingdoms_starting_past_any_used_id()
    _create_item("galaxies", {"galaxies": {"1:1": [], "1:2": []}})

    with app.app_context():
        created = bots.create_bots({"attacker": 2, "thief": 1}, rng=random.Random(4))

    assert created == ["bot_attacker_1", "bot_attacker_2", "bot_thief_3"]
    kingdoms = _get("/kingdoms")["kingdoms"]
    ids = [kd_id for kd_id, name in kingdoms.items() if name in created]
    assert len(ids) == 3
    galaxies = _get("/galaxies")["galaxies"]
    assert sorted(len(members) for members in galaxies.values()) == [1, 2] or sum(map(len, galaxies.values())) == 3

    attacker = _get(f"/kingdom/{ids[0]}")
    assert attacker["race"] == "Xo" and attacker["auto_spending_enabled"] is True
    assert attacker["units"]["attack"] == 1200 and attacker["units"]["flex"] == 1000
    assert attacker["auto_attack_enabled"] is True and attacker["auto_attack_settings"]["pure"] > 0
    assert sum(attacker["auto_spending"].values()) <= 1.0001
    assert attacker["next_resolve"]["auto_spending"] < uas.DATE_SENTINEL

    thief = _get(f"/kingdom/{ids[2]}")
    assert thief["race"] == "Vult" and thief["drones"] == 8000
    assert thief["auto_rob_enabled"] is True and thief["auto_attack_enabled"] is False


def test_bots_cannot_be_logged_in_to(app, client):
    _set_up_kingdom(money=0)
    _kingdoms_starting_past_any_used_id()
    _create_item("galaxies", {"galaxies": {"1:1": []}})
    with app.app_context():
        (name,) = bots.create_bots({"explorer": 1}, rng=random.Random(1))

    assert client.post("/api/login", json={"username": name, "password": ""}).status_code == 401
    assert client.post("/api/login", json={"username": name, "password": "bot"}).status_code == 401


def test_only_an_admin_can_create_bots_and_unknown_types_are_refused(app, client, jwt1):
    assert client.post("/api/admin/bots", json={"explorer": 1}, headers={"Authorization": f"Bearer {jwt1}"}).status_code in (401, 403)
    admin = client.post("/api/login", json={"username": "admin", "password": "admin"}).get_json()["accessToken"]
    refused = client.post("/api/admin/bots", json={"wizard": 1}, headers={"Authorization": f"Bearer {admin}"})
    assert refused.status_code == 400 and "wizard" in refused.get_json()["message"]


def test_the_refresh_runs_a_bot_for_a_while_without_error(app, client):
    """A bot's kingdom gets through several ticks, spending its funding as the builder is told to."""
    import datetime

    _set_up_kingdom(money=0)
    _kingdoms_starting_past_any_used_id()
    _create_item("galaxies", {"galaxies": {"1:1": []}})
    _create_item("empires", {"empires": {}})
    _create_item("galaxy_votes_1:1", {"active_policies": [], "votes": {}, "leader": "", "empire_invitations": [], "empire_join_requests": []})
    with app.app_context():
        (name,) = bots.create_bots({"explorer": 1}, rng=random.Random(3))
        kd_id = next(k for k, v in _get("/kingdoms")["kingdoms"].items() if v == name)
        state = refresh.uag._get_state()
        before = _get(f"/kingdom/{kd_id}")
        for minutes in (30, 90, 200):
            when = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)
            refresh._refresh_kd(kd_id, state, when, False)

    after = _get(f"/kingdom/{kd_id}")
    assert after["money"] != before["money"] or after["funding"] != before["funding"]
