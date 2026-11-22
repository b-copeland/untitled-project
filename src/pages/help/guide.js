import React from "react";
import { Topic } from "./util";

function Guide() {
    return (
        <Topic id="guide" title="Guide"
            lead="You rule a kingdom of stars. Grow it, defend it, and work with your galaxy to finish the round with the most points.">
            <h4>How you win</h4>
            <p>
                You earn points for every hour your kingdom is among the largest by networth (see Scores). A kingdom
                that loses all its stars or all its population is dead for the rest of the round, but keeps the points
                it has earned.
            </p>

            <h4>Your first steps</h4>
            <ol>
                <li><b>Build on every star.</b> Each star holds one structure. Empty stars earn nothing (Structures).</li>
                <li><b>Defend first.</b> If an attacker's offense beats your defense, you lose stars. Keep your defense above what the kingdoms around you could send (Military).</li>
                <li><b>Keep fuel up.</b> Without fuel, your population stops growing, your army gets much weaker and your shields switch off. Build enough fuel plants to keep a buffer (Structures, Shields).</li>
                <li><b>Grow.</b> Settle new stars, attack primitives, or attack other players (Settle, Primitives, Attack).</li>
                <li><b>Turn on auto spending</b> so your income keeps building while you are away. Set its targets too, or it has nothing to build (Automation).</li>
            </ol>

            <h4>The main systems</h4>
            <ul>
                <li><b>Military.</b> Units have offense, defense or both. A failed attack on you costs you some defenders but no stars.</li>
                <li><b>Projects.</b> Engineers earn project points. Continuous projects give a bonus that gets harder to hold as you grow. One-time projects unlock units and fixed bonuses.</li>
                <li><b>Drones and intel.</b> Drones spy on other kingdoms. Military intel shows what an attack would need. Having many drones also makes you harder to spy on.</li>
                <li><b>Shields.</b> Shields burn fuel to boost your defense, block spies and soften missiles. Keep military shields at their maximum if you can afford it.</li>
                <li><b>Your galaxy.</b> Your galaxy is your team. Share intel, plan attacks together and vote on policies. Galaxies form empires, which go to war together.</li>
            </ul>

            <h4>A rule of thumb for spending</h4>
            <p>
                Military first, then structures, then settling, then engineers. Never leave stars empty while it is
                safe to build.
            </p>
            <p>
                Every page has a Help button at the bottom right that opens its topic here.
            </p>
        </Topic>
    );
}

export default Guide;
