"""
Projects: the shared helpers in shared.py, the lock rules (race, required projects, completed one-time projects) that the
project routes enforce, and kingdoms made before a project existed.

What each project does is tested in tests/test_project_effects.py.
"""
import json

import untitledapp.shared as uas
from tests import kingdoms
from tests.test_concurrency import _get, _set_up_kingdom


def _post(client, jwt, path, body):
    return client.post(path, headers={"Authorization": f"Bearer {jwt}"}, data=json.dumps(body))


# --- helpers ------------------------------------------------------------------------------------------------------------

def test_project_bonus_is_the_share_of_max_points_earned_times_the_max_bonus_and_stops_at_the_max():
    kd = {"projects_points": {"money_bonus": 50}, "projects_max_points": {"money_bonus": 100}}
    assert uas.project_bonus(kd, "money_bonus") == uas.PROJECTS["money_bonus"]["max_bonus"] * 0.5
    kd["projects_points"]["money_bonus"] = 500
    assert uas.project_bonus(kd, "money_bonus") == uas.PROJECTS["money_bonus"]["max_bonus"]


def test_a_project_the_kingdom_has_no_keys_for_counts_as_no_points():
    kd = {"stars": 300, "projects_points": {}, "projects_max_points": {}}
    assert uas.project_bonus(kd, "money_bonus") == 0
    assert set(uas.project_bonuses(kd)) == set(uas.BONUS_PROJECTS)
    assert all(value == 0 for value in uas.project_bonuses(kd).values())


def test_one_time_and_continuous_projects_are_told_apart_by_max_bonus():
    assert set(uas.ONE_TIME_PROJECTS) | set(uas.CONTINUOUS_PROJECTS) == set(uas.PROJECTS)
    assert not set(uas.ONE_TIME_PROJECTS) & set(uas.CONTINUOUS_PROJECTS)
    assert all("max_bonus" in uas.PROJECTS[key] for key in uas.CONTINUOUS_PROJECTS)


def test_every_project_has_a_name_a_description_a_known_category_and_existing_requirements():
    for key, project in uas.PROJECTS.items():
        assert project["name"] and project["desc"], key
        assert project["category"] in uas.PROJECT_CATEGORIES, key
        for required in project.get("requires", []):
            assert required in uas.ONE_TIME_PROJECTS, (key, required)
        if project.get("race"):
            assert project["race"] in uas.RACES, key


def test_a_project_is_locked_until_what_it_requires_is_completed():
    kd = {"race": "Xo", "completed_projects": []}
    assert uas.project_locked_reason(kd, "spy_bonus") == 'Complete "Drone Gadgets" first'
    kd["completed_projects"] = ["drone_gadgets"]
    assert uas.project_locked_reason(kd, "spy_bonus") is None


def test_a_racial_project_is_locked_for_other_races(monkeypatch):
    monkeypatch.setitem(uas.PROJECTS, "test_racial", {"name": "Test", "desc": "", "category": "racial", "race": "Gaian",
                                                      "stars_power": 0, "constant": 1})
    assert uas.project_locked_reason({"race": "Xo"}, "test_racial") == "Only Gaian kingdoms can research Test"
    assert uas.project_locked_reason({"race": "Gaian"}, "test_racial") is None


def test_an_old_kingdom_is_given_the_keys_of_new_units_and_projects_without_changing_what_it_has():
    kd = {
        "stars": 400,
        "units": {"attack": 7},
        "projects_points": {"money_bonus": 12},
        "projects_max_points": {"money_bonus": 99},
        "projects_assigned": {},
        "projects_target": {},
    }
    uas.with_new_fields(kd)
    assert kd["units"]["attack"] == 7
    assert set(kd["units"]) == set(uas.UNITS)
    assert kd["projects_points"]["money_bonus"] == 12
    assert kd["projects_max_points"]["money_bonus"] == 99
    assert set(kd["projects_points"]) == set(uas.PROJECTS)
    assert kd["projects_max_points"]["military_bonus"] == uas.PROJECTS_FUNCS["military_bonus"](400)
    assert "units_target" not in kd  # only what is there is filled


