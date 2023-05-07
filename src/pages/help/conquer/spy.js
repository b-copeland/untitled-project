import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Spy(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "spy") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const siphonDurationHours = props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_DRONES_SIPHON_TIME_MULTIPLIER / 3600
    const siphonMax = displayPercent(props.state.game_config?.BASE_MAX_SIPHON);
    const operationsDesc = {
        "spykingdom": `Reveals non-military information about a kingdom and missiles`,
        "spymilitary": `Reveals units and generals information`,
        "spyshields": `Reveals shields information`,
        "spystructures": `Reveals structures`,
        "spyprojects": `Reveals projects information`,
        "spydrones": `Reveals drones and spy attempts`,
        "siphonfunds": `Steals up to ${props.state.game_config?.BASE_DRONES_SIPHON_PER_DRONE} money per drone over the next ${siphonDurationHours} hours, up to ${siphonMax} of the target's income. Siphons will be split across all siphoning kingdoms, proportional to drones sent.`,
        "bombhomes": `Destroys 1 home per ${props.state.game_config?.BASE_DRONES_PER_HOME_DAMAGE} drones, up to ${displayPercent(props.state.game_config?.BASE_DRONES_MAX_HOME_DAMAGE)} of the target's homes.`,
        "sabotagefuelplants": `Destroys 1 fuel plant per ${props.state.game_config?.BASE_DRONES_PER_FUEL_PLANT_DAMAGE} drones, up to ${displayPercent(props.state.game_config?.BASE_DRONES_MAX_FUEL_PLANT_DAMAGE)} of the target's fuel plants.`,
        "kidnappopulation": `Kidnaps 1 population per ${props.state.game_config?.BASE_DRONES_PER_KIDNAP} drones, up to ${displayPercent(props.state.game_config?.BASE_DRONES_MAX_KIDNAP_DAMAGE)} of the target's population. ${displayPercent(props.state.game_config?.BASE_KIDNAP_RETURN_RATE)} of the kidnapped populaton returns to your kingdom.`,
        "suicidedrones": `Destroys ${props.state.game_config?.BASE_DRONES_SUICIDE_FUEL_DAMAGE} fuel per drone sent. All of the sent drones are lost.`,
    };
    const prettyNames = props.state.pretty_names || {};
    const operationsRows = Object.keys(operationsDesc).map((operationsKey, iter) => {
        return <tr key={"operations_" + iter}>
            <td style={{textAlign: "left"}}>{prettyNames[operationsKey]}</td>
            <td style={{textAlign: "left"}}>{operationsDesc[operationsKey]}</td>
            <td style={{textAlign: "left"}}>{props.state.aggro_operations?.includes(operationsKey).toString()}</td>
        </tr>
    })
    return (
        <div id="spy" ref={yourElementRef} className="help-section">
            <h2>Conquer - Spy</h2>
            <p>
                The spy page is used to carry out spy operations on other kingdoms. The first section of the page is used to 
                fill out the details of the target kingdom and operation, while the second part of the page is used to select the amount 
                of drones you would like to send.
            </p>
            <p>
                Each star in the target's kindom will provide {props.state.game_config?.BASE_STARS_DRONE_DEFENSE_MULTIPLIER} spy defense, 
                while each drone in the target's kingdom provides {props.state.game_config?.BASE_DRONES_DRONE_DEFENSE_MULTIPLIER} spy defense.
            </p>
            <p>
                In order to maximimze your chance of success, you would like to send as many drones as the target's total spy defense. 
                Your success chance in an operation will be reduced by the target's current Spy Shields. Each operation has a 
                minimum chance of {displayPercent(props.state.game_config?.BASE_SPY_MIN_SUCCESS_CHANCE)} for succeeding, regardless of 
                how many drones you send.
            </p>
            <p>
                During successful spy operations, {displayPercent(props.state.game_config?.BASE_DRONES_SUCCESS_LOSS_RATE)} of drones will be lost, 
                while {displayPercent(props.state.game_config?.BASE_DRONES_FAILURE_LOSS_RATE)} will be lost during failed operations. 
                Shielding drones during any operation will reduce drones losses 
                by {displayPercent(props.state.game_config?.BASE_DRONES_SHIELDING_LOSS_REDUCTION)}. Each drone during a shielded operation 
                requires 1 fuel.
            </p>
            <p>
                If you fail an aggressive spy operation, or your target's spy radar catches you, your drones will be revealed to the target
                for {props.state.game_config?.BASE_REVEAL_DURATION_MULTIPLIER * props.state.game_config?.BASE_EPOCH_SECONDS / 3600} hours.
            </p>
            <Table striped bordered hover>
                <thead>
                    <tr>
                        <th>Operation</th>
                        <th>Description</th>
                        <th>Aggresive</th>
                    </tr>
                </thead>
                <tbody>
                    {operationsRows}
                </tbody>
            </Table>
        </div>
    )
}

export default Spy;