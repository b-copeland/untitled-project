import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Attack(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "attack") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="attack" ref={yourElementRef} className="help-section">
            <h2>Conquer - Attack</h2>
            <p>
                The attack page is used to carry out attacks on other kingdoms. The first section of the page is used to 
                fill out the details of the target kingdom, while the second part of the page is used to select the units
                and generals that you would like to attack with.
            </p>
            <p>
                If you have any relevant intel on your target, that information will automatically be populated and 
                used in calculating an attack against the defender.
            </p>
            <p>
                The Calculate button projects the results of the attack on the target kingdom. Note that the calculator is only 
                as good as the information that you give it, combined with intel that you've gathered. If you do not provide accurate details
                about the target's units, it's likely that the calculator will falsely tell you that an attack will be successful. 
            </p>
            <p>
                It's a good idea to at least gather Military intel on the target prior to attempting an attack. You can then assume 
                maximum Military Efficiency and Shields for determining if your attack will be a success.
            </p>
            <p>
                To make an attack, you must send at least 1 general. Each general beyond the first will increase your offensive strength
                by {displayPercent(props.state.game_config?.BASE_GENERALS_ATTACK_MODIFIER)}. Sending more generals allows some of your 
                units to return quicker; your attacking units will be equally split across the returning generals. The base return time 
                for generals is {props.state.game_config?.BASE_GENERALS_RETURN_TIME_MULTIPLIER * props.state.game_config?.BASE_EPOCH_SECONDS / 3600} hours.
            </p>
            <p>
                Return times will be further modified by your projects, your politics, and your coordinates distance relative to your target. 
                Coordinates range from 0 to 99 in a loop (i.e. 99 is 1 distance from 0). Your return times will be increased
                by {displayPercent(props.state.game_config?.BASE_RETURN_TIME_PENALTY_PER_COORDINATE)} per distance for distances beyond 25, or 
                reduced by {displayPercent(props.state.game_config?.BASE_RETURN_TIME_PENALTY_PER_COORDINATE)} per distance for distances under 25.
            </p>
            <p>
                Other attack info:
            </p>
            <ul>
                <li>Max defender unit losses - {displayPercent(props.state.game_config?.BASE_DEFENDER_UNIT_LOSS_RATE)}</li>
                <li>Max attacker unit losses - {displayPercent(props.state.game_config?.BASE_ATTACKER_UNIT_LOSS_RATE)}</li>
                <li>Successful attack gains rate - {displayPercent(props.state.game_config?.BASE_KINGDOM_LOSS_RATE)}</li>
                <li>Strength reduction when out of fuel - {displayPercent(props.state.game_config?.BASE_FUELLESS_STRENGTH_REDUCTION)}</li>
                <li>Minimum stars gain - {props.state.game_config?.BASE_ATTACK_MIN_STARS_GAIN}</li>
            </ul>
        </div>
    )
}

export default Attack;