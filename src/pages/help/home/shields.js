import { displayPercent } from "../../../format";
import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Shields(props) {
    const yourElementRef = useRef(null);

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "shields") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="shields" ref={yourElementRef} className="help-section">
            <h2>Shields</h2>
            <p>
                The Shields page allows you to update your shields usage. Shields consume power to provide some benefits. 
            </p>
            <Table className="shields-table" hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Shield</th>
                        <th style={{textAlign: "left"}}>Description</th>
                        <th style={{textAlign: "right"}}>Max %</th>
                        <th style={{textAlign: "right"}}>Cost Per Star Per %</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Military</td>
                        <td style={{textAlign: "left"}}>Boosts your kingdom's defense based on current shields %</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.state.game_config?.BASE_MILITARY_SHIELDS_MAX || 0)}</td>
                        <td style={{textAlign: "right"}}>{props.state.game_config?.BASE_MILITARY_SHIELDS_COST_PER_LAND_PER_PCT || 0}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Spy</td>
                        <td style={{textAlign: "left"}}>Spy attempts against you have a chance to fail based on current shields %</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.state.game_config?.BASE_SPY_SHIELDS_MAX || 0)}</td>
                        <td style={{textAlign: "right"}}>{props.state.game_config?.BASE_SPY_SHIELDS_COST_PER_LAND_PER_PCT || 0}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Spy Radar</td>
                        <td style={{textAlign: "left"}}>Spy attempts against you have a chance to reveal the sender based on current radar %</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.state.game_config?.BASE_SPY_RADAR_MAX || 0)}</td>
                        <td style={{textAlign: "right"}}>{props.state.game_config?.BASE_SPY_RADAR_COST_PER_LAND_PER_PCT || 0}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Missiles</td>
                        <td style={{textAlign: "left"}}>Missiles used against you have their damage reduced based on current shields %</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.state.game_config?.BASE_MISSILE_SHIELDS_MAX || 0)}</td>
                        <td style={{textAlign: "right"}}>{props.state.game_config?.BASE_MISSILES_SHIELDS_COST_PER_LAND_PER_PCT || 0}</td>
                    </tr>
                </tbody>
            </Table>
        </div>
    )
}

export default Shields;
