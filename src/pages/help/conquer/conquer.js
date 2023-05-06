import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Conquer(props) {
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="conquer" className="help-section">
            <h2>Conquer</h2>
            <p>
                The conquer page shows kingdoms which have at least 1 of their intel categories revealed to you. 
                Various actions cause intel to be revealed, such as:
            </p>
            <ul>
                <li>A kingdom in another galaxy attacks a kingdom in your galaxy</li>
                <li>You successfully execute a spy operation on another kingdom</li>
                <li>Your spy radar catches another kingdom who is spying on you</li>
                <li>A kingdom fails a spy attempt on you</li>
                <li>You accept shared intel from one of your galaxymates</li>
            </ul>
            <p>
                Revealed information is active for {props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_REVEAL_DURATION_MULTIPLIER / 3600} hours.
            </p>
            <p>
                The shared tab shows intel which has been:
            </p>
            <ul>
                <li>Accepted by you</li>
                <li>Shared to you by a galaxymate and pending acceptance</li>
                <li>Offered to a galaxymate by you</li>
            </ul>
            <p>
                When you successfully attack a kingdom for which you have actively accepted shared intel for, the galaxymate that shared intel 
                with you will receive a cut of the spoils (e.g. stars). The maximum cut is {displayPercent(props.state.game_config?.BASE_MAX_SHARE_CUT)}. 
                You can only accept 1 piece of intel per target kingdom; accepting a second piece of intel will overwrite the previously accepted intel.
            </p>
            <p>
                The pinned tab is used to track kingdoms which you have pinned.
            </p>
        </div>
    )
}

export default Conquer;