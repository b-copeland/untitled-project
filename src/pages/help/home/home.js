import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Home(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "home") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const nwRows = Object.keys(props.state.game_config?.NETWORTH_VALUES || {}).map((keyItem, iter) => {
        return <tr key={"networthvalues_" + iter}>
            <td style={{textAlign: "left"}}>{props.state.pretty_names[keyItem] || keyItem}</td>
            <td style={{textAlign: "right"}}>{props.state.game_config?.NETWORTH_VALUES[keyItem]}</td>
        </tr>
    })
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="home" ref={yourElementRef} className="help-section">
            <h2>Home</h2>
            <h4>Home - Kingdom</h4>
            <p>The kingdom page displays information about your kingdom's status, such as networth, stars, and units.</p>
            <p>
                Additionally, you can view your kingdom's current income. 
                Income is updated continuously as the game progresses. Income is continuously accumulated as the game progresses, 
                based on the number of seconds elapsed since the last update. Updates occur every 15 to 60 seconds, based on the
                current game config.
            </p>
            <p>Networth is calculated by summing the values below</p>
            <Table striped bordered hover>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Networth Value</th>
                    </tr>
                </thead>
                <tbody>
                    {nwRows}
                </tbody>
            </Table>
            <h4>Home - Shields</h4>
            <p>
                The shields page allows you to update your shields usage. Shields consume power to provide some benefits. 
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
            <h4>Home - Spending</h4>
            <p>
                The spending page allows you to update your auto-spending allocation or enable auto-spending. With auto-spending enabled, 
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
            <h4>Home - Military</h4>
            <p>
                The military page displays the current status of your generals and the production status of your military.
            </p>
            <p>
                The max offense and max defense statistics are calculated assuming that your kingdom has the max possible bonuses, 
                that is: your military efficiency is maxed, your military shields are maxed, you are sending 4 generals, and you are not fuelless.
            </p>
            <h4>Home - Structures</h4>
            <p>
                The structures page displays the current and future status of your structures.
            </p>
        </div>
    )
}

export default Home;