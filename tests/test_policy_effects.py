"""
Every effect a policy can have (shared.EFFECTS), through the function the game charges, credits or times with, so the
forecast on a page and the action agree. A galaxy option, a cluster benefit or a universe policy is only a source of
these effects; these tests are for the effects themselves.
"""
import copy
import datetime

import pytest

import untitledapp.build as uab
import untitledapp.conquer as uac
import untitledapp.getters as uag
import untitledapp.refresh as refresh
import untitledapp.shared as uas
from tests import kingdoms
from tests.test_concurrency import KD_ID, _create_item, _get, _set_up_kingdom

EPOCH = uas.GAME_CONFIG["BASE_EPOCH_SECONDS"]
NOW = datetime.datetime(2026, 1, 1, 12, tzinfo=datetime.timezone.utc)


# --- building ------------------------------------------------------------------------------------------------------------

def test_settle_cost():
    kd = kingdoms.kingdom()
    assert uag._get_settle_price(kd, {"settle_cost": -0.15}) == pytest.approx(uag._get_settle_price(kd) - 0.15 * uas.GAME_FUNCS["BASE_SETTLE_COST"](300))


def test_structure_cost_and_the_page_buy_count_follow_it():
    kd = kingdoms.kingdom(money=1_000_000)
    base = uas.GAME_FUNCS["BASE_STRUCTURE_COST"](300)
    assert uag._get_structure_price(kd) == pytest.approx(base)
    assert uag._get_structure_price(kd, {"structure_cost": -0.15}) == pytest.approx(base * 0.85)


def test_structure_time():
    kd = kingdoms.kingdom()
    plain, _ = uab._get_new_structures({"homes": 80}, NOW, kd)
    faster, _ = uab._get_new_structures({"homes": 80}, NOW, kd, {"structure_time": -0.2})
    plain_times = sorted(uas.utc(entry["time"]) - NOW for entry in plain)
    faster_times = sorted(uas.utc(entry["time"]) - NOW for entry in faster)
    assert [f.total_seconds() for f in faster_times] == pytest.approx([p.total_seconds() * 0.8 for p in plain_times])
    # It stacks with Gaian Terraforming's own cut.
    gaian = kingdoms.kingdom(completed_projects=["gaian_capstone"])
    assert uab._structure_time_multiplier(gaian, {"structure_time": -0.2}) == pytest.approx(
        0.8 * (1 - uas.GAME_CONFIG["GAIAN_CAPSTONE_STRUCTURE_TIME_REDUCTION"]))


def test_raze_return():
    assert uag._raze_return() == uas.GAME_CONFIG["BASE_STRUCTURES_RAZE_RETURN"]
    assert uag._raze_return({"raze_return": 1.0}) == pytest.approx(2 * uas.GAME_CONFIG["BASE_STRUCTURES_RAZE_RETURN"])


def test_engineer_cost_and_how_many_the_page_says_it_can_afford():
    assert uag._engineer_price({"engineer_cost": -0.2}) == pytest.approx(uas.GAME_CONFIG["BASE_ENGINEER_COST"] * 0.8)
    kd = kingdoms.kingdom(money=uas.GAME_CONFIG["BASE_ENGINEER_COST"] * 8, population=100_000)
    _, plain = uag._calc_max_engineers(kd, 0, 10_000)
    _, cheaper = uag._calc_max_engineers(kd, 0, 10_000, {"engineer_cost": -0.2})
    assert (plain, cheaper) == (8, 10)


