import React, { useEffect, useState } from "react";
import {useNavigate} from "react-router-dom";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Select from 'react-select';
import "./createkingdom.css";
import HelpButton from "../components/helpbutton";

const initialStructuresChoices = {
    "homes": 60,
    "mines": 80,
    "fuel_plants": 30,
    "hangars": 48,
    "drone_factories": 60,
    "missile_silos": 0,
    "workshops": 12,
}

const initialUnitsChoices = {
    "drones": 2000,
    "recruits": 500,
    "attack": 500,
    "defense": 800,
    "flex": 500,
    "engineers": 500,
}

function CreateKingdom(props) {
    const [kdName, setKdName] = useState("");
    const [kdMessage, setKdMessage] = useState({});
    const [createKingdomData, setCreateKingdomData] = useState({});
    const [structuresChoices, setStructuresChoices] = useState(initialStructuresChoices);
    const [unitsChoices, setUnitsChoices] = useState(initialUnitsChoices);
    const [race, setRace] = useState();
    const [createLoading, setCreateLoading] = useState(false);
    const navigate = useNavigate();
    
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
    const handleRaceChange = (selectedOption) => {
        setRace(selectedOption.value);
    };

    const onSubmitNameClick = (e)=>{
        if (kdName != "") {
            let opts = {
                'kdName': kdName,
            };
            setKdMessage("");
            setCreateLoading(true);
            const updateFunc = () => authFetch('api/createkingdom', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => {setKdMessage(r);setCreateLoading(false)})
            props.updateData(['kingdomid'], [updateFunc])
        }
    }

    const onSubmitKingdomClick = (e)=>{
        let opts = {
            'unitsChoices': unitsChoices,
            'structuresChoices': structuresChoices,
            'race': race || "",
        };
        setKdMessage("")
        const updateFunc = () => authFetch('api/createkingdomchoices', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setKdMessage(r))
        props.updateData(['kingdomid'], [updateFunc])
    }

    const onClickGoHome = (e)=>{
        navigate("/status")
        props.updateData(['all'], [])
    }

    if (Object.keys(createKingdomData).length === 0) {
        return <h2>Loading...</h2>
    }
    if (Object.keys(props.state).length === 0) {
        return <h2>Loading...</h2>
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

    const calcOffense = (unitsData) => {
        var total = 0;
        for (const unit in unitsData) {
            const unitDesc = props.state.units[unit] || {};
            total += (unitDesc.offense || 0) * unitsData[unit]
        }
        return total
    }
    const calcDefense = (unitsData) => {
        var total = 0;
        for (const unit in unitsData) {
            const unitDesc = props.state.units[unit] || {};
            total += (unitDesc.defense || 0) * unitsData[unit]
        }
        return total
    }
    const calcUnitsFuelConsumption = (unitsData) => {
        var total = 0;
        for (const unit in unitsData) {
            const unitDesc = props.state.units[unit] || {};
            total += (unitDesc.fuel || 0) * unitsData[unit]
        }
        return total
    }
    const calcUnitsHangarCapacity = (unitsData) => {
        var total = 0;
        for (const unit in unitsData) {
            const unitDesc = props.state.units[unit] || {};
            total += (unitDesc.hangar_capacity || 0) * unitsData[unit]
        }
        return total
    }
    const offense = calcOffense(unitsChoices);
    const defense = calcDefense(unitsChoices);
    const unitsFuel = calcUnitsFuelConsumption(unitsChoices);
    const hangarCapacityUsed = calcUnitsHangarCapacity(unitsChoices);
    const maxPop = structuresChoices.homes * props.state.structures.pop_per_home;
    const popIncome = maxPop * props.state.income_per_pop;
    const popFuel = maxPop * props.state.fuel_consumption_per_pop;
    const minesIncome = structuresChoices.mines * props.state.structures.income_per_mine;
    const fuelPlantsIncome = structuresChoices.fuel_plants * props.state.structures.fuel_per_fuel_plant;
    const fuelPlantsCap = structuresChoices.fuel_plants * props.state.structures.fuel_cap_per_fuel_plant;
    const hangarCapacityMax = structuresChoices.hangars * props.state.structures.hangar_capacity;
    const droneProduction = structuresChoices.drone_factories * props.state.structures.drone_production_per_drone_plant;
    const missileCapacity = structuresChoices.missile_silos * props.state.structures.missile_capacity_per_missile_silo;
    const workshopCapacity = structuresChoices.workshops * props.state.structures.engineers_capacity_per_workshop;
    
    const raceOptions = props.state.races.map(race => ({value: race, "label": race}))
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
                        autoComplete="off"
                    />
                </InputGroup>
                {createLoading
                ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="submit-name-button" variant="primary" type="submit" onClick={onSubmitNameClick}>
                    Submit
                </Button>
                }
                {
                    kdMessage.message !== ""
                    ? <h4>{kdMessage.message}</h4>
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            </InputGroup>
                        </div>
                    </div>
                </div>
                <form className="race-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a Race
                    </label>
                    <Select id="select-race" className="race-select" options={raceOptions} onChange={handleRaceChange} autoFocus={false} 
                        styles={{
                            control: (baseStyles, state) => ({
                                ...baseStyles,
                                borderColor: state.isFocused ? 'var(--bs-body-color)' : 'var(--bs-primary-text)',
                                backgroundColor: 'var(--bs-body-bg)',
                            }),
                            placeholder: (baseStyles, state) => ({
                                ...baseStyles,
                                color: 'var(--bs-primary-text)',
                            }),
                            input: (baseStyles, state) => ({
                                ...baseStyles,
                                color: 'var(--bs-secondary-text)',
                            }),
                            option: (baseStyles, state) => ({
                                ...baseStyles,
                                backgroundColor: state.isFocused ? 'var(--bs-primary-bg-subtle)' : 'var(--bs-secondary-bg-subtle)',
                                color: state.isFocused ? 'var(--bs-primary-text)' : 'var(--bs-secondary-text)',
                            }),
                            menuList: (baseStyles, state) => ({
                                ...baseStyles,
                                backgroundColor: 'var(--bs-secondary-bg)',
                                // borderColor: 'var(--bs-secondary-bg)',
                            }),
                            singleValue: (baseStyles, state) => ({
                                ...baseStyles,
                                color: 'var(--bs-secondary-text)',
                            }),
                        }}/>
                </form>
                {props.loading.kingdomid
                ? <Button className="submit-kingdom-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="submit-kingdom-button" variant="primary" type="submit" onClick={onSubmitKingdomClick}>
                    Submit
                </Button>
                }
                {
                    kdMessage.message !== ""
                    ? <h4>{kdMessage.message}</h4>
                    : null
                }
                <div className="text-box kingdom-card">
                    <h4>Kingdom Stats</h4>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Offense</span>
                        <span className="text-box-item-value">{offense.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Defense</span>
                        <span className="text-box-item-value">{defense.toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Population</span>
                        <span className="text-box-item-value">{maxPop.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Income</span>
                        <span className="text-box-item-value">{(popIncome + minesIncome).toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Fuel Production</span>
                        <span className="text-box-item-value">{fuelPlantsIncome.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Fuel Usage</span>
                        <span className="text-box-item-value">{(unitsFuel + popFuel).toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Fuel Capacity</span>
                        <span className="text-box-item-value">{fuelPlantsCap.toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Hangar Capacity</span>
                        <span className="text-box-item-value">{hangarCapacityUsed.toLocaleString()} / {hangarCapacityMax.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Drones Production</span>
                        <span className="text-box-item-value">{droneProduction}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Missile Capacity</span>
                        <span className="text-box-item-value">{missileCapacity}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Workshop Capacity</span>
                        <span className="text-box-item-value">{unitsChoices.engineers.toLocaleString()} / {workshopCapacity.toLocaleString()}</span>
                    </div>
                </div>
            </div>
            : <div>
                <h2>Kingdom Created!</h2>
                <Button variant="primary" type="submit" onClick={onClickGoHome}>Go to Home</Button>
            </div>
        }
            <HelpButton scrollTarget={"createkingdom"}/>
        </div>
    )
}

export default CreateKingdom;