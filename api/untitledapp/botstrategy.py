"""
Bot strategy: the sums a bot does before it decides anything. Plain functions of what the bot can see (its own kingdom
and the numbers in ``shared.py``): no Flask, no storage. ``botbrain.py`` turns the answers into actions.

The ideas, each of which is a rule a player could follow from the Help pages:

* **The round has three phases** (``phase``): early (grow: primitives, cheap settling, the key project), mid (keep
  the bonuses, keep defended), late (military, and the leaders).
* **Nothing sits idle** (``spending_plan``): income is split by what each category can actually use in the coming
  hours. Settling is capped at a tenth of the kingdom, structures at the empty stars, engineers by workshops and
  population, the army by the rate recruits can be drafted. Funding a category beyond that just piles up.
* **Enough defense to not be worth it** (``deterrence_per_star``): an attacker gains a tenth of your stars, or what
  the same army takes from primitives. Primitives get harder all round, so the defense per star that makes you the worse
  deal rises with the square root of time.
* **Build for the army you are paying for** (``structures_plan``): hangars and fuel plants for the units the budget
  will buy, before they arrive. Units without a hangar push people out of their homes.
* **Engineers go where a bonus is slipping** (``projects_plan``): a continuous bonus only needs its points topped up
  as the kingdom grows; the rest of the engineers work on the unlock the playstyle wants.
* **Value a target by stars per point of offense** (``player_edge``): the same army can always hit primitives.

All tunable numbers are in ``botbrain.Personality``; this module only has the game's own.
"""
import math

import untitledapp.shared as uas

CONFIG = uas.GAME_CONFIG
EPOCH = CONFIG["BASE_EPOCH_SECONDS"]
PHASES = ("early", "mid", "late")
EARLY_UNTIL = 0.3   # TUNE: share of the round
MID_UNTIL = 0.7
HORIZON = 12        # epochs a spending plan looks ahead: about how long a build takes to arrive
IDLE_EPOCHS = 3     # funding waiting in a category is counted as spent over this many epochs
COMBAT_UNITS = ("attack", "defense", "flex", "big_flex")
CONTINUOUS_PROJECTS = tuple(key for key in uas.PROJECTS if key not in uas.ONE_TIME_PROJECTS)


def round_progress(now, game_start, game_end):
    """How far through the round ``now`` is, from 0 to 1."""
    length = (game_end - game_start).total_seconds()
    if length <= 0:
        return 1.0
    return min(max((now - game_start).total_seconds() / length, 0.0), 1.0)


def phase(progress):
    if progress < EARLY_UNTIL:
        return "early"
    return "mid" if progress < MID_UNTIL else "late"


def epochs_since(now, game_start):
    return max((now - game_start).total_seconds(), 0.0) / EPOCH


# ------------------------------------------------------------------------------------------------- one's own kingdom

def bonuses(kd):
    """The continuous project bonuses a kingdom has right now."""
    return {
        project: details["max_bonus"] * min(kd["projects_points"][project] / max(kd["projects_max_points"][project], 1e-9), 1.0)
        for project, details in uas.PROJECTS.items() if "max_bonus" in details
    }


def all_units(kd):
    """Units at home plus those out with generals."""
    total = {unit: kd["units"].get(unit, 0) for unit in uas.UNITS}
    for general in kd.get("generals_out", []):
        for unit, count in general.items():
            if unit != "return_time":
                total[unit] = total.get(unit, 0) + count
    return total


def defense_multiplier(kd):
    """What one point of raw defense at home is worth, with the kingdom's military bonus and shields."""
    return (1 + bonuses(kd)["military_bonus"] + kd.get("shields", {}).get("military", 0)
            - (CONFIG["BASE_FUELLESS_STRENGTH_REDUCTION"] if kd.get("fuel", 1) <= 0 else 0))


def raw_defense(units):
    return sum(uas.UNITS[unit]["defense"] * count for unit, count in units.items() if unit in uas.UNITS)


def raw_offense(units):
    return sum(uas.UNITS[unit]["offense"] * count for unit, count in units.items() if unit in uas.UNITS)


def primitives_defense_per_star(epochs):
    return uas.GAME_FUNCS["BASE_PRIMITIVES_DEFENSE_PER_STAR"](epochs * EPOCH)


def rob_per_drone(epochs):
    return uas.GAME_FUNCS["BASE_PRIMITIVES_ROB_PER_DRONE"](epochs * EPOCH)


def gains_multiplier(race, war=False):
    return 1 + (CONFIG["XO_ATTACK_GAINS_INCREASE"] if race == "Xo" else 0) + (CONFIG["WAR_GAINS_INCREASE"] if war else 0)


