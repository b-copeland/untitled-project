import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Military(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "military") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const unitsDesc = props.state.units || {};
    const prettyNames = props.state.pretty_names || {};
    const unitsRows = Object.keys(unitsDesc).map((unitKey, iter) => {
        return <tr key={"units_" + iter}>
            <td style={{textAlign: "left"}}>{prettyNames[unitKey]}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].cost}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].offense}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].defense}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].hangar_capacity}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].fuel}</td>
        </tr>
    })
    return (
        <div id="military" ref={yourElementRef} className="help-section">
            <h2>Build - Military</h2>
            <p>
                The Recruits page allows you to train recruits. You can train 
                up to {displayPercent(props.state.game_config?.BASE_MAX_RECRUITS_CAP)} of your
                current population at one time.
            </p>
            <p>
                Base recruit cost is {props.state.game_config?.BASE_RECRUIT_COST}. 
                The base average training time is {props.state.game_config?.BASE_EPOCH_SECONDS * (props.state.game_config?.BASE_RECRUIT_TIME_MIN_MULTIPLIER + props.state.game_config?.BASE_RECRUIT_TIME_MAX_MUTLIPLIER) / 2 / 3600} hours.
            </p>
            <p>
                The Specialists page allows you to train recruits into specialists. 
                The base average training time is {props.state.game_config?.BASE_EPOCH_SECONDS * (props.state.game_config?.BASE_SPECIALIST_TIME_MIN_MULTIPLIER + props.state.game_config?.BASE_SPECIALIST_TIME_MAX_MUTLIPLIER) / 2 / 3600} hours.
            </p>
            <p>
                You can exceed your maximum hangar capacity at any time. However, units which do not have a hangar will displace civilians from their homes 
                and cause population loss.
            </p>
            <p>
                The allocate page allows you to specify the target mix of units that you would like the auto-spender to 
                build towards, as well as the maximum number of recruits to train. The auto-spender will first spend funding on training recruits if enabled, 
                and then prioritize training units that are farther from their target allocation. Both 
                currently trained and in-training units are considered when determining the "current" mix of units. The allocation is based on the number of 
                units (i.e. the allocation does not consider cost of the unit).
            </p>
            <p>
                Units consume fuel every {props.state.game_config?.BASE_EPOCH_SECONDS} seconds based on the table below.
            </p>
            <Table className="specialists-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Unit</th>
                        <th style={{textAlign: "right"}}>Cost</th>
                        <th style={{textAlign: "right"}}>Offense</th>
                        <th style={{textAlign: "right"}}>Defense</th>
                        <th style={{textAlign: "right"}}>Hangar Usage</th>
                        <th style={{textAlign: "right"}}>Fuel</th>
                    </tr>
                </thead>
                <tbody>
                    {unitsRows}
                </tbody>
            </Table>
        </div>
    )
}

export default Military;