def test_unit_cost_and_the_pure_unit_discounts():
    state = {"state": {"active_policies": []}}
    plain = uag._get_units_adjusted_costs(state)
    attack = uag._get_units_adjusted_costs(state, {"pure_attack_cost": -0.1})
    defense = uag._get_units_adjusted_costs(state, {"pure_defense_cost": -0.1})
    every = uag._get_units_adjusted_costs(state, {"unit_cost": -0.05, "pure_attack_cost": -0.1})
    for unit in uas.PURE_ATTACK_UNITS:
        assert attack[unit]["cost"] == pytest.approx(plain[unit]["cost"] * 0.9)
        assert defense[unit]["cost"] == pytest.approx(plain[unit]["cost"])
        assert every[unit]["cost"] == pytest.approx(plain[unit]["cost"] * 0.85)
    for unit in uas.PURE_DEFENSE_UNITS:
        assert defense[unit]["cost"] == pytest.approx(plain[unit]["cost"] * 0.9)
        assert attack[unit]["cost"] == pytest.approx(plain[unit]["cost"])
    for unit in ("flex", "big_flex"):
        assert attack[unit]["cost"] == defense[unit]["cost"] == plain[unit]["cost"]


def test_upgrade_cost_is_the_difference_in_price_less_the_discount():
    state = {"state": {"active_policies": []}}
    units = uag._get_units_adjusted_costs(state)
    difference = units["heavy_attack"]["cost"] - units["attack"]["cost"]
    assert uas.upgrade_cost(units, "heavy_attack", {"upgrade_cost": -0.2}) == pytest.approx(difference * 0.8)
    shown = uas.units_for(kingdoms.kingdom(), units, {"upgrade_cost": -0.2})
    assert shown["heavy_attack"]["upgrade_cost"] == pytest.approx(difference * 0.8)
    assert uab._upgrade_cost({"heavy_attack": 10}, units, {"upgrade_cost": -0.2}) == pytest.approx(difference * 8)


def test_missile_cost_stacks_with_the_fuzi_discount():
    xo, fuzi = kingdoms.kingdom(), kingdoms.kingdom(race="Fuzi")
    assert uag._missile_cost_modifier(xo, {"missile_cost": -0.2}) == pytest.approx(0.8)
    assert uag._missile_cost_modifier(fuzi, {"missile_cost": -0.2}) == pytest.approx(
        0.8 - uas.GAME_CONFIG["FUZI_MISSILE_COST_REDUCTION"])


def test_recruit_time():
    assert uag._calc_recruit_time(10, {"recruit_time": -0.2}) == pytest.approx(uag._calc_recruit_time(10) * 0.8)
    plain, _ = uab._get_new_recruits(100, None, NOW)
    faster, _ = uab._get_new_recruits(100, {"recruit_time": -0.2}, NOW)
    assert min(uas.utc(e["time"]) for e in faster) - NOW == (min(uas.utc(e["time"]) for e in plain) - NOW) * 0.8


# --- the economy, through the refresh's income step ---------------------------------------------------------------------

def _income(app, kd, modifiers):
    return kingdoms.income(app, kd, modifiers=modifiers)["income"]


def test_mines_income(app):
    kd = kingdoms.kingdom(structures={"mines": 100}, population=10_000)
    plain, more = _income(app, kd, None), _income(app, kd, {"mines_income": 0.15})
    assert more["money"]["mines"] == pytest.approx(plain["money"]["mines"] * 1.15)
    assert more["money"]["population"] == plain["money"]["population"]


def test_pop_income(app):
    kd = kingdoms.kingdom(population=10_000)
    plain, more = _income(app, kd, None), _income(app, kd, {"pop_income": 0.15})
    assert more["money"]["population"] == pytest.approx(plain["money"]["population"] * 1.15)


def test_fuel_production(app):
    kd = kingdoms.kingdom(structures={"fuel_plants": 50})
    plain, more = _income(app, kd, None), _income(app, kd, {"fuel_production": 0.2})
    produced = 50 * uas.GAME_CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"]
    assert more["fuel"]["net"] - plain["fuel"]["net"] == pytest.approx(produced * 0.2)


def test_unit_fuel(app):
    kd = kingdoms.kingdom(units={"attack": 1000, "defense": 1000})
    plain, less = _income(app, kd, None), _income(app, kd, {"unit_fuel": -0.15})
    assert sum(less["fuel"]["units"].values()) == pytest.approx(sum(plain["fuel"]["units"].values()) * 0.85)


