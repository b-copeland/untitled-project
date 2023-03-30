import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./structures.css"

const initialStructuresValues = {
    "homes": "",
    "mines": "",
    "fuel_plants": "",
    "hangars": "",
    "drone_factories": "",
    "missile_silos": "",
    "workshops": ""
}

function Structures(props) {
    const [reloading, setReloading] = useState(false);
    const [structuresResult, setStructuresResult] = useState([]);
    const [structuresInput, setStructuresInput] = useState(initialStructuresValues);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setStructuresInput({
          ...structuresInput,
          [name]: value,
        });
      };

    const onSubmitClick = (e)=>{
        let opts = structuresInput;
        const updateFunc = () => authFetch('api/structures', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setStructuresResult(structuresResult.concat(r)))
        props.updateData(['structures', 'kingdom'], [updateFunc])
        setStructuresInput(initialStructuresValues);
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
    const toasts = structuresResult.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setStructuresResult(structuresResult.slice(0, index).concat(structuresResult.slice(index + 1, 999)))}
            show={true}
            bg={results.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Structures Results</strong>
            </Toast.Header>
            <Toast.Body>{results.message}</Toast.Body>
        </Toast>
    )
    const calcStructuresStarsUsed = (structuresInput) => {
        var total = 0
        for (const structure in structuresInput) {
            total += (parseInt(structuresInput[structure] || 0));
        }
        return total
    }
    const structuresStars = calcStructuresStarsUsed(structuresInput)
    const structuresCost = structuresStars * structuresInfo.price
    return (
        <div className="structures">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="text-box structures-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Build Time</span>
                    <span className="text-box-item-value">8h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Build Cost</span>
                    <span className="text-box-item-value">{structuresInfo["price"].toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Structures</span>
                    <span className="text-box-item-value">{structuresInfo["max_available_structures"].toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Stuctures</span>
                    <span className="text-box-item-value">{structuresInfo["current_available_structures"].toLocaleString()}</span>
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
                        <td>{Math.floor(structuresInfo.current.homes || 0).toLocaleString()}</td>
                        <td>{Math.floor(structuresInfo.hour_24.homes || 0).toLocaleString()}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="homes-input"
                                name="homes"
                                onChange={handleInputChange}
                                value={structuresInput.homes || ""} 
                                placeholder="0"
                                autoComplete="off"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Mines</td>
                        <td>{displayPercent((structuresInfo.current.mines || 0) / kdInfo["stars"])}</td>
                        <td>{Math.floor(structuresInfo.current.mines || 0).toLocaleString()}</td>
                        <td>{Math.floor(structuresInfo.hour_24.mines || 0).toLocaleString()}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="mines-input"
                                name="mines"
                                onChange={handleInputChange}
                                value={structuresInput.mines || ""} 
                                placeholder="0"
                                autoComplete="off"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Fuel Plants</td>
                        <td>{displayPercent((structuresInfo.current.fuel_plants || 0) / kdInfo["stars"])}</td>
                        <td>{Math.floor(structuresInfo.current.fuel_plants || 0).toLocaleString()}</td>
                        <td>{Math.floor(structuresInfo.hour_24.fuel_plants || 0).toLocaleString()}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="fuel-plants-input"
                                name="fuel_plants"
                                onChange={handleInputChange}
                                value={structuresInput.fuel_plants || ""} 
                                placeholder="0"
                                autoComplete="off"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Hangars</td>
                        <td>{displayPercent((structuresInfo.current.hangars || 0) / kdInfo["stars"])}</td>
                        <td>{Math.floor(structuresInfo.current.hangars || 0).toLocaleString()}</td>
                        <td>{Math.floor(structuresInfo.hour_24.hangars || 0).toLocaleString()}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="hangars-input"
                                name="hangars"
                                onChange={handleInputChange}
                                value={structuresInput.hangars || ""} 
                                placeholder="0"
                                autoComplete="off"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Drone Factories</td>
                        <td>{displayPercent((structuresInfo.current.drone_factories || 0) / kdInfo["stars"])}</td>
                        <td>{Math.floor(structuresInfo.current.drone_factories || 0).toLocaleString()}</td>
                        <td>{Math.floor(structuresInfo.hour_24.drone_factories || 0).toLocaleString()}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="drone-factories-input"
                                name="drone_factories"
                                onChange={handleInputChange}
                                value={structuresInput.drone_factories || ""} 
                                placeholder="0"
                                autoComplete="off"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Missile Silos</td>
                        <td>{displayPercent((structuresInfo.current.missile_silos || 0) / kdInfo["stars"])}</td>
                        <td>{Math.floor(structuresInfo.current.missile_silos || 0).toLocaleString()}</td>
                        <td>{Math.floor(structuresInfo.hour_24.missile_silos || 0).toLocaleString()}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="missile-silos-input"
                                name="missile_silos"
                                onChange={handleInputChange}
                                value={structuresInput.missile_silos || ""} 
                                placeholder="0"
                                autoComplete="off"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Workshops</td>
                        <td>{displayPercent((structuresInfo.current.workshops || 0) / kdInfo["stars"])}</td>
                        <td>{Math.floor(structuresInfo.current.workshops || 0).toLocaleString()}</td>
                        <td>{Math.floor(structuresInfo.hour_24.workshops || 0).toLocaleString()}</td>
                        <td className="structures-form-data">{
                            <Form.Control 
                                className="structures-form"
                                id="workshops-input"
                                name="workshops"
                                onChange={handleInputChange}
                                value={structuresInput.workshops || ""} 
                                placeholder="0"
                                autoComplete="off"
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
            {
                structuresStars !== 0
                ? <div>
                    <h3>Structures Cost: {structuresCost.toLocaleString()}</h3>
                    <h3>Stars Remaining: {(structuresInfo.max_available_structures - structuresStars).toLocaleString()}</h3>
                </div>
                : null
            }
        </div>
        )
}

export default Structures;