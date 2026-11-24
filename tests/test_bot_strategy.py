"""The sums a bot does before deciding (botstrategy.py): plain functions, tried on made-up kingdoms."""
import copy
import datetime

import pytest

import untitledapp.botstrategy as strategy
import untitledapp.shared as uas

START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
DAY = datetime.timedelta(days=1)


def kingdom(**changes):
    """A set-up kingdom: 300 stars, all built on, an army and some engineers."""
    kd = copy.deepcopy(uas.INITIAL_KINGDOM_STATE["kingdom"])
    kd.update({
        "kdId": "1", "race": "Gaian", "population": 5000, "money": 0,
        "units": {"attack": 400, "defense": 1000, "flex": 0, "big_flex": 0, "recruits": 200, "engineers": 600},
        "structures": {"homes": 110, "mines": 97, "fuel_plants": 30, "hangars": 32, "drone_factories": 15,
                       "missile_silos": 0, "workshops": 16},
    })
    kd.update(changes)
    return kd


# ------------------------------------------------------------------------------------------------------- the round

@pytest.mark.parametrize("day, expected", [(0, "early"), (2, "early"), (3.1, "mid"), (6.9, "mid"), (7.1, "late"), (10, "late"), (12, "late")])
def test_the_round_has_three_phases(day, expected):
    progress = strategy.round_progress(START + day * DAY, START, START + 10 * DAY)
    assert strategy.phase(progress) == expected


def test_progress_stays_between_the_start_and_the_end():
    assert strategy.round_progress(START - DAY, START, START + DAY) == 0.0
    assert strategy.round_progress(START + 5 * DAY, START, START + DAY) == 1.0
    assert strategy.round_progress(START, START, START) == 1.0  # a round with no length is over


# ------------------------------------------------------------------------------------------------------- targets

def test_deterrence_is_where_a_kingdom_and_primitives_pay_the_same():
    """At exactly the deterrence line, the best-placed attacker (at war with us) gains the same stars either way."""
    for epochs in (0, 48, 336):
        stars = 1000
        defense = stars * strategy.deterrence_per_star(epochs)
        assert strategy.player_edge(stars, defense, epochs, "Gaian", war=True) == pytest.approx(1.0)
        # An Xo gains a fifth more from kingdoms and from primitives alike, so war helps it relatively less.
        assert strategy.player_edge(stars, defense, epochs, "Xo", war=True) == pytest.approx(1.4 / 1.2 / 1.2)
        assert strategy.player_edge(stars, defense, epochs, "Gaian") < 1
        assert strategy.player_edge(stars, defense * 0.5, epochs, "Gaian") > 1


def test_primitives_get_harder_so_kingdoms_get_more_attractive_as_the_round_goes_on():
    early = strategy.player_edge(1000, 50_000, 0, "Xo")
    late = strategy.player_edge(1000, 50_000, 24 * 30, "Xo")
    assert early < 1 < late


def test_a_tiny_kingdom_still_gives_the_minimum_stars():
    assert strategy.player_edge(10, 1000, 0, "Gaian") == pytest.approx(25 / (1000 / 100))


def test_spy_chance_matches_the_spy_page():
    assert strategy.spy_chance(1000, 1000, 250) == pytest.approx(0.5)       # 1000 against 1000 + 4 * 250
    assert strategy.spy_chance(10, 1000, 250) == pytest.approx(0.10)        # never below the minimum
    assert strategy.spy_chance(10 ** 6, 1000, 250, 0.2) == pytest.approx(0.8)  # shields take their share
    assert strategy.drones_for_chance(0.5, 1000, 250) == 1000


def test_a_siphon_is_capped_by_what_the_target_earns():
    assert strategy.siphon_take(100, 10 ** 9) == 800
    assert strategy.siphon_take(10 ** 9, 1000) == pytest.approx(1000 * 0.15 * 12)


def test_networth_beyond_land_is_read_as_army():
    assert strategy.military_networth(50 * 300, 300) == 0
    assert strategy.guess_defense(50 * 300 + 8 * 1000, 300) == pytest.approx(1000 * 5 * 1.35)


# ------------------------------------------------------------------------------------------------------- spending