@pytest.mark.parametrize("kind, effect", [
    ("military", "military_shield_fuel"), ("spy", "spy_shield_fuel"), ("spy_radar", "spy_shield_fuel"),
    ("missiles", "missile_shield_fuel"),
])
def test_shield_fuel(app, kind, effect):
    kd = kingdoms.kingdom(shields={"military": 0.1, "spy": 0.2, "spy_radar": 0.2, "missiles": 1.0})
    plain, less = _income(app, kd, None), _income(app, kd, {effect: -0.5})
    assert less["fuel"]["shields"][kind] == pytest.approx(plain["fuel"]["shields"][kind] * 0.5)
    for other in ("military", "spy", "spy_radar", "missiles"):
        if uas.SHIELD_FUEL[other][1] != effect:
            assert less["fuel"]["shields"][other] == plain["fuel"]["shields"][other]
    assert uas.shield_fuel_per_pct(kind, {effect: -0.5}) == pytest.approx(uas.shield_fuel_per_pct(kind) * 0.5)


def test_drone_production(app):
    kd = kingdoms.kingdom(structures={"drone_factories": 100})
    plain, more = _income(app, kd, None), _income(app, kd, {"drone_production": 0.15})
    assert more["drones"] - plain["drones"] == pytest.approx(100 * uas.GAME_CONFIG["BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH"] * 0.15)


@pytest.mark.parametrize("effect, project, other", [
    ("project_points_continuous", "money_bonus", "big_flexers"),
    ("project_points_one_time", "big_flexers", "money_bonus"),
])
def test_project_points_for_each_kind_of_project(app, effect, project, other):
    kd = kingdoms.kingdom(units={"engineers": 200}, projects_assigned={project: 100, other: 100})
    plain = kingdoms.income(app, kd)["projects_points"]
    more = kingdoms.income(app, kd, modifiers={effect: 0.25})["projects_points"]
    assert more[project] == pytest.approx(plain[project] * 1.25)
    assert more[other] == pytest.approx(plain[other])


def test_pop_growth():
    roomy = kingdoms.kingdom(structures={"homes": 1000}, population=100)
    plain, _ = refresh._calc_pop_change_per_epoch(roomy, False, 1, [])
    faster, _ = refresh._calc_pop_change_per_epoch(roomy, False, 1, [], {"pop_growth": 0.5})
    assert faster == pytest.approx(plain * 1.5)
    # It changes how fast people come, not how many fit.
    full = kingdoms.kingdom(structures={"homes": 1}, population=0)
    _, plain_cap = refresh._calc_pop_change_per_epoch(full, False, 1, [])
    _, boom_cap = refresh._calc_pop_change_per_epoch(full, False, 1, [], {"pop_growth": 0.5})
    assert plain_cap == boom_cap


def test_spy_attempt_time():
    kd = kingdoms.kingdom(spy_attempts=0, next_resolve={"spy_attempt": NOW.isoformat()})
    current_bonuses = uas.project_bonuses(kd)

    class Context:
        def __init__(self, modifiers):
            self._modifiers = modifiers

        def modifiers(self, kd_id, time_update):
            return self._modifiers

    _, plain = refresh._resolve_spy(copy.deepcopy(kd), NOW, current_bonuses, Context({}))
    _, faster = refresh._resolve_spy(copy.deepcopy(kd), NOW, current_bonuses, Context({"spy_attempt_time": -0.1}))
    assert (faster - NOW) == (plain - NOW) * 0.9


# --- attacks, spying and primitives -------------------------------------------------------------------------------------

def test_generals_return_time():
    plain = uac._calc_generals_return_time(2, 24, NOW)
    faster = uac._calc_generals_return_time(2, 24, NOW, return_modifier=-0.1)
    assert [(f - NOW) for f in faster] == [(p - NOW) * 0.9 for p in plain]