# --- the routes ---------------------------------------------------------------------------------------------------------

def test_engineers_can_not_be_assigned_to_a_locked_project(app, client, jwt1):
    _set_up_kingdom(0, race="Xo", units={**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "engineers": 10})
    response = _post(client, jwt1, "/api/projects", {"assign": {"spy_bonus": 5}})
    assert response.status_code == 400
    assert response.get_json()["message"] == 'Complete "Drone Gadgets" first'
    assert _get("/kingdom/1")["projects_assigned"]["spy_bonus"] == 0


def test_engineers_can_be_assigned_once_the_required_project_is_done(app, client, jwt1):
    _set_up_kingdom(0, race="Xo", completed_projects=["drone_gadgets"],
                    units={**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "engineers": 10})
    response = _post(client, jwt1, "/api/projects", {"add": {"spy_bonus": 5}})
    assert response.status_code == 200, response.get_json()
    assert _get("/kingdom/1")["projects_assigned"]["spy_bonus"] == 5


def test_engineers_can_not_go_to_a_completed_one_time_project(app, client, jwt1):
    _set_up_kingdom(0, race="Xo", completed_projects=["big_flexers"],
                    units={**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "engineers": 10})
    response = _post(client, jwt1, "/api/projects", {"add": {"big_flexers": 1}})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Big Flexers is already completed"
    response = _post(client, jwt1, "/api/projects/target", {"targets": {"big_flexers": 10}})
    assert response.status_code == 400


def test_a_target_for_a_locked_project_is_refused(app, client, jwt1):
    _set_up_kingdom(0, race="Xo", projects_target={key: 0 for key in uas.PROJECTS})
    response = _post(client, jwt1, "/api/projects/target", {"targets": {"spy_bonus": 10}})
    assert response.status_code == 400
    assert response.get_json()["message"] == 'Complete "Drone Gadgets" first'


def test_an_old_kingdom_without_a_projects_keys_can_still_assign_to_it(app, client, jwt1):
    _set_up_kingdom(
        0, race="Xo", units={**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "engineers": 10},
        projects_assigned={"money_bonus": 0},
    )
    response = _post(client, jwt1, "/api/projects", {"add": {"military_bonus": 4}})
    assert response.status_code == 200, response.get_json()
    assert _get("/kingdom/1")["projects_assigned"]["military_bonus"] == 4


def test_the_projects_route_says_which_projects_are_locked_and_why(app, client, jwt1):
    _set_up_kingdom(0, race="Xo")
    payload = client.get("/api/projects", headers={"Authorization": f"Bearer {jwt1}"}).get_json()
    assert payload["locked"]["spy_bonus"] == 'Complete "Drone Gadgets" first'
    assert "money_bonus" not in payload["locked"]
    assert set(payload["points"]) == set(uas.PROJECTS)
    assert set(payload["max_points"]) == set(uas.PROJECTS)


def test_a_locked_unit_can_not_be_trained_or_targeted(app, client, jwt1):
    _set_up_kingdom(100000, race="Xo", units={**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "recruits": 10})
    assert _post(client, jwt1, "/api/mobis", {"big_flex": 1}).status_code == 400
    response = _post(client, jwt1, "/api/mobis/target", {"targets": {"big_flex": 10}})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Complete the Big Flexers project to train Big Flexers"


# --- the improved units (heavy and elite attackers and defenders) ------------------------------------------------------

import pytest
import untitledapp.getters as uag

IMPROVED_UNITS = {
    "heavy_attack": "heavy_attackers",
    "elite_attack": "elite_attackers",
    "heavy_defense": "heavy_defenders",
    "elite_defense": "elite_defenders",
}


