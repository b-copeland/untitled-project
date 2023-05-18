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
import HelpButton from "../../components/helpbutton";



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
      <HelpButton scrollTarget={"primitives"}/>
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
    const [enabled, setEnabled] = useState(props.data.kingdom.auto_attack_enabled)
    const [autoPure, setAutoPure] = useState("");
    const [autoFlex, setAutoFlex] = useState("");

    const handleAttackerChange = (e) => {
        const { name, value } = e.target;
        setAttackerValues({
          ...attackerValues,
          [name]: value,
        });
    };
    const handleEnabledChange = (e) => {
        let opts = {
            'enabled': e.target.checked
        }
        const updateFunc = () => authFetch('api/attackprimitives/auto', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
        setEnabled(e.target.checked)
    }
    const handleAutoPureInput = (e) => {
        setAutoPure(e.target.value)
    }
    const handleAutoFlexInput = (e) => {
        setAutoFlex(e.target.value)
    }
  
    const onClickAttack = () => {
        const opts = {
            "attackerValues": attackerValues,
        };
        const updateFunc = async () => authFetch('api/attackprimitives', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r)); setCalcMessage("")})
        props.updateData(['kingdom', 'projects', 'attackhistory', 'mobis', 'settle', 'structures', 'projects'], [updateFunc]);
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
    const onSubmitAutoSettingsClick = async (e)=>{
        let opts = {
            "pure": autoPure,
            "flex": autoFlex,
        }
        const updateFunc = () => authFetch('api/attackprimitives/auto', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
    }
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
            <Toast.Body  className="text-black">{results.message}</Toast.Body>
        </Toast>
    )
    return (
        <div className="primitives">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="primitives-content">
                <div className="attack-primitives">
                    <h2>Attack Primitives</h2>
                    <div className="text-box primitives-box">
                        <span className="box-span">Your military will exploit primitive galaxies to conquer distant stars.</span>
                        <br />
                        <span className="box-span">Primitives defense per star: {(props.data.state.primitives_defense_per_star || 100).toFixed(2)}</span>
                    </div>
                    <div className="primitives-battle-stats">
                        <div className="primitives-attacker-detail">
                            <Table className="attacker-table" striped bordered hover size="sm">
                                <thead>
                                    <tr>
                                        <th>Unit</th>
                                        <th style={{textAlign: "right"}}>Available</th>
                                        <th style={{textAlign: "right"}}>Offense</th>
                                        <th style={{textAlign: "right"}}>Input</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>Attackers</td>
                                        <td style={{textAlign: "right"}}>{props.data.kingdom?.units?.attack?.toLocaleString()}</td>
                                        <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.attack?.offense || "--"}</td>
                                        <td style={{textAlign: "right"}}>
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
                                        <td style={{textAlign: "right"}}>{props.data.kingdom?.units?.flex?.toLocaleString()}</td>
                                        <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.flex?.offense || "--"}</td>
                                        <td style={{textAlign: "right"}}>
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
                                        <td style={{textAlign: "right"}}>{props.data.kingdom?.units?.big_flex?.toLocaleString() || 0}</td>
                                        <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.big_flex?.offense || "--"}</td>
                                        <td style={{textAlign: "right"}}>
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
                                        <td style={{textAlign: "right"}}></td>
                                        <td style={{textAlign: "right"}}></td>
                                        <td style={{textAlign: "right"}}>
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
                                        <td style={{textAlign: "right"}}></td>
                                        <td style={{textAlign: "right"}}></td>
                                        <td style={{textAlign: "right"}}>
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
                                        <td style={{textAlign: "right"}}>{props.data.kingdom?.generals_available}</td>
                                        <td style={{textAlign: "right"}}></td>
                                        <td style={{textAlign: "right"}}>
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
                            <div className="primitives-attacker-text-boxes">
                                <div className="text-box primitives-losses-box">
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
                                <div className="text-box primitives-offense-box">
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
                <div className="primitives-attack-auto">
                    <h2>Auto Settings</h2>
                    <Form>
                        <Form.Check 
                            type="switch"
                            id="enable-auto-attack-switch"
                            label="Enable Auto Attack"
                            checked={props.data.kingdom.auto_attack_enabled || false}
                            onChange={handleEnabledChange}
                            disabled={props.loading.kingdom}
                        />
                    </Form>
                    <InputGroup className="mb-3 auto-attack-percent">
                        <InputGroup.Text id="text-pure-percent" className="auto-attack-percent-text">
                            Pure Offense to Send (Current: {props.data.kingdom.auto_attack_settings?.pure * 100}%)
                        </InputGroup.Text>
                        <Form.Control 
                            id="pure-percent"
                            aria-describedby="basic-addon3" 
                            onChange={handleAutoPureInput}
                            value={autoPure} 
                            placeholder={(props.data.kingdom.auto_attack_settings?.pure || 0) * 100}
                            autoComplete="off"
                        />
                        <InputGroup.Text id="pure-offense-pct" style={{width: '12%'}}>
                            %
                        </InputGroup.Text>
                    </InputGroup>
                    <InputGroup className="mb-3 auto-attack-percent">
                        <InputGroup.Text id="text-settle-percent" className="auto-attack-percent-text">
                            Flex Offense to Send (Current: {props.data.kingdom.auto_attack_settings?.flex * 100}%)
                        </InputGroup.Text>
                        <Form.Control 
                            id="flex-percent"
                            aria-describedby="basic-addon3" 
                            onChange={handleAutoFlexInput}
                            value={autoFlex} 
                            placeholder={(props.data.kingdom.auto_attack_settings?.flex || 0) * 100}
                            autoComplete="off"
                        />
                        <InputGroup.Text id="flex-offense-pct" style={{width: '12%'}}>
                            %
                        </InputGroup.Text>
                    </InputGroup>
                    {props.loading.kingdom
                    ? <Button className="auto-attack-settings-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="auto-attack-settings-button" variant="primary" type="submit" onClick={onSubmitAutoSettingsClick}>
                        Update
                    </Button>
                    }
                </div>
            </div>
        </div>
    )
}