def deterrence_per_star(epochs):
    """
    The defense per star at which attacking this kingdom pays an attacker no better than sending the same army at
    primitives, in the best case for the attacker: at war with us (an Xo gains more from kingdoms, but as much more
    from primitives, so its race changes nothing). Below this line, a kingdom is the better target.
    """
    return CONFIG["BASE_KINGDOM_LOSS_RATE"] * gains_multiplier(None, war=True) * primitives_defense_per_star(epochs)


def player_edge(target_stars, offense_needed, epochs, race, war=False):
    """
    How many times more stars an attack on a kingdom takes than sending the same offense at primitives. Above 1 the
    kingdom is the better target.
    """
    if offense_needed <= 0:
        return float("inf")
    multiplier = gains_multiplier(race, war)
    stars = max(target_stars * CONFIG["BASE_KINGDOM_LOSS_RATE"] * multiplier, CONFIG["BASE_ATTACK_MIN_STARS_GAIN"] * multiplier)
    from_primitives = offense_needed / primitives_defense_per_star(epochs) * gains_multiplier(race)
    return stars / max(from_primitives, 1e-9)


def spy_chance(drones_sent, target_drones, target_stars, target_shields=0.0):
    """The chance a spy operation works, as the Spy page's forecast has it (without peace)."""
    defense = max(target_drones * CONFIG["BASE_DRONES_DRONE_DEFENSE_MULTIPLIER"]
                  + target_stars * CONFIG["BASE_STARS_DRONE_DEFENSE_MULTIPLIER"], 1)
    return min(max(drones_sent / defense, CONFIG["BASE_SPY_MIN_SUCCESS_CHANCE"]), 1.0) * (1 - target_shields)


def drones_for_chance(chance, target_drones, target_stars):
    """Drones to send for a spy operation to work with this chance (before the target's spy shields)."""
    return math.ceil(chance * (target_drones * CONFIG["BASE_DRONES_DRONE_DEFENSE_MULTIPLIER"]
                               + target_stars * CONFIG["BASE_STARS_DRONE_DEFENSE_MULTIPLIER"]))


def guess_income(stars):
    """A kingdom's gross income per epoch when all that is known is its stars: about a third mines, the rest homes."""
    return stars * (0.33 * CONFIG["BASE_MINES_INCOME_PER_EPOCH"]
                    + 0.4 * CONFIG["BASE_HOMES_CAPACITY"] * CONFIG["BASE_POP_INCOME_PER_EPOCH"])


def siphon_take(drones, target_income):
    """Money a successful siphon brings in over its whole run."""
    return min(drones * CONFIG["BASE_DRONES_SIPHON_PER_DRONE"],
               target_income * CONFIG["BASE_MAX_SIPHON"] * CONFIG["BASE_DRONES_SIPHON_TIME_MULTIPLIER"])


def military_networth(networth, stars):
    """What is left of a kingdom's networth after its land, if every star has a structure: its army, more or less."""
    values = CONFIG["NETWORTH_VALUES"]
    return max(networth - stars * (values["stars"] + values["structures"]), 0)


def guess_defense(networth, stars):
    """The most defense a kingdom could have if all of its networth beyond land were defenders, fully boosted."""
    defenders = military_networth(networth, stars) / CONFIG["NETWORTH_VALUES"]["defense"]
    return defenders * uas.UNITS["defense"]["defense"] * (
        1 + uas.PROJECTS["military_bonus"]["max_bonus"] + CONFIG["BASE_MILITARY_SHIELDS_MAX"])


# ------------------------------------------------------------------------------------------------------- the economy

def settle_price(kd, expansionist):
    return uas.GAME_FUNCS["BASE_SETTLE_COST"](int(kd["stars"])) * (
        1 - (CONFIG["BASE_EXPANSIONIST_SETTLE_REDUCTION"] if expansionist else 0)
        - (CONFIG["GAIAN_SETTLE_COST_REDUCTION"] if kd["race"] == "Gaian" else 0))


def workshop_capacity(kd):
    per_workshop = math.floor(CONFIG["BASE_WORKSHOP_CAPACITY"] * (
        1 - (CONFIG["XO_WORKSHOP_CAPACITY_REDUCTION"] if kd["race"] == "Xo" else 0)))
    return math.floor(kd["structures"]["workshops"]) * per_workshop


def defense_wanted(kd, epochs, margin):
    """Home defense (with bonuses) that makes this kingdom a worse deal than primitives, times the bot's margin."""
    return kd["stars"] * deterrence_per_star(epochs) * margin


