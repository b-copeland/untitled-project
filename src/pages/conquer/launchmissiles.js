import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Table from 'react-bootstrap/Table';
import InputGroup from 'react-bootstrap/InputGroup';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./launchmissiles.css";
import Select from 'react-select';
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";

const initialAttackerValues = {
    "planet_busters": "",
    "star_busters": "",
    "galaxy_busters": "",
}

function LaunchMissiles(props) {
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [calcMessage, setCalcMessage] = useState({"message": "Press calculate to project results"})
    const [loadingCalc, setLoadingCalc] = useState(false);
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [attackResults, setAttackResults] = useState([]);
    const [attackerValues, setAttackerValues] = useState(initialAttackerValues);
    const [defenderShields, setDefenderShielders] = useState("");

    useEffect(() => {
        if (props.initialKd != undefined) {
            const fetchData = async () => {
                await authFetch("api/kingdom/" + props.initialKd).then(r => r.json()).then(r => setTargetKdInfo(r));
            };
            fetchData();
        }
    }, []);
    
    const handleChange = (selectedOption) => {
        setSelected(selectedOption.value);
        const fetchData = async () => {
            await authFetch("api/kingdom/" + selectedOption.value).then(r => r.json()).then(r => setTargetKdInfo(r));
        };
        fetchData();
    };
    const handleAttackerChange = (e) => {
        const { name, value } = e.target;
        setAttackerValues({
          ...attackerValues,
          [name]: value,
        });
    };
    const handleShieldsChange = (e) => {
        setDefenderShielders(e.target.value);
    }
    const onClickAttack = () => {
        if (selected != undefined) {
            const opts = {
                "attackerValues": attackerValues,
            };
            const updateFunc = async () => authFetch('api/launchmissiles/' + selected, {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r)); setCalcMessage("")})
            props.updateData(['kingdom', 'missilehistory'], [updateFunc]);
        } else {
            setCalcMessage({"message": "Please select a target in order to attack"})
        }
    };
    const onClickCalculate = async (e) => {
        if (selected != undefined) {
            const opts = {
                "attackerValues": attackerValues,
                "defenderShields": defenderShields,
            };
            const updateFunc = async () => authFetch('api/calculatemissiles/' + selected, {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setCalcMessage(r))
            setLoadingCalc(true);
            await updateFunc();
            setLoadingCalc(false);
        } else {
            setCalcMessage({"message": "Please select a target in order to calculate"})
        }
    };
    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")"
        } else {
            return "Defender"
        }
        
    }
    const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => {
        return {"value": kdId, "label": kdFullLabel(kdId)}
    })
    const toasts = attackResults.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setAttackResults(attackResults.slice(0, index).concat(attackResults.slice(index + 1, 999)))}
            show={true}
            bg="primary"
        >
            <Toast.Header>
                <strong className="me-auto">Attack Results</strong>
            </Toast.Header>
            <Toast.Body  className="text-black">{results.message}</Toast.Body>
        </Toast>
    )

    return (
    <>
        <Header data={props.data} />
        <div className="attack">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <h2>Missiles</h2>
            <form className="attack-kingdom-form">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select a target (type to filter)
                </label>
                <Select className="attack-kingdom-select" options={kingdomOptions} onChange={handleChange} autoFocus={selected == undefined} defaultValue={kingdomOptions.filter(option => option.value === props.initialKd)}
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
            <div className="defender-stats">
                <h3>{kdFullLabel(selected)}</h3>
                {   targetKdInfo.hasOwnProperty("shields")
                    ? <InputGroup className="mb-3 missiles-input">
                        <Form.Control
                            className="unit-form"
                            id="missile-shields-input"
                            name="shields"
                            value={targetKdInfo.shields.missiles * 100 || ""} 
                            placeholder="Missile Shields"
                            disabled
                            autoComplete="off"
                        />
                        <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                    </InputGroup>
                    : <InputGroup className="mb-3 missiles-input">
                        <Form.Control
                            className="unit-form"
                            id="missile-shields-input"
                            name="shields"
                            onChange={handleShieldsChange}
                            value={defenderShields || ""} 
                            placeholder="Missile Shields"
                            autoComplete="off"
                        />
                        <InputGroup.Text id="basic-addon2" className="missile-shields-input-group-text">%</InputGroup.Text>
                    </InputGroup>
                }
            </div>
            <div className="attacker-stats">
                <h3>Missiles to Send</h3>
                <Table striped bordered hover size="sm" className="launch-missiles-table">
                    <thead>
                        <tr>
                            <th>Missile</th>
                            <th style={{textAlign: "right"}}>Available</th>
                            <th style={{textAlign: "right"}}>Stars Damage</th>
                            <th style={{textAlign: "right"}}>Fuel Damage</th>
                            <th style={{textAlign: "right"}}>Pop Damage</th>
                            <th style={{textAlign: "right"}}>To Send</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Planet Busters</td>
                            <td style={{textAlign: "right"}}>{props.data.kingdom.missiles?.planet_busters?.toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.planet_busters?.stars_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.planet_busters?.fuel_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.planet_busters?.pop_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>
                                <Form.Control 
                                    className="launch-missile-form"
                                    id="planet-busters-input"
                                    name="planet_busters"
                                    onChange={handleAttackerChange}
                                    value={attackerValues.planet_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                        <tr>
                            <td>Star Busters</td>
                            <td style={{textAlign: "right"}}>{props.data.kingdom.missiles?.star_busters?.toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.star_busters?.stars_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.star_busters?.fuel_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.star_busters?.pop_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>
                                <Form.Control 
                                    className="launch-missile-form"
                                    id="star-busters-input"
                                    name="star_busters"
                                    onChange={handleAttackerChange}
                                    value={attackerValues.star_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                        <tr>
                            <td>Galaxy Busters</td>
                            <td style={{textAlign: "right"}}>{props.data.kingdom.missiles?.galaxy_busters?.toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.galaxy_busters?.stars_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.galaxy_busters?.fuel_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.data.missiles.desc?.galaxy_busters?.pop_damage || 0)}</td>
                            <td style={{textAlign: "right"}}>
                                <Form.Control 
                                    className="launch-missile-form"
                                    id="galaxy-busters-input"
                                    name="galaxy_busters"
                                    onChange={handleAttackerChange}
                                    value={attackerValues.galaxy_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                    </tbody>
                </Table>
                <div className="text-box spy-results-box">
                    <span className="box-span">{calcMessage.message}</span>
                </div>
                <div className="attack-buttons">
                    {
                        loadingCalc
                        ? <Button className="calculate-button" variant="primary" type="submit" disabled>
                            Loading...
                        </Button>
                        : <Button className="calculate-button" variant="primary" type="submit" onClick={onClickCalculate}>
                            Calculate
                        </Button>
                    }
                    {
                        props.loading.kingdom
                        ? <Button className="attack-button" variant="primary" type="submit" disabled>
                            Loading...
                        </Button>
                        : <Button className="attack-button" variant="primary" type="submit" onClick={onClickAttack}>
                            Launch
                        </Button>
                    }
                </div>
            </div>
            <HelpButton scrollTarget={"launchmissiles"}/>
        </div>
        </>
    )
}

export default LaunchMissiles;