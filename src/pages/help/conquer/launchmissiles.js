import React from "react";
import { Topic } from "../util";

function LaunchMissiles() {
    return (
        <Topic id="launchmissiles" title="Launch Missiles" lead="Fire your missiles at another kingdom.">
            <ol>
                <li>Choose a target.</li>
                <li>Choose how many of each missile to send.</li>
                <li>Check the forecast and launch. You are asked to confirm first.</li>
            </ol>
            <p>
                The target's missile shields reduce the damage. If their shields are revealed, the forecast uses them.
                Otherwise enter your best guess. Missiles are used up when launched. Build more on the Build Missiles
                page, which lists what each kind destroys.
            </p>
        </Topic>
    );
}

export default LaunchMissiles;
