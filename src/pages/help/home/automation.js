import React from "react";
import { Topic } from "../util";

function Automation() {
    return (
        <Topic id="automation" title="Automation" lead="Everything your kingdom can do while you are away, in one place.">
            <p>
                The <b>Overview</b> tab lists each automatic feature, says whether it is on and what it will do next,
                and has a switch for each. The other tabs hold their settings:
            </p>
            <ul>
                <li><b>Spending</b>: how your income is split between settling, structures, military and engineers (see Auto spending).</li>
                <li><b>Structure targets</b> and <b>Unit targets</b>: the mix auto spending builds towards. The same settings are on the Allocate tabs of the Structures and Military pages.</li>
                <li><b>Project targets</b>: how engineers are spread across projects when auto assign is on.</li>
                <li><b>Primitives</b>: automatic attacks and robs on primitives. Set a share of attackers or flexers, or of drones, before you switch them on.</li>
                <li><b>Schedule</b>: your queue of scheduled actions. Add new ones on the Schedule page.</li>
            </ul>
        </Topic>
    );
}

export default Automation;