def test_attacker_losses_and_only_the_attackers():
    kd = kingdoms.kingdom()
    plain_attacker, plain_defender = uac._battle_loss_rates(kd, kingdoms.kingdom())
    fewer_attacker, fewer_defender = uac._battle_loss_rates(kd, kingdoms.kingdom(), attacker_modifiers={"attacker_losses": -0.2})
    assert fewer_attacker == pytest.approx(plain_attacker * 0.8) and fewer_defender == plain_defender
    assert uac._battle_loss_rates(kd, None, attacker_modifiers={"attacker_losses": -0.2})[0] == pytest.approx(plain_attacker * 0.8)


def test_primitives_attack_stars():
    kd = kingdoms.kingdom(race="Gaian")
    assert uac._primitives_stars(10_000, 100, kd) == 100
    assert uac._primitives_stars(10_000, 100, kd, {"primitives_attack_stars": 0.2}) == 120
    xo = kingdoms.kingdom(race="Xo")  # adds to Xo's own gains
    assert uac._primitives_stars(10_000, 100, xo, {"primitives_attack_stars": 0.2}) == int(
        100 * (1.2 + uas.GAME_CONFIG["XO_ATTACK_GAINS_INCREASE"]))


def test_rob_primitives():
    assert uac._rob_per_drone(4.0, {"rob_primitives": 0.2}) == pytest.approx(4.8)
    assert uac._rob_per_drone(4.0) == 4.0


def test_drone_losses_stack_with_drone_gadgets():
    plain = uac._calculate_spy_losses(10_000, False)
    fewer = uac._calculate_spy_losses(10_000, False, modifiers={"drone_losses": -0.25})
    both = uac._calculate_spy_losses(10_000, False, has_drone_gadgets=True, modifiers={"drone_losses": -0.25})
    assert fewer == (int(plain[0] * 0.75), int(plain[1] * 0.75))
    assert both == (int(plain[0] * 0.5), int(plain[1] * 0.5))


def test_siphon_shield_fuel_is_only_for_siphons():
    kd = kingdoms.kingdom()
    plain = uac._shielding_fuel(kd, 1000, "siphonfunds")
    assert uac._shielding_fuel(kd, 1000, "siphonfunds", {"siphon_shield_fuel": -0.25}) == pytest.approx(plain * 0.75)
    assert uac._shielding_fuel(kd, 1000, "spykingdom", {"siphon_shield_fuel": -0.25}) == pytest.approx(plain)
    assert uac._shielding_fuel(kd, 1000, None, {"siphon_shield_fuel": -0.25}) == pytest.approx(plain)


def test_reveal_duration():
    base = uas.GAME_CONFIG["BASE_REVEAL_DURATION_MULTIPLIER"] * EPOCH
    assert uac._reveal_seconds() == base
    assert uac._reveal_seconds({"reveal_duration": 0.25}) == pytest.approx(base * 1.25)


def test_no_effect_drives_a_price_or_a_time_below_nothing():
    kd = kingdoms.kingdom()
    assert uag._get_structure_price(kd, {"structure_cost": -2}) == 0
    assert uag._engineer_price({"engineer_cost": -2}) == 0
    assert uag._calc_recruit_time(10, {"recruit_time": -2}) == 0
    assert uac._reveal_seconds({"reveal_duration": -2}) == 0


# --- through the routes: what the page shows is what the action charges --------------------------------------------------