ORDER = ["structures", "settle", "military", "engineers"]


def test_spending_never_exceeds_income_and_reserves_what_is_asked():
    kd = kingdom()
    shares, _ = strategy.spending_plan(kd, 20_000, ORDER, 1.0, 0.5, 500)
    assert 0 < sum(shares.values()) <= 1.0
    assert all(0 <= share <= 1 for share in shares.values())
    kept, _ = strategy.spending_plan(kd, 20_000, ORDER, 1.0, 0.5, 500, reserve=0.3)
    assert sum(kept.values()) <= 0.7 + 1e-9


def test_a_category_that_can_not_spend_is_not_funded():
    """The baseline bots piled up millions in categories that were capped. Funding already waiting counts against the ask."""
    kd = kingdom()
    full = strategy.spending_plan(kd, 20_000, ORDER, 1.0, 0.1, 0)[0]
    assert full["settle"] > 0
    kd["funding"]["settle"] = 500_000
    assert strategy.spending_plan(kd, 20_000, ORDER, 1.0, 0.1, 0)[0]["settle"] == 0
    # No workshop room: no engineers money.
    kd["units"]["engineers"] = 16 * 50
    assert strategy.spending_plan(kd, 20_000, ORDER, 1.0, 0.1, 0)[0]["engineers"] == 0
    # Not settling: no settle money.
    assert strategy.spending_plan(kingdom(), 20_000, ORDER, 0.0, 0.1, 0)[0]["settle"] == 0


def test_the_most_urgent_category_is_served_first_when_money_is_short():
    kd = kingdom(structures={"homes": 50, "mines": 50, "fuel_plants": 30, "hangars": 32, "drone_factories": 0,
                             "missile_silos": 0, "workshops": 16})  # 122 empty stars
    poor = 3_000
    structures_first, _ = strategy.spending_plan(kd, poor, ["structures", "settle", "military", "engineers"], 1.0, 0.5, 2000)
    military_first, _ = strategy.spending_plan(kd, poor, ["military", "structures", "settle", "engineers"], 1.0, 0.5, 2000)
    assert structures_first["structures"] > structures_first["military"]
    assert military_first["military"] > military_first["structures"]


def test_the_army_is_only_funded_as_fast_as_recruits_can_be_drafted():
    kd = kingdom(population=1000)
    shares, _ = strategy.spending_plan(kd, 1_000_000, ORDER, 0.0, 0.9, 100_000)
    recruits_per_epoch = 0.12 * 1000 / 12
    assert shares["military"] * 1_000_000 <= recruits_per_epoch * 450 + 1


def test_settling_stops_paying_as_the_kingdom_grows_and_the_round_runs_out():
    small, big = kingdom(stars=300), kingdom(stars=20_000)
    assert strategy.settle_worth(small, 300, 0.0) > 1
    assert strategy.settle_worth(small, 300, 0.0) > strategy.settle_worth(big, 300, 0.0)
    assert strategy.settle_worth(big, 300, 0.0) > strategy.settle_worth(big, 10, 0.0)
    assert strategy.settle_worth(big, 10, 0.0) < 1
    # Gaians and Expansionist galaxies settle for less, so it pays them for longer.
    assert strategy.settle_worth(small, 300, -0.15) > strategy.settle_worth(kingdom(stars=300, race="Xo"), 300, 0.0)


# ------------------------------------------------------------------------------------------------------- the army

def test_missing_defenders_come_first_then_the_playstyles_mix():
    kd = kingdom()
    target, buy = strategy.army_plan(kd, 450 * 100, 100, offense_share=1.0, offense_mix={"attack": 1.0})
    assert buy["defense"] == pytest.approx(100) and buy["attack"] == 0  # the money ran out on the defenders
    target, buy = strategy.army_plan(kd, 450 * 100 + 400 * 50, 100, offense_share=1.0, offense_mix={"attack": 1.0})
    assert buy["attack"] == pytest.approx(50)
    assert sum(target.values()) <= 1.0 and target["defense"] > target["attack"]


