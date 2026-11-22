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


# --- playstyle units ----------------------------------------------------------------------------------------------------
# Each playstyle project unlocks a unit with a trait. The trait belongs to that unit, not to every unit of its kind.

PLAYSTYLE_UNITS = {
    "solar_attackers": "solar_attack", "self_destructing_attackers": "self_destruct_attack",
    "solar_defenders": "solar_defense", "self_destructing_defenders": "self_destruct_defense",
    "warp_speed": "warp_big_flex", "compact_flexers": "compact_big_flex",
}
NO_UNITS = {"attack": 0, "defense": 0, "flex": 0, "recruits": 0, "engineers": 0, "big_flex": 0}


@pytest.mark.parametrize("project, unit", PLAYSTYLE_UNITS.items())
def test_each_playstyle_project_unlocks_its_unit_and_nothing_else(project, unit):
    assert uas.UNITS[unit]["project"] == project
    assert uas.unit_locked({"completed_projects": []}, unit)
    assert not uas.unit_locked({"completed_projects": [project]}, unit)
    others = [other for other in PLAYSTYLE_UNITS.values() if other != unit]
    assert all(uas.unit_locked({"completed_projects": [project]}, other) for other in others)


@pytest.mark.parametrize("unit, best", [
    ("solar_attack", "elite_attack"), ("self_destruct_attack", "elite_attack"),
    ("solar_defense", "elite_defense"), ("self_destruct_defense", "elite_defense"),
    ("warp_big_flex", "big_flex"), ("compact_big_flex", "big_flex"),
])
def test_a_playstyle_unit_is_as_strong_as_the_best_unit_of_its_line_and_upgrades_from_it(unit, best):
    assert uas.UNITS[unit]["offense"] == uas.UNITS[best]["offense"]
    assert uas.UNITS[unit]["defense"] == uas.UNITS[best]["defense"]
    assert uas.UNITS[unit]["upgrades_from"] == best


def test_solar_units_use_less_fuel_and_their_projects_change_no_other_unit(app):
    units = {"solar_attack": 100, "elite_attack": 100, "solar_defense": 100, "elite_defense": 100}
    kd = kingdoms.kingdom(units=units, completed_projects=["solar_attackers", "solar_defenders"])
    cut = 1 - uas.GAME_CONFIG["SOLAR_FUEL_REDUCTION"]
    assert _fuel_used(app, kd, "solar_attack") == pytest.approx(_fuel_used(app, kd, "elite_attack") * cut)
    assert _fuel_used(app, kd, "solar_defense") == pytest.approx(_fuel_used(app, kd, "elite_defense") * cut)
    assert _fuel_used(app, kd, "elite_attack") == 100 * uas.UNITS["elite_attack"]["fuel"]
    assert _fuel_used(app, kd, "elite_defense") == 100 * uas.UNITS["elite_defense"]["fuel"]


def test_the_military_page_shows_the_fuel_each_unit_uses():
    desc = uas.units_for(kingdoms.kingdom(completed_projects=["solar_attackers"]))
    assert desc["solar_attack"]["fuel"] == uas.UNITS["elite_attack"]["fuel"] * (1 - uas.GAME_CONFIG["SOLAR_FUEL_REDUCTION"])
    assert desc["elite_attack"]["fuel"] == uas.UNITS["elite_attack"]["fuel"]


def test_self_destruct_share_is_the_share_of_the_strength_from_self_destructing_units():
    assert uas.self_destruct_share({"self_destruct_attack": 10}, "offense") == 1
    assert uas.self_destruct_share({"self_destruct_attack": 10, "elite_attack": 10}, "offense") == pytest.approx(0.5)
    # Flexers defend too, and attackers at home add no defense.
    share = uas.self_destruct_share({"self_destruct_defense": 10, "flex": 14, "attack": 1000}, "defense")
    assert share == pytest.approx(70 / (70 + 70))
    assert uas.self_destruct_share({}, "defense") == 0
    assert uas.self_destruct_share({"attack": 10}, "defense") == 0