function RobPrimitives(props) {
    const [results, setResults] = useState([]);
    const [drones, setDrones] = useState("");
    const [shieldDrones, setShieldDrones] = useState(false);
    const [enabled, setEnabled] = useState(props.data.kingdom.auto_rob_enabled || false)
    const [autoDrones, setAutoDrones] = useState("");
    const [autoSpyAttemptsKeep, setAutoSpyAttemptsKeep] = useState("");
    const [autoShieldDrones, setAutoShieldDrones] = useState(props.data.kingdom.auto_rob_settings?.shielded || false);

    const handleShieldChange = (e) => {
        setShieldDrones(e.target.checked)
    };
    const handleDronesChange = (e) => {
        setDrones(e.target.value);
    };
    const handleAutoSpyAttemptsKeepChange = (e) => {
        setAutoSpyAttemptsKeep(e.target.value);
    };
    const handleEnabledChange = (e) => {
        let opts = {
            'enabled': e.target.checked
        }
        const updateFunc = () => authFetch('api/robprimitives/auto', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
        setEnabled(e.target.checked)
    }
    const handleAutoDronesInput = (e) => {
        setAutoDrones(e.target.value)
    }
    const handleAutoShieldChange = (e) => {
        setAutoShieldDrones(e.target.checked);
        let opts = {
            'shielded': e.target.checked
        }
        const updateFunc = () => authFetch('api/robprimitives/auto', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
        setEnabled(e.target.checked)
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
    const onSubmitAutoSettingsClick = async (e)=>{
        let opts = {
            "drones": autoDrones,
            "keep": autoSpyAttemptsKeep,
            "shielded": autoShieldDrones,
        }
        const updateFunc = () => authFetch('api/robprimitives/auto', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
    }
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
            <Toast.Body  className="text-black">{result.message}</Toast.Body>
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
            <div className="primitives-content">
                <div className="rob-primitives">
                <h2>Rob Primitives</h2>
                <div className="text-box primitives-box">
                    <span className="box-span">Your drones will exploit primitive galaxies to steal resources.</span>
                    <br />
                    <span className="box-span">Primitives money per drone: {(props.data.state.primitives_rob_per_drone || 4).toFixed(2)}</span>
                </div>
                <InputGroup className="mb-3 rob-drones-input-group">
                    <InputGroup.Text id="basic-addon2" className="rob-drones-input-text">Drones (Max {Math.floor(props.data.kingdom?.drones).toLocaleString()})</InputGroup.Text>
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
                        checked={shieldDrones}
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
                <div className="auto-rob-primitives">
                    <h2>Auto Settings</h2>
                    <Form>
                        <Form.Check 
                            type="switch"
                            id="enable-auto-rob-switch"
                            label="Enable Auto Rob"
                            checked={props.data.kingdom.auto_rob_enabled || false}
                            onChange={handleEnabledChange}
                            disabled={props.loading.kingdom}
                        />
                    </Form>
                    <InputGroup className="mb-3">
                        <InputGroup.Text id="text-drones-percent" className="auto-drones-input-text">
                            Drones to Send (Current: {props.data.kingdom.auto_rob_settings?.drones * 100}%)
                        </InputGroup.Text>
                        <Form.Control 
                            id="drones-percent"
                            aria-describedby="basic-addon3" 
                            onChange={handleAutoDronesInput}
                            value={autoDrones} 
                            placeholder={(props.data.kingdom.auto_rob_settings?.drones || 0) * 100}
                            autoComplete="off"
                        />
                        <InputGroup.Text id="text-engineers-percent" style={{width: '12%'}}>
                            %
                        </InputGroup.Text>
                    </InputGroup>
                    <InputGroup className="mb-3">
                        <InputGroup.Text id="text-spy-attempts" className="auto-drones-input-text">
                        Spy Attempts to Keep (Current: {props.data.kingdom.auto_rob_settings?.keep})
                        </InputGroup.Text>
                        <Form.Control 
                            id="keep-attempts"
                            aria-describedby="basic-addon3" 
                            onChange={handleAutoSpyAttemptsKeepChange}
                            value={autoSpyAttemptsKeep} 
                            placeholder={props.data.kingdom.auto_rob_settings?.keep || 0}
                            autoComplete="off"
                        />
                    </InputGroup>
                    <Form>
                        <Form.Check 
                            type="switch"
                            id="enable-auto-rob-shields-switch"
                            label="Shield Auto Robs?"
                            checked={autoShieldDrones}
                            onChange={handleAutoShieldChange}
                            disabled={props.loading.kingdom}
                        />
                    </Form>
                    {props.loading.kingdom
                    ? <Button className="auto-attack-settings-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="auto-attack-settings-button" variant="primary" type="submit" onClick={onSubmitAutoSettingsClick}>
                        Update
                    </Button>
                    }
                </div>
            </div>
        </div>
    )
}
  
export default Primitives;