import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Conquer(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "conquer") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="conquer" ref={yourElementRef} className="help-section">
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
                <li>You buy intel from a galaxymate, a galaxymate answers your bounty, or one shares intel free</li>
            </ul>
            <p>
                Revealed information is active for {props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_REVEAL_DURATION_MULTIPLIER / 3600} hours.
            </p>
            <p>
                The Intel button on a kingdom shows what you can share, buy or ask for on it. Trading intel with your
                galaxymates is on the Intel page.
            </p>
            <p>
                The pinned tab is used to track kingdoms which you have pinned.
            </p>
        </div>
    )
}

export default Conquer;