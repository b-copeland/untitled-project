import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Schedule(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "schedule") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="schedule" ref={yourElementRef} className="help-section">
            <h2>Conquer - Schedule</h2>
            <p>
                The Schedule page allows you to schedule future actions that will be taken automatically when 
                the time arrives. 
            </p>
            <p>
                The Attack and Attack Primitives actions require you to specify the percent of pure offense and flex 
                offense that you require to send. Pure offense is units that don't have defense, while flex offense is 
                units that have both offense and defense. The actions will not be executed if the percent of request units 
                are not available when the time arrives. <b>Note that these actions are currently only compatible with 
                scheduling 1 attack.</b> Scheduling multiple consecutive attacks (i.e. an attack while generals are already out) 
                will likely not work.
            </p>
            <p>
                The Intel Spy action will attempt spy operations until getting a success, up to "Max Tries" tries. If 
                Share to Galaxy is selected, the acquired intel will be shared to your galaxy.
            </p>
            <p>
                The Aggressive Spy action will attempt aggressive spy operations for the number of attempts specified.
            </p>
        </div>
    )
}

export default Schedule;