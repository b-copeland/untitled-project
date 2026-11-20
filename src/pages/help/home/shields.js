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
            <h2>Shields & Spending</h2>
            <h4>Shields</h4>
            <p>
                The Shields tab allows you to update your shields usage. Shields consume power to provide some benefits. 
            </p>
            <Table className="shields-table" striped bordered hover size="sm">
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
            <h4>Auto spending</h4>
            <p>
                The Spending tab allows you to update your auto-spending allocation or enable auto-spending. With auto-spending enabled, 
                the game automatically spends your money to build your kingdom.
            </p>
            <p>
                When auto-spending is enabled, money from your income, attacks, or robs is allocated to funding in the percentages you've chosen. 
                You can view your current funding by category on the "Build" page.
            </p>
            <p>
                Every {(props.state.game_config?.BASE_AUTO_SPENDING_TIME_MULTIPLIER || 0) * (props.state.game_config?.BASE_EPOCH_SECONDS || 0)} seconds 
                the game engine will spend any available funding to the extent that it is able. In order for the auto-spender to build structures or units, their respective allocations
                must first be set in the "Allocation" tab of the "Structures" and "Military" pages.
            </p>
            <p>
                When auto-spending is disabled, all reserved funding is released back into money to be spent as you wish.
            </p>
        </div>
    )
}

export default Shields;