def test_big_flexers_are_only_planned_once_unlocked():
    kd = kingdom()
    mix = {"attack": 0.5, "big_flex": 0.5}
    target, buy = strategy.army_plan(kd, 100_000, 0, 1.0, mix)
    assert buy["big_flex"] == 0 and "big_flex" not in target
    kd["completed_projects"] = ["big_flexers"]
    target, buy = strategy.army_plan(kd, 100_000, 0, 1.0, mix)
    assert buy["big_flex"] > 0 and target["big_flex"] > 0


def test_with_money_to_spare_defense_is_bought_as_flexers_which_need_fewer_recruits():
    kd = kingdom()
    plain_target, plain = strategy.army_plan(kd, 10 ** 9, 1000, 0.0, {"attack": 1.0})
    target, buy = strategy.army_plan(kd, 10 ** 9, 1000, 0.0, {"attack": 1.0}, defender="flex")
    assert plain["defense"] > 1000 and plain["flex"] == 0
    assert buy["defense"] == 0 and buy["flex"] > 1000 and target["flex"] > 0
    # Big flexers only once unlocked: until then, flexers. One big flexer stands in for two defenders.
    assert strategy.army_plan(kd, 10 ** 9, 1000, 0.0, {}, defender="big_flex")[1]["big_flex"] == 0
    kd["completed_projects"] = ["big_flexers"]
    exact = strategy.unit_cost("big_flex") * 500
    assert strategy.army_plan(kd, exact, 1000, 0.0, {}, defender="big_flex")[1]["big_flex"] == pytest.approx(500)


def test_a_kingdom_with_no_army_still_gets_a_target():
    kd = kingdom(units={"attack": 0, "defense": 0, "flex": 0, "big_flex": 0, "recruits": 0, "engineers": 0})
    target, _ = strategy.army_plan(kd, 0, 0, 0.0, {"attack": 1.0})
    assert target == {"defense": 1.0}


# ------------------------------------------------------------------------------------------------------- the land

LAND = {"workshops": 0.06, "drone_factories": 0.05, "missile_silos": 0.0, "homes": 0.55}


def test_the_structures_target_uses_every_star_and_houses_and_fuels_the_army():
    kd = kingdom()
    target = strategy.structures_plan(kd, LAND, {"defense": 0})
    assert 0.99 < sum(target.values()) <= 1.0
    assert set(target) == set(uas.STRUCTURES)
    stars = kd["stars"]
    housed = 400 + 1000 + 200
    assert target["hangars"] * stars * 75 >= housed
    people = target["homes"] * stars * 50
    burn = housed + 600 + people * 0.5
    assert target["fuel_plants"] * stars * 200 * 1.25 >= burn  # with the starting fuel bonus


def test_an_army_on_order_gets_its_hangars_before_it_arrives():
    kd = kingdom()
    now = strategy.structures_plan(kd, LAND, {"defense": 0})
    coming = strategy.structures_plan(kd, LAND, {"defense": 3000})
    assert coming["hangars"] > now["hangars"] and coming["fuel_plants"] > now["fuel_plants"]
    assert coming["homes"] < now["homes"]


def test_units_in_training_get_their_hangars_too():
    """The game's overflow rule counts units in training, so the bots' hangars must too (docs/status.md, Advisors)."""
    kd = kingdom()
    without = strategy.structures_plan(kd, LAND, {"defense": 0})
    training = strategy.structures_plan(kd, LAND, {"defense": 0}, training={"attack": 3000})
    assert training["hangars"] > without["hangars"] and training["fuel_plants"] > without["fuel_plants"]


def test_bigger_hangars_need_fewer_of_them():
    kd = kingdom()
    base = strategy.structures_plan(kd, LAND, {"defense": 3000})
    bigger = strategy.structures_plan(kd, LAND, {"defense": 3000}, per_hangar=150)
    assert bigger["hangars"] < base["hangars"]


