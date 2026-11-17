"""
What each project does: one or more tests per project, each failing if the project's effect were not wired in. Grouped
as the Projects page groups them. The lock rules shared by every project are in tests/test_projects.py.
"""
import datetime
import math

import pytest

import untitledapp.conquer as uac
import untitledapp.getters as uag
import untitledapp.shared as uas
from tests import kingdoms
from tests.test_attack import TARGET_ID, _set_up_two_kingdoms
from tests.test_concurrency import KD_ID, _get

NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def _fuel_used(app, kd, unit):
    return kingdoms.income(app, kd)["income"]["fuel"]["units"][unit]


def _hangar_used(kd, units):
    counts = {"current_total": units, "hour_24": {}}
    return uag._calc_hangar_capacity(kd, counts)[1]


def _attack(client, jwt, units):
    return client.post(
        f"/api/attack/{TARGET_ID}",
        json={"attackerValues": {**units, "generals": 1}},
        headers={"Authorization": f"Bearer {jwt}"},
    )


# --- playstyle projects -------------------------------------------------------------------------------------------------

def test_solar_attackers_cut_the_fuel_pure_attackers_use_and_nothing_else(app):
    units = {"elite_attack": 100, "attack": 100, "defense": 100, "flex": 100}
    without = kingdoms.kingdom(units=units)
    with_project = kingdoms.kingdom(units=units, completed_projects=["solar_attackers"])
    cut = 1 - uas.GAME_CONFIG["SOLAR_FUEL_REDUCTION"]
    for unit in ("elite_attack", "attack"):
        assert _fuel_used(app, with_project, unit) == pytest.approx(_fuel_used(app, without, unit) * cut)
    for unit in ("defense", "flex"):
        assert _fuel_used(app, with_project, unit) == _fuel_used(app, without, unit)


def test_solar_defenders_cut_the_fuel_pure_defenders_use_and_nothing_else(app):
    units = {"heavy_defense": 100, "defense": 100, "attack": 100, "recruits": 100}
    without = kingdoms.kingdom(units=units)
    with_project = kingdoms.kingdom(units=units, completed_projects=["solar_defenders"])
    cut = 1 - uas.GAME_CONFIG["SOLAR_FUEL_REDUCTION"]
    for unit in ("heavy_defense", "defense"):
        assert _fuel_used(app, with_project, unit) == pytest.approx(_fuel_used(app, without, unit) * cut)
    for unit in ("attack", "recruits"):
        assert _fuel_used(app, with_project, unit) == _fuel_used(app, without, unit)


def test_the_military_page_shows_the_fuel_a_unit_uses_after_projects():
    kd = kingdoms.kingdom(completed_projects=["solar_attackers"])
    desc = uas.units_for(kd)
    assert desc["elite_attack"]["fuel"] == uas.UNITS["elite_attack"]["fuel"] * (1 - uas.GAME_CONFIG["SOLAR_FUEL_REDUCTION"])
    assert desc["defense"]["fuel"] == uas.UNITS["defense"]["fuel"]


def test_self_destructing_attackers_raise_the_defenders_losses_against_kingdoms_only():
    plain = {"completed_projects": []}
    bomber = {"completed_projects": ["self_destructing_attackers"]}
    increase = 1 + uas.GAME_CONFIG["SELF_DESTRUCT_LOSSES_INCREASE"]
    assert uac._battle_loss_rates(bomber, plain, 0.5)[1] == pytest.approx(uac._battle_loss_rates(plain, plain, 0.5)[1] * increase)
    assert uac._battle_loss_rates(bomber, plain)[0] == uac._battle_loss_rates(plain, plain)[0]
    assert uac._battle_loss_rates(bomber, None) == uac._battle_loss_rates(plain, None)  # primitives are not kingdoms


def test_self_destructing_defenders_raise_the_attackers_losses():
    plain = {"completed_projects": []}
    fortress = {"completed_projects": ["self_destructing_defenders"]}
    increase = 1 + uas.GAME_CONFIG["SELF_DESTRUCT_LOSSES_INCREASE"]
    assert uac._battle_loss_rates(plain, fortress)[0] == pytest.approx(uac._battle_loss_rates(plain, plain)[0] * increase)
    assert uac._battle_loss_rates(plain, fortress)[1] == uac._battle_loss_rates(plain, plain)[1]


