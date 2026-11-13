import { displayPercent } from "./format";

/**
 * What each race is good and bad at, as lines of text, from the numbers in the game's config (``state.game_config``), so
 * the Create Kingdom page and the help page always agree with the rules.
 */
export function raceDescriptions(config = {}) {
    const pct = (key) => displayPercent(config[key] || 0);
    return {
        Gaian: {
            pros: [`Settle Cost -${pct("GAIAN_SETTLE_COST_REDUCTION")}`, `Settle Time -${pct("GAIAN_SETTLE_TIME_REDUCTION")}`],
            cons: [`Defense -${pct("GAIAN_DEFENSE_REDUCTION")}`],
        },
        Vult: {
            pros: [`Drone Production +${pct("VULT_DRONE_PRODUCTION_INCREASE")}`, "Aggressive spy operations ignore spy shields and spy radar"],
            cons: [`Population -${pct("VULT_POPULATION_REDUCTION")}`],
        },
        Lumina: {
            pros: [`Fuel Production +${pct("LUMINA_FUEL_PRODUCTION_INCREASE")}`,
                "Intel spy operations do not consume spy attempts (when sending at least 50% of your drones)"],
            cons: [`Offense -${pct("LUMINA_OFFENSE_REDUCTION")}`],
        },
        Xo: {
            pros: [`Attack Gains +${pct("XO_ATTACK_GAINS_INCREASE")}`, `Attack Unit Losses -${pct("XO_ATTACK_UNIT_LOSSES_REDUCTION")}`],
            cons: [`Workshop Capacity -${pct("XO_WORKSHOP_CAPACITY_REDUCTION")}`],
        },
        Fuzi: {
            pros: [`Missiles Cost -${pct("FUZI_MISSILE_COST_REDUCTION")}`,
                `Missiles Silo Capacity +${pct("FUZI_MISSILE_SILO_CAPACITY_INCREASE")}`,
                `Ignores missile shields beyond ${pct("FUZI_MISSILE_SHIELDS_MAX")}`],
            cons: [],
        },
    };
}
