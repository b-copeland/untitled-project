import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import "./structures.css"


function Structures(props) {
    const [homesInput, setHomesInput] = useState('');
    const [minesInput, setMinesInput] = useState('');
    const [fuelPlantsInput, setFuelPlantsInput] = useState('');
    const [hangarsInput, setHangarsInput] = useState('');
    const [droneFactoriesInput, setDroneFactoriesInput] = useState('');
    const [missileSilosInput, setMissileSilosInput] = useState('');
    const [workshopsInput, setWorkshopsInput] = useState('');
    const [reloading, setReloading] = useState(false);

    const handleHomesInput = (e) => {
        setHomesInput(e.target.value);
    }
    const handleMinesInput = (e) => {
        setMinesInput(e.target.value);
    }
    const handleFuelPlantsInput = (e) => {
        setFuelPlantsInput(e.target.value);
    }
    const handleHangarsInput = (e) => {
        setHangarsInput(e.target.value);
    }
    const handleDroneFactoriesInput = (e) => {
        setDroneFactoriesInput(e.target.value);
    }
    const handleMissileSilosInput = (e) => {
        setMissileSilosInput(e.target.value);
    }
    const handleWorkshopsInput = (e) => {
        setWorkshopsInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (
            homesInput || minesInput || fuelPlantsInput || hangarsInput || droneFactoriesInput || missileSilosInput || workshopsInput
        ) {
            let opts = {
                'homes': homesInput === '' ? undefined : homesInput,
                'mines': minesInput === '' ? undefined : minesInput,
                'fuel_plants': fuelPlantsInput === '' ? undefined : fuelPlantsInput,
                'hangars': hangarsInput === '' ? undefined : hangarsInput,
                'drone_factories': droneFactoriesInput === '' ? undefined : droneFactoriesInput,
                'missile_silos': missileSilosInput === '' ? undefined : missileSilosInput,
                'workshops': workshopsInput === '' ? undefined : workshopsInput,
            };
            const updateFunc = () => authFetch('api/structures', {
                method: 'post',
                body: JSON.stringify(opts)
            })
            props.updateData(['structures'], [updateFunc])
            setHomesInput('');
            setMinesInput('');
            setFuelPlantsInput('');
            setHangarsInput('');
            setDroneFactoriesInput('');
            setMissileSilosInput('');
            setWorkshopsInput('');
        }
    }

    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;

    if (Object.keys(props.data.structures).length === 0) {
        return null;
    }
    if (Object.keys(props.data.kingdom).length === 0) {
        return null;
    }
    const structuresInfo = props.data.structures;
    const kdInfo = props.data.kingdom;
    return (
        <div className="structures">
            <div className="text-box structures-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Build Time</span>
                    <span className="text-box-item-value">8h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Build Cost</span>
                    <span className="text-box-item-value">{structuresInfo["price"]}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Structures</span>
                    <span className="text-box-item-value">{structuresInfo["max_available_structures"]}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Stuctures</span>
                    <span className="text-box-item-value">{structuresInfo["current_available_structures"]}</span>
                </div>
            </div>
            <Table className="structures-table" striped bordered hover>
                <thead>
                    <tr>
                        <th>Structure</th>
                        <th>% Built</th>
                        <th># Built</th>
                        <th># Building</th>
                        <th>To Build</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Homes</td>
                        <td>{displayPercent((structuresInfo.current.homes || 0) / kdInfo["stars"])}</td>
                        <td>{(structuresInfo.current.homes || 0)}</td>
                        <td>{(structuresInfo.hour_24.homes || 0)}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="homes-input"
                                onChange={handleHomesInput}
                                value={homesInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Mines</td>
                        <td>{displayPercent((structuresInfo.current.mines || 0) / kdInfo["stars"])}</td>
                        <td>{(structuresInfo.current.mines || 0)}</td>
                        <td>{(structuresInfo.hour_24.mines || 0)}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="mines-input"
                                onChange={handleMinesInput}
                                value={minesInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Fuel Plants</td>
                        <td>{displayPercent((structuresInfo.current.fuel_plants || 0) / kdInfo["stars"])}</td>
                        <td>{(structuresInfo.current.fuel_plants || 0)}</td>
                        <td>{(structuresInfo.hour_24.fuel_plants || 0)}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="fuel-plants-input"
                                onChange={handleFuelPlantsInput}
                                value={fuelPlantsInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Hangars</td>
                        <td>{displayPercent((structuresInfo.current.hangars || 0) / kdInfo["stars"])}</td>
                        <td>{(structuresInfo.current.hangars || 0)}</td>
                        <td>{(structuresInfo.hour_24.hangars || 0)}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="hangars-input"
                                onChange={handleHangarsInput}
                                value={hangarsInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Drone Factories</td>
                        <td>{displayPercent((structuresInfo.current.drone_factories || 0) / kdInfo["stars"])}</td>
                        <td>{(structuresInfo.current.drone_factories || 0)}</td>
                        <td>{(structuresInfo.hour_24.drone_factories || 0)}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="drone-factories-input"
                                onChange={handleDroneFactoriesInput}
                                value={droneFactoriesInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Missile Silos</td>
                        <td>{displayPercent((structuresInfo.current.missile_silos || 0) / kdInfo["stars"])}</td>
                        <td>{(structuresInfo.current.missile_silos || 0)}</td>
                        <td>{(structuresInfo.hour_24.missile_silos || 0)}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="missile-silos-input"
                                onChange={handleMissileSilosInput}
                                value={missileSilosInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Workshops</td>
                        <td>{displayPercent((structuresInfo.current.workshops || 0) / kdInfo["stars"])}</td>
                        <td>{(structuresInfo.current.workshops || 0)}</td>
                        <td>{(structuresInfo.hour_24.workshops || 0)}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="workshops-input"
                                onChange={handleWorkshopsInput}
                                value={workshopsInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                </tbody>
            </Table>
            {props.loading.structures
            ? <Button className="structures-button" variant="primary" type="submit" disabled>
                Loading...
            </Button>
            : <Button className="structures-button" variant="primary" type="submit" onClick={onSubmitClick}>
                Build
            </Button>
            }
            {/* <Button variant="primary" type="submit" onClick={onSubmitClick}>
                Settle
            </Button> */}
        </div>
        )
}

export default Structures;