def settle_worth(kd, epochs_left, expansionist, income_per_star=None):
    """
    Whether one more settled star still pays: the networth of the star and its structure, plus the networth its income
    buys as units before the round ends, per unit of money, against simply buying units with the money. Above 1,
    settling is the better use. Land gets dearer as a kingdom grows and the round runs out, so this falls with both.
    """
    values = CONFIG["NETWORTH_VALUES"]
    unit_value = values["attack"] / unit_cost("attack")
    if income_per_star is None:
        income_per_star = guess_income(1)
    cost = settle_price(kd, expansionist) + uas.GAME_FUNCS["BASE_STRUCTURE_COST"](int(kd["stars"]))
    earning_epochs = max(epochs_left - HORIZON * 1.5, 0)  # it has to be settled and built on first
    worth = values["stars"] + values["structures"] + income_per_star * earning_epochs * unit_value
    return worth / max(cost, 1) / unit_value


def unit_cost(unit, cost_modifier=1.0):
    return uas.UNITS[unit]["cost"] * cost_modifier + CONFIG["BASE_RECRUIT_COST"]


def spending_plan(kd, income, order, settle_drive, military_drive, defense_deficit_units, expansionist=False,
                  growth_per_epoch=0.012, reserve=0.0, cost_modifier=1.0):
    """
    Split ``income`` (money per epoch) over the four auto spending categories by what each can use.

    ``order`` is the categories from most to least urgent; each takes what it can use, in turn, from what is left.
    ``settle_drive`` is the share of the settling cap to fill (1: settle as fast as allowed), ``military_drive`` the
    share of income the army may take on top of closing ``defense_deficit_units``. Funding already waiting in a category
    counts against what it asks for, so a category that can not spend is starved until it can. ``reserve`` is a share of
    income to leave as money (for missiles and votes). Returns ``(shares, wants)``.
    """
    stars = max(kd["stars"], 1)
    income = max(income, 1.0)
    funding = kd.get("funding", {})
    population = max(kd.get("population", 0), 0)
    structure_price = uas.GAME_FUNCS["BASE_STRUCTURE_COST"](int(stars))
    empty = max(stars - sum(kd["structures"].values()), 0)
    settle_time = (CONFIG["BASE_SETTLE_TIME_MIN_MULTIPLIER"] + CONFIG["BASE_SETTLE_TIME_MAX_MUTLIPLIER"]) / 2
    recruit_time = (CONFIG["BASE_RECRUIT_TIME_MIN_MULTIPLIER"] + CONFIG["BASE_RECRUIT_TIME_MAX_MUTLIPLIER"]) / 2
    engineer_time = (CONFIG["BASE_ENGINEER_TIME_MIN_MULTIPLIER"] + CONFIG["BASE_ENGINEER_TIME_MAX_MUTLIPLIER"]) / 2

    settle_rate = CONFIG["BASE_MAX_SETTLE_CAP"] * stars / settle_time  # stars per epoch with the queue kept full
    engineer_room = max(workshop_capacity(kd) - kd["units"].get("engineers", 0), 0)
    engineer_rate = min(engineer_room / HORIZON, CONFIG["BASE_MAX_ENGINEERS_POP_CAP"] * population / engineer_time)
    recruit_rate = CONFIG["BASE_MAX_RECRUITS_CAP"] * population / recruit_time
    average_unit = (unit_cost("attack", cost_modifier) + unit_cost("defense", cost_modifier)) / 2
    # Stars with nothing on them yet, less those that are (probably) being built on: a structure takes some epochs.
    build_time = (CONFIG["BASE_STRUCTURE_TIME_MIN_MULTIPLIER"] + CONFIG["BASE_STRUCTURE_TIME_MAX_MUTLIPLIER"]) / 2
    backlog = max(empty - stars * growth_per_epoch * build_time, 0)
    wants = {
        "settle": settle_drive * settle_rate * settle_price(kd, expansionist) * 1.1,
        "structures": structure_price * (backlog / 4 + stars * growth_per_epoch * 1.15),
        "engineers": CONFIG["BASE_ENGINEER_COST"] * engineer_rate,
        "military": min(defense_deficit_units * unit_cost("defense", cost_modifier) / HORIZON + military_drive * income,
                        recruit_rate * average_unit),
    }
    # Money already set aside is spent first: what waits in a category comes off what it asks for, quickly, so a
    # category that can not spend what it has gets nothing more until it can.
    wants = {key: max(want - funding.get(key, 0) / IDLE_EPOCHS, 0.0) for key, want in wants.items()}

    left = income * (1 - reserve)
    shares = {key: 0.0 for key in ("settle", "structures", "military", "engineers")}
    for key in order:
        take = min(wants[key], left)
        shares[key] = take / income
        left -= take
    if left > 0:
        # Everything that can be used is funded. More army is the one thing that is never useless: until the drafting
        # rate is reached it takes the rest; what even that can not use stays as money.
        room = max(recruit_rate * average_unit - funding.get("military", 0) / IDLE_EPOCHS - shares["military"] * income, 0)
        shares["military"] += min(left, room) / income
    shares = {key: math.floor(share * 1000) / 1000 for key, share in shares.items()}
    return shares, wants


