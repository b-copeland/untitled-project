import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import "./status.css"

function StatusContent() {
    const [key, setKey] = useState('kingdom');
    const [kdInfo, setKdInfo] = useState({});

    useEffect(() => {
        const fetchData = async () => {
        await authFetch("api/kingdom").then(r => r.json()).then(r => setKdInfo(r));
        }
        fetchData();
    }, [])
    return (
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="kingdom"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="kingdom" title="Kingdom">
          <Status kdInfo={kdInfo}/>
        </Tab>
        <Tab eventKey="revealed" title="Revealed">
          <Revealed kdInfo={kdInfo}/>
        </Tab>
        <Tab eventKey="spending" title="Spending">
          <Spending kdInfo={kdInfo}/>
        </Tab>
        <Tab eventKey="military" title="Military">
          <Military />
        </Tab>
        <Tab eventKey="structures" title="Structures">
          <Structures kdInfo={kdInfo}/>
        </Tab>
      </Tabs>
    );
}

function Status(props) {
    return (
        <div className="status">
            <div className="text-box kingdom-card">
                <h4>Omni (1:2)</h4>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Name</span>
                    <span className="text-box-item-value">Player1</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Race</span>
                    <span className="text-box-item-value">Human</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Stars</span>
                    <span className="text-box-item-value">{props.kdInfo.stars}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Population</span>
                    <span className="text-box-item-value">{props.kdInfo.population}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Fuel</span>
                    <span className="text-box-item-value">{props.kdInfo.fuel}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Engineers</span>
                    <span className="text-box-item-value">{props.kdInfo["units"]?.engineers}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Drones</span>
                    <span className="text-box-item-value">{props.kdInfo.drones}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Attackers</span>
                    <span className="text-box-item-value">{props.kdInfo["units"]?.attack}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Defenders</span>
                    <span className="text-box-item-value">{props.kdInfo["units"]?.defense}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Flexers</span>
                    <span className="text-box-item-value">{props.kdInfo["units"]?.flex}</span>
                </div>
            </div>
            <div className="text-box income-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Income (per hour)</span>
                    <span className="text-box-item-value">9999</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Fuel (per hour)</span>
                    <span className="text-box-item-value">9999</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Score (per hour)</span>
                    <span className="text-box-item-value">9999</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Population (per hour)</span>
                    <span className="text-box-item-value">9999</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Drones (per hour)</span>
                    <span className="text-box-item-value">9999</span>
                </div>
            </div>
        </div>
    );
}

function Revealed(props) {
    const [kdNames, setKdNames] = useState({});

    useEffect(() => {
        const fetchData = async () => {
        await authFetch("api/kingdoms").then(r => r.json()).then(r => setKdNames(r));
        }
        fetchData();
    }, [])
    const revealed_to = props.kdInfo?.revealed_to;
    if (revealed_to === undefined) {
        return null
    }
    if (Object.keys(kdNames).length === 0) {
        return null;
    }
    const revealedItems = Object.keys(revealed_to).map((kdId) =>
        <div key={kdId} className="text-box-item">
            <span className="text-box-item-title" >{kdNames[kdId]}</span>
            <span className="text-box-item-value" >{revealed_to[kdId]}</span>
        </div>
    );
    return (
        <div className="revealed">
            <h2>Kingdom Revealed To:</h2>
            <div className="text-box revealed-box">
                {revealedItems}
            </div>

        </div>
    )
}

