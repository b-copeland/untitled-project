import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import "./createkingdom.css"

const initialStructuresChoices = {
    "homes": 60,
    "mines": 60,
    "fuel_plants": 30,
    "hangars": 60,
    "drone_factories": 60,
    "missile_silos": 0,
    "workshops": 15,
}

const initialUnitsChoices = {
    "drones": 2000,
    "recruits": 500,
    "attack": 300,
    "defense": 500,
    "flex": 500,
    "engineers": 800,
}

function CreateKingdom(props) {
    const [kdName, setKdName] = useState("");
    const [kdMessage, setKdMessage] = useState("");
    const [createKingdomData, setCreateKingdomData] = useState({});
    const [structuresChoices, setStructuresChoices] = useState(initialStructuresChoices);
    const [unitsChoices, setUnitsChoices] = useState(initialUnitsChoices);
    
    useEffect(() => {
        authFetch('api/createkingdomdata').then(
            r => r.json()
        ).then(r => setCreateKingdomData(r)).catch(
            err => {
                console.log('Failed to fetch createkingdomdata');
                console.log(err);
            }
        );
    }, []);

    const handleNameInput = (e) => {
        setKdName(e.target.value);
    }
    const handleStructuresInputChange = (e) => {
        const { name, value } = e.target;
        setStructuresChoices({
          ...structuresChoices,
          [name]: value,
        });
      };
    const handleUnitsInputChange = (e) => {
        const { name, value } = e.target;
        setUnitsChoices({
        ...unitsChoices,
        [name]: value,
        });
    };

    const onSubmitNameClick = (e)=>{
        if (kdName != "") {
            let opts = {
                'kdName': kdName,
            };
            setKdMessage("")
            const updateFunc = () => authFetch('api/createkingdom', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setKdMessage(r))
            props.updateData(['kingdomid'], [updateFunc])
        }
    }

    const onSubmitKingdomClick = (e)=>{
        let opts = {
            'unitsChoices': unitsChoices,
            'structuresChoices': structuresChoices,
        };
        setKdMessage("")
        const updateFunc = () => authFetch('api/createkingdomchoices', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setKdMessage(r))
        props.updateData(['kingdomid'], [updateFunc])
    }

    if (Object.keys(createKingdomData).length === 0) {
        return <h2>Loading...</h2>
    }

    if (kdMessage != "" && kdMessage == props.kingdomid.kd_id) {
        setKdMessage("");
    }
    const calcStructuresRemaining = (structuresData, availableStructures) => {
        var total = 0
        for (const structure in structuresData) {
            total += parseInt(structuresData[structure] || 0);
        }
        return availableStructures - total
    }

    const calcPointsRemaining = (unitsData, availablePoints) => {
        var total = 0
        for (const unit in unitsData) {
            total += parseInt(unitsData[unit] || 0) * createKingdomData.selection_points[unit];
        }
        return availablePoints - total
    }

    return (
        <div>
        {
            (props.kingdomid.kd_id === "")
            ? <div>
                <h2>Choose a kingdom name</h2>
                <InputGroup className="kd-name-group">
                    <InputGroup.Text id="kd-name-input-display">
                        Kingdom Name
                    </InputGroup.Text>
                    <Form.Control 
                        id="kd-name-input"
                        onChange={handleNameInput}
                        value={kdName || ""} 
                        placeholder=""
                    />
                </InputGroup>
                {props.loading.kingdomid
                ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="submit-name-button" variant="primary" type="submit" onClick={onSubmitNameClick}>
                    Submit
                </Button>
                }
                {
                    kdMessage !== ""
                    ? <h4>{kdMessage}</h4>
                    : null
                }
            </div>
            : (props.kingdomid.created === false)
            ? <div className="kingdom-creator">
                <div className="kingdom-creator-row">
                    <div className="units-creator">
                        <h3>Total Units Points: {createKingdomData.total_points}</h3>
                        <h3>Points Remaining: {calcPointsRemaining(unitsChoices, createKingdomData.total_points)}</h3>
                        <div className="units-choices">
                            <InputGroup className="units-choices-input">
                                <InputGroup.Text id="drones-input-group">
                                    Drones ({createKingdomData.selection_points.drones} points)
                                </InputGroup.Text>
                                <Form.Control 
                                    id="drones-input"
                                    name="drones"
                                    onChange={handleUnitsInputChange}
                                    value={unitsChoices.drones || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="units-choices-input">
                                <InputGroup.Text id="recruits-input-group">
                                    Recruits ({createKingdomData.selection_points.recruits} points)
                                </InputGroup.Text>
                                <Form.Control 
                                    id="recruits-input"
                                    name="recruits"
                                    onChange={handleUnitsInputChange}
                                    value={unitsChoices.recruits || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="units-choices-input">
                                <InputGroup.Text id="attack-input-group">
                                    Attackers ({createKingdomData.selection_points.attack} points)
                                </InputGroup.Text>
                                <Form.Control 
                                    id="attack-input"
                                    name="attack"
                                    onChange={handleUnitsInputChange}
                                    value={unitsChoices.attack || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="units-choices-input">
                                <InputGroup.Text id="defense-input-group">
                                    Defenders ({createKingdomData.selection_points.defense} points)
                                </InputGroup.Text>
                                <Form.Control 
                                    id="defense-input"
                                    name="defense"
                                    onChange={handleUnitsInputChange}
                                    value={unitsChoices.defense || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="units-choices-input">
                                <InputGroup.Text id="flex-input-group">
                                    Flexers ({createKingdomData.selection_points.flex} points)
                                </InputGroup.Text>
                                <Form.Control 
                                    id="flex-input"
                                    name="flex"
                                    onChange={handleUnitsInputChange}
                                    value={unitsChoices.flex || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="units-choices-input">
                                <InputGroup.Text id="engineers-input-group">
                                    Engineers ({createKingdomData.selection_points.engineers} points)
                                </InputGroup.Text>
                                <Form.Control 
                                    id="engineers-input"
                                    name="engineers"
                                    onChange={handleUnitsInputChange}
                                    value={unitsChoices.engineers || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                        </div>
                    </div>
                    <div className="structures-creator">
                        <h3>Total Stars: {createKingdomData.total_stars}</h3>
                        <h3>Stars Remaining: {calcStructuresRemaining(structuresChoices, createKingdomData.total_stars)}</h3>
                        <div className="structures-choices">
                            <InputGroup className="structures-choices-input">
                                <InputGroup.Text id="homes-input-group">
                                    Homes
                                </InputGroup.Text>
                                <Form.Control 
                                    id="homes-input"
                                    name="homes"
                                    onChange={handleStructuresInputChange}
                                    value={structuresChoices.homes || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="structures-choices-input">
                                <InputGroup.Text id="mines-input-group">
                                    Mines
                                </InputGroup.Text>
                                <Form.Control 
                                    id="mines-input"
                                    name="mines"
                                    onChange={handleStructuresInputChange}
                                    value={structuresChoices.mines || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="structures-choices-input">
                                <InputGroup.Text id="fuel-plants-input-group">
                                    Fuel Plants
                                </InputGroup.Text>
                                <Form.Control 
                                    id="fuel-plants-input"
                                    name="fuel_plants"
                                    onChange={handleStructuresInputChange}
                                    value={structuresChoices.fuel_plants || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="structures-choices-input">
                                <InputGroup.Text id="hangars-input-group">
                                    Hangars
                                </InputGroup.Text>
                                <Form.Control 
                                    id="hangars-input"
                                    name="hangars"
                                    onChange={handleStructuresInputChange}
                                    value={structuresChoices.hangars || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="structures-choices-input">
                                <InputGroup.Text id="drone-factories-input-group">
                                    Drone Factories
                                </InputGroup.Text>
                                <Form.Control 
                                    id="drone-factories-input"
                                    name="drone_factories"
                                    onChange={handleStructuresInputChange}
                                    value={structuresChoices.drone_factories || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="structures-choices-input">
                                <InputGroup.Text id="missile-silos-input-group">
                                    Missile Silos
                                </InputGroup.Text>
                                <Form.Control 
                                    id="missile-silos-input"
                                    name="missile_silos"
                                    onChange={handleStructuresInputChange}
                                    value={structuresChoices.missile_silos || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                            <InputGroup className="structures-choices-input">
                                <InputGroup.Text id="workshops-input-group">
                                    Workshops
                                </InputGroup.Text>
                                <Form.Control 
                                    id="workshops-input"
                                    name="workshops"
                                    onChange={handleStructuresInputChange}
                                    value={structuresChoices.workshops || ""} 
                                    placeholder=""
                                />
                            </InputGroup>
                        </div>
                    </div>
                </div>
                {props.loading.kingdomid
                ? <Button className="submit-kingdom-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="submit-kingdom-button" variant="primary" type="submit" onClick={onSubmitKingdomClick}>
                    Submit
                </Button>
                }
                {
                    kdMessage !== ""
                    ? <h4>{kdMessage}</h4>
                    : null
                }
            </div>
            : <h2>Kingdom Created!</h2>
        }
        </div>
    )
}

export default CreateKingdom;