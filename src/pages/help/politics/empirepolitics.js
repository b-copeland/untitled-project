import { displayPercent } from "../../../format";
import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function EmpirePolitics(props) {
    const yourElementRef = useRef(null);
    const config = props.state.game_config || {};

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "empirepolitics") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="empirepolitics" ref={yourElementRef} className="help-section">
            <h2>Politics - Empire</h2>
            <p>
                An Empire is a group of galaxies. A galaxy leader can found an Empire, ask to join one, or accept an
                invitation from one. The leader of the Empire's ruling galaxy invites galaxies and accepts their
                requests. Empires can denounce, declare war on, make peace with and surrender to other Empires.
            </p>
            <h3>How large an Empire can be</h3>
            <p>
                A galaxy can not join an Empire if the Empire would then have more
                than {displayPercent(config.EMPIRE_MAX_KINGDOMS_SHARE)} of the universe's kingdoms or more
                than {displayPercent(config.EMPIRE_MAX_NETWORTH_SHARE)} of its networth (the galaxies' networth on the
                Scores page). An Empire of {config.EMPIRE_ALWAYS_ALLOWED_GALAXIES} galaxies is always allowed. The rule is
                checked when a galaxy joins: an Empire that grows past it afterwards keeps its galaxies, but takes in no
                more until it is back under.
            </p>
        </div>
    )
}

export default EmpirePolitics;