function Spending(props) {
    const [settleInput, setSettleInput] = useState('')
    const [structuresInput, setStructuresInput] = useState('')
    const [militaryInput, setMilitaryInput] = useState('')
    const [engineersInput, setEngineersInput] = useState('')

    const spendingInfo = props.kdInfo?.auto_spending;
    if (spendingInfo === undefined) {
        return null
    }

    const handleSettleInput = (e) => {
        setSettleInput(e.target.value)
    }
  
    const handleStructuresInput = (e) => {
        setStructuresInput(e.target.value)
    }

    const handleMilitaryInput = (e) => {
        setMilitaryInput(e.target.value)
    }
  
    const handleEngineersInput = (e) => {
        setEngineersInput(e.target.value)
    }

    const onSubmitClick = (e)=>{
        let opts = {
            'settleInput': settleInput === '' ? undefined : settleInput,
            'structuresInput': structuresInput === '' ? undefined : structuresInput,
            'militaryInput': militaryInput === '' ? undefined : militaryInput,
            'engineersInput': engineersInput === '' ? undefined : engineersInput,
        }
        authFetch('api/spending', {
            method: 'post',
            body: JSON.stringify(opts)
        })
    }
    return (
        <div className="spending">
            <h2>Update Auto Spending:</h2>
            <InputGroup className="mb-3">
                <InputGroup.Text id="text-settle-percent">
                    Settle (Current: {spendingInfo.settle}%)
                </InputGroup.Text>
                <Form.Control 
                    id="settle-percent"
                    aria-describedby="basic-addon3" 
                    onChange={handleSettleInput}
                    value={settleInput} 
                    placeholder={spendingInfo.settle}
                />
            </InputGroup>
            <InputGroup className="mb-3">
                <InputGroup.Text id="text-structures-percent">
                    Structures (Current: {spendingInfo.structures}%)
                </InputGroup.Text>
                <Form.Control 
                    id="structures-percent"
                    aria-describedby="basic-addon3" 
                    onChange={handleStructuresInput}
                    value={structuresInput} 
                    placeholder={spendingInfo.structures}
                />
            </InputGroup>
            <InputGroup className="mb-3">
                <InputGroup.Text id="text-military-percent">
                    Military (Current: {spendingInfo.military}%)
                </InputGroup.Text>
                <Form.Control 
                    id="military-percent"
                    aria-describedby="basic-addon3" 
                    onChange={handleMilitaryInput}
                    value={militaryInput} 
                    placeholder={spendingInfo.military}
                />
            </InputGroup>
            <InputGroup className="mb-3">
                <InputGroup.Text id="text-engineers-percent">
                    Engineers (Current: {spendingInfo.engineers}%)
                </InputGroup.Text>
                <Form.Control 
                    id="engineers-percent"
                    aria-describedby="basic-addon3" 
                    onChange={handleEngineersInput}
                    value={engineersInput} 
                    placeholder={spendingInfo.engineers}
                />
            </InputGroup>
            <Button variant="primary" type="submit" onClick={onSubmitClick}>
                Submit
            </Button>
        </div>
    )
}

function getTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.abs(Date.parse(date) - Date.now()) / 3.6e6;
    var n = new Date(0, 0);
    n.setSeconds(+hours * 60 * 60);
    return n.toTimeString().slice(0, 8);
}

