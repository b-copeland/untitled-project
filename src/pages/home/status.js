import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
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
          <Status kingdom={props.data.kingdom} kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} state={props.data.state}/>
        </Tab>
        <Tab eventKey="shields" title="Shields">
          <Shields data={props.data} loading={props.loading} updateData={props.updateData}/>
        </Tab>
        <Tab eventKey="spending" title="Spending">
          <Spending kingdom={props.data.kingdom} loading={props.loading} updateData={props.updateData} />
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
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

function Status(props) {
    if (Object.keys(props.kingdom).length === 0 || Object.keys(props.state).length === 0) {
        return null;
    }
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const unitsFuelCosts = Object.keys(props.kingdom.income?.fuel?.units || {}).sort().map((unit) => 
        <div className="text-box-item" key={unit}>
            <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;{props.state.pretty_names[unit] || unit}</span>
            <span className="text-box-item-value">-{props.kingdom.income?.fuel?.units[unit].toLocaleString()}</span>
        </div>
    )
    const shieldsFuelCosts = Object.keys(props.kingdom.income?.fuel?.shields || {}).sort().map((shield) => 
        <div className="text-box-item" key={shield}>
            <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;{(shield === "spy_radar") ? "Spy radar" : capitalizeFirstLetter(shield) + " shields"}</span>
            <span className="text-box-item-value">-{props.kingdom.income?.fuel?.shields[shield].toLocaleString()}</span>
        </div>
    )
    return (
        <div className="status">
            <div className="text-box kingdom-card">
                <h4>{props.kingdoms[props.kingdom.kdId] || ""} ({props.galaxies_inverted[props.kingdom.kdId] || ""})</h4>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Name</span>
                    <span className="text-box-item-value">{props.kingdoms[props.kingdom.kdId] || ""}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Race</span>
                    <span className="text-box-item-value">{props.kingdom.race}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Stars</span>
                    <span className="text-box-item-value">{props.kingdom.stars?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Population</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.population)?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Fuel</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.fuel)?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Engineers</span>
                    <span className="text-box-item-value">{props.kingdom["units"]?.engineers.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Drones</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.drones)?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Attackers</span>
                    <span className="text-box-item-value">{props.kingdom["units"]?.attack.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Defenders</span>
                    <span className="text-box-item-value">{props.kingdom["units"]?.defense.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Flexers</span>
                    <span className="text-box-item-value">{props.kingdom["units"]?.flex.toLocaleString()}</span>
                </div>
            </div>
            <div className="text-box income-box">
                <h3>Income (per hour)</h3>
                <div className="text-box-item">
                    <span className="text-box-item-title">Money</span>
                    <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.money?.net).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Mines</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.income?.money?.mines).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Population</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.income?.money?.population).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Bonus</span>
                    <span className="text-box-item-value">{displayPercent(props.kingdom.income?.money?.bonus)}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Siphons In</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.income?.money?.siphons_in).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Siphons Out</span>
                    <span className="text-box-item-value">-{Math.floor(props.kingdom.income?.money?.siphons_out).toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Fuel</span>
                    <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.fuel?.net).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Fuel Plants</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.income?.fuel?.fuel_plants).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Bonus</span>
                    <span className="text-box-item-value">{displayPercent(props.kingdom.income?.fuel?.bonus)}</span>
                </div>
                <br />
                {unitsFuelCosts}
                <br />
                {shieldsFuelCosts}
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Population</span>
                    <span className="text-box-item-value">-{Math.floor(props.kingdom.income?.fuel?.population).toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Population</span>
                    <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.population).toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Drones</span>
                    <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.drones).toLocaleString()}</span>
                </div>
            </div>
        </div>
    );
}


