import React from "react";
import { Topic, config, duration, num, pct } from "../util";

function Attack(props) {
    const cfg = config(props.state);
    return (
        <Topic id="attack" title="Attack" lead="Send your army at another kingdom to take its stars.">
            <h4>How to attack</h4>
            <ol>
                <li><b>Choose a target.</b> The page fills in everything your intel reveals about it.</li>
                <li><b>Check their defense.</b> Each number shows whether it is revealed, your estimate, or still needed. Fill in what is missing. The forecast is only as good as these numbers, so get military intel first if you can.</li>
                <li><b>Choose your attack.</b> The page suggests units that should win, with the margin you set. Change them freely, or press Suggest again.</li>
                <li><b>Check the forecast and send.</b> It updates as you type. It asks you to confirm if their units are a guess or the forecast says you would lose.</li>
            </ol>
            <p>
                If you have to guess, assume the worst: maximum military efficiency and shields.
            </p>
            <h4>Generals and return times</h4>
            <ul>
                <li>Every attack needs at least 1 general. Each extra one adds {pct(cfg.BASE_GENERALS_ATTACK_MODIFIER)} offense.</li>
                <li>Your units split evenly across the generals sent and come home with them, so more generals bring part of the army back sooner. Warp Speed Big Flexers all return with the first.</li>
                <li>Generals take {duration(cfg.BASE_GENERALS_RETURN_TIME_MULTIPLIER, cfg)} to return, changed by projects, policies and distance.</li>
                <li>Distance: coordinates run 0 to 99 in a loop (99 is next to 0). Each step closer than 25 makes the return {pct(cfg.BASE_RETURN_TIME_PENALTY_PER_COORDINATE)} faster, and each step further makes it that much slower.</li>
            </ul>
            <h4>The numbers</h4>
            <ul>
                <li>A win takes {pct(cfg.BASE_KINGDOM_LOSS_RATE)} of the target's stars, at least {num(cfg.BASE_ATTACK_MIN_STARS_GAIN)}.</li>
                <li>The defender loses up to {pct(cfg.BASE_DEFENDER_UNIT_LOSS_RATE)} of its defending units and the attacker up to {pct(cfg.BASE_ATTACKER_UNIT_LOSS_RATE)} of the units sent, win or lose.</li>
                <li>A kingdom with no fuel fights at {pct(cfg.BASE_FUELLESS_STRENGTH_REDUCTION)} less strength.</li>
                <li>Races, war, projects and self-destructing units change losses. Self-Destructing Attackers raise the defender's losses by up to {pct(cfg.SELF_DESTRUCT_LOSSES_INCREASE)}, in proportion to their share of your offense. Self-Destructing Defenders do the same to attackers, by their share of your defense at home.</li>
            </ul>
            <h4>Intel cuts and empire targets</h4>
            <p>
                Under the target, a line shows the intel you took from galaxymates and the cut of your winnings they
                get. The forecast names each one and their share. On one of your empire's targets, part of the stars
                and money goes to the target's spoils fund instead, and no intel cuts are paid (see Empire politics).
            </p>
        </Topic>
    );
}

export default Attack;
