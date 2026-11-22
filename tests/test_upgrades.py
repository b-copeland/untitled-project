"""
Upgrading units already trained to the next unit of their line (/api/mobis/upgrade): one tier at a time, for the
difference in price, through the mobis queue.
"""
import datetime

import pytest

import untitledapp.build as uab
import untitledapp.getters as uag
import untitledapp.refresh as refresh
import untitledapp.shared as uas
from tests.test_concurrency import KD_ID, _get, _post, _run_together, _set_up_kingdom

ALL_PROJECTS = [project for project in uas.PROJECTS if uas.PROJECTS[project].get("category") == "military"]
NO_UNITS = {key: 0 for key in uas.UNITS}


def _upgrade(client, jwt, counts):
    return client.post("/api/mobis/upgrade", json={"input": counts}, headers={"Authorization": f"Bearer {jwt}"})


def _queued(unit):
    return sum(entry.get(unit, 0) for entry in _get(f"/kingdom/{KD_ID}/mobis")["mobis"])


def _kingdom(units, money=10**7, projects=ALL_PROJECTS):
    return {"units": {**NO_UNITS, **units}, "money": money, "completed_projects": list(projects)}


# --- the paths ----------------------------------------------------------------------------------------------------------

def test_every_line_goes_up_one_tier_at_a_time():
    assert {unit: uas.UNITS[unit]["upgrades_from"] for unit in uas.UPGRADABLE_UNITS} == {
        "heavy_attack": "attack", "elite_attack": "heavy_attack",
        "solar_attack": "elite_attack", "self_destruct_attack": "elite_attack",
        "heavy_defense": "defense", "elite_defense": "heavy_defense",
        "solar_defense": "elite_defense", "self_destruct_defense": "elite_defense",
        "warp_big_flex": "big_flex", "compact_big_flex": "big_flex",
    }


def test_an_upgrade_always_costs_something_and_keeps_to_its_line():
    for unit in uas.UPGRADABLE_UNITS:
        source = uas.UNITS[unit]["upgrades_from"]
        assert uas.upgrade_cost(uas.UNITS, unit) > 0, unit
        assert (uas.UNITS[unit]["offense"] > 0) == (uas.UNITS[source]["offense"] > 0), unit
        assert (uas.UNITS[unit]["defense"] > 0) == (uas.UNITS[source]["defense"] > 0), unit


def test_the_upgrade_cost_is_the_difference_in_the_prices_the_kingdom_pays():
    assert uas.upgrade_cost(uas.UNITS, "heavy_attack") == uas.UNITS["heavy_attack"]["cost"] - uas.UNITS["attack"]["cost"]
    cheap = uag._get_units_adjusted_costs({"state": {"active_policies": []}}, {"unit_cost": -0.2})
    expected = uas.upgrade_cost(uas.UNITS, "heavy_attack") * 0.8
    assert uas.upgrade_cost(cheap, "heavy_attack") == pytest.approx(expected)
    assert uas.units_for({"completed_projects": []}, cheap)["heavy_attack"]["upgrade_cost"] == pytest.approx(expected)
    assert "upgrade_cost" not in uas.units_for({"completed_projects": []})["attack"]


# --- refusals -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("request_, kingdom, problem", [
    ({}, _kingdom({"attack": 10}), "Choose some units to upgrade"),
    ({"heavy_attack": -1}, _kingdom({"attack": 10}), "Upgrade counts can not be negative"),
    ({"attack": 1}, _kingdom({"attack": 10}), "Attackers can not be upgraded to"),
    ({"big_flex": 1}, _kingdom({"flex": 10}), "Big Flexers can not be upgraded to"),
    ({"heavy_attack": 1}, _kingdom({"attack": 10}, projects=[]),
     "Complete the Heavy Attackers project to upgrade to Heavy Attackers"),
    # One tier at a time: Elite Attackers come from Heavy Attackers, not straight from Attackers.
    ({"elite_attack": 1}, _kingdom({"attack": 10}), "You have 0 Heavy Attackers at home"),
    ({"heavy_attack": 11}, _kingdom({"attack": 10}), "You have 10 Attackers at home"),
    # Both playstyle units come from the same Elite Attackers.
    ({"solar_attack": 6, "self_destruct_attack": 5}, _kingdom({"elite_attack": 10}), "You have 10 Elite Attackers at home"),
    ({"heavy_attack": 10}, _kingdom({"attack": 10}, money=999), "Upgrading costs 1,000, you have 999"),
])
def test_an_upgrade_is_refused_with_the_reason(request_, kingdom, problem):
    assert uab._upgrade_problem(request_, kingdom, uas.UNITS) == problem


