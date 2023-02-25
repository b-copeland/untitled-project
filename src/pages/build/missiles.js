import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import "./missiles.css";

function Missiles(props) {
    const [planetBustersInput, setPlanetBustersInput] = useState('');
    const [starBustersInput, setStarBustersInput] = useState('');
    const [galaxyBustersInput, setGalaxyBustersInput] = useState('');

    if (Object.keys(props.data.kingdom).length === 0) {
        return null;
    }
    if (Object.keys(props.data.missiles).length === 0) {
        return null;
    }
    const kdInfo = props.data.kingdom;
    const missilesInfo = props.data.missiles;
    const handlePlanetBustersInput = (e) => {
        setPlanetBustersInput(e.target.value);
    }
    const handleStarBustersInput = (e) => {
        setStarBustersInput(e.target.value);
    }
    const handleGalaxyBustersInput = (e) => {
        setGalaxyBustersInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (
            planetBustersInput || starBustersInput || galaxyBustersInput
        ) {
            let opts = {
                'planet_busters': planetBustersInput === '' ? undefined : planetBustersInput,
                'star_busters': starBustersInput === '' ? undefined : starBustersInput,
                'galaxy_busters': galaxyBustersInput === '' ? undefined : galaxyBustersInput,
            };
            const updateFunc = () => authFetch('api/missiles', {
                method: 'post',
                body: JSON.stringify(opts)
            })
            props.updateData(['missiles'], [updateFunc]);
        }
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
    return (
        <div className="missiles">
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
                        <td>{(missilesInfo.current.planet_busters || 0)}</td>
                        <td>{(missilesInfo.building.planet_busters || 0)}</td>
                        <td>{(missilesInfo.capacity || 0)}</td>
                        <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                        <td>{(missilesInfo.desc.planet_busters.cost || 0)}</td>
                        <td>{(missilesInfo.desc.planet_busters.fuel_cost || 0)}</td>
                        <td>{(missilesInfo.desc.planet_busters.stars_damage || 0)}</td>
                        <td>{(missilesInfo.desc.planet_busters.fuel_damage || 0)}</td>
                        <td>{(missilesInfo.desc.planet_busters.pop_damage || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="missiles-form"
                                id="planet-busters-input"
                                onChange={handlePlanetBustersInput}
                                value={planetBustersInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    {
                        kdInfo.completed_projects.indexOf('star_busters') >= 0
                        ? <tr>
                            <td>Star Buster</td>
                            <td>{(missilesInfo.current.star_busters || 0)}</td>
                            <td>{(missilesInfo.building.star_busters || 0)}</td>
                            <td>{(missilesInfo.capacity || 0)}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.cost || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.fuel_cost || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="star-busters-input"
                                    onChange={handleStarBustersInput}
                                    value={starBustersInput || ""} 
                                    placeholder="0"
                                />
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Star Buster</td>
                            <td colSpan={2}>Research "Star Busters" Project to Unlock</td>
                            <td>{(missilesInfo.capacity || 0)}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.cost || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.fuel_cost || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.star_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="star-busters-input"
                                    onChange={handleStarBustersInput}
                                    value={starBustersInput || ""} 
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
                            <td>{(missilesInfo.current.galaxy_busters || 0)}</td>
                            <td>{(missilesInfo.building.galaxy_busters || 0)}</td>
                            <td>{(missilesInfo.capacity || 0)}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.cost || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.fuel_cost || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="galaxy-busters-input"
                                    onChange={handleGalaxyBustersInput}
                                    value={galaxyBustersInput || ""} 
                                    placeholder="0"
                                />
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Galaxy Buster</td>
                            <td colSpan={2}>Research "Galaxy Busters" Project to Unlock</td>
                            <td>{(missilesInfo.capacity || 0)}</td>
                            <td>{toHHMMSS(missilesInfo.build_time || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.cost || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.fuel_cost || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.stars_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.fuel_damage || 0)}</td>
                            <td>{(missilesInfo.desc.galaxy_busters.pop_damage || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="missiles-form"
                                    id="galaxy-busters-input"
                                    onChange={handleGalaxyBustersInput}
                                    value={galaxyBustersInput || ""} 
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
        </div>
    )
}

export default Missiles;