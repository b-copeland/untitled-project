import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Structures(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "structures") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const structuresDescs = {
        "homes": `Houses ${props.state.game_config?.BASE_HOMES_CAPACITY} population`,
        "mines": `Produces ${props.state.game_config?.BASE_MINES_INCOME_PER_EPOCH} money per ${props.state.game_config?.BASE_EPOCH_SECONDS} seconds`,
        "fuel_plants": `Produces ${props.state.game_config?.BASE_FUEL_PLANTS_INCOME_PER_EPOCH} fuel per ${props.state.game_config?.BASE_EPOCH_SECONDS} seconds. Provides storage for ${props.state.game_config?.BASE_FUEL_PLANTS_CAPACITY} fuel`,
        "hangars": `Provides storage for ${props.state.game_config?.BASE_HANGAR_CAPACITY} units`,
        "drone_factories": `Produces ${props.state.game_config?.BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH} drones per ${props.state.game_config?.BASE_EPOCH_SECONDS} seconds`,
        "missile_silos": `Provides storage for ${props.state.game_config?.BASE_MISSILE_SILO_CAPACITY} of each missile`,
        "workshops": `Houses ${props.state.game_config?.BASE_WORKSHOP_CAPACITY} engineers`,
    };
    const prettyNames = props.state.pretty_names || {};
    const structuresRows = Object.keys(structuresDescs).map((structuresKey, iter) => {
        return <tr key={"structures_" + iter}>
            <td style={{textAlign: "left"}}>{prettyNames[structuresKey]}</td>
            <td style={{textAlign: "left"}}>{structuresDescs[structuresKey]}</td>
        </tr>
    })
    return (
        <div id="structures" ref={yourElementRef} className="help-section">
            <h2>Build - Structures</h2>
            <p>
                The structures page allows you to build structures to support your kingdom. You can build one structure 
                for each star that you have.
            </p>
            <p>
                Structure cost increases with your stars at a rate of `(stars ^ {props.state.game_config?.BASE_STRUCTURE_STARS_POWER}) * {props.state.game_config?.BASE_STRUCTURE_COST_CONSTANT}`. 
                The base construction time is {props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_STRUCTURE_TIME_MULTIPLIER / 3600} hours.
            </p>
            <p>
                When you have more structures than land (such as when you get attacked), your structures decrease at a rate of 
                the greater of {displayPercent(props.state.game_config?.BASE_STRUCTURES_LOSS_RETURN_RATE)} of your structures overflow 
                or {displayPercent(props.state.game_config?.BASE_STRUCTURES_LOSS_PER_STAR_PER_EPOCH)} of your stars 
                per {props.state.game_config?.BASE_EPOCH_SECONDS} seconds.
            </p>
            <p>
                The allocate page allows you to specify the target mix of structures that you would like the auto-spender to 
                build towards. The auto-spender will prioritize building structures that are farther from their target. Both 
                currently built and in-construction structures are considered when determining the "current" mix of buildings.
            </p>
            <Table striped bordered hover>
                <thead>
                    <tr>
                        <th>Structure</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    {structuresRows}
                </tbody>
            </Table>
        </div>
    )
}

export default Structures;