def test_an_upgrade_the_kingdom_can_make_has_no_problem():
    kingdom = _kingdom({"elite_attack": 10, "big_flex": 3})
    assert uab._upgrade_problem({"solar_attack": 5, "self_destruct_attack": 5, "compact_big_flex": 3}, kingdom, uas.UNITS) is None


def test_the_route_refuses_input_that_is_not_a_number(app, client, jwt1):
    _set_up_kingdom(10**7, units={**NO_UNITS, "attack": 10}, completed_projects=ALL_PROJECTS)
    response = _upgrade(client, jwt1, {"heavy_attack": "ten"})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Please enter whole numbers of units to upgrade"


def test_a_refused_upgrade_changes_nothing(app, client, jwt1):
    _set_up_kingdom(10**7, units={**NO_UNITS, "attack": 10})
    response = _upgrade(client, jwt1, {"heavy_attack": 5})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Complete the Heavy Attackers project to upgrade to Heavy Attackers"
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["units"]["attack"] == 10 and kingdom["money"] == 10**7
    assert _queued("heavy_attack") == 0


# --- the route ----------------------------------------------------------------------------------------------------------

def test_an_upgrade_takes_the_units_charges_the_difference_and_queues_the_new_ones(app, client, jwt1):
    _set_up_kingdom(10**7, units={**NO_UNITS, "attack": 10, "heavy_attack": 4}, completed_projects=ALL_PROJECTS)

    response = _upgrade(client, jwt1, {"heavy_attack": "6", "elite_attack": "4"})

    assert response.status_code == 200, response.get_json()
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["units"]["attack"] == 4
    assert kingdom["units"]["heavy_attack"] == 0  # its 4 are becoming elite; the 6 new ones are still upgrading
    cost = 6 * uas.upgrade_cost(uas.UNITS, "heavy_attack") + 4 * uas.upgrade_cost(uas.UNITS, "elite_attack")
    assert kingdom["money"] == pytest.approx(10**7 - cost)
    assert _queued("heavy_attack") == 6 and _queued("elite_attack") == 4
    assert uas.utc(kingdom["next_resolve"]["mobis"]) < uas.utc(uas.INITIAL_KINGDOM_STATE["kingdom"]["next_resolve"]["mobis"])


def test_the_military_page_shows_what_each_upgrade_costs(app, client, jwt1):
    _set_up_kingdom(10**7, units={**NO_UNITS, "attack": 10})
    desc = client.get("/api/mobis", headers={"Authorization": f"Bearer {jwt1}"}).get_json()["units_desc"]
    assert desc["heavy_attack"]["upgrade_cost"] == uas.upgrade_cost(uas.UNITS, "heavy_attack")
    assert desc["heavy_attack"]["upgrades_from"] == "attack"
    assert "upgrade_cost" not in desc["attack"]


def test_upgraded_units_arrive_on_a_kingdom_made_before_the_unit_existed(app, client, jwt1):
    old_units = {key: 0 for key in ("attack", "defense", "flex", "recruits", "engineers", "big_flex", "elite_attack")}
    now = datetime.datetime.now(datetime.timezone.utc)
    alive = {"stars": 300, "population": 10_000, "fuel": 10**6,  # so the refresh does not find it dead
             "structures": {**uas.INITIAL_KINGDOM_STATE["kingdom"]["structures"], "homes": 300}}
    _set_up_kingdom(10**7, race="Xo", last_income=now.isoformat(), units={**old_units, "elite_attack": 10},
                    completed_projects=ALL_PROJECTS, **alive)
    assert _upgrade(client, jwt1, {"solar_attack": 10}).status_code == 200
    done = max(uas.utc(entry["time"]) for entry in _get(f"/kingdom/{KD_ID}/mobis")["mobis"])

    with app.app_context():
        refresh._refresh_kd(KD_ID, _get("/state"), done + datetime.timedelta(seconds=1), False)

    units = _get(f"/kingdom/{KD_ID}")["units"]
    assert units["solar_attack"] == 10 and units["elite_attack"] == 0


def test_racing_upgrades_take_the_units_once(app, client, jwt1):
    _set_up_kingdom(10**7, units={**NO_UNITS, "attack": 10}, completed_projects=ALL_PROJECTS)

    responses = _run_together(app, 8, _post(app, jwt1, "/api/mobis/upgrade", {"input": {"heavy_attack": "10"}}))

    assert sorted(r.status_code for r in responses) == [200] + [400] * 7, [r.get_json() for r in responses]
    kingdom = _get(f"/kingdom/{KD_ID}")
    assert kingdom["units"]["attack"] == 0
    assert kingdom["money"] == pytest.approx(10**7 - 10 * uas.upgrade_cost(uas.UNITS, "heavy_attack"))
    assert _queued("heavy_attack") == 10