const initialShields = {
    "military": "",
    "spy": "",
    "spy_radar": "",
    "missiles": "",
}
function Shields(props) {
    const [shields, setShields] = useState(initialShields);
    const [results, setResults] = useState([]);
    
    const onClick = (e)=>{
        const opts = shields;
        const updateFunc = () => authFetch('api/shields', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['kingdom'], [updateFunc]);
        // setShields(initialShields);
    }
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setShields({
          ...shields,
          [name]: value,
        });
      };
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const toasts = results.map((result, index) =>
        <Toast
            key={index}
            onClose={(e) => setResults(results.slice(0, index).concat(results.slice(index + 1, 999)))}
            show={true}
            bg={result.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Shields Results</strong>
            </Toast.Header>
            <Toast.Body>{result.message}</Toast.Body>
        </Toast>
    )
    return (
        <div className="shields">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <Table className="projects-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th>Shield</th>
                        <th>Current %</th>
                        <th>Max %</th>
                        <th>Current Power Cost</th>
                        <th>Max Power Cost</th>
                        <td>Input</td>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Military</td>
                        <td>{displayPercent(props.data.kingdom.shields?.military || 0)}</td>
                        <td>{displayPercent(props.data.shields.desc?.military?.max || 0)}</td>
                        <td>{Math.floor(props.data.kingdom.shields?.military * props.data.shields.desc?.military?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.data.shields.desc?.military?.max * props.data.shields.desc?.military?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3">
                                <Form.Control
                                className="shields-assign-form"
                                id="military-input"
                                onChange={handleInputChange}
                                name="military"
                                value={shields.military || ""} 
                                placeholder="0"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                    <tr>
                        <td>Spy</td>
                        <td>{displayPercent(props.data.kingdom.shields?.spy || 0)}</td>
                        <td>{displayPercent(props.data.shields.desc?.spy?.max || 0)}</td>
                        <td>{Math.floor(props.data.kingdom.shields?.spy * props.data.shields.desc?.spy?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.data.shields.desc?.spy?.max * props.data.shields.desc?.spy?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3">
                                <Form.Control
                                className="shields-assign-form"
                                id="spy-input"
                                onChange={handleInputChange}
                                name="spy"
                                value={shields.spy || ""} 
                                placeholder="0"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                    <tr>
                        <td>Spy Radar</td>
                        <td>{displayPercent(props.data.kingdom.shields?.spy_radar || 0)}</td>
                        <td>{displayPercent(props.data.shields.desc?.spy_radar?.max || 0)}</td>
                        <td>{Math.floor(props.data.kingdom.shields?.spy_radar * props.data.shields.desc?.spy_radar?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.data.shields.desc?.spy_radar?.max * props.data.shields.desc?.spy_radar?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3">
                                <Form.Control
                                className="shields-assign-form"
                                id="spy-radar-input"
                                onChange={handleInputChange}
                                name="spy_radar"
                                value={shields.spy_radar || ""} 
                                placeholder="0"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                    <tr>
                        <td>Missiles</td>
                        <td>{displayPercent(props.data.kingdom.shields?.missiles || 0)}</td>
                        <td>{displayPercent(props.data.shields.desc?.missiles?.max || 0)}</td>
                        <td>{Math.floor(props.data.kingdom.shields?.missiles * props.data.shields.desc?.missiles?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>{Math.floor(props.data.shields.desc?.missiles?.max * props.data.shields.desc?.missiles?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3">
                                <Form.Control
                                className="shields-assign-form"
                                id="missiles-input"
                                onChange={handleInputChange}
                                name="missiles"
                                value={shields.missiles || ""} 
                                placeholder="0"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                </tbody>
            </Table>
            {props.loading.kingdom
            ? <Button className="shields-button" variant="primary" type="submit" disabled>
                Loading...
            </Button>
            : <Button className="shields-button" variant="primary" type="submit" onClick={onClick}>
                Update
            </Button>
            }
        </div>
    )
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

    return <h2>Coming Soon...</h2>
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
    const units = props.mobis?.units || {};
    const maxOffense = props.mobis?.maxes?.offense || {};
    const maxDefense = props.mobis?.maxes?.defense || {};
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
                            <td>{units.current?.recruits?.toLocaleString() || 0}</td>
                            <td>{units.general_0?.recruits?.toLocaleString() || 0}</td>
                            <td>{units.general_1?.recruits?.toLocaleString() || 0}</td>
                            <td>{units.general_2?.recruits?.toLocaleString() || 0}</td>
                            <td>{units.general_3?.recruits?.toLocaleString() || 0}</td>
                        </tr>
                        <tr>
                            <td>Attackers</td>
                            <td>{units.current?.attack?.toLocaleString() || 0}</td>
                            <td>{units.general_0?.attack?.toLocaleString() || 0}</td>
                            <td>{units.general_1?.attack?.toLocaleString() || 0}</td>
                            <td>{units.general_2?.attack?.toLocaleString() || 0}</td>
                            <td>{units.general_3?.attack?.toLocaleString() || 0}</td>
                        </tr>
                        <tr>
                            <td>Defenders</td>
                            <td>{units.current?.defense?.toLocaleString() || 0}</td>
                            <td>{units.general_0?.defense?.toLocaleString() || 0}</td>
                            <td>{units.general_1?.defense?.toLocaleString() || 0}</td>
                            <td>{units.general_2?.defense?.toLocaleString() || 0}</td>
                            <td>{units.general_3?.defense?.toLocaleString() || 0}</td>
                        </tr>
                        <tr>
                            <td>Flexers</td>
                            <td>{units.current?.flex?.toLocaleString() || 0}</td>
                            <td>{units.general_0?.flex?.toLocaleString() || 0}</td>
                            <td>{units.general_1?.flex?.toLocaleString() || 0}</td>
                            <td>{units.general_2?.flex?.toLocaleString() || 0}</td>
                            <td>{units.general_3?.flex?.toLocaleString() || 0}</td>
                        </tr>
                        <tr>
                            <td>Big Flexers</td>
                            <td>{units.current?.big_flex?.toLocaleString() || 0}</td>
                            <td>{units.general_0?.big_flex?.toLocaleString() || 0}</td>
                            <td>{units.general_1?.big_flex?.toLocaleString() || 0}</td>
                            <td>{units.general_2?.big_flex?.toLocaleString() || 0}</td>
                            <td>{units.general_3?.big_flex?.toLocaleString() || 0}</td>
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
                            <td>{Math.floor(maxOffense.current || 0).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0) + (maxOffense.general_2 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0) + (maxOffense.general_2 || 0) + (maxOffense.general_3 || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Max defense</td>
                            <td>{Math.floor(maxDefense.current || 0).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0) + (maxDefense.general_2 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0) + (maxDefense.general_2 || 0) + (maxDefense.general_3 || 0)).toLocaleString()}</td>
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
                            <td>{Math.floor(units.current_total?.recruits || 0).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.recruits || 0) + (units.hour_1?.recruits || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.recruits || 0) + (units.hour_2?.recruits || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.recruits || 0) + (units.hour_4?.recruits || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.recruits || 0) + (units.hour_8?.recruits || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.recruits || 0) + (units.hour_24?.recruits || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Attackers</td>
                            <td>{Math.floor(units.current_total?.attack || 0).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.attack || 0) + (units.hour_1?.attack || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.attack || 0) + (units.hour_2?.attack || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.attack || 0) + (units.hour_4?.attack || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.attack || 0) + (units.hour_8?.attack || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.attack || 0) + (units.hour_24?.attack || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Defenders</td>
                            <td>{Math.floor(units.current_total?.defense || 0).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.defense || 0) + (units.hour_1?.defense || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.defense || 0) + (units.hour_2?.defense || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.defense || 0) + (units.hour_4?.defense || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.defense || 0) + (units.hour_8?.defense || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.defense || 0) + (units.hour_24?.defense || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Flexers</td>
                            <td>{Math.floor(units.current_total?.flex || 0).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.flex || 0) + (units.hour_1?.flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.flex || 0) + (units.hour_2?.flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.flex || 0) + (units.hour_4?.flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.flex || 0) + (units.hour_8?.flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.flex || 0) + (units.hour_24?.flex || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Big Flexers</td>
                            <td>{Math.floor(units.current_total?.big_flex || 0).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.big_flex || 0) + (units.hour_1?.big_flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.big_flex || 0) + (units.hour_2?.big_flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.big_flex || 0) + (units.hour_4?.big_flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.big_flex || 0) + (units.hour_8?.big_flex || 0)).toLocaleString()}</td>
                            <td>{Math.floor((units.current_total?.big_flex || 0) + (units.hour_24?.big_flex || 0)).toLocaleString()}</td>
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
                            <td>{Math.floor(maxOffense.current_total || 0).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current_total || 0) + (maxOffense.hour_1 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current_total || 0) + (maxOffense.hour_2 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current_total || 0) + (maxOffense.hour_4 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current_total || 0) + (maxOffense.hour_8 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxOffense.current_total || 0) + (maxOffense.hour_24 || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Max defense</td>
                            <td>{Math.floor(maxDefense.current_total || 0).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current_total || 0) + (maxDefense.hour_1 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current_total || 0) + (maxDefense.hour_2 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current_total || 0) + (maxDefense.hour_4 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current_total || 0) + (maxDefense.hour_8 || 0)).toLocaleString()}</td>
                            <td>{Math.floor((maxDefense.current_total || 0) + (maxDefense.hour_24 || 0)).toLocaleString()}</td>
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
                            <td>{Math.floor(props.structures.current?.homes || 0).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.homes || 0) + (props.structures.hour_1?.homes || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.homes || 0) + (props.structures.hour_2?.homes || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.homes || 0) + (props.structures.hour_4?.homes || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.homes || 0) + (props.structures.hour_8?.homes || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.homes || 0) + (props.structures.hour_24?.homes || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Mines</td>
                            <td>{Math.floor(props.structures.current?.mines || 0).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.mines || 0) + (props.structures.hour_1?.mines || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.mines || 0) + (props.structures.hour_2?.mines || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.mines || 0) + (props.structures.hour_4?.mines || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.mines || 0) + (props.structures.hour_8?.mines || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.mines || 0) + (props.structures.hour_24?.mines || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Fuel Plants</td>
                            <td>{Math.floor(props.structures.current?.fuel_plants || 0).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.fuel_plants || 0) + (props.structures.hour_1?.fuel_plants || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.fuel_plants || 0) + (props.structures.hour_2?.fuel_plants || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.fuel_plants || 0) + (props.structures.hour_4?.fuel_plants || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.fuel_plants || 0) + (props.structures.hour_8?.fuel_plants || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.fuel_plants || 0) + (props.structures.hour_24?.fuel_plants || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Hangars</td>
                            <td>{Math.floor(props.structures.current?.hangars || 0).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.hangars || 0) + (props.structures.hour_1?.hangars || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.hangars || 0) + (props.structures.hour_2?.hangars || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.hangars || 0) + (props.structures.hour_4?.hangars || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.hangars || 0) + (props.structures.hour_8?.hangars || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.hangars || 0) + (props.structures.hour_24?.hangars || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Drone Factories</td>
                            <td>{Math.floor(props.structures.current?.drone_factories || 0).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.drone_factories || 0) + (props.structures.hour_1?.drone_factories || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.drone_factories || 0) + (props.structures.hour_2?.drone_factories || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.drone_factories || 0) + (props.structures.hour_4?.drone_factories || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.drone_factories || 0) + (props.structures.hour_8?.drone_factories || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.drone_factories || 0) + (props.structures.hour_24?.drone_factories || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Missile Silos</td>
                            <td>{Math.floor(props.structures.current?.missile_silos || 0).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.missile_silos || 0) + (props.structures.hour_1?.missile_silos || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.missile_silos || 0) + (props.structures.hour_2?.missile_silos || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.missile_silos || 0) + (props.structures.hour_4?.missile_silos || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.missile_silos || 0) + (props.structures.hour_8?.missile_silos || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.missile_silos || 0) + (props.structures.hour_24?.missile_silos || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td>Workshops</td>
                            <td>{Math.floor(props.structures.current?.workshops || 0).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.workshops || 0) + (props.structures.hour_1?.workshops || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.workshops || 0) + (props.structures.hour_2?.workshops || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.workshops || 0) + (props.structures.hour_4?.workshops || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.workshops || 0) + (props.structures.hour_8?.workshops || 0)).toLocaleString()}</td>
                            <td>{Math.floor((props.structures.current?.workshops || 0) + (props.structures.hour_24?.workshops || 0)).toLocaleString()}</td>
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
                            <td>{displayPercent((props.structures.current?.homes || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.homes || 0) + (props.structures.hour_1?.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.homes || 0) + (props.structures.hour_2?.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.homes || 0) + (props.structures.hour_4?.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.homes || 0) + (props.structures.hour_8?.homes || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.homes || 0) + (props.structures.hour_24?.homes || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Mines</td>
                            <td>{displayPercent((props.structures.current?.mines || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.mines || 0) + (props.structures.hour_1?.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.mines || 0) + (props.structures.hour_2?.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.mines || 0) + (props.structures.hour_4?.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.mines || 0) + (props.structures.hour_8?.mines || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.mines || 0) + (props.structures.hour_24?.mines || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Fuel Plants</td>
                            <td>{displayPercent((props.structures.current?.fuel_plants || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.fuel_plants || 0) + (props.structures.hour_1?.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.fuel_plants || 0) + (props.structures.hour_2?.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.fuel_plants || 0) + (props.structures.hour_4?.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.fuel_plants || 0) + (props.structures.hour_8?.fuel_plants || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.fuel_plants || 0) + (props.structures.hour_24?.fuel_plants || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Hangars</td>
                            <td>{displayPercent((props.structures.current?.hangars || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.hangars || 0) + (props.structures.hour_1?.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.hangars || 0) + (props.structures.hour_2?.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.hangars || 0) + (props.structures.hour_4?.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.hangars || 0) + (props.structures.hour_8?.hangars || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.hangars || 0) + (props.structures.hour_24?.hangars || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Drone Factories</td>
                            <td>{displayPercent((props.structures.current?.drone_factories || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.drone_factories || 0) + (props.structures.hour_1?.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.drone_factories || 0) + (props.structures.hour_2?.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.drone_factories || 0) + (props.structures.hour_4?.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.drone_factories || 0) + (props.structures.hour_8?.drone_factories || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.drone_factories || 0) + (props.structures.hour_24?.drone_factories || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Missile Silos</td>
                            <td>{displayPercent((props.structures.current?.missile_silos || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.missile_silos || 0) + (props.structures.hour_1?.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.missile_silos || 0) + (props.structures.hour_2?.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.missile_silos || 0) + (props.structures.hour_4?.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.missile_silos || 0) + (props.structures.hour_8?.missile_silos || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.missile_silos || 0) + (props.structures.hour_24?.missile_silos || 0)) / props.kingdom.stars)}</td>
                        </tr>
                        <tr>
                            <td>Workshops</td>
                            <td>{displayPercent((props.structures.current?.workshops || 0) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.workshops || 0) + (props.structures.hour_1?.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.workshops || 0) + (props.structures.hour_2?.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.workshops || 0) + (props.structures.hour_4?.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.workshops || 0) + (props.structures.hour_8?.workshops || 0)) / props.kingdom.stars)}</td>
                            <td>{displayPercent(((props.structures.current?.workshops || 0) + (props.structures.hour_24?.workshops || 0)) / props.kingdom.stars)}</td>
                        </tr>
                    </tbody>
                </Table>
            </div>
        </div>
    )
}

export default StatusContent;