def test_an_army_over_its_hangars_gets_hangars_first_on_new_land():
    kd = kingdom(stars=1000, structures={"homes": 300, "mines": 300, "fuel_plants": 100, "hangars": 100,
                                         "drone_factories": 50, "missile_silos": 0, "workshops": 50})
    target = strategy.structures_plan(kd, LAND, {"defense": 0})
    # 100 hangars hold 7,500; the army needs 9,000 after losing land: 20 more hangars before anything else.
    first = strategy.hangars_first(target, kd, held=7500, used=9000, per_hangar=75)
    assert first["hangars"] >= 0.12
    for key in ("homes", "mines", "drone_factories", "workshops", "missile_silos"):
        assert first[key] <= kd["structures"][key] / 1000 + 1e-9, key  # held at what is built: no gap
    assert first["fuel_plants"] == target["fuel_plants"]
    # Within the slack, or housed again: the plan as it was.
    assert strategy.hangars_first(target, kd, held=7500, used=7600, per_hangar=75) == target
    assert strategy.hangars_first(target, kd, held=9000, used=9000, per_hangar=75) == target


def test_an_army_far_too_big_for_the_land_still_leaves_an_economy():
    target = strategy.structures_plan(kingdom(), LAND, {"defense": 500_000})
    assert target["homes"] + target["mines"] >= 0.29


# ------------------------------------------------------------------------------------------------------- projects

WEIGHTS = {"money_bonus": 1.0, "military_bonus": 1.0, "fuel_bonus": 0.5}


def test_engineers_are_all_assigned_and_none_to_what_can_not_be_worked_on():
    kd = kingdom(stars=2000)
    kd["projects_max_points"] = {key: uas.PROJECTS_FUNCS[key](2000) for key in uas.PROJECTS}
    assigned = strategy.projects_plan(kd, {**WEIGHTS, "spy_bonus": 1.0}, ("drone_gadgets",), 0.5)
    assert sum(assigned.values()) == 600
    assert assigned["spy_bonus"] == 0  # locked until drone gadgets are done
    assert assigned["drone_gadgets"] >= 300
    assert assigned["pop_bonus"] == 0  # not asked for


def test_full_bonuses_only_get_upkeep_and_the_unlock_takes_the_rest():
    kd = kingdom()  # 300 stars: every bonus starts above its cap
    assigned = strategy.projects_plan(kd, WEIGHTS, ("big_flexers",), 0.2)
    assert sum(assigned.values()) == 600
    assert assigned["big_flexers"] > 400


def test_a_finished_unlock_frees_its_engineers_for_the_next_one_or_the_bonuses():
    kd = kingdom(completed_projects=["big_flexers"])
    assert strategy.projects_plan(kd, WEIGHTS, ("big_flexers", "star_busters"), 0.2)["star_busters"] > 0
    assigned = strategy.projects_plan(kd, WEIGHTS, ("big_flexers",), 0.2)
    assert assigned["big_flexers"] == 0 and sum(assigned.values()) == 600


def test_no_engineers_no_assignment():
    kd = kingdom()
    kd["units"]["engineers"] = 0
    assert sum(strategy.projects_plan(kd, WEIGHTS, (), 0.5).values()) == 0


# ------------------------------------------------------------------------------------------------------- shields

def test_military_shields_go_up_after_the_early_game_when_there_is_fuel():
    kd = kingdom(fuel=20_000)
    assert strategy.shields_plan(kd, "early", False, False)[0]["military"] == 0
    levels, cost = strategy.shields_plan(kd, "mid", False, False)
    assert levels["military"] == uas.GAME_CONFIG["BASE_MILITARY_SHIELDS_MAX"] and cost == pytest.approx(300)
    assert strategy.shields_plan(kingdom(fuel=0), "late", True, True)[0] == {"military": 0.0, "spy": 0.0, "spy_radar": 0.0, "missiles": 0.0}


def test_other_shields_only_with_a_reason():
    kd = kingdom(fuel=20_000)
    quiet = strategy.shields_plan(kd, "mid", False, False)[0]
    assert quiet["spy"] == 0 and quiet["missiles"] == 0
    alarmed = strategy.shields_plan(kd, "mid", True, True)[0]
    assert alarmed["spy"] > 0 and alarmed["spy_radar"] > 0 and alarmed["missiles"] > 0


