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


def _done(project):
    """``kingdom()`` overrides that complete the one-time ``project``, and what it adds to each structure."""
    return {"completed_projects": [project]}, uas.PROJECTS[project]["increase"]


def test_the_mines_project_makes_each_mine_produce_more_money(app):
    done, more = _done("mines_bonus")
    assert more == uas.GAME_CONFIG["MINES_PROJECT_MONEY_PER_MINE"]
    plain = kingdoms.income(app, kingdoms.kingdom(structures={"mines": 100}))
    boosted = kingdoms.income(app, kingdoms.kingdom(structures={"mines": 100}, **done))
    assert boosted["income"]["money"]["mines"] == plain["income"]["money"]["mines"] + 100 * more
    assert boosted["income"]["money"]["population"] == plain["income"]["money"]["population"]


def test_the_fuel_plants_project_makes_fuel_plants_produce_more_fuel(app):
    points, bonus = _full("fuel_bonus")
    plants = {"fuel_plants": 100}
    plain = kingdoms.income(app, kingdoms.kingdom(structures=plants))
    boosted = kingdoms.income(app, kingdoms.kingdom(structures=plants, **points))
    produced = 100 * uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"]
    assert boosted["income"]["fuel"]["net"] - plain["income"]["fuel"]["net"] == pytest.approx(produced * bonus)


def test_the_hangars_project_makes_each_hangar_hold_more_units():
    done, more = _done("hangars_bonus")
    empty = {"current_total": {}, "hour_24": {}}
    plain, _ = uag._calc_hangar_capacity(kingdoms.kingdom(structures={"hangars": 100}), empty)
    boosted, _ = uag._calc_hangar_capacity(kingdoms.kingdom(structures={"hangars": 100}, **done), empty)
    assert plain == 100 * uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"]
    assert boosted == plain + 100 * more


@pytest.mark.parametrize("race", ["Xo", "Vult"])
def test_the_drone_factories_project_makes_each_factory_produce_more_drones(app, race):
    done, more = _done("drone_factories_bonus")
    plain = kingdoms.income(app, kingdoms.kingdom(race=race, structures={"drone_factories": 100}))
    boosted = kingdoms.income(app, kingdoms.kingdom(race=race, structures={"drone_factories": 100}, **done))
    assert boosted["income"]["drones"] == pytest.approx(plain["income"]["drones"] + 100 * more)
    assert boosted["drones"] - plain["drones"] == pytest.approx(100 * more)


def test_the_missile_silos_project_makes_each_silo_hold_more_missiles():
    done, more = _done("missile_silos_bonus")
    plain = uag._calc_missile_capacity(kingdoms.kingdom(structures={"missile_silos": 100}))
    boosted = uag._calc_missile_capacity(kingdoms.kingdom(structures={"missile_silos": 100}, **done))
    assert plain == 100 * uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"]
    assert boosted == plain + 100 * more


def test_the_workshops_project_makes_each_workshop_house_more_engineers():
    done, more = _done("workshops_bonus")
    plain, _ = uag._calc_workshop_capacity(kingdoms.kingdom(race="Gaian", structures={"workshops": 100}), 0)
    boosted, _ = uag._calc_workshop_capacity(
        kingdoms.kingdom(race="Gaian", structures={"workshops": 100}, **done), 0)
    assert plain == 100 * uas.GAME_CONFIG["BASE_WORKSHOP_CAPACITY"]
    assert boosted == plain + 100 * more


def test_the_new_structure_projects_are_one_time_with_a_raw_increase_once_completed():
    for project in ("mines_bonus", "hangars_bonus", "drone_factories_bonus", "missile_silos_bonus", "workshops_bonus"):
        assert project in uas.ONE_TIME_PROJECTS, project
        assert uas.PROJECTS[project]["increase"] > 0, project
        assert "bonus" not in uas.PROJECTS[project], project
    assert "pop_bonus" in uas.CONTINUOUS_PROJECTS and "fuel_bonus" in uas.CONTINUOUS_PROJECTS


def test_a_one_time_increase_counts_only_once_completed_not_for_points():
    max_points = uas.PROJECTS_FUNCS["mines_bonus"](300)
    almost = kingdoms.kingdom(projects_points={"mines_bonus": max_points * 2})
    assert uas.project_increase(almost, "mines_bonus") == 0
    done = kingdoms.kingdom(completed_projects=["mines_bonus"])
    assert uas.project_increase(done, "mines_bonus") == uas.PROJECTS["mines_bonus"]["increase"]


