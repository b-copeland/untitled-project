import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Politics(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "politics") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="politics" ref={yourElementRef} className="help-section">
            <h2>Politics - Galaxy</h2>
            <p>
                The Politics page allows you to interact with your galaxy's politics. The 
                Galaxy Leader vote currently does nothing.
            </p>
            <p>
                The Policies tab allows you to vote with your galaxy on difference policies across 
                doctrines. You can only vote for one policy within each doctrine. The active policy will 
                change when it has more votes than the other policy in the doctrine.
            </p>
        </div>
    )
}

export default Politics;