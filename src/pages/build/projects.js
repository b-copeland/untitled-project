import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./projects.css";
import Header from "../../components/header";

function ProjectsContent(props) {
    const kdInfo = props.data.kingdom;
    const engineersInfo = props.data.engineers;
    const projectsInfo = props.data.projects;
    return (
    <>
        <Header data={props.data} />
        <Tabs
          id="controlled-tab-example"
          defaultActiveKey="train"
          justify
          fill
          variant="tabs"
        >
          <Tab eventKey="train" title="Train">
            <Train kdInfo={kdInfo} engineersInfo={engineersInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="assign" title="Assign">
            <Assign kdInfo={kdInfo} engineersInfo={engineersInfo} projectsInfo={projectsInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="allocate" title="Allocate">
            <Allocate kdInfo={kdInfo} engineersInfo={engineersInfo} projectsInfo={projectsInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
        </Tabs>
    </>
    )
}

function Train(props) {
    const [engineersInput, setEngineersInput] = useState("");
    const [engineersResult, setEngineersResult] = useState([]);

    const handleEngineersInput = (e) => {
        setEngineersInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (engineersInput > 0) {
            let opts = {
                'engineersInput': engineersInput,
            };
            const updateFunc = () => authFetch('api/engineers', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setEngineersResult(engineersResult.concat(r)))
            props.updateData(['engineers', 'kingdom'], [updateFunc]);
            setEngineersInput('');
        }
    }
    if (Object.keys(props.engineersInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const calcTrainCosts = (input) => parseInt(input || 0) * props.engineersInfo.engineers_price;
    const trainCosts = calcTrainCosts(engineersInput);
    const toasts = engineersResult.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setEngineersResult(engineersResult.slice(0, index).concat(engineersResult.slice(index + 1, 999)))}
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
        <div className="engineers">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="text-box engineers-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Time</span>
                    <span className="text-box-item-value">12h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Cost</span>
                    <span className="text-box-item-value">{props.engineersInfo.engineers_price?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Workshop Capacity</span>
                    <span className="text-box-item-value">
                        {props.engineersInfo.current_workshop_capacity?.toLocaleString()} / {props.engineersInfo.max_workshop_capacity?.toLocaleString()} ({displayPercent(props.engineersInfo.current_workshop_capacity / props.engineersInfo.max_workshop_capacity)})
                    </span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.engineers_building?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.max_available_engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_available_engineers?.toLocaleString()}</span>
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
                        autoComplete="off"
                    />
                </InputGroup>
                {props.loading.engineers
                ? <Button className="engineers-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="engineers-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Train
                </Button>
                }
                {
                    trainCosts !== 0
                    ? <h3>Engineers Cost: {trainCosts.toLocaleString()}</h3>
                    : null
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
    const [assignResult, setAssignResult] = useState([]);

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
            const updateFunc = () => authFetch('api/projects', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setAssignResult(assignResult.concat(r)))
            props.updateData(['projects', 'kingdom'], [updateFunc]);
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
            const updateFunc = () => authFetch('api/projects', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setAssignResult(assignResult.concat(r)))
            props.updateData(['projects', 'kingdom'], [updateFunc]);
        }
        setAddValues(initialProjectsValues);
    }

    const OnClearAllClick = (e)=>{
        const opts = {
            "clear": Object.keys(initialProjectsValues)
        };
        const updateFunc = () => authFetch('api/projects', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setAssignResult(assignResult.concat(r)))
        props.updateData(['projects', 'kingdom'], [updateFunc]);
    }

    const OnClearClick = (e)=>{
        const opts = {
            "clear": [e.target.name]
        };
        const updateFunc = () => authFetch('api/projects', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setAssignResult(assignResult.concat(r)))
        props.updateData(['projects', 'kingdom'], [updateFunc]);
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
    const calcEngineersAssigned = (assignValues) => {
        var total = 0
        for (const assign in assignValues) {
            total += (parseInt(assignValues[assign] || 0));
        }
        return total
    }
    const calcEngineersAdd = (addValues) => {
        var total = 0
        for (const addVal in addValues) {
            total += (parseInt(addValues[addVal] || 0));
        }
        return total
    }
    const engineersAssigned = calcEngineersAssigned(assignValues);
    const engineersAdded = calcEngineersAdd(addValues);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const toasts = assignResult.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setAssignResult(assignResult.slice(0, index).concat(assignResult.slice(index + 1, 999)))}
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
        <div className="projects">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="text-box projects-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Total Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available Engineers</span>
                    <span className="text-box-item-value">{props.projectsInfo.available_engineers?.toLocaleString()}</span>
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
                        <td>{(props.kdInfo.projects_assigned.pop_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.pop_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.pop_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.pop_bonus || 0).toLocaleString()}</td>
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
                                autoComplete="off"
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
                                autoComplete="off"
                            />
                        }</td>
                        <td>{
                            props.loading.projects
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
                        <td>{(props.kdInfo.projects_assigned.fuel_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.fuel_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.fuel_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.fuel_bonus || 0).toLocaleString()}</td>
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
                                autoComplete="off"
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
                                autoComplete="off"
                            />
                        }</td>
                        <td>{
                            props.loading.projects
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
                        <td>{(props.kdInfo.projects_assigned.military_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.military_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.military_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.military_bonus || 0).toLocaleString()}</td>
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
                                autoComplete="off"
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
                                autoComplete="off"
                            />
                        }</td>
                        <td>{
                            props.loading.projects
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
                        <td>{(props.kdInfo.projects_assigned.money_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.money_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.money_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.money_bonus || 0).toLocaleString()}</td>
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
                                autoComplete="off"
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
                                autoComplete="off"
                            />
                        }</td>
                        <td>{
                            props.loading.projects
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
                        <td>{(props.kdInfo.projects_assigned.general_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.general_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.general_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.general_bonus || 0).toLocaleString()}</td>
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
                                autoComplete="off"
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
                                autoComplete="off"
                            />
                        }</td>
                        <td>{
                            props.loading.projects
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
                            <td>{(props.kdInfo.projects_assigned.spy_bonus || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.spy_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.spy_bonus || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.spy_bonus || 0).toLocaleString()}</td>
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
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
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
                            <td>{Math.floor(props.kdInfo.projects_points.spy_bonus || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.spy_bonus || 0).toLocaleString()}</td>
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
                                    autoComplete="off"
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
                                    autoComplete="off"
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
                        <th colSpan={2}>% Completed</th>
                        <th>Assign</th>
                        <th>Add</th>
                        <th>Remove</th>
                    </tr>
                </thead>
                <tbody>
                    
                    {
                        props.kdInfo.completed_projects.indexOf('big_flexers') < 0
                        ? <tr>
                            <td>Big Flexers</td>
                            <td>{(props.kdInfo.projects_assigned.big_flexers || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.big_flexers || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.big_flexers || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.big_flexers || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.big_flexers || 0)/(props.kdInfo.projects_max_points.big_flexers))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="big-flexers-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="big_flexers"
                                    value={assignValues.big_flexers || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="big_flexers" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="big_flexers" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.big_flexers || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Big Flexers</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.big_flexers || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.big_flexers || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.big_flexers || 0)/(props.kdInfo.projects_max_points.big_flexers))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="big-flexers-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="big_flexers"
                                    value={assignValues.big_flexers || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="big_flexers" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="big_flexers" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.big_flexers || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                    }
                    {
                        props.kdInfo.completed_projects.indexOf('star_busters') < 0
                        ? <tr>
                            <td>Star Busters</td>
                            <td>{(props.kdInfo.projects_assigned.star_busters || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.star_busters || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.star_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.star_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.star_busters || 0)/(props.kdInfo.projects_max_points.star_busters))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="star-busters-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="star_busters"
                                    value={assignValues.star_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="star_busters" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="star_busters" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.star_busters || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Star Busters</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.star_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.star_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.star_busters || 0)/(props.kdInfo.projects_max_points.star_busters))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="star-busters-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="star_busters"
                                    value={assignValues.star_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="star_busters" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="star_busters" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.star_busters || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                    }
                    {
                        props.kdInfo.completed_projects.indexOf('galaxy_busters') < 0
                        ? <tr>
                            <td>Galaxy Busters</td>
                            <td>{(props.kdInfo.projects_assigned.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.galaxy_busters || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.galaxy_busters || 0)/(props.kdInfo.projects_max_points.galaxy_busters))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="galaxy-busters-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="galaxy_busters"
                                    value={assignValues.galaxy_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="galaxy_busters" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="galaxy_busters" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.galaxy_busters || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Galaxy Busters</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.galaxy_busters || 0)/(props.kdInfo.projects_max_points.galaxy_busters))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="galaxy-busters-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="galaxy_busters"
                                    value={assignValues.galaxy_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="galaxy_busters" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="galaxy_busters" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.galaxy_busters || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                    }
                    {
                        props.kdInfo.completed_projects.indexOf('drone_gadgets') < 0
                        ? <tr>
                            <td>Drone Gadgets</td>
                            <td>{(props.kdInfo.projects_assigned.drone_gadgets || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.drone_gadgets || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.drone_gadgets || 0)/(props.kdInfo.projects_max_points.drone_gadgets))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="drone-gadgets-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="drone_gadgets"
                                    value={assignValues.drone_gadgets || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="drone_gadgets" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="drone_gadgets" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.drone_gadgets || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Drone Gadgets</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.drone_gadgets || 0)/(props.kdInfo.projects_max_points.drone_gadgets))}</td>
                            <td>{
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="drone-gadgets-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="drone_gadgets"
                                    value={assignValues.drone_gadgets || ""} 
                                    placeholder="0"
                                    autoComplete="off"
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
                                    autoComplete="off"
                                />
                            }</td>
                            <td>{
                                props.loading.projects
                                ? <Button className="remove-button" name="drone_gadgets" variant="primary" type="submit" disabled>
                                    Loading...
                                </Button>
                                : <Button className="remove-button" name="drone_gadgets" variant="primary" type="submit" onClick={OnClearClick} disabled={(props.kdInfo.projects_assigned.drone_gadgets || 0) == 0}>
                                    Remove
                                </Button>
                            }</td>
                        </tr>
                    }
                </tbody>
            </Table>
            <div className="projects-buttons">
                {
                    props.loading.projects
                    ? <Button className="projects-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="projects-button" variant="primary" type="submit" onClick={onAssignClick}>
                        Assign
                    </Button>
                }
                {
                    props.loading.projects
                    ? <Button className="projects-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="projects-button" variant="primary" type="submit" onClick={onAddClick}>
                        Add
                    </Button>
                }
                {
                    props.loading.projects
                    ? <Button className="projects-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="projects-button" variant="primary" type="submit" onClick={OnClearAllClick}>
                        Remove All
                    </Button>
                }
                {
                    engineersAssigned !== 0
                    ? <h3>Unassigned Engineers: {(props.engineersInfo.current_engineers - engineersAssigned).toLocaleString()}</h3>
                    : engineersAdded !== 0
                        ? <h3>Unassigned Engineers: {(props.projectsInfo.available_engineers - engineersAdded).toLocaleString()}</h3>
                        : null
                }
            </div>
        </div>
    )
}

