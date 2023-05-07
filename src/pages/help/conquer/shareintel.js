import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function ShareIntel(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "shareintel") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="shareintel" ref={yourElementRef} className="help-section">
            <h2>Conquer - Share Intel</h2>
            <p>
                The Share Intel page allows you to share intel that you have acquired with your 
                galaxymates. You can not share intel with other kingdoms if you acquired that intel 
                by accepting it from a galaxymate.
            </p>
            <p>
                The Select Cut field specifies your cut of spoils when a galaxymate acts on intel you have provided. 
                When a galaxymate successfully attacks a kingdom after they accepted intel from you, you will 
                receive a cut of the spoils (e.g. stars). The maximum cut is {displayPercent(props.state.game_config?.BASE_MAX_SHARE_CUT)}.
            </p>
        </div>
    )
}

export default ShareIntel;