def test_self_destructing_attackers_raise_the_defenders_losses_by_their_share_of_the_offense():
    plain = {"completed_projects": []}
    increase = uas.GAME_CONFIG["SELF_DESTRUCT_LOSSES_INCREASE"]
    base = uac._battle_loss_rates(plain, plain, 0.5, attacker_units={"elite_attack": 10})
    all_of_them = uac._battle_loss_rates(plain, plain, 0.5, attacker_units={"self_destruct_attack": 10})
    half = uac._battle_loss_rates(plain, plain, 0.5, attacker_units={"self_destruct_attack": 10, "elite_attack": 10})
    assert all_of_them[1] == pytest.approx(base[1] * (1 + increase))
    assert half[1] == pytest.approx(base[1] * (1 + increase / 2))
    assert all_of_them[0] == base[0]
    # Primitives are not kingdoms.
    assert uac._battle_loss_rates(plain, None, attacker_units={"self_destruct_attack": 10}) == uac._battle_loss_rates(plain, None)


def test_self_destructing_defenders_raise_the_attackers_losses_by_their_share_of_the_defense():
    plain = {"completed_projects": []}
    increase = uas.GAME_CONFIG["SELF_DESTRUCT_LOSSES_INCREASE"]
    base = uac._battle_loss_rates(plain, plain, defender_units={"elite_defense": 10})
    fortress = uac._battle_loss_rates(plain, plain, defender_units={"self_destruct_defense": 10})
    assert fortress[0] == pytest.approx(base[0] * (1 + increase))
    assert fortress[1] == base[1]


def test_the_self_destructing_projects_alone_change_no_losses():
    both = {"completed_projects": ["self_destructing_attackers", "self_destructing_defenders"]}
    plain = {"completed_projects": []}
    units = {"elite_attack": 10, "elite_defense": 10}
    assert (uac._battle_loss_rates(both, both, 0.5, False, units, units)
            == uac._battle_loss_rates(plain, plain, 0.5, False, units, units))


@pytest.mark.parametrize("side", ["attacker", "defender"])
def test_self_destruct_changes_the_losses_of_a_real_attack(app, client, jwt1, side):
    from tests.test_concurrency import _create_item

    def units_lost(attacker_unit, target_unit):
        _set_up_two_kingdoms(attacker_attack=0, target_defense=0,
                             target_overrides={"units": {**NO_UNITS, target_unit: 1000}})
        kd = _get(f"/kingdom/{KD_ID}")
        kd.pop("_etag", None)
        kd["units"] = {**kd["units"], attacker_unit: 2000}
        _create_item(f"kingdom_{KD_ID}", kd)
        response = _attack(client, jwt1, {attacker_unit: 2000})
        assert response.status_code == 200, response.get_json()
        sent_home = sum(sum(v for k, v in g.items() if k != "return_time") for g in _get(f"/kingdom/{KD_ID}")["generals_out"])
        return 2000 - sent_home, 1000 - _get(f"/kingdom/{TARGET_ID}")["units"][target_unit]

    plain_attacker_lost, plain_defender_lost = units_lost("elite_attack", "elite_defense")
    if side == "defender":
        attacker_lost, defender_lost = units_lost("elite_attack", "self_destruct_defense")
        assert attacker_lost > plain_attacker_lost
        assert defender_lost == plain_defender_lost
    else:
        attacker_lost, defender_lost = units_lost("self_destruct_attack", "elite_defense")
        assert defender_lost > plain_defender_lost
        assert attacker_lost == plain_attacker_lost


def test_warp_speed_big_flexers_all_come_home_with_the_first_general_and_big_flexers_do_not():
    times = [NOW + datetime.timedelta(hours=hours) for hours in (6, 8, 12, 24)]
    generals = uac._split_across_generals({"warp_big_flex": 10, "big_flex": 10, "attack": 10}, times)
    assert [g["warp_big_flex"] for g in generals] == [10, 0, 0, 0]
    assert [g["big_flex"] for g in generals] == [3, 3, 2, 2]
    assert [g["attack"] for g in generals] == [3, 3, 2, 2]
    assert generals[0]["return_time"] == times[0].isoformat()