def test_the_refresh_completes_a_one_time_structure_project(app):
    max_points = uas.PROJECTS_FUNCS["mines_bonus"](300)
    kd = kingdoms.kingdom(structures={"mines": 100}, projects_points={"mines_bonus": max_points},
                          projects_max_points={"mines_bonus": max_points})
    after = kingdoms.income(app, kd)
    assert "mines_bonus" in after["completed_projects"]
    assert uas.project_increase(after, "mines_bonus") == uas.PROJECTS["mines_bonus"]["increase"]


def test_a_structure_project_with_no_points_changes_nothing():
    assert uag._calc_missile_capacity(kingdoms.kingdom(race="Fuzi", structures={"missile_silos": 7})) == 7 * math.floor(
        uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"] * (1 + uas.GAME_CONFIG["FUZI_MISSILE_SILO_CAPACITY_INCREASE"]))


# --- economy projects ---------------------------------------------------------------------------------------------------

def test_the_economy_and_military_projects_are_one_time_with_a_bonus_once_completed():
    for project in ("settle_cost_bonus", "recruit_cost_bonus", "pop_growth_bonus", "casualties_bonus",
                    "spy_protection_bonus"):
        assert project in uas.ONE_TIME_PROJECTS, project
        assert uas.PROJECTS[project]["bonus"] > 0, project


def test_cheaper_exploring_lowers_the_settle_price():
    points, bonus = _full("settle_cost_bonus")
    plain = uag._get_settle_price(kingdoms.kingdom(), False)
    cheaper = uag._get_settle_price(kingdoms.kingdom(**points), False)
    assert cheaper == pytest.approx(plain * (1 - bonus))


def test_cheaper_recruits_lower_what_recruiting_charges(app, client, jwt1):
    from tests.test_concurrency import _set_up_kingdom
    points, bonus = _full("recruit_cost_bonus")
    _set_up_kingdom(100000, race="Xo", population=10000, **points)
    response = client.post("/api/recruits", json={"recruitsInput": 100}, headers={"Authorization": f"Bearer {jwt1}"})
    assert response.status_code == 200, response.get_json()
    charged = 100000 - _get(f"/kingdom/{KD_ID}")["money"]
    assert charged == pytest.approx(100 * uas.GAME_CONFIG["BASE_RECRUIT_COST"] * (1 - bonus))


def test_population_growth_grows_population_faster():
    import untitledapp.refresh as refresh
    points, bonus = _full("pop_growth_bonus")
    roomy = {"structures": {"homes": 300}, "population": 1000}
    plain, _ = refresh._calc_pop_change_per_epoch(kingdoms.kingdom(**roomy), False, 1, [])
    faster, _ = refresh._calc_pop_change_per_epoch(kingdoms.kingdom(**roomy, **points), False, 1, [])
    assert plain > 0
    assert faster == pytest.approx(plain * (1 + bonus))


# --- military and spy projects ------------------------------------------------------------------------------------------

def test_fewer_casualties_lowers_the_owners_losses_attacking_defending_and_on_primitives():
    points, bonus = _full("casualties_bonus")
    plain = kingdoms.kingdom()
    tough = kingdoms.kingdom(**points)
    assert uac._battle_loss_rates(tough, plain)[0] == pytest.approx(uac._battle_loss_rates(plain, plain)[0] * (1 - bonus))
    assert uac._battle_loss_rates(plain, tough)[1] == pytest.approx(uac._battle_loss_rates(plain, plain)[1] * (1 - bonus))
    assert uac._battle_loss_rates(tough, None)[0] == pytest.approx(uac._battle_loss_rates(plain, None)[0] * (1 - bonus))
    assert uac._battle_loss_rates(tough, plain)[1] == uac._battle_loss_rates(plain, plain)[1]  # only its own losses


def test_generals_speed_bonus_needs_fewer_casualties_first():
    assert uas.project_locked_reason(kingdoms.kingdom(), "general_bonus") is not None
    assert uas.project_locked_reason(kingdoms.kingdom(completed_projects=["casualties_bonus"]), "general_bonus") is None
    assert "general_bonus" not in uas.INITIAL_PROJECTS_TARGET
    assert sum(uas.INITIAL_PROJECTS_TARGET.values()) == pytest.approx(1)


def test_auto_assign_gives_no_engineers_to_a_locked_project():
    import untitledapp.refresh as refresh
    kd = kingdoms.kingdom(units={"engineers": 100}, projects_assigned={key: 0 for key in uas.PROJECTS},
                          projects_target={**{key: 0 for key in uas.PROJECTS}, "general_bonus": 0.5, "money_bonus": 0.5})
    assert refresh._resolve_auto_projects(kd)["projects_assigned"]["general_bonus"] == 0
    assert kd["projects_assigned"]["money_bonus"] == 100
    unlocked = kingdoms.kingdom(units={"engineers": 100}, projects_assigned={key: 0 for key in uas.PROJECTS},
                                projects_target={**{key: 0 for key in uas.PROJECTS}, "general_bonus": 0.5, "money_bonus": 0.5},
                                completed_projects=["casualties_bonus"])
    assert refresh._resolve_auto_projects(unlocked)["projects_assigned"]["general_bonus"] == 50


def test_a_one_time_bonus_counts_only_once_completed_not_for_points():
    max_points = uas.PROJECTS_FUNCS["settle_cost_bonus"](300)
    almost = kingdoms.kingdom(projects_points={"settle_cost_bonus": max_points * 2})
    assert uas.project_bonus(almost, "settle_cost_bonus") == 0
    assert uas.project_bonuses(almost)["settle_cost_bonus"] == 0
    done = kingdoms.kingdom(completed_projects=["settle_cost_bonus"])
    assert uas.project_bonus(done, "settle_cost_bonus") == uas.PROJECTS["settle_cost_bonus"]["bonus"]
    assert uas.project_bonuses(done)["settle_cost_bonus"] == uas.PROJECTS["settle_cost_bonus"]["bonus"]


def test_counter_intelligence_lowers_the_damage_of_aggressive_operations(app, client, jwt1):
    points, bonus = _full("spy_protection_bonus")
    assert uac._aggro_damage_multiplier({}, kingdoms.kingdom(**points)) == pytest.approx(1 - bonus)

    def fuel_burned(target_overrides):
        _set_up_two_kingdoms(target_overrides=target_overrides)
        response = client.post(f"/api/spy/{TARGET_ID}", json={"drones": 100, "shielded": False, "operation": "suicidedrones"},
                               headers={"Authorization": f"Bearer {jwt1}"})
        assert response.status_code == 200, response.get_json()
        return uas.INITIAL_KINGDOM_STATE["kingdom"]["fuel"] - _get(f"/kingdom/{TARGET_ID}")["fuel"]

    assert fuel_burned({}) == 100 * uas.GAME_CONFIG["BASE_DRONES_SUICIDE_FUEL_DAMAGE"]
    assert fuel_burned(points) == math.floor(100 * uas.GAME_CONFIG["BASE_DRONES_SUICIDE_FUEL_DAMAGE"] * (1 - bonus))


# --- racial capstones ---------------------------------------------------------------------------------------------------

CAPSTONES = {"Gaian": "gaian_capstone", "Xo": "xo_capstone", "Vult": "vult_capstone", "Lumina": "lumina_capstone",
             "Fuzi": "fuzi_capstone"}


@pytest.mark.parametrize("race,project", CAPSTONES.items())
def test_a_racial_capstone_is_only_for_its_race_and_costs_more_than_every_project_but_the_evolutions(race, project):
    assert uas.project_locked_reason({"race": race}, project) is None
    other = next(r for r in uas.RACES if r != race)
    assert uas.project_locked_reason({"race": other}, project) == f"Only {race} kingdoms can research {uas.PROJECTS[project]['name']}"
    points = uas.PROJECTS_FUNCS[project](0)
    not_racial = [key for key in uas.ONE_TIME_PROJECTS if uas.PROJECTS[key]["category"] != "racial"]
    assert all(points > uas.PROJECTS_FUNCS[key](0) for key in not_racial)


def test_gaian_terraforming_makes_settling_and_building_faster():
    import untitledapp.build as uab
    plain = kingdoms.kingdom(race="Gaian")
    terraformed = kingdoms.kingdom(race="Gaian", completed_projects=["gaian_capstone"])
    assert uag._get_settle_time(terraformed, 10) == pytest.approx(
        uag._get_settle_time(plain, 10) * (1 - uas.GAME_CONFIG["GAIAN_CAPSTONE_SETTLE_TIME_REDUCTION"]))

    def latest(kd):
        entries, _ = uab._get_new_structures({"homes": 100}, NOW, kd)
        return max(datetime.datetime.fromisoformat(entry["time"]) for entry in entries) - NOW

    assert latest(terraformed) == latest(plain) * (1 - uas.GAME_CONFIG["GAIAN_CAPSTONE_STRUCTURE_TIME_REDUCTION"])
    assert latest(None) == latest(plain)


def test_xo_warlords_bring_generals_home_sooner():
    bonuses = {"general_bonus": 0.1}
    plain = kingdoms.kingdom()
    warlord = kingdoms.kingdom(completed_projects=["xo_capstone"])
    assert uac._general_speed(plain, bonuses) == 0.1
    assert uac._general_speed(warlord, bonuses) == pytest.approx(0.1 + uas.GAME_CONFIG["XO_CAPSTONE_RETURN_REDUCTION"])
    times = lambda kd: uac._calc_generals_return_time(1, 24, NOW, uac._general_speed(kd, bonuses))[0]
    assert times(warlord) < times(plain)


def test_xo_warlords_inflict_more_losses_only_at_war():
    plain = kingdoms.kingdom()
    warlord = kingdoms.kingdom(completed_projects=["xo_capstone"])
    assert uac._battle_loss_rates(warlord, plain, 1.0, war=False) == uac._battle_loss_rates(plain, plain, 1.0, war=False)
    assert uac._battle_loss_rates(warlord, plain, 1.0, war=True)[1] == pytest.approx(
        uac._battle_loss_rates(plain, plain, 1.0, war=True)[1] * (1 + uas.GAME_CONFIG["XO_CAPSTONE_WAR_LOSSES_INCREASE"]))


def test_vult_swarm_makes_aggressive_operations_do_more_damage():
    swarm = kingdoms.kingdom(race="Vult", completed_projects=["vult_capstone"])
    assert uac._aggro_damage_multiplier(swarm, kingdoms.kingdom()) == pytest.approx(
        1 + uas.GAME_CONFIG["VULT_CAPSTONE_DRONE_DAMAGE_INCREASE"])
    assert uac._aggro_damage_multiplier(kingdoms.kingdom(race="Vult"), kingdoms.kingdom()) == 1


def test_lumina_prisms_make_shielding_drones_cost_less_fuel():
    plain = kingdoms.kingdom(race="Lumina", fuel=60, drones=100, spy_attempts=1)
    prisms = kingdoms.kingdom(race="Lumina", fuel=60, drones=100, spy_attempts=1, completed_projects=["lumina_capstone"])
    assert uac._shielding_fuel(plain, 100) == 100 * uas.GAME_CONFIG["BASE_DRONES_SHIELDING_FUEL_PER_DRONE"]
    assert uac._shielding_fuel(prisms, 100) == pytest.approx(
        100 * (1 - uas.GAME_CONFIG["LUMINA_CAPSTONE_SHIELDING_FUEL_REDUCTION"]))
    assert uac._validate_spy_request(100, plain, True) == (False, "You do not have enough fuel")
    assert uac._validate_spy_request(100, prisms, True) == (True, "")


def test_lumina_prisms_charge_less_fuel_when_robbing_shielded(app, client, jwt1):
    from tests.test_concurrency import _set_up_kingdom
    _set_up_kingdom(0, race="Lumina", drones=1000, completed_projects=["lumina_capstone"])
    response = client.post("/api/robprimitives", json={"drones": 1000, "shielded": True},
                           headers={"Authorization": f"Bearer {jwt1}"})
    assert response.status_code == 200, response.get_json()
    spent = uas.INITIAL_KINGDOM_STATE["kingdom"]["fuel"] - _get(f"/kingdom/{KD_ID}")["fuel"]
    assert spent == pytest.approx(1000 * (1 - uas.GAME_CONFIG["LUMINA_CAPSTONE_SHIELDING_FUEL_REDUCTION"]))


def test_fuzi_warheads_make_missiles_do_more_damage():
    missiles = {"planet_busters": 100}
    warheads = kingdoms.kingdom(race="Fuzi", completed_projects=["fuzi_capstone"])
    assert uac._missile_damage_multiplier(kingdoms.kingdom(race="Fuzi")) == 1
    damage = uac._calculate_missiles_damage(missiles, 0, fuzi=True)
    boosted = uac._calculate_missiles_damage(missiles, 0, fuzi=True, damage_multiplier=uac._missile_damage_multiplier(warheads))
    assert boosted["stars_damage"] == math.floor(damage["stars_damage"] * (1 + uas.GAME_CONFIG["FUZI_CAPSTONE_MISSILE_DAMAGE_INCREASE"]))
