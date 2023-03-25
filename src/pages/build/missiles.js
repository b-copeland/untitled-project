import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./missiles.css";

const initialInput = {
    "planet_busters": "",
    "star_busters": "",
    "galaxy_busters": "",
}

function Missiles(props) {
    const [missilesResult, setMissilesResult] = useState([]);
    const [input, setInput] = useState(initialInput);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput({
          ...input,
          [name]: value,
        });
      };

    if (Object.keys(props.data.kingdom).length === 0) {
        return null;
    }
    if (Object.keys(props.data.missiles).length === 0) {
        return null;
    }
    const kdInfo = props.data.kingdom;
    const missilesInfo = props.data.missiles;

    const onSubmitClick = (e)=>{
        let opts = input;
        const updateFunc = () => authFetch('api/missiles', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setMissilesResult(missilesResult.concat(r)))
        props.updateData(['missiles', 'kingdom'], [updateFunc]);
    }
    const toHHMMSS = (secs) => {
        var sec_num = parseInt(secs, 10)
        var hours   = Math.floor(sec_num / 3600)
        var minutes = Math.floor(sec_num / 60) % 60
        var seconds = sec_num % 60
    
        return [hours,minutes,seconds]
            .map(v => v < 10 ? "0" + v : v)
            .filter((v,i) => v !== "00" || i > 0)
            .join(":")
    }
    const calcMissilesCosts = (input, desc) => {
        var total = 0
        for (const missile in input) {
            total += (parseInt(input[missile] || 0) * desc[missile]["cost"]);
        }
        return total
    }
    const calcMissilesFuelCosts = (input, desc) => {
        var total = 0
        for (const missile in input) {
            total += (parseInt(input[missile] || 0) * desc[missile]["fuel_cost"]);
        }
        return total
    }
    const missilesCost = calcMissilesCosts(input, missilesInfo.desc);
    const missilesFuelCost = calcMissilesFuelCosts(input, missilesInfo.desc);
    const toasts = missilesResult.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setMissilesResult(missilesResult.slice(0, index).concat(missilesResult.slice(index + 1, 999)))}
            show={true}
            bg={results.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Structures Results</strong>
            </Toast.Header>
            <Toast.Body>{results.message}</Toast.Body>
        </Toast>
    )
    return (
        <div className="missiles">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <Table className="missiles-table" striped bordered hover>
                <thead>
                    <tr>
                        <th>Missile</th>
                        <th>Built</th>
                        <th>Building</th>
                        <th>Capacity</th>
                        <th>Build Time</th>
                        <th>Cost</th>
                        <th>Fuel Cost</th>
                        <th>Stars Damage</th>
                        <th>Fuel Damage</th>
                        <th>Pop Damage</th>
                        <th>To Build</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Planet Buster</td>
                        <td>{(missilesInfo.current.planet_busters || 0).toLocaleString()}</td>
                        <td>{(missilesInfo.building.planet_busters || 0).toLocaleString()}</td>
                        <td>{(missilesInfo.capacity || 0).toLocaleString()}</td>
                        <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                        <td>{Math.floor(missilesInfo.desc.planet_busters.cost || 0).toLocaleString()}</td>
                        <td>{Math.floor(missilesInfo.desc.planet_busters.fuel_cost || 0).toLocaleString()}</td>
                        <td>{(missilesInfo.desc.planet_busters.stars_damage || 0)}</td>
                        <td>{(missilesInfo.desc.planet_busters.fuel_damage || 0)}</td>
                        <td>{(missilesInfo.desc.planet_busters.pop_damage || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="missiles-form"
                                id="planet-busters-input"
                                name="planet_busters"
                                onChange={handleInputChange}
                                value={input.planet_busters || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    {
                        kdInfo.completed_projects.indexOf('star_busters') >= 0
                        ? <tr>
                            <td>Star Buster</td>
                            <td>{(missilesInfo.current.star_busters || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.building.star_busters || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.capacity || 0).toLocaleString()}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{Math.floor(missilesInfo.desc.star_busters.cost || 0).toLocaleString()}</td>
                            <td>{Math.floor(missilesInfo.desc.star_busters.fuel_cost || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.desc.star_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="star-busters-input"
                                    name="star_busters"
                                    onChange={handleInputChange}
                                    value={input.star_busters || ""} 
                                    placeholder="0"
                                />
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Star Buster</td>
                            <td colSpan={2}>Research "Star Busters" Project to Unlock</td>
                            <td>{(missilesInfo.capacity || 0).toLocaleString()}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{Math.floor(missilesInfo.desc.star_busters.cost || 0).toLocaleString()}</td>
                            <td>{Math.floor(missilesInfo.desc.star_busters.fuel_cost || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.desc.star_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="star-busters-input"
                                    name="star_busters"
                                    onChange={handleInputChange}
                                    value={input.star_busters || ""} 
                                    placeholder="0"
                                    disabled
                                />
                            }</td>
                        </tr>
                    }
                    {
                        kdInfo.completed_projects.indexOf('galaxy_busters') >= 0
                        ? <tr>
                            <td>Galaxy Buster</td>
                            <td>{(missilesInfo.current.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.building.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.capacity || 0).toLocaleString()}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{Math.floor(missilesInfo.desc.galaxy_busters.cost || 0).toLocaleString()}</td>
                            <td>{Math.floor(missilesInfo.desc.galaxy_busters.fuel_cost || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="galaxy-busters-input"
                                    name="galaxy_busters"
                                    onChange={handleInputChange}
                                    value={input.galaxy_busters || ""} 
                                    placeholder="0"
                                />
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Galaxy Buster</td>
                            <td colSpan={2}>Research "Galaxy Busters" Project to Unlock</td>
                            <td>{(missilesInfo.capacity || 0).toLocaleString()}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{Math.floor(missilesInfo.desc.galaxy_busters.cost || 0).toLocaleString()}</td>
                            <td>{Math.floor(missilesInfo.desc.galaxy_busters.fuel_cost || 0).toLocaleString()}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="galaxy-busters-input"
                                    name="galaxy_busters"
                                    onChange={handleInputChange}
                                    value={input.galaxy_busters || ""} 
                                    placeholder="0"
                                    disabled
                                />
                            }</td>
                        </tr>
                    }
                </tbody>
            </Table>
            {
                props.loading.missiles
                ? <Button className="missiles-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="missiles-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Build
                </Button>
            }
            {
                missilesCost !== 0
                ? <div>
                    <h3>Missiles Cost: {missilesCost.toLocaleString()}</h3>
                    <h3>Missiles Fuel Cost: {missilesFuelCost.toLocaleString()}</h3>
                </div>
                : null
            }
        </div>
    )
}

export default Missiles;