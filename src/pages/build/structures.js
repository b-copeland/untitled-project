import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./structures.css"
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";

function Structures(props) {
    const [key, setKey] = useState('build');

    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="build"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="build" title="Build">
          <BuildStructures
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}
            />
        </Tab>
        <Tab eventKey="allocate" title="Allocate">
          <AllocateStructures
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}/>
        </Tab>
        <Tab eventKey="raze" title="Raze">
          <RazeStructures
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}
          />
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"structures"}/>
    </>
    );
}

const initialStructuresValues = {
    "homes": "",
    "mines": "",
    "fuel_plants": "",
    "hangars": "",
    "drone_factories": "",
    "missile_silos": "",
    "workshops": ""
}

function BuildStructures(props) {
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
            <Toast.Body  className="text-black">{results.message}</Toast.Body>
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
        <>
        <div className="structures">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="text-box structures-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Average Build Time</span>
                    <span className="text-box-item-value">{props.data.state.game_config?.BASE_EPOCH_SECONDS * (props.data.state.game_config?.BASE_STRUCTURE_TIME_MIN_MULTIPLIER + props.data.state.game_config?.BASE_STRUCTURE_TIME_MAX_MUTLIPLIER) / 2 / 3600}h</span>
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
                    <span className="text-box-item-title">Available New Structures</span>
                    <span className="text-box-item-value">{structuresInfo["current_available_structures"].toLocaleString()}</span>
                </div>
            </div>
            <Table className="structures-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Structure</th>
                        <th style={{textAlign: "right"}}>% Built</th>
                        <th style={{textAlign: "right"}}># Built</th>
                        <th style={{textAlign: "right"}}># Building</th>
                        <th style={{textAlign: "right"}}>To Build</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Homes</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.homes || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.homes || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.homes || 0).toLocaleString()}</td>
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
                        <td style={{textAlign: "left"}}>Mines</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.mines || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.mines || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.mines || 0).toLocaleString()}</td>
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
                        <td style={{textAlign: "left"}}>Fuel Plants</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.fuel_plants || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.fuel_plants || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.fuel_plants || 0).toLocaleString()}</td>
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
                        <td style={{textAlign: "left"}}>Hangars</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.hangars || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.hangars || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.hangars || 0).toLocaleString()}</td>
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
                        <td style={{textAlign: "left"}}>Drone Factories</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.drone_factories || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.drone_factories || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.drone_factories || 0).toLocaleString()}</td>
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
                        <td style={{textAlign: "left"}}>Missile Silos</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.missile_silos || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.missile_silos || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.missile_silos || 0).toLocaleString()}</td>
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
                        <td style={{textAlign: "left"}}>Workshops</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.workshops || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.workshops || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.workshops || 0).toLocaleString()}</td>
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
        </>
        )
}

