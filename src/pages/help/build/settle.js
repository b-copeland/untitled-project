import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Settle(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "settle") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="settle" ref={yourElementRef} className="help-section">
            <h2>Build - Settle</h2>
            <p>
                The settle page allows you to explore stars to expand your kingdom. You can explore 
                up to {displayPercent(props.state.game_config?.BASE_MAX_SETTLE_CAP)} of your current stars.
            </p>
            <p>
                Settle cost increases with your stars at a rate of `(stars ^ {props.state.game_config?.BASE_SETTLE_STARS_POWER}) * {props.state.game_config?.BASE_SETTLE_COST_CONSTANT}`. 
                The base settle time is {props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_SETTLE_TIME_MULTIPLIER / 3600} hours.
            </p>
        </div>
    )
}

export default Settle;