def test_warp_speed_picks_the_earliest_general_whatever_the_order():
    times = [NOW + datetime.timedelta(hours=hours) for hours in (24, 6, 12)]
    generals = uac._split_across_generals({"warp_big_flex": 9}, times)
    assert [g["warp_big_flex"] for g in generals] == [0, 9, 0]


def test_compact_big_flexers_take_less_hangar_space_and_big_flexers_do_not():
    units = {"compact_big_flex": 100, "big_flex": 100}
    kd = kingdoms.kingdom(completed_projects=["compact_flexers"])
    compact = uas.GAME_CONFIG["COMPACT_FLEX_HANGAR_CAPACITY"]
    assert _hangar_used(kd, units) == 100 * compact + 100 * uas.UNITS["big_flex"]["hangar_capacity"]
    assert uas.units_for(kd)["compact_big_flex"]["hangar_capacity"] == compact
    assert uas.units_for(kd)["big_flex"]["hangar_capacity"] == uas.UNITS["big_flex"]["hangar_capacity"]


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


@pytest.mark.parametrize("silos,expected", [(1, 1), (2, 3), (3, 4), (4, 6), (101, 151)])
def test_half_a_missile_per_silo_gives_one_more_missile_for_every_two_silos(monkeypatch, silos, expected):
    monkeypatch.setitem(uas.PROJECTS["missile_silos_bonus"], "increase", 0.5)
    done = kingdoms.kingdom(structures={"missile_silos": silos}, completed_projects=["missile_silos_bonus"])
    assert uas.GAME_CONFIG["BASE_MISSILE_SILO_CAPACITY"] == 1
    assert uag._calc_missile_capacity(done) == expected


def test_empty_silos_are_counted_with_a_fractional_capacity_per_silo(monkeypatch):
    monkeypatch.setitem(uas.PROJECTS["missile_silos_bonus"], "increase", 0.5)
    # 10 silos hold 15 of each missile, so 6 missiles fill 4 silos (1.5 each) and leave 6 empty.
    kd = kingdoms.kingdom(structures={"missile_silos": 10}, completed_projects=["missile_silos_bonus"],
                          missiles={"planet_busters": 6})
    assert uag._empty_missile_silos(kd) == 6


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
def test_a_racial_capstone_is_only_for_its_race(race, project):
    assert uas.project_locked_reason({"race": race}, project) is None
    other = next(r for r in uas.RACES if r != race)
    assert uas.project_locked_reason({"race": other}, project) == f"Only {race} kingdoms can research {uas.PROJECTS[project]['name']}"


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


# --- racial evolutions --------------------------------------------------------------------------------------------------

EVOLUTIONS = {"Gaian": "gaian_evolution", "Xo": "xo_evolution", "Vult": "vult_evolution", "Lumina": "lumina_evolution",
              "Fuzi": "fuzi_evolution"}


@pytest.mark.parametrize("race,project", EVOLUTIONS.items())
def test_an_evolution_is_only_for_its_race_needs_no_capstone_and_is_the_most_expensive_kind_of_project(race, project):
    assert uas.project_locked_reason({"race": race}, project) is None
    assert "requires" not in uas.PROJECTS[project]
    other = next(r for r in uas.RACES if r != race)
    assert uas.project_locked_reason({"race": other}, project) is not None
    points = uas.PROJECTS_FUNCS[project](0)
    assert all(points > uas.PROJECTS_FUNCS[key](0) for key in uas.ONE_TIME_PROJECTS if not key.endswith("_evolution"))


def test_gaian_evolution_halves_the_hangar_space_of_pure_attackers():
    units = {"elite_attack": 100, "attack": 100, "defense": 100, "flex": 100}
    plain = kingdoms.kingdom(race="Gaian")
    evolved = kingdoms.kingdom(race="Gaian", completed_projects=["gaian_evolution"])
    half = uas.GAME_CONFIG["GAIAN_EVOLUTION_ATTACK_HANGAR_MULTIPLIER"]
    assert _hangar_used(plain, units) == 400
    assert _hangar_used(evolved, units) == pytest.approx(200 * half + 200)


def test_xo_evolution_makes_settling_cheaper():
    plain = uag._get_settle_price(kingdoms.kingdom(), False)
    evolved = uag._get_settle_price(kingdoms.kingdom(completed_projects=["xo_evolution"]), False)
    assert evolved == pytest.approx(plain * (1 - uas.GAME_CONFIG["XO_EVOLUTION_SETTLE_COST_REDUCTION"]))