def _galaxy_with(policy, option):
    """Kingdom 1's galaxy plays ``policy`` with ``option`` active since a tally long ago."""
    state = _get("/state")
    _create_item("state", {"state": {**state["state"], "galaxy_policies": [policy]}})
    _create_item("galaxy_votes_1", {"votes": {"leader": {}}, "policy_active": {policy: option},
                                    "policy_votes": {policy: {KD_ID: option}}, "policy_held": {},
                                    "policy_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()})


def test_an_active_galaxy_policy_prices_the_page_and_the_build_alike(app, client, jwt1):
    price = uas.GAME_FUNCS["BASE_STRUCTURE_COST"](int(uas.INITIAL_KINGDOM_STATE["kingdom"]["stars"])) * 0.85
    _set_up_kingdom(money=price * 10)
    _galaxy_with("industry", "industrialists")
    page = client.get("/api/structures", headers={"Authorization": f"Bearer {jwt1}"}).get_json()
    assert page["price"] == pytest.approx(price) and page["current_available_structures"] == 10
    built = client.post("/api/structures", json={"homes": 10}, headers={"Authorization": f"Bearer {jwt1}"})
    assert built.status_code == 200, built.get_json()
    assert _get(f"/kingdom/{KD_ID}")["money"] == pytest.approx(0, abs=1e-6)


def test_the_shields_page_shows_the_kingdoms_own_fuel_cost(app, client, jwt1):
    _set_up_kingdom(money=0)
    _galaxy_with("shield_doctrine", "fortress")
    desc = client.get("/api/shields", headers={"Authorization": f"Bearer {jwt1}"}).get_json()["desc"]
    assert desc["military"]["cost"] == pytest.approx(uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT"] * 0.75)
    assert desc["spy"]["cost"] == uas.GAME_CONFIG["BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT"]


def test_razing_refunds_the_share_the_page_shows(app, client, jwt1):
    _set_up_kingdom(money=0, structures={**uas.INITIAL_KINGDOM_STATE["kingdom"]["structures"], "homes": 20})
    _galaxy_with("refit_doctrine", "renovators")
    page = client.get("/api/structures", headers={"Authorization": f"Bearer {jwt1}"}).get_json()
    assert page["raze_return"] == pytest.approx(2 * uas.GAME_CONFIG["BASE_STRUCTURES_RAZE_RETURN"])
    razed = client.post("/api/structures/raze", json={"input": {"homes": "10"}}, headers={"Authorization": f"Bearer {jwt1}"})
    assert razed.status_code == 200, razed.get_json()
    assert _get(f"/kingdom/{KD_ID}")["money"] == pytest.approx(10 * page["price"] * page["raze_return"])


def test_the_rob_figure_the_page_shows_is_the_kingdoms_own(app, client, jwt1):
    _set_up_kingdom(money=0)
    _galaxy_with("shadow_doctrine", "plunderers")
    shown = client.get("/api/modifiers", headers={"Authorization": f"Bearer {jwt1}"}).get_json()
    state = client.get("/api/state").get_json()
    assert shown["primitives_rob_per_drone"] == pytest.approx(state["primitives_rob_per_drone"] * 1.2, rel=1e-3)
    assert shown["texts"]["siphon_shield_fuel"] == "Shielding Siphon Funds operations costs 25% less fuel"


def test_the_refresh_credits_income_with_the_galaxys_policies(app):
    _set_up_kingdom(money=0, race="Xo", structures={**uas.INITIAL_KINGDOM_STATE["kingdom"]["structures"], "mines": 100},
                    last_income=(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat())
    _galaxy_with("economy", "mining_guilds")
    with app.app_context():
        context = refresh._RefreshContext(_get("/state"))
        modifiers = context.modifiers(KD_ID, datetime.datetime.now(datetime.timezone.utc))
        assert {effect: value for effect, value in modifiers.items() if value} == {"mines_income": pytest.approx(0.15)}
        refresh._refresh_kd(KD_ID, _get("/state"), datetime.datetime.now(datetime.timezone.utc), False)
    income = _get(f"/kingdom/{KD_ID}")["income"]["money"]
    per_mine = uas.GAME_CONFIG["BASE_MINES_INCOME_PER_EPOCH"] + uas.project_increase(kingdoms.kingdom(), "mines_bonus")
    assert income["mines"] == pytest.approx(100 * per_mine * 1.15)


# --- what only cluster benefits do: capacities, and a few that apply to everything ---------------------------------------

def test_homes_capacity():
    kd = kingdoms.kingdom(structures={"homes": 100}, population=0)
    _, plain = refresh._calc_pop_change_per_epoch(kd, False, 1, [])
    _, roomier = refresh._calc_pop_change_per_epoch(kd, False, 1, [], {"homes_capacity": 0.1})
    assert roomier == pytest.approx(plain * 1.1, abs=1)


def test_hangar_capacity():
    kd = kingdoms.kingdom(structures={"hangars": 100})
    units = {"current_total": {}, "hour_24": {}}
    plain, _ = uag._calc_hangar_capacity(kd, units)
    bigger, _ = uag._calc_hangar_capacity(kd, units, {"hangar_capacity": 0.1})
    assert bigger == int(plain * 1.1)


def test_workshop_capacity():
    kd = kingdoms.kingdom(structures={"workshops": 100}, race="Gaian")
    plain, _ = uag._calc_workshop_capacity(kd, 0)
    bigger, _ = uag._calc_workshop_capacity(kd, 0, {"workshop_capacity": 0.1})
    assert bigger == int(plain * 1.1)


def test_missile_silo_capacity():
    kd = kingdoms.kingdom(structures={"missile_silos": 40})
    assert uag._calc_missile_capacity(kd, {"missile_silo_capacity": 0.25}) == int(uag._calc_missile_capacity(kd) * 1.25)


def test_fuel_storage(app):
    kd = kingdoms.kingdom(structures={"fuel_plants": 10}, fuel=10_000_000)  # far over: it is held at the cap
    plain = kingdoms.income(app, kd)["fuel"]
    more = kingdoms.income(app, kd, modifiers={"fuel_storage": 0.2})["fuel"]
    assert more == pytest.approx(plain * 1.2)


def test_recruit_cap_and_recruit_cost():
    kd = kingdoms.kingdom(population=100_000, money=10_000_000)
    units = {"hour_24": {"recruits": 0}}
    plain_max, _ = uag._calc_max_recruits(kd, units)
    wider_max, _ = uag._calc_max_recruits(kd, units, {"recruit_cap": 0.15})
    assert wider_max == int(plain_max * 1.15)
    assert uag._recruit_price(kd, {"recruit_cost": -0.1}) == pytest.approx(uag._recruit_price(kd) * 0.9)
    poor = kingdoms.kingdom(population=100_000, money=uag._recruit_price(kd) * 100)
    assert uag._calc_max_recruits(poor, units, {"recruit_cost": -0.5})[1] == 200


def test_project_points_on_every_project(app):
    kd = kingdoms.kingdom(units={"engineers": 200}, projects_assigned={"money_bonus": 100, "big_flexers": 100})
    plain = kingdoms.income(app, kd)["projects_points"]
    more = kingdoms.income(app, kd, modifiers={"project_points": 0.1, "project_points_one_time": 0.25})["projects_points"]
    assert more["money_bonus"] == pytest.approx(plain["money_bonus"] * 1.1)
    assert more["big_flexers"] == pytest.approx(plain["big_flexers"] * 1.35)  # they add up


def test_shield_fuel_on_every_kind_of_shield():
    for kind in ("military", "spy", "spy_radar", "missiles"):
        assert uas.shield_fuel_per_pct(kind, {"shield_fuel": -0.15}) == pytest.approx(uas.shield_fuel_per_pct(kind) * 0.85)
    assert uas.shield_fuel_per_pct("military", {"shield_fuel": -0.15, "military_shield_fuel": -0.25}) == pytest.approx(
        uas.shield_fuel_per_pct("military") * 0.6)


def test_a_cluster_benefit_sets_what_the_military_page_shows(app, client, jwt1):
    _set_up_kingdom(money=0, structures={**uas.INITIAL_KINGDOM_STATE["kingdom"]["structures"], "hangars": 100})
    state = _get("/state")
    _create_item("state", {"state": {**state["state"], "cluster_benefits": ["hangar_capacity"]}})
    _create_item("cluster_1", {"levels": {"hangar_capacity": 1.0},
                               "last_update": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    plain = 100 * uas.GAME_CONFIG["BASE_HANGAR_CAPACITY"]
    page = client.get("/api/mobis", headers={"Authorization": f"Bearer {jwt1}"}).get_json()
    # The level has faded a hair since it was written, so within one hangar space of full.
    assert page["max_hangar_capacity"] == pytest.approx(plain * (1 + uas.CLUSTER_BENEFITS["hangar_capacity"]["max"]), abs=1)