@pytest.mark.parametrize("side", ["attacker", "defender"])
def test_self_destruct_changes_the_losses_of_a_real_attack(app, client, jwt1, side):
    def attacker_units_lost(projects_of_attacker, projects_of_target):
        _set_up_two_kingdoms(attacker_attack=2000, target_defense=1000,
                             target_overrides={"completed_projects": projects_of_target})
        if projects_of_attacker:
            from tests.test_concurrency import _create_item
            kd = _get(f"/kingdom/{KD_ID}")
            kd.pop("_etag", None)
            kd["completed_projects"] = projects_of_attacker
            _create_item(f"kingdom_{KD_ID}", kd)
        response = _attack(client, jwt1, {"attack": 2000})
        assert response.status_code == 200, response.get_json()
        sent_home = sum(sum(v for k, v in g.items() if k != "return_time") for g in _get(f"/kingdom/{KD_ID}")["generals_out"])
        return 2000 - sent_home, 1000 - _get(f"/kingdom/{TARGET_ID}")["units"]["defense"]

    plain_attacker_lost, plain_defender_lost = attacker_units_lost([], [])
    if side == "defender":
        attacker_lost, defender_lost = attacker_units_lost([], ["self_destructing_defenders"])
        assert attacker_lost > plain_attacker_lost
        assert defender_lost == plain_defender_lost
    else:
        attacker_lost, defender_lost = attacker_units_lost(["self_destructing_attackers"], [])
        assert defender_lost > plain_defender_lost
        assert attacker_lost == plain_attacker_lost


def test_warp_speed_sends_every_big_flexer_home_with_the_first_general():
    times = [NOW + datetime.timedelta(hours=hours) for hours in (6, 8, 12, 24)]
    units = {"big_flex": 10, "attack": 10}
    plain = uac._split_across_generals({"completed_projects": []}, units, times)
    warped = uac._split_across_generals({"completed_projects": ["warp_speed"]}, units, times)
    assert [g["big_flex"] for g in plain] == [3, 3, 2, 2]
    assert [g["big_flex"] for g in warped] == [10, 0, 0, 0]
    assert [g["attack"] for g in warped] == [g["attack"] for g in plain]
    assert warped[0]["return_time"] == times[0].isoformat()


def test_warp_speed_picks_the_earliest_general_whatever_the_order():
    times = [NOW + datetime.timedelta(hours=hours) for hours in (24, 6, 12)]
    warped = uac._split_across_generals({"completed_projects": ["warp_speed"]}, {"big_flex": 9}, times)
    assert [g["big_flex"] for g in warped] == [0, 9, 0]


def test_compact_flexers_make_big_flexers_take_one_hangar_space():
    units = {"big_flex": 100, "attack": 100}
    plain = kingdoms.kingdom()
    compact = kingdoms.kingdom(completed_projects=["compact_flexers"])
    assert _hangar_used(plain, units) == 100 * uas.UNITS["big_flex"]["hangar_capacity"] + 100
    assert _hangar_used(compact, units) == 100 * uas.GAME_CONFIG["COMPACT_FLEX_HANGAR_CAPACITY"] + 100
    assert uas.units_for(compact)["big_flex"]["hangar_capacity"] == uas.GAME_CONFIG["COMPACT_FLEX_HANGAR_CAPACITY"]


def test_the_playstyle_projects_need_the_best_unit_of_their_kind():
    nothing = {"race": "Xo", "completed_projects": []}
    for project, needs in {
        "solar_attackers": "elite_attackers", "self_destructing_attackers": "elite_attackers",
        "solar_defenders": "elite_defenders", "self_destructing_defenders": "elite_defenders",
        "warp_speed": "big_flexers", "compact_flexers": "big_flexers",
    }.items():
        assert uas.project_locked_reason(nothing, project) is not None, project
        assert uas.project_locked_reason({**nothing, "completed_projects": [needs]}, project) is None, project


# --- structure projects -------------------------------------------------------------------------------------------------

def _full(project):
    """``kingdom()`` overrides that give ``project`` its full bonus, and the bonus."""
    return kingdoms.full_bonus(project)


def test_the_homes_project_houses_more_population():
    import untitledapp.refresh as refresh
    points, bonus = _full("pop_bonus")
    plain = kingdoms.kingdom(structures={"homes": 100})
    boosted = kingdoms.kingdom(structures={"homes": 100}, **points)
    _, capacity = refresh._calc_pop_change_per_epoch(plain, False, 1, [])
    _, boosted_capacity = refresh._calc_pop_change_per_epoch(boosted, False, 1, [])
    assert capacity == 100 * uas.GAME_CONFIG["BASE_HOMES_CAPACITY"]
    assert boosted_capacity == pytest.approx(capacity * (1 + bonus), abs=1)


def test_the_mines_project_makes_mines_produce_more_money(app):
    points, bonus = _full("mines_bonus")
    plain = kingdoms.income(app, kingdoms.kingdom(structures={"mines": 100}))
    boosted = kingdoms.income(app, kingdoms.kingdom(structures={"mines": 100}, **points))
    assert boosted["income"]["money"]["mines"] == pytest.approx(plain["income"]["money"]["mines"] * (1 + bonus))
    assert boosted["income"]["money"]["population"] == plain["income"]["money"]["population"]


