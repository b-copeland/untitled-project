import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./projects.css";

function ProjectsContent() {
    const [kdInfo, setKdInfo] = useState({});
    const [engineersInfo, setEngineersInfo] = useState({});
    const [projectsInfo, setProjectsInfo] = useState({});
    const [reloading, setReloading] = useState(false);
    
    useEffect(() => {
        const fetchData = async () => {
            await authFetch("api/kingdom").then(r => r.json()).then(r => setKdInfo(r));
            await authFetch("api/engineers").then(r => r.json()).then(r => setEngineersInfo(r));
            await authFetch("api/projects").then(r => r.json()).then(r => setProjectsInfo(r));
            setReloading(false);
        }
        fetchData();
    }, [reloading])

    return (
        <Tabs
          id="controlled-tab-example"
          defaultActiveKey="train"
          justify
          fill
          variant="tabs"
        >
          <Tab eventKey="train" title="Train">
            <Train kdInfo={kdInfo} engineersInfo={engineersInfo} reloading={reloading} setReloading={v => setReloading(v)}/>
          </Tab>
          <Tab eventKey="assign" title="Assign">
            <Assign kdInfo={kdInfo} engineersInfo={engineersInfo} projectsInfo={projectsInfo} reloading={reloading} setReloading={v => setReloading(v)}/>
          </Tab>
        </Tabs>
    )
}

function Train(props) {
    const [engineersInput, setEngineersInput] = useState();

    const handleEngineersInput = (e) => {
        setEngineersInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (engineersInput > 0) {
            let opts = {
                'engineersInput': engineersInput,
            };
            authFetch('api/engineers', {
                method: 'post',
                body: JSON.stringify(opts)
            });
            props.setReloading(true);
        }
    }
    if (Object.keys(props.engineersInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div className="engineers">
            <div className="text-box engineers-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Time</span>
                    <span className="text-box-item-value">12h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Cost</span>
                    <span className="text-box-item-value">{props.engineersInfo.engineers_price}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Workshop Capacity</span>
                    <span className="text-box-item-value">
                        {props.engineersInfo.current_workshop_capacity} / {props.engineersInfo.max_workshop_capacity} ({displayPercent(props.engineersInfo.current_workshop_capacity / props.engineersInfo.max_workshop_capacity)})
                    </span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_engineers}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.engineers_building}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.max_available_engineers}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_available_engineers}</span>
                </div>
                <InputGroup className="engineers-input-group">
                    <InputGroup.Text id="engineers-input-display">
                        New Engineers
                    </InputGroup.Text>
                    <Form.Control 
                        id="engineers-input"
                        onChange={handleEngineersInput}
                        value={engineersInput || ""} 
                        placeholder="0"
                    />
                </InputGroup>
                {props.reloading
                ? <Button className="engineers-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="engineers-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Train
                </Button>
                }
            </div>
        </div>
    )
}

const initialProjectsValues = {
    "pop_bonus": "",
    "fuel_bonus": "",
    "military_bonus": "",
    "money_bonus": "",
    "general_bonus": "",
    "spy_bonus": "",
    "big_flexers": "",
    "star_busters": "",
    "galaxy_busters": "",
    "drone_gadgets": "",
}