function Military() {
    const [mobis, setMobis] = useState({});
    
    useEffect(() => {
        const fetchData = async () => {
        await authFetch("api/mobis").then(r => r.json()).then(r => setMobis(r));
        }
        fetchData();
    }, []);
    if (Object.keys(mobis).length === 0) {
        return null;
    }
    console.log(mobis);
    const units = mobis.units;
    const maxOffense = mobis.maxes.offense;
    const maxDefense = mobis.maxes.defense;
    return (
        <div className="status">
            <div className="army-info">
                <h2>Armies</h2>
                <Table striped bordered hover>
                    <thead>
                        <tr>
                        <th colSpan={2}></th>
                        <th colSpan={4}>Generals</th>
                        </tr>
                    </thead>
                    <thead>
                        <tr>
                            <th>Unit</th>
                            <th>Home</th>
                            <th>{getTimeString(units.general_0?.return_time)}</th>
                            <th>{getTimeString(units.general_1?.return_time)}</th>
                            <th>{getTimeString(units.general_2?.return_time)}</th>
                            <th>{getTimeString(units.general_3?.return_time)}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Attackers</td>
                            <td>{units.current?.attack || 0}</td>
                            <td>{units.general_0?.attack || 0}</td>
                            <td>{units.general_1?.attack || 0}</td>
                            <td>{units.general_2?.attack || 0}</td>
                            <td>{units.general_3?.attack || 0}</td>
                        </tr>
                        <tr>
                            <td>Defenders</td>
                            <td>{units.current?.defense || 0}</td>
                            <td>{units.general_0?.defense || 0}</td>
                            <td>{units.general_1?.defense || 0}</td>
                            <td>{units.general_2?.defense || 0}</td>
                            <td>{units.general_3?.defense || 0}</td>
                        </tr>
                        <tr>
                            <td>Flexers</td>
                            <td>{units.current?.flex || 0}</td>
                            <td>{units.general_0?.flex || 0}</td>
                            <td>{units.general_1?.flex || 0}</td>
                            <td>{units.general_2?.flex || 0}</td>
                            <td>{units.general_3?.flex || 0}</td>
                        </tr>
                    </tbody>
                </Table>
                <Table striped bordered hover>
                    <thead>
                        <tr>
                        <th colSpan={2}></th>
                        <th colSpan={4}>Generals</th>
                        </tr>
                    </thead>
                    <thead>
                        <tr>
                            <th></th>
                            <th>Home</th>
                            <th>{getTimeString(units.general_0?.return_time)}</th>
                            <th>{getTimeString(units.general_1?.return_time)}</th>
                            <th>{getTimeString(units.general_2?.return_time)}</th>
                            <th>{getTimeString(units.general_3?.return_time)}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Max offense</td>
                            <td>{maxOffense.current || 0}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.general_0 || 0)}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0)}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0) + (maxOffense.general_2 || 0)}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0) + (maxOffense.general_2 || 0) + (maxOffense.general_3 || 0)}</td>
                        </tr>
                        <tr>
                            <td>Max defense</td>
                            <td>{maxDefense.current || 0}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.general_0 || 0)}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0)}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0) + (maxDefense.general_2 || 0)}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0) + (maxDefense.general_2 || 0) + (maxDefense.general_3 || 0)}</td>
                        </tr>
                    </tbody>
                </Table>
            </div>
            <div className="mobi-info">
                <h2>Mobilization</h2>
                <Table striped bordered hover>
                    <thead>
                        <tr>
                        <th></th>
                        <th>Now</th>
                        <th>1h</th>
                        <th>2h</th>
                        <th>4h</th>
                        <th>8h</th>
                        <th>24h</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Attackers</td>
                            <td>{units.current.attack || 0}</td>
                            <td>{(units.current.attack || 0) + (units.hour_1.attack || 0)}</td>
                            <td>{(units.current.attack || 0) + (units.hour_2.attack || 0)}</td>
                            <td>{(units.current.attack || 0) + (units.hour_4.attack || 0)}</td>
                            <td>{(units.current.attack || 0) + (units.hour_8.attack || 0)}</td>
                            <td>{(units.current.attack || 0) + (units.hour_24.attack || 0)}</td>
                        </tr>
                        <tr>
                            <td>Defenders</td>
                            <td>{units.current.defense || 0}</td>
                            <td>{(units.current.defense || 0) + (units.hour_1.defense || 0)}</td>
                            <td>{(units.current.defense || 0) + (units.hour_2.defense || 0)}</td>
                            <td>{(units.current.defense || 0) + (units.hour_4.defense || 0)}</td>
                            <td>{(units.current.defense || 0) + (units.hour_8.defense || 0)}</td>
                            <td>{(units.current.defense || 0) + (units.hour_24.defense || 0)}</td>
                        </tr>
                        <tr>
                            <td>Flexers</td>
                            <td>{units.current.flex || 0}</td>
                            <td>{(units.current.flex || 0) + (units.hour_1.flex || 0)}</td>
                            <td>{(units.current.flex || 0) + (units.hour_2.flex || 0)}</td>
                            <td>{(units.current.flex || 0) + (units.hour_4.flex || 0)}</td>
                            <td>{(units.current.flex || 0) + (units.hour_8.flex || 0)}</td>
                            <td>{(units.current.flex || 0) + (units.hour_24.flex || 0)}</td>
                        </tr>
                    </tbody>
                </Table>
                <Table striped bordered hover>
                    <thead>
                        <tr>
                        <th></th>
                        <th>Now</th>
                        <th>1h</th>
                        <th>2h</th>
                        <th>4h</th>
                        <th>8h</th>
                        <th>24h</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Max offense</td>
                            <td>{maxOffense.current || 0}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.hour_1 || 0)}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.hour_2 || 0)}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.hour_4 || 0)}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.hour_8 || 0)}</td>
                            <td>{(maxOffense.current || 0) + (maxOffense.hour_24 || 0)}</td>
                        </tr>
                        <tr>
                            <td>Max defense</td>
                            <td>{maxDefense.current || 0}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.hour_1 || 0)}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.hour_2 || 0)}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.hour_4 || 0)}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.hour_8 || 0)}</td>
                            <td>{(maxDefense.current || 0) + (maxDefense.hour_24 || 0)}</td>
                        </tr>
                    </tbody>
                </Table>
            </div>
        </div>
    )
}