def test_the_fuel_plants_project_makes_fuel_plants_produce_more_fuel(app):
    points, bonus = _full("fuel_bonus")
    plants = {"fuel_plants": 100}
    plain = kingdoms.income(app, kingdoms.kingdom(structures=plants))
    boosted = kingdoms.income(app, kingdoms.kingdom(structures=plants, **points))
    produced = 100 * uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"]
    assert boosted["income"]["fuel"]["net"] - plain["income"]["fuel"]["net"] == pytest.approx(produced * bonus)


def test_the_hangars_project_makes_hangars_hold_more_units():
    points, bonus = _full("hangars_bonus")
    empty = {"current_total": {}, "hour_24": {}}
    plain, _ = uag._calc_hangar_capacity(kingdoms.kingdom(structures={"hangars": 100}), empty)
    boosted, _ = uag._calc_hangar_capacity(kingdoms.kingdom(structures={"hangars": 100}, **points), empty)
    assert plain == 100 * uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"]
    assert boosted == pytest.approx(plain * (1 + bonus), abs=1)


def test_the_drone_factories_project_makes_more_drones(app):
    points, bonus = _full("drone_factories_bonus")
    plain = kingdoms.income(app, kingdoms.kingdom(structures={"drone_factories": 100}))
    boosted = kingdoms.income(app, kingdoms.kingdom(structures={"drone_factories": 100}, **points))
    assert boosted["income"]["drones"] == pytest.approx(plain["income"]["drones"] * (1 + bonus))
    assert boosted["drones"] - plain["drones"] == pytest.approx(plain["income"]["drones"] * bonus)


def test_the_missile_silos_project_makes_silos_hold_more_missiles():
    points, bonus = _full("missile_silos_bonus")
    plain = uag._calc_missile_capacity(kingdoms.kingdom(structures={"missile_silos": 100}))
    boosted = uag._calc_missile_capacity(kingdoms.kingdom(structures={"missile_silos": 100}, **points))
    assert plain == 100 * uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"]
    assert boosted == pytest.approx(plain * (1 + bonus), abs=1)


def test_the_workshops_project_makes_workshops_house_more_engineers():
    points, bonus = _full("workshops_bonus")
    plain, _ = uag._calc_workshop_capacity(kingdoms.kingdom(race="Gaian", structures={"workshops": 100}), 0)
    boosted, _ = uag._calc_workshop_capacity(
        kingdoms.kingdom(race="Gaian", structures={"workshops": 100}, **points), 0)
    assert plain == 100 * uas.GAME_CONFIG["BASE_WORKSHOP_CAPACITY"]
    assert boosted == pytest.approx(plain * (1 + bonus), abs=1)


def test_the_new_structure_projects_are_one_time_with_a_bonus_once_completed():
    for project in ("mines_bonus", "hangars_bonus", "drone_factories_bonus", "missile_silos_bonus", "workshops_bonus"):
        assert project in uas.ONE_TIME_PROJECTS, project
        assert uas.PROJECTS[project]["bonus"] > 0, project
    assert "pop_bonus" in uas.CONTINUOUS_PROJECTS and "fuel_bonus" in uas.CONTINUOUS_PROJECTS


def test_a_one_time_bonus_counts_only_once_completed_not_for_points():
    max_points = uas.PROJECTS_FUNCS["mines_bonus"](300)
    almost = kingdoms.kingdom(projects_points={"mines_bonus": max_points * 2})
    assert uas.project_bonus(almost, "mines_bonus") == 0
    assert uas.project_bonuses(almost)["mines_bonus"] == 0
    done = kingdoms.kingdom(completed_projects=["mines_bonus"])
    assert uas.project_bonus(done, "mines_bonus") == uas.PROJECTS["mines_bonus"]["bonus"]
    assert uas.project_bonuses(done)["mines_bonus"] == uas.PROJECTS["mines_bonus"]["bonus"]


def test_the_refresh_completes_a_one_time_bonus_project(app):
    max_points = uas.PROJECTS_FUNCS["mines_bonus"](300)
    kd = kingdoms.kingdom(structures={"mines": 100}, projects_points={"mines_bonus": max_points},
                          projects_max_points={"mines_bonus": max_points})
    after = kingdoms.income(app, kd)
    assert "mines_bonus" in after["completed_projects"]
    assert uas.project_bonus(after, "mines_bonus") == uas.PROJECTS["mines_bonus"]["bonus"]


def test_a_structure_project_with_no_points_changes_nothing():
    assert uag._calc_missile_capacity(kingdoms.kingdom(race="Fuzi", structures={"missile_silos": 7})) == 7 * math.floor(
        uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"] * (1 + uas.GAME_CONFIG["FUZI_MISSILE_SILO_CAPACITY_INCREASE"]))