def test_xo_evolution_pays_for_each_open_hangar_space(app):
    setup = {"structures": {"hangars": 100}, "units": {"attack": 1000}}
    plain = kingdoms.income(app, kingdoms.kingdom(**setup))
    evolved = kingdoms.income(app, kingdoms.kingdom(**setup, completed_projects=["xo_evolution"]))
    open_space = 100 * uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"] - 1000
    expected = open_space * uas.GAME_CONFIG["XO_EVOLUTION_MONEY_PER_OPEN_HANGAR_SPACE"]
    assert plain["income"]["money"]["open_hangars"] == 0
    assert evolved["income"]["money"]["open_hangars"] == pytest.approx(expected)
    assert evolved["money"] - plain["money"] == pytest.approx(expected)


def test_xo_evolution_pays_nothing_for_full_hangars(app):
    evolved = kingdoms.income(app, kingdoms.kingdom(structures={"hangars": 10}, units={"attack": 5000},
                                                    completed_projects=["xo_evolution"]))
    assert evolved["income"]["money"]["open_hangars"] == 0


def _vult_spies(client, jwt, operation, completed):
    from tests.test_concurrency import _create_item
    _set_up_two_kingdoms()
    kd = _get(f"/kingdom/{KD_ID}")
    kd.pop("_etag", None)
    kd.update({"race": "Vult", "drones": 100000, "completed_projects": completed})
    _create_item(f"kingdom_{KD_ID}", kd)
    return client.post(f"/api/spy/{TARGET_ID}", json={"drones": 100000, "shielded": False, "operation": operation},
                       headers={"Authorization": f"Bearer {jwt}"})


def test_full_infiltration_needs_vult_evolution(app, client, jwt1):
    response = _vult_spies(client, jwt1, "spyall", ["vult_capstone"])
    assert response.status_code == 400
    assert response.get_json()["message"] == "Complete the Vult Evolution: Full Infiltration project to use Full Infiltration"
    assert _get(f"/kingdom/{KD_ID}")["drones"] == 100000  # nothing spent


def test_full_infiltration_reveals_everything_about_the_target(app, client, jwt1):
    response = _vult_spies(client, jwt1, "spyall", ["vult_capstone", "vult_evolution"])
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["status"] == "success"
    revealed = _get(f"/kingdom/{KD_ID}/revealed")["revealed"][TARGET_ID]
    assert set(revealed) == set(uas.REVEAL_OPERATION_STATS["spyall"])
    with app.app_context():
        target = uag._get_max_kd_info(TARGET_ID, KD_ID, _get(f"/kingdom/{KD_ID}/revealed"))
    for field in ("units", "structures", "shields", "projects_points", "drones", "money"):
        assert field in target, field


def test_full_infiltration_replaces_the_single_intel_operations_on_the_pages():
    replaced = uas.OPERATIONS_REPLACED_BY_PROJECT["vult_evolution"]
    assert set(replaced) == set(uas.REVEAL_OPERATIONS) - {"spyall"}
    assert set().union(*(uas.REVEAL_OPERATION_STATS[op] for op in replaced)) == set(uas.REVEAL_OPERATION_STATS["spyall"])


def _lumina(completed):
    from tests.test_concurrency import _create_item
    _set_up_two_kingdoms()
    kd = _get(f"/kingdom/{KD_ID}")
    kd.pop("_etag", None)
    kd.update({"race": "Lumina", "last_income": NOW.isoformat(), "completed_projects": completed})
    _create_item(f"kingdom_{KD_ID}", kd)


