import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function UniversePolitics(props) {
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="universepolitics" className="help-section">
            <h2>Politics - Universe</h2>
            <p>
                The Universe Politics page allows you periodically participate in universal elections. 
                The election period lasts for {props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_ELECTION_LENGTH_MULTIPLIER / 3600} hours, 
                while the results of the election are active 
                for {props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_ELECTION_RESULTS_DURATION_MULTIPLIER / 3600} hours.
            </p>
            <p>
                During the election period, you can buy votes to participate in the election. At the end of the election period, the policy with the 
                most votes within each doctrine will become active and you will no longer be able to vote. Unused votes will be retained for the 
                next election cycle.
            </p>
        </div>
    )
}

export default UniversePolitics;