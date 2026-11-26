import React from "react";
import { HelpTable, Topic, config, duration, num, pct } from "../util";

function Spy(props) {
    const cfg = config(props.state);
    const names = props.state.pretty_names || {};
    const aggressive = props.state.aggro_operations || [];
    const operations = {
        spykingdom: "Reveals the kingdom's resources, population and missiles",
        spymilitary: "Reveals units and generals",
        spyshields: "Reveals shields",
        spystructures: "Reveals structures",
        spyprojects: "Reveals projects",
        spydrones: "Reveals drones and spy attempts",
        spyproduction: "Reveals what the kingdom has in production: units in training, structures being built, engineers in training, stars being settled and missiles being built, and when they arrive",
        spyall: "Reveals all of the above at once. Vult kingdoms with Vult Evolution only, in place of the other intel operations",
        siphonfunds: `Steals up to ${num(cfg.BASE_DRONES_SIPHON_PER_DRONE)} money per drone, paid evenly over the next ${duration(cfg.BASE_DRONES_SIPHON_TIME_MULTIPLIER, cfg)}. A kingdom loses at most ${pct(cfg.BASE_MAX_SIPHON)} of its income to all siphons together. When the siphons on it would take more, the oldest siphon is reduced first, then the next oldest, until they fit, and the newer ones pay in full. A reduced siphon stays reduced, and what it could not take is lost. If the siphoning kingdom dies, its siphons end. The forecast warns you when you already have a siphon running on the kingdom you choose; siphons on different kingdoms are no concern.`,
        bombhomes: `Destroys 1 home per ${num(cfg.BASE_DRONES_PER_HOME_DAMAGE)} drones, up to ${pct(cfg.BASE_DRONES_MAX_HOME_DAMAGE)} of the target's homes`,
        sabotagefuelplants: `Destroys 1 fuel plant per ${num(cfg.BASE_DRONES_PER_FUEL_PLANT_DAMAGE)} drones, up to ${pct(cfg.BASE_DRONES_MAX_FUEL_PLANT_DAMAGE)} of the target's fuel plants`,
        kidnappopulation: `Takes 1 person per ${num(cfg.BASE_DRONES_PER_KIDNAP)} drones, up to ${pct(cfg.BASE_DRONES_MAX_KIDNAP_DAMAGE)} of the target's population. ${pct(cfg.BASE_KIDNAP_RETURN_RATE)} of them join your kingdom`,
        suicidedrones: `Destroys ${num(cfg.BASE_DRONES_SUICIDE_FUEL_DAMAGE)} fuel per drone. Every drone sent is lost`,
    };
    return (
        <Topic id="spy" title="Spy" lead="Send drones to gather intel or to hurt another kingdom.">
            <h4>How to spy</h4>
            <ol>
                <li>Choose a target and an operation.</li>
                <li>Choose how many drones to send, and whether to shield them.</li>
                <li>Fill in what you know of their drones and shields, if it is not revealed.</li>
                <li>Check the forecast and send. It asks you to confirm when the chance of success is low, or before a hostile operation on a kingdom in your own galaxy or empire (shaded and tagged in the target list).</li>
            </ol>
            <h4>Success</h4>
            <ul>
                <li>A kingdom's spy defense is {num(cfg.BASE_STARS_DRONE_DEFENSE_MULTIPLIER)} per star plus {num(cfg.BASE_DRONES_DRONE_DEFENSE_MULTIPLIER)} per drone. Send as many drones as their spy defense for your best chance.</li>
                <li>Their spy shields lower your chance. It never drops below {pct(cfg.BASE_SPY_MIN_SUCCESS_CHANCE)}.</li>
                <li>Each operation uses a spy attempt. Attempts come back over time.</li>
            </ul>
            <h4>Drone losses</h4>
            <ul>
                <li>You lose {pct(cfg.BASE_DRONES_SUCCESS_LOSS_RATE)} of the drones sent on a success and {pct(cfg.BASE_DRONES_FAILURE_LOSS_RATE)} on a failure.</li>
                <li>Shielding cuts losses by {pct(cfg.BASE_DRONES_SHIELDING_LOSS_REDUCTION)} and costs 1 fuel per drone. The Drone Gadgets project cuts them further.</li>
            </ul>
            <h4>Good to know</h4>
            <ul>
                <li>An intel operation is refused, before anything is spent, when everything it would reveal is already revealed to you: by your own spying, by intel from a galaxymate, or by a galaxymate sharing their kingdom. Full Infiltration goes ahead while any part of it is not revealed.</li>
                <li>If an aggressive operation fails, or their spy radar catches you, your stars, networth and drones are revealed to them for {duration(cfg.BASE_REVEAL_DURATION_MULTIPLIER, cfg)}.</li>
                <li>Aggressive operations do less damage to a kingdom with Counter-Intelligence. The forecast counts it only if their projects are revealed.</li>
                <li>When gathering intel, you can share it with your galaxy: free, or listed on the Intel market for a cut.</li>
            </ul>
            <HelpTable columns={[["Operation"], ["What it does"], ["Aggressive"]]}
                rows={Object.keys(operations).map((key) => [names[key] || key, operations[key], aggressive.includes(key) ? "Yes" : ""])} />
        </Topic>
    );
}

export default Spy;