function Assign(props) {
    const [assignValues, setAssignValues] = useState(initialProjectsValues);
    const [addValues, setAddValues] = useState(initialProjectsValues);

    const handleAssignInputChange = (e) => {
        const { name, value } = e.target;
        setAssignValues({
          ...assignValues,
          [name]: value,
        });
      };
      const handleAddInputChange = (e) => {
          const { name, value } = e.target;
          setAddValues({
            ...addValues,
            [name]: value,
          });
        };

    const onAssignClick = (e)=>{
        const assignOpts = {};
        for (const [key, value] of Object.entries(assignValues)) {
            if (value != "") {
                assignOpts[key] = value
            }
        }
        const hasAssign = Object.keys(assignOpts).length > 0;
        if (hasAssign) {
            const opts = {"assign": assignOpts}
            authFetch('api/projects', {
                method: 'post',
                body: JSON.stringify(opts)
            });
            props.setReloading(true);
        }
        setAssignValues(initialProjectsValues);
    }

    const onAddClick = (e)=>{
        const addOpts = {};
        for (const [key, value] of Object.entries(addValues)) {
            if (value != "") {
                addOpts[key] = value
            }
        }
        const hasAdd = Object.keys(addOpts).length > 0;
        if (hasAdd){
            const opts = {"add": addOpts}
            authFetch('api/projects', {
                method: 'post',
                body: JSON.stringify(opts)
            });
            props.setReloading(true);
        }
        setAddValues(initialProjectsValues);
    }

    const OnClearAllClick = (e)=>{
        const opts = {
            "clear": Object.keys(initialProjectsValues)
        };
        authFetch('api/projects', {
            method: 'post',
            body: JSON.stringify(opts)
        });
        props.setReloading(true);
    }

    const OnClearClick = (e)=>{
        const opts = {
            "clear": [e.target.name]
        };
        authFetch('api/projects', {
            method: 'post',
            body: JSON.stringify(opts)
        });
        props.setReloading(true);
    }
    if (Object.keys(props.engineersInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.projectsInfo).length === 0) {
        return null;
    }
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div className="projects">
            <div className="text-box projects-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Total Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_engineers}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available Engineers</span>
                    <span className="text-box-item-value">{props.projectsInfo.available_engineers}</span>
                </div>
            </div>
            <Table className="projects-table" striped bordered hover size="sm">
                <thead>
                    <tr><th colSpan={10}>Continuous Projects</th></tr>
                    <tr>
                        <th>Project</th>
                        <th>Assigned Engineers</th>
                        <th>Assigned %</th>
                        <th>Current Pts</th>
                        <th>Max Pts</th>
                        <th>Current Bonus</th>
                        <th>Max Bonus</th>
                        <th>Assign</th>
                        <th>Add</th>
                        <th>Remove</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Pop Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.pop_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.pop_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.pop_bonus || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.pop_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.pop_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.pop_bonus || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="pop-bonus-assign-input"
                                onChange={handleAssignInputChange}
                                name="pop_bonus"
                                value={assignValues.pop_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="pop-bonus-add-input"
                                onChange={handleAddInputChange}
                                name="pop_bonus"
                                value={addValues.pop_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="pop_bonus" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="pop_bonus" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.pop_bonus || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    <tr>
                        <td>Fuel Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.fuel_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.fuel_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.fuel_bonus || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.fuel_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.fuel_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.fuel_bonus || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="fuel-bonus-assign-input"
                                onChange={handleAssignInputChange}
                                name="fuel_bonus"
                                value={assignValues.fuel_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="fuel-bonus-add-input"
                                onChange={handleAddInputChange}
                                name="fuel_bonus"
                                value={addValues.fuel_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="fuel_bonus" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="fuel_bonus" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.fuel_bonus || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    <tr>
                        <td>Military Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.military_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.military_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.military_bonus || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.military_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.military_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.military_bonus || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="military-bonus-assign-input"
                                onChange={handleAssignInputChange}
                                name="military_bonus"
                                value={assignValues.military_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="military-bonus-add-input"
                                onChange={handleAddInputChange}
                                name="military_bonus"
                                value={addValues.military_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="military_bonus" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="military_bonus" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.military_bonus || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    <tr>
                        <td>Money Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.money_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.money_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.money_bonus || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.money_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.money_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.money_bonus || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="money-bonus-assign-input"
                                onChange={handleAssignInputChange}
                                name="money_bonus"
                                value={assignValues.money_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="money-bonus-add-input"
                                onChange={handleAddInputChange}
                                name="money_bonus"
                                value={addValues.money_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="money_bonus" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="money_bonus" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.money_bonus || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    <tr>
                        <td>Generals Speed Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.general_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.general_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.general_bonus || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.general_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.general_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.general_bonus || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="general-bonus-assign-input"
                                onChange={handleAssignInputChange}
                                name="general_bonus"
                                value={assignValues.general_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="general-bonus-add-input"
                                onChange={handleAddInputChange}
                                name="general_bonus"
                                value={addValues.general_bonus || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="general_bonus" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="general_bonus" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.general_bonus || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    {
                        props.kdInfo.completed_projects.indexOf('drone_gadgets') >= 0
                        ? <tr>
                            <td>Spy Bonus</td>
                            <td>{(props.kdInfo.projects_assigned.spy_bonus || 0)}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.spy_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{(props.kdInfo.projects_points.spy_bonus || 0)}</td>
                            <td>{(props.kdInfo.projects_max_points.spy_bonus || 0)}</td>
                            <td>{displayPercent(props.projectsInfo.current_bonuses.spy_bonus || 0)}</td>
                            <td>{displayPercent(props.projectsInfo.max_bonuses.spy_bonus || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="spy-bonus-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="spy_bonus"
                                    value={assignValues.spy_bonus || ""} 
                                    placeholder="0"
                                />
                            }</td>
                            <td>{
                                <Form.Control 
                                    className="projects-add-form"
                                    id="spy-bonus-add-input"
                                    onChange={handleAddInputChange}
                                    name="spy_bonus"
                                    value={addValues.spy_bonus || ""} 
                                    placeholder="0"
                                />
                            }</td>
                            <td>{
                                props.reloading
                                ? <Button className="remove-button" name="spy_bonus" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="spy_bonus" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.spy_bonus || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Spy Bonus</td>
                            <td colSpan={2}>Complete "Drone Gadgets" Project to Unlock</td>
                            <td>{(props.kdInfo.projects_points.spy_bonus || 0)}</td>
                            <td>{(props.kdInfo.projects_max_points.spy_bonus || 0)}</td>
                            <td>{displayPercent(props.projectsInfo.current_bonuses.spy_bonus || 0)}</td>
                            <td>{displayPercent(props.projectsInfo.max_bonuses.spy_bonus || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="spy-bonus-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="pop"
                                    value={assignValues.spy_bonus || ""} 
                                    placeholder="0"
                                    disabled
                                />
                            }</td>
                            <td>{
                                <Form.Control 
                                    className="projects-add-form"
                                    id="spy-bonus-add-input"
                                    onChange={handleAddInputChange}
                                    name="pop"
                                    value={addValues.spy_bonus || ""} 
                                    placeholder="0"
                                    disabled
                                />
                            }</td>
                            <td></td>
                        </tr>
                    }
                </tbody>
                <thead>
                    <tr><th colSpan={10}>One-Time Projects</th></tr>
                    <tr>
                        <th>Project</th>
                        <th>Assigned Engineers</th>
                        <th>Assigned %</th>
                        <th>Current Pts</th>
                        <th>Max Pts</th>
                        <th colspan={2}>% Completed</th>
                        <th>Assign</th>
                        <th>Add</th>
                        <th>Remove</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Big Flexers</td>
                        <td>{(props.kdInfo.projects_assigned.big_flexers || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.big_flexers || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.big_flexers || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.big_flexers || 0)}</td>
                        <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.big_flexers || 0)/(props.kdInfo.projects_max_points.big_flexers))}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="big-flexers-assign-input"
                                onChange={handleAssignInputChange}
                                name="big_flexers"
                                value={assignValues.big_flexers || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="big-flexers-add-input"
                                onChange={handleAddInputChange}
                                name="big_flexers"
                                value={addValues.big_flexers || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="big_flexers" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="big_flexers" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.big_flexers || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    <tr>
                        <td>Star Busters</td>
                        <td>{(props.kdInfo.projects_assigned.star_busters || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.star_busters || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.star_busters || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.star_busters || 0)}</td>
                        <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.star_busters || 0)/(props.kdInfo.projects_max_points.star_busters))}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="star-busters-assign-input"
                                onChange={handleAssignInputChange}
                                name="star_busters"
                                value={assignValues.star_busters || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="star-busters-add-input"
                                onChange={handleAddInputChange}
                                name="star_busters"
                                value={addValues.star_busters || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="star_busters" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="star_busters" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.star_busters || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    <tr>
                        <td>Galaxy Busters</td>
                        <td>{(props.kdInfo.projects_assigned.galaxy_busters || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.galaxy_busters || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.galaxy_busters || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.galaxy_busters || 0)}</td>
                        <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.galaxy_busters || 0)/(props.kdInfo.projects_max_points.galaxy_busters))}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="galaxy-busters-assign-input"
                                onChange={handleAssignInputChange}
                                name="galaxy_busters"
                                value={assignValues.galaxy_busters || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="galaxy-busters-add-input"
                                onChange={handleAddInputChange}
                                name="galaxy_busters"
                                value={addValues.galaxy_busters || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="galaxy_busters" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="galaxy_busters" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.galaxy_busters || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                    <tr>
                        <td>Drone Gadgets</td>
                        <td>{(props.kdInfo.projects_assigned.drone_gadgets || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.drone_gadgets || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{(props.kdInfo.projects_points.drone_gadgets || 0)}</td>
                        <td>{(props.kdInfo.projects_max_points.drone_gadgets || 0)}</td>
                        <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.drone_gadgets || 0)/(props.kdInfo.projects_max_points.drone_gadgets))}</td>
                        <td>{
                            <Form.Control 
                                className="projects-assign-form"
                                id="drone-gadgets-assign-input"
                                onChange={handleAssignInputChange}
                                name="drone_gadgets"
                                value={assignValues.drone_gadgets || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            <Form.Control 
                                className="projects-add-form"
                                id="drone-gadgets-add-input"
                                onChange={handleAddInputChange}
                                name="drone_gadgets"
                                value={addValues.drone_gadgets || ""} 
                                placeholder="0"
                            />
                        }</td>
                        <td>{
                            props.reloading
                            ? <Button className="remove-button" name="drone_gadgets" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="remove-button" name="drone_gadgets" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.drone_gadgets || 0) == 0}>
                                Remove
                            </Button>
                        }</td>
                    </tr>
                </tbody>
            </Table>
            <div className="projects-buttons">
                {
                    props.reloading
                    ? <Button className="projects-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="projects-button" variant="primary" type="submit" onClick={onAssignClick}>
                        Assign
                    </Button>
                }
                {
                    props.reloading
                    ? <Button className="projects-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="projects-button" variant="primary" type="submit" onClick={onAddClick}>
                        Add
                    </Button>
                }
                {
                    props.reloading
                    ? <Button className="projects-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="projects-button" variant="primary" type="submit" onClick={OnClearAllClick}>
                        Remove All
                    </Button>
                }
            </div>
        </div>
    )
}

export default ProjectsContent;