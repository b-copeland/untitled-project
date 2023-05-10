import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function CreateKingdom(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "createkingdom") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    
    const racesDesc = {
        "Gaian": {
            pros: <div>
                <span>{`Settle Cost -${displayPercent(props.state.game_config.GAIAN_SETTLE_COST_REDUCTION)}`}</span>
                <br/>
                <span>{`Settle Time -${displayPercent(props.state.game_config.GAIAN_SETTLE_TIME_REDUCTION)}`}</span>
            </div>,
            cons: <span>{`Defense -${displayPercent(props.state.game_config.GAIAN_DEFENSE_REDUCTION)}`}</span>,
        },
        "Vult": {
            pros: <div>
                <span>{`Drone Production +${displayPercent(props.state.game_config.VULT_DRONE_PRODUCTION_INCREASE)}`}</span>
                <br/>
                <span>Aggressive spy operations ignore spy shields and spy radar</span>
            </div>,
            cons: <span>{`Population -${displayPercent(props.state.game_config.VULT_POPULATION_REDUCTION)}`}</span>,
        },
        "Lumina": {
            pros: <div>
                <span>{`Fuel Production +${displayPercent(props.state.game_config.LUMINA_FUEL_PRODUCTION_INCREASE)}`}</span>
                <br/>
                <span>Intel spy operations do not consume spy attempts</span>
            </div>,
            cons: <span>{`Offense -${displayPercent(props.state.game_config.LUMINA_OFFENSE_REDUCTION)}`}</span>,
        },
        "Xo": {
            pros: <div>
                <span>{`Attack Gains +${displayPercent(props.state.game_config.XO_ATTACK_GAINS_INCREASE)}`}</span>
                <br/>
                <span>{`Attack Unit Losses -${displayPercent(props.state.game_config.XO_ATTACK_UNIT_LOSSES_REDUCTION)}`}</span>
            </div>,
            cons: <span>{`Workshop Capacity -${displayPercent(props.state.game_config.XO_WORKSHOP_CAPACITY_REDUCTION)}`}</span>,
        },
        "Fuzi": {
            pros: <div>
                <span>{`Missiles Cost -${displayPercent(props.state.game_config.FUZI_MISSILE_COST_REDUCTION)}`}</span>
                <br/>
                <span>{`Missiles Silo Capacity +${displayPercent(props.state.game_config.FUZI_MISSILE_SILO_CAPACITY_INCREASE)}`}</span>
                <br/>
                <span>{`Ignores missile shields beyond ${displayPercent(props.state.game_config.FUZI_MISSILE_SHIELDS_MAX)}`}</span>
            </div>,
            cons: null
        },
    };
    const prettyNames = props.state.pretty_names || {};
    const racesRows = Object.keys(racesDesc).map((racesKey, iter) => {
        return <tr key={"races_" + iter}>
            <td style={{textAlign: "left"}}>{racesKey}</td>
            <td style={{textAlign: "left"}}>{racesDesc[racesKey].pros}</td>
            <td style={{textAlign: "left"}}>{racesDesc[racesKey].cons}</td>
        </tr>
    })
    return (
        <div id="createkingdom" ref={yourElementRef} className="help-section">
            <h2>Create Kingdom</h2>
            <p>
                The Create Kingdom page allows you to choose your kingdom name and starting state. You 
                will randomly be placed into the galaxy with the fewest kingdoms when you create your 
                kingdom.
            </p>
            <p>
                You must use all kingdom creator points and stars in order to build your kingdom. The stats section 
                at the bottom of the page will update as you change your selection.
            </p>
            <Table striped bordered hover size="sm" className="races-table">
                <thead>
                    <tr>
                        <th>Race</th>
                        <th>Pros</th>
                        <th>Cons</th>
                    </tr>
                </thead>
                <tbody>
                    {racesRows}
                </tbody>
            </Table>
        </div>
    )
}

export default CreateKingdom;