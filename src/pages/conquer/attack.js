import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import InputGroup from 'react-bootstrap/InputGroup';
import Modal from 'react-bootstrap/Modal';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer'
import "./attack.css";
import Select from 'react-select';
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";


const initialDefenderValues = {
    "recruits": "",
    "defense": "",
    "flex": "",
    "big_flex": "",
    "military_bonus": "25",
    "shields": "10",
}
const initialAttackerValues = {
    "attack": "",
    "flex": "",
    "big_flex": "",
    "generals": "",
    "buffer": "1.0",
}


function Attack(props) {
    const [defenderValues, setDefenderValues] = useState(initialDefenderValues);
    const [attackerValues, setAttackerValues] = useState(initialAttackerValues);
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [calcMessage, setCalcMessage] = useState({"message": "Press calculate to project results"})
    const [loadingCalc, setLoadingCalc] = useState(false);
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [attackResults, setAttackResults] = useState([]);
    const [showOverrideModal, setShowOverrideModal] = useState(false);

    useEffect(() => {
        if (props.initialKd != undefined) {
            const fetchData = async () => {
                await authFetch("api/kingdom/" + props.initialKd).then(r => r.json()).then(r => setTargetKdInfo(r));
            };
            fetchData();
        }
    }, []);
    const handleChange = (selectedOption) => {
        setSelected(selectedOption.value);
        const fetchData = async () => {
            await authFetch("api/kingdom/" + selectedOption.value).then(r => r.json()).then(r => setTargetKdInfo(r));
        };
        fetchData();
    };
    const handleDefenderChange = (e) => {
        const { name, value } = e.target;
        setDefenderValues({
          ...defenderValues,
          [name]: value,
        });
    };
    const handleAttackerChange = (e) => {
        const { name, value } = e.target;
        setAttackerValues({
          ...attackerValues,
          [name]: value,
        });
    };
    const countUnits = (input) => {
        var total = 0
        for (const unit in Object.keys(props.data.state.units || {})) {
            total += (parseInt(input[unit] || 0));
        }
        return total
    }
    const onClickAttack = (e, overrideWarning=false) => {
        if (selected != undefined) {
            const defenderUnits = countUnits(defenderValues);
            if (defenderUnits > 0 || overrideWarning || targetKdInfo.hasOwnProperty("units")) {
                const opts = {
                    "attackerValues": attackerValues,
                };
                const updateFunc = async () => authFetch('api/attack/' + selected, {
                    method: 'POST',
                    body: JSON.stringify(opts)
                }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r)); setCalcMessage("")})
                props.updateData(['kingdom', 'projects', 'attackhistory', 'mobis', 'settle', 'structures', 'projects', 'galaxynews'], [updateFunc]);
                setShowOverrideModal(false);
            } else {
                setShowOverrideModal(true);
            }
        } else {
            setCalcMessage({"message": "Please select a target in order to attack"})
        }
    };
    const onClickCalculate = async (e) => {
        if (selected != undefined) {
            const opts = {
                "attackerValues": attackerValues,
                "defenderValues": defenderValues,
            };
            const updateFunc = async () => authFetch('api/calculate/' + selected, {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setCalcMessage(r))
            setLoadingCalc(true);
            await updateFunc();
            setLoadingCalc(false);
        } else {
            setCalcMessage({"message": "Please select a target in order to calculate"})
        }
    };
    const onClickAutofill = async (e) => {
        if (selected != undefined) {
            const opts = {
                "buffer": attackerValues.buffer,
                "generals": attackerValues.generals,
                "defenderValues": defenderValues,
            };
            const updateFunc = async () => authFetch('api/autofill/' + selected, {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => {
                setCalcMessage(r);
                setAttackerValues({
                  ...attackerValues,
                  ...r.attacker_units,
                });

            })
            setLoadingCalc(true);
            await updateFunc();
            setLoadingCalc(false);
        } else {
            setCalcMessage({"message": "Please select a target in order to calculate"})
        }
    };
    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")"
        } else {
            return "Defender"
        }
        
    }

    const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => {
        return {"value": kdId, "label": kdFullLabel(kdId)}
    })
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    if (props.data.projects.current_bonuses?.military_bonus && attackerValues.military_bonus === "") {
        setAttackerValues({
            ...attackerValues,
            ["military_bonus"]: props.data.projects.current_bonuses.military_bonus,
        });
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
    const getRemainingSpans = (kdId, revealed) => {
        if (revealed === undefined) {
            return []
        }
        const remainingSpans = Object.keys(revealed[kdId] || {}).map((category) =>
            <div key={kdId.toString() + '_' + category} className="remaining-timer">
                <span className="remaining-time-title">{category}</span>
                <span className="remaining-time-value">{getTimeString(revealed[kdId][category])}</span>
                <br />
            </div>
        )
        return remainingSpans;
    }
    const revealedStats = getRemainingSpans(selected, props.data.revealed?.revealed);

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
    <>
        <Header data={props.data} />
        <div className="attack">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <Modal
                show={showOverrideModal}
                onHide={() => setShowOverrideModal(false)}
                animation={false}
                dialogClassName="attack-override-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Attack?</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div>
                        <span>You're trying to make an attack without inputting any information about the target's units</span>
                        <br />
                        <br />
                        <span>Are you sure?</span>
                        <br />
                        <br />
                        <Button variant="primary" type="submit" onClick={(e) => onClickAttack(e, true)}>
                            Attack 
                        </Button>
                    </div>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowOverrideModal(false)}>
                    Cancel
                    </Button>
                </Modal.Footer>
            </Modal>
            <h2>Attack</h2>
            <form className="attack-kingdom-form">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select a target (type to filter)
                </label>
                <Select
                    className="attack-kingdom-select"
                    options={kingdomOptions}
                    onChange={handleChange}
                    autoFocus={selected == undefined}
                    defaultValue={kingdomOptions.filter(option => option.value === props.initialKd)}
                    styles={{
                        control: (baseStyles, state) => ({
                            ...baseStyles,
                            borderColor: state.isFocused ? 'var(--bs-body-color)' : 'var(--bs-primary-text)',
                            backgroundColor: 'var(--bs-body-bg)',
                        }),
                        placeholder: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-primary-text)',
                        }),
                        input: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                        option: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: state.isFocused ? 'var(--bs-primary-bg-subtle)' : 'var(--bs-secondary-bg-subtle)',
                            color: state.isFocused ? 'var(--bs-primary-text)' : 'var(--bs-secondary-text)',
                        }),
                        menuList: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: 'var(--bs-secondary-bg)',
                            // borderColor: 'var(--bs-secondary-bg)',
                        }),
                        singleValue: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                    }}
                />
            </form>
            <div className="battle-stats">
                <div className="defender-stats">
                    <h3>{kdFullLabel(selected)}</h3>
                    <div className="defender-detail">
                        <Table className="defender-table" striped bordered hover size="sm">
                            <thead>
                                <tr>
                                    <th>Input</th>
                                    <th style={{textAlign: "right"}}>Defense</th>
                                    <th style={{textAlign: "right"}}>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Recruits</td>
                                    <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.recruits?.defense || "--"}</td>
                                    <td style={{textAlign: "right"}}>
                                        {   targetKdInfo.hasOwnProperty("units")
                                            ? <Form.Control 
                                                className="unit-form"
                                                id="recruits-input"
                                                name="recruits"
                                                value={targetKdInfo.units.recruits?.toLocaleString() || "0"} 
                                                placeholder="0"
                                                disabled
                                                autoComplete="off"
                                            />
                                            : <Form.Control 
                                                className="unit-form"
                                                id="recruits-input"
                                                name="recruits"
                                                onChange={handleDefenderChange}
                                                value={defenderValues.recruits || ""} 
                                                placeholder="0"
                                                autoComplete="off"
                                            />
                                        }
                                    </td>
                                </tr>
                                <tr>
                                    <td>Defenders</td>
                                    <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.defense?.defense || "--"}</td>
                                    <td style={{textAlign: "right"}}>
                                        {   targetKdInfo.hasOwnProperty("units")
                                            ? <Form.Control 
                                                className="unit-form"
                                                id="defenders-input"
                                                name="defense"
                                                onChange={handleDefenderChange}
                                                value={targetKdInfo.units.defense?.toLocaleString() || "0"} 
                                                placeholder="0"
                                                disabled
                                                autoComplete="off"
                                            />
                                            : <Form.Control 
                                                className="unit-form"
                                                id="defenders-input"
                                                name="defense"
                                                onChange={handleDefenderChange}
                                                value={defenderValues.defense || ""} 
                                                placeholder="0"
                                                autoComplete="off"
                                            />
                                        }
                                    </td>
                                </tr>
                                <tr>
                                    <td>Flexers</td>
                                    <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.flex?.defense || "--"}</td>
                                    <td style={{textAlign: "right"}}>
                                        {   targetKdInfo.hasOwnProperty("units")
                                            ? <Form.Control 
                                                className="unit-form"
                                                id="flexers-input"
                                                name="flex"
                                                value={targetKdInfo.units.flex?.toLocaleString() || "0"} 
                                                placeholder="0"
                                                disabled
                                                autoComplete="off"
                                            />
                                            : <Form.Control 
                                                className="unit-form"
                                                id="flexers-input"
                                                name="flex"
                                                onChange={handleDefenderChange}
                                                value={defenderValues.flex || ""} 
                                                placeholder="0"
                                                autoComplete="off"
                                            />
                                        }
                                    </td>
                                </tr>
                                <tr>
                                    <td>Big Flexers</td>
                                    <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.big_flex?.defense || "--"}</td>
                                    <td style={{textAlign: "right"}}>
                                        {   targetKdInfo.hasOwnProperty("units")
                                            ? <Form.Control 
                                                className="unit-form"
                                                id="big-flexers-input"
                                                name="big_flex"
                                                value={targetKdInfo.units.big_flex?.toLocaleString() || "0"} 
                                                placeholder="0"
                                                disabled
                                                autoComplete="off"
                                            />
                                            : <Form.Control 
                                                className="unit-form"
                                                id="big-flexers-input"
                                                name="big_flex"
                                                onChange={handleDefenderChange}
                                                value={defenderValues.big_flex || ""} 
                                                placeholder="0"
                                                autoComplete="off"
                                            />
                                        }
                                    </td>
                                </tr>
                                <tr>
                                    <td>Military Efficiency</td>
                                    <td style={{textAlign: "right"}}></td>
                                    <td style={{textAlign: "right"}}>
                                        {   targetKdInfo.hasOwnProperty("current_bonuses")
                                            ? <InputGroup className="mb-3 unit-input-group">
                                                <Form.Control
                                                    className="unit-form"
                                                    id="military-efficiency-input"
                                                    name="military_bonus"
                                                    value={targetKdInfo.current_bonuses.military_bonus * 100 || ""} 
                                                    placeholder="0"
                                                    disabled
                                                    autoComplete="off"
                                                />
                                                <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                            </InputGroup>
                                            : <InputGroup className="mb-3 unit-input-group">
                                                <Form.Control
                                                    className="unit-form"
                                                    id="military-efficiency-input"
                                                    name="military_bonus"
                                                    onChange={handleDefenderChange}
                                                    value={defenderValues.military_bonus || ""} 
                                                    placeholder="0"
                                                    autoComplete="off"
                                                />
                                                <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                            </InputGroup>
                                        }
                                    </td>
                                </tr>
                                <tr>
                                    <td>Shields</td>
                                    <td style={{textAlign: "right"}}></td>
                                    <td style={{textAlign: "right"}}>
                                        {   targetKdInfo.hasOwnProperty("shields")
                                            ? <InputGroup className="mb-3 unit-input-group">
                                                <Form.Control
                                                    className="unit-form"
                                                    id="shields-input"
                                                    name="shields"
                                                    value={targetKdInfo.shields.military * 100 || ""} 
                                                    placeholder="0"
                                                    disabled
                                                    autoComplete="off"
                                                />
                                                <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                            </InputGroup>
                                            : <InputGroup className="mb-3 unit-input-group">
                                                <Form.Control
                                                    className="unit-form"
                                                    id="shields-input"
                                                    name="shields"
                                                    onChange={handleDefenderChange}
                                                    value={defenderValues.shields || ""} 
                                                    placeholder="0"
                                                    autoComplete="off"
                                                />
                                                <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                            </InputGroup>
                                        }
                                    </td>
                                </tr>
                                <tr>
                                    <td>Other Bonuses</td>
                                    <td style={{textAlign: "right"}}></td>
                                    <td style={{textAlign: "right"}}>
                                        <InputGroup className="mb-3 unit-input-group">
                                            <Form.Control
                                            className="unit-form"
                                            id="other-bonuses-input"
                                            name="other_bonuses"
                                            value={defenderValues.other_bonuses * 100 || ""} 
                                            placeholder="0"
                                            disabled
                                            autoComplete="off"
                                            />
                                            <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                        </InputGroup>
                                    </td>
                                </tr>
                            </tbody>
                        </Table>
                        <div className="defender-text-boxes">
                            <div className="text-box defender-losses-box">
                                <h4>Their Losses</h4> 
                                <div className="text-box-item">
                                    <span className="text-box-item-title">Recruits</span>
                                    <span className="text-box-item-value">{calcMessage.defender_losses?.recruits?.toLocaleString() || "--"}</span>
                                </div>
                                <div className="text-box-item">
                                    <span className="text-box-item-title">Defenders</span>
                                    <span className="text-box-item-value">{calcMessage.defender_losses?.defense?.toLocaleString() || "--"}</span>
                                </div>
                                <div className="text-box-item">
                                    <span className="text-box-item-title">Flexers</span>
                                    <span className="text-box-item-value">{calcMessage.defender_losses?.flex?.toLocaleString() || "--"}</span>
                                </div>
                                <div className="text-box-item">
                                    <span className="text-box-item-title">Big Flexers</span>
                                    <span className="text-box-item-value">{calcMessage.defender_losses?.big_flex?.toLocaleString() || "--"}</span>
                                </div>
                                <br />
                                <div className="text-box-item">
                                    <span className="text-box-item-title">Unit Loss Rate</span>
                                    <span className="text-box-item-value">{displayPercent(calcMessage.defender_unit_losses_rate) || "--"}</span>
                                </div>
                                <div className="text-box-item">
                                    <span className="text-box-item-title">Stars Loss Rate</span>
                                    <span className="text-box-item-value">{displayPercent(calcMessage.defender_stars_loss_rate) || "--"}</span>
                                </div>

                            </div>
                            <div className="text-box defender-defense-box">
                                <h4>Their Defense</h4> 
                                <div className="text-box-item">
                                    <span className="defender-defense">{calcMessage.defender_defense?.toLocaleString() || "--"}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="attacker-stats">
                    <h3>{kdFullLabel(props.data.kingdom.kdId)}</h3>
                    <div className="attacker-detail">
                        <Table className="attacker-table" striped bordered hover size="sm">
                            <thead>
                                <tr>
                                    <th>Input</th>
                                    <th style={{textAlign: "right"}}>Offense</th>
                                    <th style={{textAlign: "right"}}>Available</th>
                                    <th style={{textAlign: "right"}}>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Attackers</td>
                                    <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.attack?.offense || "--"}</td>
                                    <td style={{textAlign: "right"}}>{props.data.kingdom?.units?.attack?.toLocaleString()}</td>
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
                                    <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.flex?.offense || "--"}</td>
                                    <td style={{textAlign: "right"}}>{props.data.kingdom?.units?.flex?.toLocaleString()}</td>
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
                                    <td style={{textAlign: "right"}}>{props.data.mobis?.units_desc?.big_flex?.offense || "--"}</td>
                                    <td style={{textAlign: "right"}}>{props.data.kingdom?.units?.big_flex?.toLocaleString() || 0}</td>
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
                                    <td style={{textAlign: "right"}}></td>
                                    <td style={{textAlign: "right"}}>{props.data.kingdom?.generals_available}</td>
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
                                <tr>
                                    <td>Autofill Buffer</td>
                                    <td style={{textAlign: "right"}}></td>
                                    <td style={{textAlign: "right"}}></td>
                                    <td style={{textAlign: "right"}}>
                                        <InputGroup className="mb-3 unit-input-group">
                                            <Form.Control
                                                className="unit-form"
                                                id="buffer-input"
                                                name="buffer"
                                                onChange={handleAttackerChange}
                                                value={attackerValues.buffer || ""} 
                                                placeholder="1.0"
                                                autoComplete="off"
                                            />
                                            <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                        </InputGroup>
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
            </div>
            {/* <div className="attack-results"> */}
                <div className="text-box attack-results-box">
                    <span className="box-span">{calcMessage.message}</span>
                </div>
            {/* </div> */}
            <div className="attack-buttons">
                {
                    loadingCalc
                    ? <Button className="autofill-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="autofill-button" variant="primary" type="submit" onClick={onClickAutofill}>
                        Autofill
                    </Button>
                }
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
            {
                revealedStats.length > 0
                ? <div className="text-box revealed-stats-box">
                    <h3>Target's Revealed Stats</h3>
                    {revealedStats}
                </div>
                : null
            }
            <HelpButton scrollTarget={"attack"}/>
        </div>
    </>
    )
}

export default Attack;