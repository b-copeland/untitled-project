import React from "react";
import { Topic } from "../util";

function Build() {
    return (
        <Topic id="build" title="Build overview" lead="What is on its way, and what auto spending has set aside.">
            <p>
                <b>Auto spending funding</b> shows the money held for each category while auto spending is on.
            </p>
            <p>
                Below it, one queue each for settling, structures, units, engineers and missiles lists what is closest
                to finishing and when. The number in each title is the total still in that queue.
            </p>
        </Topic>
    );
}

export default Build;