@pytest.mark.parametrize("unit,project", IMPROVED_UNITS.items())
def test_an_improved_unit_is_trained_only_once_its_project_is_done(app, client, jwt1, unit, project):
    units = {**uas.INITIAL_KINGDOM_STATE["kingdom"]["units"], "recruits": 10}
    _set_up_kingdom(100000, race="Xo", units=units)
    assert _post(client, jwt1, "/api/mobis", {unit: 1}).status_code == 400

    _set_up_kingdom(100000, race="Xo", units=units, completed_projects=[project])
    response = _post(client, jwt1, "/api/mobis", {unit: 1})
    assert response.status_code == 200, response.get_json()
    assert _get("/kingdom/1")["units"]["recruits"] == 9
    assert any(entry.get(unit) for entry in _get("/kingdom/1/mobis")["mobis"])


def test_the_elite_projects_need_the_heavy_ones_first():
    kd = {"race": "Xo", "completed_projects": []}
    assert uas.project_locked_reason(kd, "elite_attackers") == 'Complete "Heavy Attackers" first'
    assert uas.project_locked_reason(kd, "elite_defenders") == 'Complete "Heavy Defenders" first'
    assert uas.project_locked_reason(kd, "heavy_attackers") is None
    kd["completed_projects"] = ["heavy_attackers", "heavy_defenders"]
    assert uas.project_locked_reason(kd, "elite_attackers") is None
    assert uas.project_locked_reason(kd, "elite_defenders") is None


def test_improved_units_are_stronger_and_count_in_offense_and_defense():
    assert uag._calc_max_offense({"heavy_attack": 10}, military_bonus=0, generals=1) == 60
    assert uag._calc_max_offense({"elite_attack": 10}, military_bonus=0, generals=1) == 70
    assert uag._calc_max_defense({"heavy_defense": 10}, military_bonus=0, shields=0) == 60
    assert uag._calc_max_defense({"elite_defense": 10}, military_bonus=0, shields=0) == 70


def test_each_improvement_costs_more_per_point_of_strength_but_takes_the_same_hangar_space():
    def per_strength(unit):
        return uas.UNITS[unit]["cost"] / max(uas.UNITS[unit]["offense"], uas.UNITS[unit]["defense"])

    for line in (("attack", "heavy_attack", "elite_attack"), ("defense", "heavy_defense", "elite_defense")):
        assert per_strength(line[0]) < per_strength(line[1]) < per_strength(line[2])
        assert len({uas.UNITS[unit]["hangar_capacity"] for unit in line}) == 1


def test_elite_projects_cost_more_than_the_heavy_ones_and_defense_about_a_fifth_more():
    points = {key: uas.PROJECTS_FUNCS[key](0) for key in IMPROVED_UNITS.values()}
    assert points["elite_attackers"] > points["heavy_attackers"]
    assert points["elite_defenders"] > points["heavy_defenders"]
    assert points["heavy_defenders"] / points["heavy_attackers"] == pytest.approx(1.2, rel=0.05)
    assert points["elite_defenders"] / points["elite_attackers"] == pytest.approx(1.2, rel=0.05)


def test_improved_units_have_a_networth_and_a_name():
    for unit in IMPROVED_UNITS:
        assert uas.GAME_CONFIG["NETWORTH_VALUES"][unit] > 0
        assert uas.PRETTY_NAMES[unit]


def test_the_refresh_completes_a_unit_project_once_its_points_are_reached(app):
    kd = kingdoms.kingdom(
        units={"engineers": 100},
        projects_assigned={"heavy_attackers": 100},
        projects_points={"heavy_attackers": uas.PROJECTS_FUNCS["heavy_attackers"](0) - 10},
        structures={"homes": 100},
    )
    new = kingdoms.income(app, kd, epochs=1)
    assert "heavy_attackers" in new["completed_projects"]
    assert new["projects_assigned"]["heavy_attackers"] == 0