def army_plan(kd, military_money, defense_deficit_units, offense_share, offense_mix, cost_modifier=1.0,
              defender="defense"):
    """
    What ``military_money`` (over the horizon) should become: first the defense still missing, then offense and more
    defense in the bot's proportions. Returns ``(units_target, units_to_buy)``: the auto builder's shares of the army,
    and the number of units the money buys (which is also how many recruits are worth having).

    ``defender`` is the unit bought for defense. Defenders are the cheapest defense for the money; flexers and big
    flexers give two and four times the strength for each recruit and hangar place, which is what counts for a kingdom
    with money left over and no more people to draft. ``defense_deficit_units`` is in defenders either way.
    """
    units = all_units(kd)
    buy = {unit: 0.0 for unit in COMBAT_UNITS}
    money = max(military_money, 0.0)
    if defender == "big_flex" and "big_flexers" not in kd.get("completed_projects", []):
        defender = "flex"
    per_defender = uas.UNITS["defense"]["defense"] / uas.UNITS[defender]["defense"]
    defenders = min(defense_deficit_units * per_defender, money / unit_cost(defender, cost_modifier))
    buy[defender] += defenders
    money -= defenders * unit_cost(defender, cost_modifier)
    mix = {unit: weight for unit, weight in offense_mix.items()
           if weight > 0 and (unit != "big_flex" or "big_flexers" in kd.get("completed_projects", []))}
    total_weight = sum(mix.values())
    if total_weight > 0 and offense_share > 0:
        for unit, weight in mix.items():
            buy[unit] += money * offense_share * weight / total_weight / unit_cost(unit, cost_modifier)
        money *= (1 - offense_share)
    buy[defender] += money / unit_cost(defender, cost_modifier)

    wanted = {unit: units.get(unit, 0) + buy[unit] for unit in COMBAT_UNITS}
    total = sum(wanted.values())
    if total <= 0:
        return {"defense": 1.0}, buy
    target = {unit: math.floor(count / total * 10000) / 10000 for unit, count in wanted.items() if count > 0}
    return target, buy


def structures_plan(kd, shares, units_to_buy, shields_fuel=0.0):
    """
    The structures target (shares of all stars). ``shares`` gives the playstyle's ``workshops``, ``drone_factories``
    and ``missile_silos`` as shares of the kingdom and ``homes`` as the share of what is left over that is homes (the
    rest is mines). Hangars and fuel plants are sized for the army as it will be once ``units_to_buy`` have arrived.
    """
    stars = max(kd["stars"], 1)
    units = all_units(kd)
    housed = sum(count * uas.UNITS[unit]["hangar_capacity"] for unit, count in units.items())
    housed += sum(count * uas.UNITS[unit]["hangar_capacity"] for unit, count in units_to_buy.items())
    hangars = housed * 1.1 / CONFIG["BASE_HANGAR_CAPACITY"]

    fixed = {
        "workshops": shares.get("workshops", 0) * stars,
        "drone_factories": shares.get("drone_factories", 0) * stars,
        "missile_silos": shares.get("missile_silos", 0) * stars,
        "hangars": hangars,
    }
    engineers = max(units.get("engineers", 0), workshop_capacity(kd), fixed["workshops"] * CONFIG["BASE_WORKSHOP_CAPACITY"] * 0.8)
    fed = sum(count * uas.UNITS[unit]["fuel"] for unit, count in units.items() if unit != "engineers")
    fed += sum(count * uas.UNITS[unit]["fuel"] for unit, count in units_to_buy.items()) + engineers
    plant_output = CONFIG["BASE_FUEL_PLANTS_INCOME_PER_EPOCH"] * (
        1 + bonuses(kd)["fuel_bonus"] + (CONFIG["LUMINA_FUEL_PRODUCTION_INCREASE"] if kd["race"] == "Lumina" else 0))
    # People burn fuel too, and how many there are depends on the homes, which depend on what is left: solve for it.
    homes_share = shares.get("homes", 0.5)
    people_per_home = CONFIG["BASE_HOMES_CAPACITY"] * (1 - (CONFIG["VULT_POPULATION_REDUCTION"] if kd["race"] == "Vult" else 0))
    burn_per_home = people_per_home * CONFIG["BASE_POP_FUEL_CONSUMPTION_PER_EPOCH"]
    other = sum(fixed.values())
    margin = 1.15
    # plants * output = margin * (fed + shields + homes * burn), homes = homes_share * (stars - other - plants)
    plants = margin * (fed + shields_fuel + homes_share * (stars - other) * burn_per_home) / (
        plant_output + margin * homes_share * burn_per_home)
    fixed["fuel_plants"] = max(plants, 0.04 * stars)

    total_fixed = sum(fixed.values())
    if total_fixed > 0.7 * stars:  # an army far too big for the land: keep an economy all the same
        scale = 0.7 * stars / total_fixed
        fixed = {key: value * scale for key, value in fixed.items()}
        total_fixed = 0.7 * stars
    left = stars - total_fixed
    fixed["homes"] = left * homes_share
    fixed["mines"] = left - fixed["homes"]
    target = {key: math.floor(fixed.get(key, 0) / stars * 10000) / 10000 for key in uas.STRUCTURES}
    return target