function Structures(props) {
    const [structures, setStructures] = useState({});
    
    useEffect(() => {
        const fetchData = async () => {
        await authFetch("api/structures").then(r => r.json()).then(r => setStructures(r));
        }
        fetchData();
    }, []);
    if (Object.keys(structures).length === 0) {
        return null;
    }
    console.log(structures);
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div className="revealed">
            <h2>Structures</h2>
            <div className="structures-info">
                <Table striped bordered hover>
                    <thead>
                        <tr>
                        <th></th>
                        <th>Now</th>
                        <th>1h</th>
                        <th>2h</th>
                        <th>4h</th>
                        <th>8h</th>
                        <th>24h</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Homes</td>
                            <td>{structures.current.homes || 0}</td>
                            <td>{(structures.current.homes || 0) + (structures.hour_1.homes || 0)}</td>
                            <td>{(structures.current.homes || 0) + (structures.hour_2.homes || 0)}</td>
                            <td>{(structures.current.homes || 0) + (structures.hour_4.homes || 0)}</td>
                            <td>{(structures.current.homes || 0) + (structures.hour_8.homes || 0)}</td>
                            <td>{(structures.current.homes || 0) + (structures.hour_24.homes || 0)}</td>
                        </tr>
                        <tr>
                            <td>Mines</td>
                            <td>{structures.current.mines || 0}</td>
                            <td>{(structures.current.mines || 0) + (structures.hour_1.mines || 0)}</td>
                            <td>{(structures.current.mines || 0) + (structures.hour_2.mines || 0)}</td>
                            <td>{(structures.current.mines || 0) + (structures.hour_4.mines || 0)}</td>
                            <td>{(structures.current.mines || 0) + (structures.hour_8.mines || 0)}</td>
                            <td>{(structures.current.mines || 0) + (structures.hour_24.mines || 0)}</td>
                        </tr>
                        <tr>
                            <td>Fuel Plants</td>
                            <td>{structures.current.fuel_plants || 0}</td>
                            <td>{(structures.current.fuel_plants || 0) + (structures.hour_1.fuel_plants || 0)}</td>
                            <td>{(structures.current.fuel_plants || 0) + (structures.hour_2.fuel_plants || 0)}</td>
                            <td>{(structures.current.fuel_plants || 0) + (structures.hour_4.fuel_plants || 0)}</td>
                            <td>{(structures.current.fuel_plants || 0) + (structures.hour_8.fuel_plants || 0)}</td>
                            <td>{(structures.current.fuel_plants || 0) + (structures.hour_24.fuel_plants || 0)}</td>
                        </tr>
                        <tr>
                            <td>Hangars</td>
                            <td>{structures.current.hangars || 0}</td>
                            <td>{(structures.current.hangars || 0) + (structures.hour_1.hangars || 0)}</td>
                            <td>{(structures.current.hangars || 0) + (structures.hour_2.hangars || 0)}</td>
                            <td>{(structures.current.hangars || 0) + (structures.hour_4.hangars || 0)}</td>
                            <td>{(structures.current.hangars || 0) + (structures.hour_8.hangars || 0)}</td>
                            <td>{(structures.current.hangars || 0) + (structures.hour_24.hangars || 0)}</td>
                        </tr>
                        <tr>
                            <td>Drone Factories</td>
                            <td>{structures.current.drone_factories || 0}</td>
                            <td>{(structures.current.drone_factories || 0) + (structures.hour_1.drone_factories || 0)}</td>
                            <td>{(structures.current.drone_factories || 0) + (structures.hour_2.drone_factories || 0)}</td>
                            <td>{(structures.current.drone_factories || 0) + (structures.hour_4.drone_factories || 0)}</td>
                            <td>{(structures.current.drone_factories || 0) + (structures.hour_8.drone_factories || 0)}</td>
                            <td>{(structures.current.drone_factories || 0) + (structures.hour_24.drone_factories || 0)}</td>
                        </tr>
                    </tbody>
                </Table>
                <Table striped bordered hover>
                    <thead>
                        <tr>
                        <th></th>
                        <th>Now</th>
                        <th>1h</th>
                        <th>2h</th>
                        <th>4h</th>
                        <th>8h</th>
                        <th>24h</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Homes</td>
                            <td>{displayPercent((structures.current.homes || 0) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.homes || 0) + (structures.hour_1.homes || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.homes || 0) + (structures.hour_2.homes || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.homes || 0) + (structures.hour_4.homes || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.homes || 0) + (structures.hour_8.homes || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.homes || 0) + (structures.hour_24.homes || 0)) / props.kdInfo.stars)}</td>
                        </tr>
                        <tr>
                            <td>Mines</td>
                            <td>{displayPercent((structures.current.mines || 0) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.mines || 0) + (structures.hour_1.mines || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.mines || 0) + (structures.hour_2.mines || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.mines || 0) + (structures.hour_4.mines || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.mines || 0) + (structures.hour_8.mines || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.mines || 0) + (structures.hour_24.mines || 0)) / props.kdInfo.stars)}</td>
                        </tr>
                        <tr>
                            <td>Fuel Plants</td>
                            <td>{displayPercent((structures.current.fuel_plants || 0) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.fuel_plants || 0) + (structures.hour_1.fuel_plants || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.fuel_plants || 0) + (structures.hour_2.fuel_plants || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.fuel_plants || 0) + (structures.hour_4.fuel_plants || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.fuel_plants || 0) + (structures.hour_8.fuel_plants || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.fuel_plants || 0) + (structures.hour_24.fuel_plants || 0)) / props.kdInfo.stars)}</td>
                        </tr>
                        <tr>
                            <td>Hangars</td>
                            <td>{displayPercent((structures.current.hangars || 0) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.hangars || 0) + (structures.hour_1.hangars || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.hangars || 0) + (structures.hour_2.hangars || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.hangars || 0) + (structures.hour_4.hangars || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.hangars || 0) + (structures.hour_8.hangars || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.hangars || 0) + (structures.hour_24.hangars || 0)) / props.kdInfo.stars)}</td>
                        </tr>
                        <tr>
                            <td>Drone Factories</td>
                            <td>{displayPercent((structures.current.drone_factories || 0) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.drone_factories || 0) + (structures.hour_1.drone_factories || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.drone_factories || 0) + (structures.hour_2.drone_factories || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.drone_factories || 0) + (structures.hour_4.drone_factories || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.drone_factories || 0) + (structures.hour_8.drone_factories || 0)) / props.kdInfo.stars)}</td>
                            <td>{displayPercent(((structures.current.drone_factories || 0) + (structures.hour_24.drone_factories || 0)) / props.kdInfo.stars)}</td>
                        </tr>
                    </tbody>
                </Table>
            </div>
        </div>
    )
}

export default StatusContent;