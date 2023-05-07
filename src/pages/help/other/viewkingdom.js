import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function ViewKingdom(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "viewkingdom") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="viewkingdom" ref={yourElementRef} className="help-section">
            <h2>View Kingdom</h2>
            <p>
                The View Kingdom button from the Galaxy or Conquer pages allows you to see view another kingdom's details. 
                You will only be able to see information which you have gained through spy operations or information that has 
                been shared with you.
            </p>
            <p>
                If you open View Kingdom for a galaxymate who has shared their kingdom information with you, you will be able to see 
                all their information.
            </p>
        </div>
    )
}

export default ViewKingdom;