def test_intel_on_structures_tells_a_kingdoms_income_better_than_its_stars():
    miner = {"structures": {"mines": 600, "homes": 200}}
    homely = {"structures": {"mines": 100, "homes": 700}, "population": 30_000}
    assert strategy.income_from_intel(miner, 1000) == 600 * 150 + 200 * 50 * 2
    assert strategy.income_from_intel(homely, 1000) == 100 * 150 + 30_000 * 2
    assert strategy.income_from_intel({}, 1000) == strategy.guess_income(1000)


def test_homes_hold_the_people_a_steady_stream_of_recruits_needs():
    # 100 units an epoch, each recruit a dozen epochs in training, at most 12% of the people training: 10,000 people.
    assert strategy.homes_for_people(100, 0) == pytest.approx(100 * 12 / 0.12 / 50)
    # Engineers draw on their own cap, so the larger need sets the homes.
    assert strategy.homes_for_people(0, 10) == pytest.approx(10 * 12 / 0.05 / 50)
    assert strategy.homes_for_people(100, 10) == strategy.homes_for_people(100, 0)


def test_a_bonus_locked_behind_a_project_gets_no_engineers_until_it_is_done():
    kd = kingdom(stars=2000)
    kd["projects_max_points"] = {key: uas.PROJECTS_FUNCS[key](2000) for key in uas.PROJECTS}
    weights = {**WEIGHTS, "general_bonus": 1.0}
    assert strategy.projects_plan(kd, weights, ("casualties_bonus",), 0.5)["general_bonus"] == 0
    kd["completed_projects"] = ["casualties_bonus"]
    assert strategy.projects_plan(kd, weights, ("casualties_bonus",), 0.5)["general_bonus"] > 0


def test_a_key_project_of_another_race_is_skipped_for_the_next_one():
    kd = kingdom()
    assert kd["race"] != "Fuzi"
    assigned = strategy.projects_plan(kd, WEIGHTS, ("fuzi_capstone", "big_flexers"), 0.2)
    assert assigned["fuzi_capstone"] == 0 and assigned["big_flexers"] > 0


# ------------------------------------------------------------------------------------------ being kind to players

def test_a_player_is_hit_three_times_and_then_left_alone():
    pressure = None
    for n in range(strategy.HIT_LIMIT):
        now = START + datetime.timedelta(seconds=n * 60)
        pressure = strategy.reserve_hit(pressure, now)
        assert pressure is not None  # the last one allowed starts the rest
    assert pressure["rest_until"]
    assert strategy.reserve_hit(pressure, now + datetime.timedelta(seconds=60)) is None


def test_the_rest_ends_and_old_hits_are_forgotten():
    rest = strategy.reserve_hit({"hits": [START.isoformat()] * 2}, START)
    after = START + datetime.timedelta(seconds=(strategy.REST_EPOCHS + 1) * strategy.EPOCH)
    fresh = strategy.reserve_hit(rest, after)
    assert fresh == {"hits": [after.isoformat()], "rest_until": ""}
    # Hits older than the window do not count towards the limit.
    old = {"hits": [START.isoformat()] * 2, "rest_until": ""}
    later = START + datetime.timedelta(seconds=(strategy.HIT_WINDOW_EPOCHS + 1) * strategy.EPOCH)
    assert strategy.reserve_hit(old, later)["rest_until"] == ""


# --------------------------------------------------------------------------------------- projects that pay for themselves

def test_projects_that_pay_for_themselves_are_chosen_best_first_and_dropped_when_the_round_runs_out():
    kd = kingdom(stars=1000, structures={"mines": 600, "hangars": 100, "homes": 200},
                 units={"engineers": 3000, "attack": 0, "defense": 0, "flex": 0, "big_flex": 0, "recruits": 0})
    kd["projects_max_points"] = uas.projects_max_points(1000)
    shares = {"military": 0.4, "settle": 0.2}
    early = strategy.economic_projects(kd, 80_000, shares, epochs_left=300)
    assert "mines_bonus" in early and "recruit_cost_bonus" in early
    assert strategy.economic_projects(kd, 80_000, shares, epochs_left=20) == []
    kd["completed_projects"] = ["mines_bonus"]
    assert "mines_bonus" not in strategy.economic_projects(kd, 80_000, shares, epochs_left=300)
