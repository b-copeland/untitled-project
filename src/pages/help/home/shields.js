import React from "react";
import { HelpTable, Topic, config, num, pct, perHour } from "../util";

function Shields(props) {
    const cfg = config(props.state);
    const shields = [
        ["Military", "Raises your defense", "MILITARY_SHIELDS"],
        ["Spy", "Gives spy operations against you a chance to fail", "SPY_SHIELDS"],
        ["Spy Radar", "Gives spy operations against you a chance to reveal who sent them", "SPY_RADAR"],
        ["Missiles", "Reduces missile damage to you", "MISSILES_SHIELDS"],
    ];
    return (
        <Topic id="shields" title="Shields" lead="Burn fuel to protect your kingdom.">
            <p>
                Set each shield with its slider and press Update. A shield's cost grows with its level and your stars,
                and the page shows what your shields cost in fuel per hour. You need fuel in stock to change them.
            </p>
            <p>
                <b>If you run out of fuel, every shield switches off.</b> Keep enough fuel income to pay for them.
            </p>
            <HelpTable columns={[["Shield"], ["Effect"], ["Max", "right"], ["Fuel per hour, per star per 1%", "right"]]}
                rows={shields.map(([name, effect, key]) => [
                    name, effect,
                    pct(cfg[`BASE_${key}_MAX`]),
                    num(perHour(cfg[`BASE_${key}_COST_PER_LAND_PER_PCT`], cfg)),
                ])} />
        </Topic>
    );
}

export default Shields;
