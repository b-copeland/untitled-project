import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function LaunchMissiles(props) {
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="launchmissiles" className="help-section">
            <h2>Conquer - Launch Missiles</h2>
            <p>
                The Launch Missiles allows you to launch missiles at other kingdoms. Damage from missiles will be reduced 
                by the target's missile shields. The shields input field allows you to input assumed shields, or it will be 
                automatically populated their shields intel is revealed to you.
            </p>
        </div>
    )
}

export default LaunchMissiles;