function AllocateStructures(props) {
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
        const updateFunc = () => authFetch('api/structures/target', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setStructuresResult(structuresResult.concat(r)))
        props.updateData(['kingdom'], [updateFunc])
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
            <Toast.Body  className="text-black">{results.message}</Toast.Body>
        </Toast>
    )
    return (
        <>
        <div className="structures">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="text-box structures-box">
                <span>Choose the target allocation of structures that you would like the auto-spender to build towards</span>
            </div>
            <Table className="structures-allocation-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Structure</th>
                        <th style={{textAlign: "right"}}>% Built</th>
                        <th style={{textAlign: "right"}}># Built</th>
                        <th style={{textAlign: "right"}}># Building</th>
                        <th style={{textAlign: "right"}}>Current Allocation</th>
                        <th style={{textAlign: "right"}}>New Allocation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Homes</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.homes || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.homes || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.homes || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((kdInfo.structures_target?.homes || 0))}</td>
                        <td className="structures-form-data">{
                            <InputGroup className="mb-3 structures-input-group">
                                <Form.Control 
                                    className="structures-form"
                                    id="homes-input"
                                    name="homes"
                                    onChange={handleInputChange}
                                    value={structuresInput.homes || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2" className="structures-pct-text">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Mines</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.mines || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.mines || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.mines || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((kdInfo.structures_target?.mines || 0))}</td>
                        <td className="structures-form-data">{
                            <InputGroup className="mb-3 structures-input-group">
                                <Form.Control 
                                    className="structures-form"
                                    id="mines-input"
                                    name="mines"
                                    onChange={handleInputChange}
                                    value={structuresInput.mines || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2" className="structures-pct-text">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Fuel Plants</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.fuel_plants || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.fuel_plants || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.fuel_plants || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((kdInfo.structures_target?.fuel_plants || 0))}</td>
                        <td className="structures-form-data">{
                            <InputGroup className="mb-3 structures-input-group">
                                <Form.Control 
                                    className="structures-form"
                                    id="fuel-plants-input"
                                    name="fuel_plants"
                                    onChange={handleInputChange}
                                    value={structuresInput.fuel_plants || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2" className="structures-pct-text">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Hangars</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.hangars || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.hangars || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.hangars || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((kdInfo.structures_target?.hangars || 0))}</td>
                        <td className="structures-form-data">{
                            <InputGroup className="mb-3 structures-input-group">
                                <Form.Control 
                                    className="structures-form"
                                    id="hangars-input"
                                    name="hangars"
                                    onChange={handleInputChange}
                                    value={structuresInput.hangars || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2" className="structures-pct-text">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Drone Factories</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.drone_factories || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.drone_factories || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.drone_factories || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((kdInfo.structures_target?.drone_factories || 0))}</td>
                        <td className="structures-form-data">{
                            <InputGroup className="mb-3 structures-input-group">
                                <Form.Control 
                                    className="structures-form"
                                    id="drone-factories-input"
                                    name="drone_factories"
                                    onChange={handleInputChange}
                                    value={structuresInput.drone_factories || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2" className="structures-pct-text">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Missile Silos</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.missile_silos || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.missile_silos || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.missile_silos || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((kdInfo.structures_target?.missile_silos || 0))}</td>
                        <td className="structures-form-data">{
                            <InputGroup className="mb-3 structures-input-group">
                                <Form.Control 
                                    className="structures-form"
                                    id="missile-silos-input"
                                    name="missile_silos"
                                    onChange={handleInputChange}
                                    value={structuresInput.missile_silos || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2" className="structures-pct-text">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Workshops</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structuresInfo.current.workshops || 0) / kdInfo["stars"])}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.current.workshops || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(structuresInfo.hour_24.workshops || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((kdInfo.structures_target?.workshops || 0))}</td>
                        <td className="structures-form-data">{
                            <InputGroup className="mb-3 structures-input-group">
                                <Form.Control 
                                    className="structures-form"
                                    id="workshops-input"
                                    name="workshops"
                                    onChange={handleInputChange}
                                    value={structuresInput.workshops || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2" className="structures-pct-text">%</InputGroup.Text>
                            </InputGroup>
                        }</td>
                    </tr>
                </tbody>
            </Table>
            {
                props.loading.kingdom
                ? <Button className="structures-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="structures-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Update
                </Button>
            }
        </div>
        </>
        )
}
function RazeStructures(props) {
    const [results, setResults] = useState([]);
    const [input, setInput] = useState({});

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput((prev) => ({
          ...prev,
          [name]: value,
        }));
      };
    const onSubmitClick = (e)=>{
        let opts = {
            "input": input,
        };
        const updateFunc = () => authFetch('api/structures/raze', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['kingdom'], [updateFunc]);
        setInput({});
    }
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;

    const structures = props.data.kingdom.structures || {};
    const razeRows = Object.keys(structures).map((structureKey, iter) => {
        const prettyNames = props.data.state.pretty_names || {};
        return <tr key={"raze_" + iter}>
            <td style={{textAlign: "left"}}>{prettyNames[structureKey] || structureKey}</td>
            <td style={{textAlign: "right"}}>{displayPercent((structures[structureKey] || 0) / (props.data.kingdom.stars || 1))}</td>
            <td style={{textAlign: "right"}}>{structures[structureKey] || 0}</td>
            <td style={{textAlign: "right"}}>{
                <Form.Control 
                    className="structures-form"
                    id={"raze-" + structureKey}
                    name={structureKey}
                    onChange={handleInputChange}
                    value={input[structureKey] || ""} 
                    placeholder="0"
                    autoComplete="off"
                />
            }</td>
        </tr>
    })
    
    const toasts = results.map((result, index) =>
        <Toast
            key={index}
            onClose={(e) => setResults(results.slice(0, index).concat(results.slice(index + 1, 999)))}
            show={true}
            bg={result.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Raze Results</strong>
            </Toast.Header>
            <Toast.Body  className="text-black">{result.message}</Toast.Body>
        </Toast>
    )
    return (
        <div className="structures-raze">
            <h2>Raze Structures</h2>
            <div className="text-box structures-box">
                <span>Raze structures to destroy them and receive {displayPercent(props.data.state.game_config?.BASE_STRUCTURES_RAZE_RETURN || 0)} of the current build cost back</span>
            </div>
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <Table className="structures-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Structure</th>
                        <th style={{textAlign: "right"}}>% Built</th>
                        <th style={{textAlign: "right"}}>Available</th>
                        <th style={{textAlign: "right"}}>To Raze</th>
                    </tr>
                </thead>
                <tbody>
                    {razeRows}
                </tbody>
            </Table>
            {
                props.loading.kingdom
                ? <Button className="structures-button" variant="warning" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="structures-button" variant="warning" type="submit" onClick={onSubmitClick}>
                    Raze
                </Button>
            }
        </div>
    )
}

export default Structures;