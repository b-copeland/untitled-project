import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import ToastContainer from 'react-bootstrap/ToastContainer'
import "./primitives.css";
import Header from "../../components/header";



function Primitives(props) {
    const [key, setKey] = useState('attack');

    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="attack"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="attack" title="Attack">
          <AttackPrimitives
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}
            />
        </Tab>
        <Tab eventKey="rob" title="Rob">
          <RobPrimitives
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}/>
        </Tab>
      </Tabs>
    </>
    );
}

const initialAttackerValues = {
    "recruits": "",
    "attack": "",
    "flex": "",
    "big_flex": "",
    "military_bonus": "",
    "generals": "",
}

function AttackPrimitives(props) {
    const [attackerValues, setAttackerValues] = useState(initialAttackerValues);
    const [calcMessage, setCalcMessage] = useState({"message": "Press calculate to project results"})
    const [loadingCalc, setLoadingCalc] = useState(false);
    const [attackResults, setAttackResults] = useState([]);

    const handleAttackerChange = (e) => {
        const { name, value } = e.target;
        setAttackerValues({
          ...attackerValues,
          [name]: value,
        });
    };
    const onClickAttack = () => {
        const opts = {
            "attackerValues": attackerValues,
        };
        const updateFunc = async () => authFetch('api/attackprimitives', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r)); setCalcMessage("")})
        props.updateData(['kingdom', 'projects', 'attackhistory', 'mobis'], [updateFunc]);
    };
    const onClickCalculate = async (e) => {
        const opts = {
            "attackerValues": attackerValues,
        };
        const updateFunc = async () => authFetch('api/calculateprimitives', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setCalcMessage(r))
        setLoadingCalc(true);
        await updateFunc();
        setLoadingCalc(false);
    };
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    if (props.data.projects.current_bonuses?.military_bonus && attackerValues.military_bonus === "") {
        setAttackerValues({
            ...attackerValues,
            ["military_bonus"]: props.data.projects.current_bonuses.military_bonus,
        });
    }

    const toasts = attackResults.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setAttackResults(attackResults.slice(0, index).concat(attackResults.slice(index + 1, 999)))}
            show={true}
            bg={results.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Attack Results</strong>
            </Toast.Header>
            <Toast.Body>{results.message}</Toast.Body>
        </Toast>
    )
    return (
        <div className="primitives">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <h2>Attack Primitives</h2>
            <div className="text-box primitives-box">
                <span className="box-span">Your military will exploit primitive galaxies to conquer distant stars.</span>
                <br />
                <span className="box-span">Primitives defense per star: 150</span>
            </div>
            <div className="primitives-battle-stats">
                <div className="attacker-detail">
                    <Table className="attacker-table" striped bordered hover size="sm">
                        <thead>
                            <tr>
                                <th>Unit</th>
                                <th>Available</th>
                                <th>Offense</th>
                                <th>Input</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Attackers</td>
                                <td>{props.data.kingdom?.units?.attack?.toLocaleString()}</td>
                                <td>{props.data.mobis?.units_desc?.attack?.offense || "--"}</td>
                                <td>
                                    <Form.Control 
                                        className="unit-form"
                                        id="attack-input"
                                        name="attack"
                                        onChange={handleAttackerChange}
                                        value={attackerValues.attack || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                </td>
                            </tr>
                            <tr>
                                <td>Flexers</td>
                                <td>{props.data.kingdom?.units?.flex?.toLocaleString()}</td>
                                <td>{props.data.mobis?.units_desc?.flex?.offense || "--"}</td>
                                <td>
                                    <Form.Control 
                                        className="unit-form"
                                        id="flexers-input"
                                        name="flex"
                                        onChange={handleAttackerChange}
                                        value={attackerValues.flex || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                </td>
                            </tr>
                            <tr>
                                <td>Big Flexers</td>
                                <td>{props.data.kingdom?.units?.big_flex?.toLocaleString() || 0}</td>
                                <td>{props.data.mobis?.units_desc?.big_flex?.offense || "--"}</td>
                                <td>
                                    <Form.Control 
                                        className="unit-form"
                                        id="big-flexers-input"
                                        name="big_flex"
                                        onChange={handleAttackerChange}
                                        value={attackerValues.big_flex || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                </td>
                            </tr>
                            <tr>
                                <td>Military Efficiency</td>
                                <td></td>
                                <td></td>
                                <td>
                                    <Form.Control 
                                        className="unit-form"
                                        id="military-efficiency-input"
                                        name="military_bonus"
                                        onChange={handleAttackerChange}
                                        value={displayPercent(props.data.projects.current_bonuses?.military_bonus)} 
                                        placeholder="0"
                                        disabled
                                        autoComplete="off"
                                    />
                                </td>
                            </tr>
                            <tr>
                                <td>Other Bonuses</td>
                                <td></td>
                                <td></td>
                                <td>
                                    <Form.Control 
                                        className="unit-form"
                                        id="other-bonuses-input"
                                        name="other_bonuses"
                                        value="0%" 
                                        placeholder="0%"
                                        disabled
                                        autoComplete="off"
                                    />
                                </td>
                            </tr>
                            <tr>
                                <td>Generals</td>
                                <td>{props.data.kingdom?.generals_available}</td>
                                <td></td>
                                <td>
                                    <Form.Control 
                                        className="unit-form"
                                        id="generals-input"
                                        name="generals"
                                        onChange={handleAttackerChange}
                                        value={attackerValues.generals || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                </td>
                            </tr>
                        </tbody>
                    </Table>
                    <div className="attacker-text-boxes">
                        <div className="text-box attacker-losses-box">
                            <h4>Your Losses</h4> 
                            <div className="text-box-item">
                                <span className="text-box-item-title">Attackers</span>
                                <span className="text-box-item-value">{calcMessage.attacker_losses?.attack?.toLocaleString() || "--"}</span>
                            </div>
                            <div className="text-box-item">
                                <span className="text-box-item-title">Flexers</span>
                                <span className="text-box-item-value">{calcMessage.attacker_losses?.flex?.toLocaleString() || "--"}</span>
                            </div>
                            <div className="text-box-item">
                                <span className="text-box-item-title">Big Flexers</span>
                                <span className="text-box-item-value">{calcMessage.attacker_losses?.big_flex?.toLocaleString() || "--"}</span>
                            </div>
                            <br />
                            <br />
                            <br />
                            <div className="text-box-item">
                                <span className="text-box-item-title">Unit Loss Rate</span>
                                <span className="text-box-item-value">{displayPercent(calcMessage.attacker_unit_losses_rate) || "--"}</span>
                            </div>
                        </div>
                        <div className="text-box attacker-defense-box">
                            <h4>Your Offense</h4> 
                            <div className="text-box-item">
                                <span className="attacker-offense">{calcMessage.attacker_offense?.toLocaleString() || "--"}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div className="text-box attack-results-box">
                <span className="box-span">{calcMessage.message}</span>
            </div>
            <div className="attack-buttons">
                {
                    loadingCalc
                    ? <Button className="calculate-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="calculate-button" variant="primary" type="submit" onClick={onClickCalculate}>
                        Calculate
                    </Button>
                }
                {
                    props.loading.kingdom
                    ? <Button className="attack-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="attack-button" variant="primary" type="submit" onClick={onClickAttack}>
                        Attack
                    </Button>
                }
            </div>
        </div>
    )
}

function RobPrimitives(props) {
    const [results, setResults] = useState([]);
    const [drones, setDrones] = useState();
    const [shieldDrones, setShieldDrones] = useState(false);
    const handleShieldChange = (e) => {
        setShieldDrones(e.target.checked)
    };
    const handleDronesChange = (e) => {
        setDrones(e.target.value);
    };
    const onClickAttack = () => {
        const opts = {
            "drones": drones,
            "shielded": shieldDrones,
        };
        const updateFunc = async () => authFetch('api/robprimitives', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['kingdom', 'spyhistory'], [updateFunc]);
    };
    const toasts = results.map((result, index) =>
        <Toast
            key={index}
            onClose={(e) => setResults(results.slice(0, index).concat(results.slice(index + 1, 999)))}
            show={true}
            bg={result.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Rob Results</strong>
            </Toast.Header>
            <Toast.Body>{result.message}</Toast.Body>
        </Toast>
    )
    if (drones > props.data.kingdom["drones"]) {
        setDrones(Math.floor(props.data.kingdom["drones"]))
    }
    return (
        <div className="primitives">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <h2>Rob Primitives</h2>
            <div className="text-box primitives-box">
                <span className="box-span">Your drones will exploit primitive galaxies to steal resources.</span>
                <br />
                <span className="box-span">Primitives money per drone: 2</span>
            </div>
            <InputGroup className="mb-3 drones-input-group">
                <InputGroup.Text id="basic-addon2">Drones (Max {Math.floor(props.data.kingdom?.drones).toLocaleString()})</InputGroup.Text>
                <Form.Control 
                    className="unit-form"
                    id="drones-input"
                    name="drones"
                    onChange={handleDronesChange}
                    value={drones || ""} 
                    placeholder="0"
                    autoComplete="off"
                />
            </InputGroup>
            <Form>
                <Form.Check 
                    type="switch"
                    id="shield-drones-switch"
                    label="Shield Drones?"
                    onChange={handleShieldChange}
                />
            </Form>
            <span>Spy Attempts Remaining: {props.data.kingdom["spy_attempts"]}</span>
            {
                props.loading.kingdom
                ? <Button className="rob-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="rob-button" variant="primary" type="submit" onClick={onClickAttack}>
                    Rob
                </Button>
            }
        </div>
    )
}
  
export default Primitives;