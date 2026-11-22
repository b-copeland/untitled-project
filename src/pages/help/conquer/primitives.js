import React from "react";
import { Topic, config, num } from "../util";

function Primitives(props) {
    const cfg = config(props.state);
    return (
        <Topic id="primitives" title="Primitives" lead="Grow without making enemies: attack and rob the unclaimed stars around you.">
            <h4>Attack</h4>
            <p>
                Choose units and generals and the forecast shows the stars you would take. Each star also brings
                {" "}{num(cfg.BASE_PRIMITIVES_MONEY_PER_STAR)} money, {num(cfg.BASE_PRIMITIVES_FUEL_PER_STAR)} fuel and
                {" "}{num(cfg.BASE_PRIMITIVES_POPULATION_PER_STAR)} population. Primitives get stronger as the round goes
                on: their defense is {num(props.state.primitives_defense_per_star)} per star now.
            </p>
            <h4>Rob</h4>
            <p>
                Send drones to steal money. Each drone brings back about {num(props.state.primitives_rob_per_drone)} money
                now, and less as the round goes on. A rob uses a spy attempt.
            </p>
            <h4>Automatic attacks and robs</h4>
            <ul>
                <li><b>Automatic attacks</b> attack the primitives whenever a general is home, sending every general at home (except any a scheduled action needs) with the shares of attackers and flexers you set. Shares count your whole army, including units already out.</li>
                <li><b>Automatic robs</b> send the share of drones you set whenever you have more spy attempts than the number to keep. They can shield the drones.</li>
            </ul>
            <p>Set the shares and save before you switch either one on. Both are also on the Automation page.</p>
        </Topic>
    );
}

export default Primitives;
