import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Primitives(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "primitives") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="primitives" ref={yourElementRef} className="help-section">
            <h2>Conquer - Primitives</h2>
            <p>
                The Primitives page provides a more casual option for utilizing your generals and spy 
                attempts to grow your kingdom.
            </p>
            <p>
                Attacking primitives will primarily yield stars. You can enter units and hit the Calculate button 
                to see your projected stars gain. In addition to stars, you will receive other spoils per star 
                that you gain. Primitives defense per star increases as the round progresses.
            </p>
            <span>Primitives spoils per star</span>
            <ul>
                <li>Money: {props.state.game_config?.BASE_PRIMITIVES_MONEY_PER_STAR}</li>
                <li>Fuel: {props.state.game_config?.BASE_PRIMITIVES_FUEL_PER_STAR}</li>
                <li>Population: {props.state.game_config?.BASE_PRIMITIVES_POPULATION_PER_STAR}</li>
            </ul>
            <p>
                You can choose to enable Auto Attack primitives. This option will automatically send your generals 
                out to attack primitives as they return. The Pure/Flex Offense settings specifies the maximum amount of 
                offense you would like to send in total.
            </p>
            <p>
                Robbing primitives will return money per drone sent. You can choose to enable Auto Rob primitives. This option 
                will automatically use your spy attempts to rob primitives, leaving you with "Spy Attempts to Keep" spy attempts 
                remaining. The amount of money received per drone decreases as the round progresses.
            </p>
        </div>
    )
}

export default Primitives;