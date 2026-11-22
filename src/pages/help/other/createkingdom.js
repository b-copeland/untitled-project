import React from "react";
import { raceDescriptions } from "../../../races";
import { HelpTable, Topic } from "../util";

function CreateKingdom(props) {
    const races = raceDescriptions(props.state.game_config);
    const lines = (list) => list.map((line, index) => <React.Fragment key={line}>{index > 0 ? <br /> : null}{line}</React.Fragment>);
    return (
        <Topic id="createkingdom" title="Create Kingdom" lead="Three steps: a name, a way to play, and a final check.">
            <ul>
                <li><b>Quick starts</b> (Explorer, Attacker, Intel and Thief) each give you a race, a starting kingdom and a ready-made plan for auto spending and the automatic attacks and robs. The plan is saved either way. You choose whether to switch it on now, or later from the Automation page.</li>
                <li><b>Custom</b> lets you choose the race and spend the starting unit points and stars yourself. You must spend all of both. The numbers under the choices update as you go.</li>
            </ul>
            <p>
                Nothing is made until you press Create kingdom. You join the galaxy with the fewest kingdoms. Each race
                also has two projects of its own, a capstone and an evolution.
            </p>
            <HelpTable columns={[["Race"], ["Strengths"], ["Weaknesses"]]}
                rows={Object.keys(races).map((race) => [race, lines(races[race].pros), lines(races[race].cons)])} />
        </Topic>
    );
}

export default CreateKingdom;