function Allocate(props) {
    const [assignValues, setAssignValues] = useState(initialProjectsValues);
    const [assignResult, setAssignResult] = useState([]);
    const [enabled, setEnabled] = useState(props.kdInfo?.auto_assign_projects)

    const handleAssignInputChange = (e) => {
        const { name, value } = e.target;
        setAssignValues({
          ...assignValues,
          [name]: value,
        });
      };

    const onSubmitClick = (e)=>{
        let opts = {"targets": assignValues};
        const updateFunc = () => authFetch('api/projects/target', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setAssignResult(assignResult.concat(r)))
        props.updateData(['kingdom'], [updateFunc])
    }
    const handleEnabledChange = (e) => {
        let opts = {
            'enabled': e.target.checked
        }
        const updateFunc = () => authFetch('api/projects/target', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setAssignResult(assignResult.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
        setEnabled(e.target.checked)
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
    const toasts = assignResult.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setAssignResult(assignResult.slice(0, index).concat(assignResult.slice(index + 1, 999)))}
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
        <div className="projects">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="text-box projects-box">
                <span>Choose the target allocation of assigned engineers that you would like the auto-spender to assign towards</span>
            </div>
            <Form>
                <Form.Check 
                    type="switch"
                    id="enable-auto-projects-switch"
                    label="Enable Auto Assign Engineers?"
                    checked={props.kdInfo.auto_assign_projects}
                    onChange={handleEnabledChange}
                    disabled={props.loading.kingdom}
                />
            </Form>
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
                        <th>Current Allocation</th>
                        <th>New Allocation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Pop Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.pop_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.pop_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.pop_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.pop_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.pop_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.pop_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_target?.pop_bonus || 0))}</td>
                        <td>{
                            <InputGroup className="mb-3">
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="pop-bonus-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="pop_bonus"
                                    value={assignValues.pop_bonus || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td>Fuel Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.fuel_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.fuel_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.fuel_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.fuel_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.fuel_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.fuel_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_target?.fuel_bonus || 0))}</td>
                        <td>{
                            <InputGroup className="mb-3">
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="fuel-bonus-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="fuel_bonus"
                                    value={assignValues.fuel_bonus || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td>Military Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.military_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.military_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.military_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.military_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.military_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.military_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_target?.military_bonus || 0))}</td>
                        <td>{
                            <InputGroup className="mb-3">
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="military-bonus-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="military_bonus"
                                    value={assignValues.military_bonus || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td>Money Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.money_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.money_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.money_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.money_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.money_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.money_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_target?.money_bonus || 0))}</td>
                        <td>{
                            <InputGroup className="mb-3">
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="money-bonus-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="money_bonus"
                                    value={assignValues.money_bonus || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td>Generals Speed Bonus</td>
                        <td>{(props.kdInfo.projects_assigned.general_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent((props.kdInfo.projects_assigned.general_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                        <td>{Math.floor(props.kdInfo.projects_points.general_bonus || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.kdInfo.projects_max_points.general_bonus || 0).toLocaleString()}</td>
                        <td>{displayPercent(props.projectsInfo.current_bonuses.general_bonus || 0)}</td>
                        <td>{displayPercent(props.projectsInfo.max_bonuses.general_bonus || 0)}</td>
                        <td>{displayPercent((props.kdInfo.projects_target?.general_bonus || 0))}</td>
                        <td>{
                            <InputGroup className="mb-3">
                                <Form.Control 
                                    className="projects-assign-form"
                                    id="general-bonus-assign-input"
                                    onChange={handleAssignInputChange}
                                    name="general_bonus"
                                    value={assignValues.general_bonus || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    {
                        props.kdInfo.completed_projects.indexOf('drone_gadgets') >= 0
                        ? <tr>
                            <td>Spy Bonus</td>
                            <td>{(props.kdInfo.projects_assigned.spy_bonus || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.spy_bonus || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.spy_bonus || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.spy_bonus || 0).toLocaleString()}</td>
                            <td>{displayPercent(props.projectsInfo.current_bonuses.spy_bonus || 0)}</td>
                            <td>{displayPercent(props.projectsInfo.max_bonuses.spy_bonus || 0)}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.spy_bonus || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="spy-bonus-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="spy_bonus"
                                        value={assignValues.spy_bonus || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Spy Bonus</td>
                            <td colSpan={2}>Complete "Drone Gadgets" Project to Unlock</td>
                            <td>{Math.floor(props.kdInfo.projects_points.spy_bonus || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.spy_bonus || 0).toLocaleString()}</td>
                            <td>{displayPercent(props.projectsInfo.current_bonuses.spy_bonus || 0)}</td>
                            <td>{displayPercent(props.projectsInfo.max_bonuses.spy_bonus || 0)}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.spy_bonus || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="spy-bonus-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="pop"
                                        value={assignValues.spy_bonus || ""} 
                                        placeholder="0"
                                        disabled
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
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
                        <th colSpan={2}>% Completed</th>
                        <th>Current Allocation</th>
                        <th>New Allocation</th>
                    </tr>
                </thead>
                <tbody>
                    
                    {
                        props.kdInfo.completed_projects.indexOf('big_flexers') < 0
                        ? <tr>
                            <td>Big Flexers</td>
                            <td>{(props.kdInfo.projects_assigned.big_flexers || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.big_flexers || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.big_flexers || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.big_flexers || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.big_flexers || 0)/(props.kdInfo.projects_max_points.big_flexers))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.big_flexers || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="big-flexers-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="big_flexers"
                                        value={assignValues.big_flexers || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Big Flexers</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.big_flexers || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.big_flexers || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.big_flexers || 0)/(props.kdInfo.projects_max_points.big_flexers))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.big_flexers || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="big-flexers-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="big_flexers"
                                        value={assignValues.big_flexers || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                    }
                    {
                        props.kdInfo.completed_projects.indexOf('star_busters') < 0
                        ? <tr>
                            <td>Star Busters</td>
                            <td>{(props.kdInfo.projects_assigned.star_busters || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.star_busters || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.star_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.star_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.star_busters || 0)/(props.kdInfo.projects_max_points.star_busters))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.star_busters || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="star-busters-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="star_busters"
                                        value={assignValues.star_busters || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Star Busters</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.star_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.star_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.star_busters || 0)/(props.kdInfo.projects_max_points.star_busters))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.star_busters || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="star-busters-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="star_busters"
                                        value={assignValues.star_busters || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                    }
                    {
                        props.kdInfo.completed_projects.indexOf('galaxy_busters') < 0
                        ? <tr>
                            <td>Galaxy Busters</td>
                            <td>{(props.kdInfo.projects_assigned.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.galaxy_busters || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.galaxy_busters || 0)/(props.kdInfo.projects_max_points.galaxy_busters))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.galaxy_busters || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="galaxy-busters-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="galaxy_busters"
                                        value={assignValues.galaxy_busters || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Galaxy Busters</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.galaxy_busters || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.galaxy_busters || 0)/(props.kdInfo.projects_max_points.galaxy_busters))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.galaxy_busters || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="galaxy-busters-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="galaxy_busters"
                                        value={assignValues.galaxy_busters || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                    }
                    {
                        props.kdInfo.completed_projects.indexOf('drone_gadgets') < 0
                        ? <tr>
                            <td>Drone Gadgets</td>
                            <td>{(props.kdInfo.projects_assigned.drone_gadgets || 0).toLocaleString()}</td>
                            <td>{displayPercent((props.kdInfo.projects_assigned.drone_gadgets || 0) / (props.engineersInfo.current_engineers || 0))}</td>
                            <td>{Math.floor(props.kdInfo.projects_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.drone_gadgets || 0)/(props.kdInfo.projects_max_points.drone_gadgets))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.drone_gadgets || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="drone-gadgets-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="drone_gadgets"
                                        value={assignValues.drone_gadgets || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Drone Gadgets</td>
                            <td colSpan={2}>Project Complete!</td>
                            <td>{Math.floor(props.kdInfo.projects_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td>{Math.floor(props.kdInfo.projects_max_points.drone_gadgets || 0).toLocaleString()}</td>
                            <td colSpan={2}>{displayPercent((props.kdInfo.projects_points.drone_gadgets || 0)/(props.kdInfo.projects_max_points.drone_gadgets))}</td>
                            <td>{displayPercent((props.kdInfo.projects_target?.drone_gadgets || 0))}</td>
                            <td>{
                                <InputGroup className="mb-3">
                                    <Form.Control 
                                        className="projects-assign-form"
                                        id="drone-gadgets-assign-input"
                                        onChange={handleAssignInputChange}
                                        name="drone_gadgets"
                                        value={assignValues.drone_gadgets || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                </InputGroup>
                            }</td>
                        </tr>
                    }
                </tbody>
            </Table>
            <div className="projects-buttons">
                {
                    props.loading.kingdom
                    ? <Button className="auto-projects-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="auto-projects-button" variant="primary" type="submit" onClick={onSubmitClick}>
                        Update
                    </Button>
                }
            </div>
        </div>
    )
}

export default ProjectsContent;