def projects_plan(kd, weights, key_projects, key_share, growth_per_epoch=0.012):
    """
    How many engineers work on each project. A continuous bonus gets what keeps it full as the kingdom grows (its cap
    rises with stars) plus a share of the catching up, weighted by how much the playstyle cares; ``key_share`` of the
    engineers are kept for the first unfinished one-time project in ``key_projects``, which also takes whatever the
    bonuses do not need. Returns ``{project: engineers}`` for every project.
    """
    engineers = int(kd["units"].get("engineers", 0))
    assigned = {project: 0 for project in uas.PROJECTS}
    if engineers <= 0:
        return assigned
    completed = kd.get("completed_projects", [])
    key = next((project for project in key_projects if project not in completed), None)
    needs = {}
    for project in CONTINUOUS_PROJECTS:
        weight = weights.get(project, 0)
        if weight <= 0 or (project == "spy_bonus" and "drone_gadgets" not in completed):
            continue
        cap = kd["projects_max_points"][project]
        gap = max(cap - kd["projects_points"][project], 0)
        upkeep = uas.PROJECTS[project]["stars_power"] * cap * growth_per_epoch
        needs[project] = weight * (upkeep + gap / HORIZON)
    for_key = math.floor(engineers * key_share) if key else 0
    pool = engineers - for_key
    total_need = sum(needs.values())
    if total_need > 0:
        scale = min(pool / total_need, 1.0 if key else pool / total_need)
        for project, need in needs.items():
            assigned[project] = math.floor(need * scale)
    spare = engineers - sum(assigned.values())
    if key:
        assigned[key] += spare
    elif needs:
        assigned[max(needs, key=needs.get)] += spare
    return assigned


def shields_plan(kd, phase_name, wants_spy_shields, under_missiles):
    """
    Shield levels, as the guide has it: military shields at their maximum whenever the fuel is there, the others when
    there is a reason. Returns ``(shields, fuel_per_epoch)``.
    """
    stars = kd["stars"]
    fuel_ok = kd.get("fuel", 0) > 0.05 * max(kd["structures"].get("fuel_plants", 0), 1) * CONFIG["BASE_FUEL_PLANTS_CAPACITY"]
    income_ok = kd.get("income", {}).get("fuel", {}).get("net", 1) > -0.02 * max(kd.get("fuel", 0), 1)
    levels = {"military": 0.0, "spy": 0.0, "spy_radar": 0.0, "missiles": 0.0}
    if fuel_ok and income_ok:
        if phase_name != "early":
            levels["military"] = CONFIG["BASE_MILITARY_SHIELDS_MAX"]
        if wants_spy_shields:
            levels["spy"] = CONFIG["BASE_SPY_SHIELDS_MAX"] / 2
            levels["spy_radar"] = CONFIG["BASE_SPY_RADAR_MAX"] / 2
        if under_missiles:
            levels["missiles"] = CONFIG["FUZI_MISSILE_SHIELDS_MAX"]
    cost = stars * 100 * (
        levels["military"] * CONFIG["BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT"]
        + levels["spy"] * CONFIG["BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT"]
        + levels["spy_radar"] * CONFIG["BASE_SPY_RADAR_COST_PER_LAND_PER_PCT"]
        + levels["missiles"] * CONFIG["BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT"])
    return levels, cost
