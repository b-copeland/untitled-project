import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import "./status.css"

function StatusContent(props) {
    const [key, setKey] = useState('kingdom');

    return (
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="kingdom"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="kingdom" title="Kingdom">
          <Status kingdom={props.data.kingdom}/>
        </Tab>
        <Tab eventKey="revealed" title="Revealed">
          <Revealed kingdom={props.data.kingdom} kingdoms={props.data.kingdoms}/>
        </Tab>
        <Tab eventKey="spending" title="Spending">
          <Spending kingdom={props.data.kingdom} loading={props.loading} /*updateData={keys => props.updateData(keys)}*/ updateData={props.updateData} />
        </Tab>
        <Tab eventKey="military" title="Military">
          <Military mobis={props.data.mobis} />
        </Tab>
        <Tab eventKey="structures" title="Structures">
          <Structures kingdom={props.data.kingdom} structures={props.data.structures}/>
        </Tab>
      </Tabs>
    );
}

function Status(props) {
    if (Object.keys(props.kingdoms).length === 0) {
        return null;
    }
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
                    <span className="text-box-item-value">{props.data.kingdom.stars}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Population</span>
                    <span className="text-box-item-value">{props.data.kingdom.population}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Fuel</span>
                    <span className="text-box-item-value">{props.data.kingdom.fuel}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Engineers</span>
                    <span className="text-box-item-value">{props.data.kingdom["units"]?.engineers}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Drones</span>
                    <span className="text-box-item-value">{props.data.kingdom.drones}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Attackers</span>
                    <span className="text-box-item-value">{props.data.kingdom["units"]?.attack}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Defenders</span>
                    <span className="text-box-item-value">{props.data.kingdom["units"]?.defense}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Flexers</span>
                    <span className="text-box-item-value">{props.data.kingdom["units"]?.flex}</span>
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
    const revealed_to = props.kingdom?.revealed_to;
    if (revealed_to === undefined) {
        return null
    }
    if (Object.keys(props.kingdoms).length === 0) {
        return null;
    }
    const revealedItems = Object.keys(revealed_to).map((kdId) =>
        <div key={kdId} className="text-box-item">
            <span className="text-box-item-title" >{props.kingdoms[kdId]}</span>
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
    const [settleInput, setSettleInput] = useState('');
    const [structuresInput, setStructuresInput] = useState('');
    const [militaryInput, setMilitaryInput] = useState('');
    const [engineersInput, setEngineersInput] = useState('');

    const spendingInfo = props.kingdom?.auto_spending;
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

    const onSubmitClick = async (e)=>{
        let opts = {
            'settleInput': settleInput === '' ? undefined : settleInput,
            'structuresInput': structuresInput === '' ? undefined : structuresInput,
            'militaryInput': militaryInput === '' ? undefined : militaryInput,
            'engineersInput': engineersInput === '' ? undefined : engineersInput,
        }
        const updateFunc = () => authFetch('api/spending', {
            method: 'post',
            body: JSON.stringify(opts)
        })
        props.updateData(['kingdom'], [updateFunc])
        setSettleInput('');
        setStructuresInput('');
        setMilitaryInput('');
        setEngineersInput('');
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
            {props.loading.kingdom
            ? <Button className="spending-button" variant="primary" type="submit" disabled>
                Loading...
            </Button>
            : <Button className="spending-button" variant="primary" type="submit" onClick={onSubmitClick}>
                Submit
            </Button>
            }
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

function Military(props) {
    if (Object.keys(props.mobis).length === 0) {
        return null;
    }
    const units = props.mobis?.units;
    const maxOffense = props.mobis?.maxes.offense;
    const maxDefense = props.mobis?.maxes.defense;
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
                            <td>Recruits</td>
                            <td>{units.current?.recruits || 0}</td>
                            <td>{units.general_0?.recruits || 0}</td>
                            <td>{units.general_1?.recruits || 0}</td>
                            <td>{units.general_2?.recruits || 0}</td>
                            <td>{units.general_3?.recruits || 0}</td>
                        </tr>
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
                        <tr>
                            <td>Big Flexers</td>
                            <td>{units.current?.big_flex || 0}</td>
                            <td>{units.general_0?.big_flex || 0}</td>
                            <td>{units.general_1?.big_flex || 0}</td>
                            <td>{units.general_2?.big_flex || 0}</td>
                            <td>{units.general_3?.big_flex || 0}</td>
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
                            <td>Recruits</td>
                            <td>{units.current_total.recruits || 0}</td>
                            <td>{(units.current_total.recruits || 0) + (units.hour_1.recruits || 0)}</td>
                            <td>{(units.current_total.recruits || 0) + (units.hour_2.recruits || 0)}</td>
                            <td>{(units.current_total.recruits || 0) + (units.hour_4.recruits || 0)}</td>
                            <td>{(units.current_total.recruits || 0) + (units.hour_8.recruits || 0)}</td>
                            <td>{(units.current_total.recruits || 0) + (units.hour_24.recruits || 0)}</td>
                        </tr>
                        <tr>
                            <td>Attackers</td>
                            <td>{units.current_total.attack || 0}</td>
                            <td>{(units.current_total.attack || 0) + (units.hour_1.attack || 0)}</td>
                            <td>{(units.current_total.attack || 0) + (units.hour_2.attack || 0)}</td>
                            <td>{(units.current_total.attack || 0) + (units.hour_4.attack || 0)}</td>
                            <td>{(units.current_total.attack || 0) + (units.hour_8.attack || 0)}</td>
                            <td>{(units.current_total.attack || 0) + (units.hour_24.attack || 0)}</td>
                        </tr>
                        <tr>
                            <td>Defenders</td>
                            <td>{units.current_total.defense || 0}</td>
                            <td>{(units.current_total.defense || 0) + (units.hour_1.defense || 0)}</td>
                            <td>{(units.current_total.defense || 0) + (units.hour_2.defense || 0)}</td>
                            <td>{(units.current_total.defense || 0) + (units.hour_4.defense || 0)}</td>
                            <td>{(units.current_total.defense || 0) + (units.hour_8.defense || 0)}</td>
                            <td>{(units.current_total.defense || 0) + (units.hour_24.defense || 0)}</td>
                        </tr>
                        <tr>
                            <td>Flexers</td>
                            <td>{units.current_total.flex || 0}</td>
                            <td>{(units.current_total.flex || 0) + (units.hour_1.flex || 0)}</td>
                            <td>{(units.current_total.flex || 0) + (units.hour_2.flex || 0)}</td>
                            <td>{(units.current_total.flex || 0) + (units.hour_4.flex || 0)}</td>
                            <td>{(units.current_total.flex || 0) + (units.hour_8.flex || 0)}</td>
                            <td>{(units.current_total.flex || 0) + (units.hour_24.flex || 0)}</td>
                        </tr>
                        <tr>
                            <td>Big Flexers</td>
                            <td>{units.current_total.big_flex || 0}</td>
                            <td>{(units.current_total.big_flex || 0) + (units.hour_1.big_flex || 0)}</td>
                            <td>{(units.current_total.big_flex || 0) + (units.hour_2.big_flex || 0)}</td>
                            <td>{(units.current_total.big_flex || 0) + (units.hour_4.big_flex || 0)}</td>
                            <td>{(units.current_total.big_flex || 0) + (units.hour_8.big_flex || 0)}</td>
                            <td>{(units.current_total.big_flex || 0) + (units.hour_24.big_flex || 0)}</td>
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
                            <td>{maxOffense.current_total || 0}</td>
                            <td>{(maxOffense.current_total || 0) + (maxOffense.hour_1 || 0)}</td>
                            <td>{(maxOffense.current_total || 0) + (maxOffense.hour_2 || 0)}</td>
                            <td>{(maxOffense.current_total || 0) + (maxOffense.hour_4 || 0)}</td>
                            <td>{(maxOffense.current_total || 0) + (maxOffense.hour_8 || 0)}</td>
                            <td>{(maxOffense.current_total || 0) + (maxOffense.hour_24 || 0)}</td>
                        </tr>
                        <tr>
                            <td>Max defense</td>
                            <td>{maxDefense.current_total || 0}</td>
                            <td>{(maxDefense.current_total || 0) + (maxDefense.hour_1 || 0)}</td>
                            <td>{(maxDefense.current_total || 0) + (maxDefense.hour_2 || 0)}</td>
                            <td>{(maxDefense.current_total || 0) + (maxDefense.hour_4 || 0)}</td>
                            <td>{(maxDefense.current_total || 0) + (maxDefense.hour_8 || 0)}</td>
                            <td>{(maxDefense.current_total || 0) + (maxDefense.hour_24 || 0)}</td>
                        </tr>
                    </tbody>
                </Table>
            </div>
        </div>
    )
}

function Structures(props) {    
    if (Object.keys(props.structures).length === 0) {
        return null;
    }
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
                            <td>{props.structures.current.homes || 0}</td>
                            <td>{(props.structures.current.homes || 0) + (props.structures.hour_1.homes || 0)}</td>
                            <td>{(props.structures.current.homes || 0) + (props.structures.hour_2.homes || 0)}</td>
                            <td>{(props.structures.current.homes || 0) + (props.structures.hour_4.homes || 0)}</td>
                            <td>{(props.structures.current.homes || 0) + (props.structures.hour_8.homes || 0)}</td>
                            <td>{(props.structures.current.homes || 0) + (props.structures.hour_24.homes || 0)}</td>
                        </tr>
                        <tr>
                            <td>Mines</td>
                            <td>{props.structures.current.mines || 0}</td>
                            <td>{(props.structures.current.mines || 0) + (props.structures.hour_1.mines || 0)}</td>
                            <td>{(props.structures.current.mines || 0) + (props.structures.hour_2.mines || 0)}</td>
                            <td>{(props.structures.current.mines || 0) + (props.structures.hour_4.mines || 0)}</td>
                            <td>{(props.structures.current.mines || 0) + (props.structures.hour_8.mines || 0)}</td>
                            <td>{(props.structures.current.mines || 0) + (props.structures.hour_24.mines || 0)}</td>
                        </tr>
                        <tr>
                            <td>Fuel Plants</td>
                            <td>{props.structures.current.fuel_plants || 0}</td>
                            <td>{(props.structures.current.fuel_plants || 0) + (props.structures.hour_1.fuel_plants || 0)}</td>
                            <td>{(props.structures.current.fuel_plants || 0) + (props.structures.hour_2.fuel_plants || 0)}</td>
                            <td>{(props.structures.current.fuel_plants || 0) + (props.structures.hour_4.fuel_plants || 0)}</td>
                            <td>{(props.structures.current.fuel_plants || 0) + (props.structures.hour_8.fuel_plants || 0)}</td>
                            <td>{(props.structures.current.fuel_plants || 0) + (props.structures.hour_24.fuel_plants || 0)}</td>
                        </tr>
                        <tr>
                            <td>Hangars</td>
                            <td>{props.structures.current.hangars || 0}</td>
                            <td>{(props.structures.current.hangars || 0) + (props.structures.hour_1.hangars || 0)}</td>
                            <td>{(props.structures.current.hangars || 0) + (props.structures.hour_2.hangars || 0)}</td>
                            <td>{(props.structures.current.hangars || 0) + (props.structures.hour_4.hangars || 0)}</td>
                            <td>{(props.structures.current.hangars || 0) + (props.structures.hour_8.hangars || 0)}</td>
                            <td>{(props.structures.current.hangars || 0) + (props.structures.hour_24.hangars || 0)}</td>
                        </tr>
                        <tr>
                            <td>Drone Factories</td>
                            <td>{props.structures.current.drone_factories || 0}</td>
                            <td>{(props.structures.current.drone_factories || 0) + (props.structures.hour_1.drone_factories || 0)}</td>
                            <td>{(props.structures.current.drone_factories || 0) + (props.structures.hour_2.drone_factories || 0)}</td>
                            <td>{(props.structures.current.drone_factories || 0) + (props.structures.hour_4.drone_factories || 0)}</td>
                            <td>{(props.structures.current.drone_factories || 0) + (props.structures.hour_8.drone_factories || 0)}</td>
                            <td>{(props.structures.current.drone_factories || 0) + (props.structures.hour_24.drone_factories || 0)}</td>
                        </tr>
                        <tr>
                            <td>Missile Silos</td>
                            <td>{props.structures.current.missile_silos || 0}</td>
                            <td>{(props.structures.current.missile_silos || 0) + (props.structures.hour_1.missile_silos || 0)}</td>
                            <td>{(props.structures.current.missile_silos || 0) + (props.structures.hour_2.missile_silos || 0)}</td>
                            <td>{(props.structures.current.missile_silos || 0) + (props.structures.hour_4.missile_silos || 0)}</td>
                            <td>{(props.structures.current.missile_silos || 0) + (props.structures.hour_8.missile_silos || 0)}</td>
                            <td>{(props.structures.current.missile_silos || 0) + (props.structures.hour_24.missile_silos || 0)}</td>
                        </tr>
                        <tr>
                            <td>Workshops</td>
                            <td>{props.structures.current.workshops || 0}</td>
                            <td>{(props.structures.current.workshops || 0) + (props.structures.hour_1.workshops || 0)}</td>
                            <td>{(props.structures.current.workshops || 0) + (props.structures.hour_2.workshops || 0)}</td>
                            <td>{(props.structures.current.workshops || 0) + (props.structures.hour_4.workshops || 0)}</td>
                            <td>{(props.structures.current.workshops || 0) + (props.structures.hour_8.workshops || 0)}</td>
                            <td>{(props.structures.current.workshops || 0) + (props.structures.hour_24.workshops || 0)}</td>
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
                            <td>{displayPercent((props.structures.current.homes || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.homes || 0) + (props.structures.hour_1.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.homes || 0) + (props.structures.hour_2.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.homes || 0) + (props.structures.hour_4.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.homes || 0) + (props.structures.hour_8.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.homes || 0) + (props.structures.hour_24.homes || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Mines</td>
                            <td>{displayPercent((props.structures.current.mines || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.mines || 0) + (props.structures.hour_1.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.mines || 0) + (props.structures.hour_2.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.mines || 0) + (props.structures.hour_4.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.mines || 0) + (props.structures.hour_8.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.mines || 0) + (props.structures.hour_24.mines || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Fuel Plants</td>
                            <td>{displayPercent((props.structures.current.fuel_plants || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.fuel_plants || 0) + (props.structures.hour_1.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.fuel_plants || 0) + (props.structures.hour_2.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.fuel_plants || 0) + (props.structures.hour_4.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.fuel_plants || 0) + (props.structures.hour_8.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.fuel_plants || 0) + (props.structures.hour_24.fuel_plants || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Hangars</td>
                            <td>{displayPercent((props.structures.current.hangars || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.hangars || 0) + (props.structures.hour_1.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.hangars || 0) + (props.structures.hour_2.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.hangars || 0) + (props.structures.hour_4.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.hangars || 0) + (props.structures.hour_8.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.hangars || 0) + (props.structures.hour_24.hangars || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Drone Factories</td>
                            <td>{displayPercent((props.structures.current.drone_factories || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.drone_factories || 0) + (props.structures.hour_1.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.drone_factories || 0) + (props.structures.hour_2.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.drone_factories || 0) + (props.structures.hour_4.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.drone_factories || 0) + (props.structures.hour_8.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.drone_factories || 0) + (props.structures.hour_24.drone_factories || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Missile Silos</td>
                            <td>{displayPercent((props.structures.current.missile_silos || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.missile_silos || 0) + (props.structures.hour_1.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.missile_silos || 0) + (props.structures.hour_2.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.missile_silos || 0) + (props.structures.hour_4.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.missile_silos || 0) + (props.structures.hour_8.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.missile_silos || 0) + (props.structures.hour_24.missile_silos || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Workshops</td>
                            <td>{displayPercent((props.structures.current.workshops || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.workshops || 0) + (props.structures.hour_1.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.workshops || 0) + (props.structures.hour_2.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.workshops || 0) + (props.structures.hour_4.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.workshops || 0) + (props.structures.hour_8.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current.workshops || 0) + (props.structures.hour_24.workshops || 0)) / props.kingdom.stars)}</td>
                        </tr>
                    </tbody>
                </Table>
            </div>
        </div>
    )
}

export default StatusContent;