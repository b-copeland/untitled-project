/**
 * What a starting kingdom would look like: the numbers shown beside the choices on the Create Kingdom page.
 * ``state`` is the game's rules (``api/state``); ``units`` and ``structures`` map names to amounts (numbers or the text
 * typed into a box).
 */
export function kingdomStats(state, units, structures) {
    const rules = state.structures || {};
    const unitRules = state.units || {};
    const count = (amounts, name) => Number(amounts[name]) || 0;
    const fromUnits = (field) => Object.keys(units).reduce((total, unit) => total + (unitRules[unit]?.[field] || 0) * count(units, unit), 0);

    const population = count(structures, "homes") * (rules.pop_per_home || 0);
    return {
        offense: fromUnits("offense"),
        defense: fromUnits("defense"),
        population,
        income: population * (state.income_per_pop || 0) + count(structures, "mines") * (rules.income_per_mine || 0),
        fuelProduction: count(structures, "fuel_plants") * (rules.fuel_per_fuel_plant || 0),
        fuelUsage: fromUnits("fuel") + population * (state.fuel_consumption_per_pop || 0),
        fuelCapacity: count(structures, "fuel_plants") * (rules.fuel_cap_per_fuel_plant || 0),
        hangarUsed: fromUnits("hangar_capacity"),
        hangarCapacity: count(structures, "hangars") * (rules.hangar_capacity || 0),
        dronesPerTick: count(structures, "drone_factories") * (rules.drone_production_per_drone_plant || 0),
        missileCapacity: count(structures, "missile_silos") * (rules.missile_capacity_per_missile_silo || 0),
        engineers: count(units, "engineers"),
        workshopCapacity: count(structures, "workshops") * (rules.engineers_capacity_per_workshop || 0),
    };
}

/** The points and stars a choice leaves unspent (negative when over), and the reason it can't be sent yet, or null. */
export function checkChoices({ units, structures, race }, { selection_points, total_points, total_stars }) {
    const pointsLeft = total_points - Object.keys(selection_points).reduce((sum, unit) => sum + (Number(units[unit]) || 0) * selection_points[unit], 0);
    const starsLeft = total_stars - Object.values(structures).reduce((sum, amount) => sum + (Number(amount) || 0), 0);
    let blocked = null;
    if (pointsLeft > 0) blocked = `Spend all ${total_points.toLocaleString()} unit points (${pointsLeft.toLocaleString()} left)`;
    else if (pointsLeft < 0) blocked = `${(-pointsLeft).toLocaleString()} unit points over`;
    else if (starsLeft > 0) blocked = `Place all ${total_stars} stars (${starsLeft} left)`;
    else if (starsLeft < 0) blocked = `${-starsLeft} stars over`;
    else if (!race) blocked = "Choose a race";
    return { pointsLeft, starsLeft, blocked };
}