def test_lumina_evolution_reveals_every_other_galaxy_and_renews_it(app):
    import untitledapp.refresh as refresh
    _lumina(["lumina_capstone", "lumina_evolution"])
    later = NOW + datetime.timedelta(minutes=1)
    with app.app_context():
        refresh._refresh_kd(KD_ID, _get("/state"), later, False)
    revealed = _get(f"/kingdom/{KD_ID}/revealed")
    duration = datetime.timedelta(seconds=uas.GAME_CONFIG["BASE_EPOCH_SECONDS"] * uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"])
    assert set(revealed["galaxies"]) == {"2"}  # every galaxy but its own
    assert revealed["revealed"][TARGET_ID]["stats"] == (later + 2 * duration).isoformat()
    assert _get(f"/kingdom/{KD_ID}")["next_resolve"]["galaxies_revealed"] == (later + duration).isoformat()


def test_without_lumina_evolution_the_refresh_reveals_nothing(app):
    import untitledapp.refresh as refresh
    _lumina(["lumina_capstone"])
    with app.app_context():
        refresh._refresh_kd(KD_ID, _get("/state"), NOW + datetime.timedelta(minutes=1), False)
    assert _get(f"/kingdom/{KD_ID}/revealed")["galaxies"] == {}
    assert "galaxies_revealed" not in _get(f"/kingdom/{KD_ID}")["next_resolve"]


def test_lumina_evolution_does_more_drone_damage_at_war_only():
    evolved = kingdoms.kingdom(race="Lumina", completed_projects=["lumina_capstone", "lumina_evolution"])
    target = kingdoms.kingdom()
    assert uac._aggro_damage_multiplier(evolved, target, war=False) == 1
    assert uac._aggro_damage_multiplier(evolved, target, war=True) == pytest.approx(
        1 + uas.GAME_CONFIG["LUMINA_EVOLUTION_WAR_DRONE_DAMAGE_INCREASE"])


def test_fuzi_evolution_counts_the_silos_with_no_missiles():
    # A Fuzi silo holds two of each missile, so 30 of one missile fill 15 silos.
    kd = kingdoms.kingdom(race="Fuzi", structures={"missile_silos": 100}, missiles={"planet_busters": 30, "star_busters": 4})
    assert uag._empty_missile_silos(kd) == 85
    assert uag._empty_missile_silos(kingdoms.kingdom(race="Fuzi")) == 0


def test_fuzi_evolution_makes_empty_silos_produce_and_house_people(app):
    import untitledapp.refresh as refresh
    setup = {"race": "Fuzi", "structures": {"missile_silos": 100, "homes": 100}, "missiles": {"planet_busters": 30}}
    plain_kd = kingdoms.kingdom(**setup)
    evolved_kd = kingdoms.kingdom(**setup, completed_projects=["fuzi_capstone", "fuzi_evolution"])
    plain, evolved = kingdoms.income(app, plain_kd), kingdoms.income(app, evolved_kd)
    empty = 85
    assert evolved["income"]["money"]["empty_silos"] == empty * uas.GAME_CONFIG["FUZI_EVOLUTION_MONEY_PER_EMPTY_SILO"]
    assert evolved["income"]["fuel"]["net"] - plain["income"]["fuel"]["net"] == pytest.approx(
        empty * uas.GAME_CONFIG["FUZI_EVOLUTION_FUEL_PER_EMPTY_SILO"])
    assert evolved["income"]["drones"] - plain["income"]["drones"] == pytest.approx(
        empty * uas.GAME_CONFIG["FUZI_EVOLUTION_DRONES_PER_EMPTY_SILO"])
    _, plain_cap = refresh._calc_pop_change_per_epoch(plain_kd, False, 1, [])
    _, evolved_cap = refresh._calc_pop_change_per_epoch(evolved_kd, False, 1, [])
    assert evolved_cap - plain_cap == empty * uas.GAME_CONFIG["FUZI_EVOLUTION_POP_PER_EMPTY_SILO"]


def test_fuzi_evolution_empty_silos_store_fuel(app):
    setup = {"race": "Fuzi", "structures": {"missile_silos": 100}, "fuel": 1_000_000}
    plain = kingdoms.income(app, kingdoms.kingdom(**setup))
    evolved = kingdoms.income(app, kingdoms.kingdom(**setup, completed_projects=["fuzi_capstone", "fuzi_evolution"]))
    assert plain["fuel"] == 0  # no fuel plants, so no storage
    assert evolved["fuel"] == 100 * uas.GAME_CONFIG["FUZI_EVOLUTION_FUEL_STORAGE_PER_EMPTY_SILO"]
