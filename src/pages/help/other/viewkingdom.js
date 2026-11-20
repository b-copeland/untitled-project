import { displayPercent } from "../../../format";
import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function ViewKingdom(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "viewkingdom") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="viewkingdom" ref={yourElementRef} className="help-section">
            <h2>View Kingdom</h2>
            <p>
                The View Kingdom button from the Galaxy or Conquer pages allows you to see view another kingdom's details. 
                You will only be able to see information which you have gained through spy operations or information that has 
                been shared with you.
            </p>
            <p>
                For a kingdom in another galaxy, the dialog also has an Intel market tab, and each kind of intel you do
                not have offers to spy on it, buy it, or ask the galaxy for it; intel you have can be shared from
                there. See Conquer - Intel.
            </p>
            <p>
                If you open View Kingdom for a galaxymate who has shared their kingdom information with you, you will be able to see 
                all their information.
            </p>
            <LastKnownHelp state={props.state} />
        </div>
    )
}

/** How last-known intel is shown, with the ages in hours from the game's thresholds. Also used by the Galaxy topic. */
export function LastKnownHelp({ state }) {
    const config = state?.game_config || {};
    const hours = (epochs) => Math.round((epochs || 0) * (config.BASE_EPOCH_SECONDS || 0) / 3600);
    const fresh = hours(config.LAST_KNOWN_FRESH_EPOCHS);
    const aging = hours(config.LAST_KNOWN_AGING_EPOCHS);
    return (
        <p>
            When intel on a kingdom ends, you keep what it last showed. Wherever that kingdom is shown and the intel is
            not active any more, those last-known values fill in, coloured by how long ago the intel ended:{" "}
            <span className="last-known last-known-fresh">yellow</span> under {fresh} hours,{" "}
            <span className="last-known last-known-aging">orange</span> under {aging} hours and{" "}
            <span className="last-known last-known-stale">red</span> after that. Hover over a value to see its age.
            Active intel always replaces them. A galaxymate who stops sharing with you leaves you their whole kingdom as
            it was then.
        </p>
    );
}

export default ViewKingdom;