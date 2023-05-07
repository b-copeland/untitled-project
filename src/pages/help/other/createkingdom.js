import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function CreateKingdom(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "createkingdom") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="createkingdom" ref={yourElementRef} className="help-section">
            <h2>Create Kingdom</h2>
            <p>
                The Create Kingdom page allows you to choose your kingdom name and starting state. You 
                will randomly be placed into the galaxy with the fewest kingdoms when you create your 
                kingdom.
            </p>
            <p>
                You must use all kingdom creator points and stars in order to build your kingdom. The stats section 
                at the bottom of the page will update as you change your selection.
            </p>
        </div>
    )
}

export default CreateKingdom;