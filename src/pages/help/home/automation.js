import React, { useEffect, useRef } from "react";

function Automation(props) {
    const yourElementRef = useRef(null);

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "automation") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="automation" ref={yourElementRef} className="help-section">
            <h2>Automation</h2>
            <p>
                The Automation page gathers everything your kingdom can do by itself. The Overview tab lists each
                feature, whether it is on, and what it will do, with a switch to turn it on or off.
            </p>
            <p>
                The other tabs hold each feature's settings, the same ones as on their own pages: the auto spending
                split, the structure, unit and project targets that auto spending builds towards, the automatic attacks
                and robs on primitives, and the queue of scheduled actions. Adding a scheduled action is on the Schedule
                page.
            </p>
            <p>
                Automatic attacks need a share of attackers or flexers to send, and automatic robs a share of drones,
                before they can be switched on.
            </p>
        </div>
    )
}

export default Automation;
