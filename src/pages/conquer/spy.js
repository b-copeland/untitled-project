import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Table from 'react-bootstrap/Table';
import InputGroup from 'react-bootstrap/InputGroup';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer'
import Accordion from 'react-bootstrap/Accordion';
import "./spy.css";
import Select from 'react-select';
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";

const initialDefenderValues = {
    "drones": "",
    "stars": "",
    "shields": "",
}

function Spy(props) {
    const [defenderValues, setDefenderValues] = useState(initialDefenderValues);
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [selectedOperation, setSelectedOperation] = useState("");
    const [calcMessage, setCalcMessage] = useState({"message": "Press calculate to project results"})
    const [loadingCalc, setLoadingCalc] = useState(false);
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [attackResults, setAttackResults] = useState([]);
    const [drones, setDrones] = useState();
    const [shieldDrones, setShieldDrones] = useState(false);
    const [cut, setCut] = useState();
    const [share, setShare] = useState(false);

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
    const handleShieldChange = (e) => {
        setShieldDrones(e.target.checked)
    }
    const handleShareChange = (e) => {
        setShare(e.target.checked)
    }
    const handleOperationChange = (selectedOption) => {
        setSelectedOperation(selectedOption.value);
        // const fetchData = async () => {
        //     await authFetch("api/kingdom/" + selectedOption.value).then(r => r.json()).then(r => setTargetKdInfo(r));
        // };
        // fetchData();
    };
    const handleDefenderChange = (e) => {
        const { name, value } = e.target;
        setDefenderValues({
          ...defenderValues,
          [name]: value,
        });
    };
    const handleDronesChange = (e) => {
        setDrones(e.target.value);
    };
    const handleCutChange = (e) => {
        setCut(e.target.value);
    };
    const onClickAttack = () => {
        if ((selected != undefined) & (selectedOperation != undefined)) {
            const opts = {
                "drones": drones,
                "shielded": shieldDrones,
                "operation": selectedOperation,
                "share_to_galaxy": share,
                "cut": cut,
            };
            const updateFunc = async () => authFetch('api/spy/' + selected, {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r)); setCalcMessage("Press calculate to project results")})
            props.updateData(['kingdom', 'spyhistory', 'revealed', 'shared'], [updateFunc]);
        } else {
            setCalcMessage({"message": "Please select a target and operation in order to spy"})
        }
    };
    const onClickCalculate = async (e) => {
        if ((selected != undefined) & (selectedOperation != undefined)) {
            const opts = {
                "drones": drones,
                "shielded": shieldDrones,
                "defenderValues": defenderValues,
                "operation": selectedOperation,
            };
            const updateFunc = async () => authFetch('api/calculatespy/' + selected, {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setCalcMessage(r))
            setLoadingCalc(true);
            await updateFunc();
            setLoadingCalc(false);
        } else {
            setCalcMessage({"message": "Please select a target and operation in order to calculate"})
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
    const spyOptions = [
        {value: "spymilitary", "label": "Spy on Military"},
        {value: "spykingdom", "label": "Spy on Kingdom"},
        {value: "spyshields", "label": "Spy on Shields"},
        {value: "spyprojects", "label": "Spy on Projects"},
        {value: "spystructures", "label": "Spy on Structures"},
        {value: "spydrones", "label": "Spy on Drones"},
        {value: "siphonfunds", "label": "Siphon Funds"},
        {value: "bombhomes", "label": "Bomb Homes"},
        {value: "sabotagefuelplants", "label": "Sabotage Fuel Plants"},
        {value: "kidnappopulation", "label": "Kidnap Population"},
        {value: "suicidedrones", "label": "Suicide Drones"},
    ];
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
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
    if (drones > props.data.kingdom["drones"]) {
        setDrones(Math.floor(props.data.kingdom["drones"]))
    }
    return (
        <>
        <Header data={props.data} />
        <div className="attack">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <h2>Spy</h2>
            <form className="attack-kingdom-form">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select a target (type to filter)
                </label>
                <Select id="select-kingdom" className="attack-kingdom-select" options={kingdomOptions} onChange={handleChange} autoFocus={selected == undefined} defaultValue={kingdomOptions.filter(option => option.value === props.initialKd)} 
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
                    }}/>
            </form>
            <div className="battle-stats">
                <div className="spy-defender-stats">
                    <h3>{kdFullLabel(selected)}</h3>
                    <form className="spy-operation-form">
                        <label id="aria-label" htmlFor="aria-example-input">
                            Select a Spy Operation
                        </label>
                        <Select id="select-operation" className="operation-select" options={spyOptions} onChange={handleOperationChange} autoFocus={false} isSearchable={false}
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
                            }}/>
                    </form>
                    <Accordion>
                        <Accordion.Item eventKey="0">
                            <Accordion.Header>Operation Planner</Accordion.Header>
                            <Accordion.Body>
                                <Table className="defender-table" striped bordered hover size="sm">
                                    <thead>
                                        <tr>
                                            <th>Input</th>
                                            <th style={{textAlign: "right"}}>Value</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td>Drones</td>
                                            <td style={{textAlign: "right"}}>
                                                {   targetKdInfo.hasOwnProperty("drones")
                                                    ? <Form.Control 
                                                        className="unit-form"
                                                        id="drones-input"
                                                        name="drones"
                                                        value={targetKdInfo.drones?.toLocaleString() || "0"} 
                                                        placeholder="0"
                                                        disabled
                                                        autoComplete="off"
                                                    />
                                                    : <Form.Control 
                                                        className="unit-form"
                                                        id="drones-input"
                                                        name="drones"
                                                        onChange={handleDefenderChange}
                                                        value={defenderValues.drones || ""} 
                                                        placeholder="0"
                                                        autoComplete="off"
                                                    />
                                                }
                                            </td>
                                        </tr>
                                        <tr>
                                            <td>Stars</td>
                                            <td style={{textAlign: "right"}}>
                                                {   targetKdInfo.hasOwnProperty("stars")
                                                    ? <Form.Control
                                                        className="unit-form"
                                                        id="spy-stars-input"
                                                        name="stars"
                                                        value={targetKdInfo.stars?.toLocaleString() || ""} 
                                                        placeholder="0"
                                                        disabled
                                                        autoComplete="off"
                                                    />
                                                    : <Form.Control
                                                        className="unit-form"
                                                        id="spy-stars-input"
                                                        name="stars"
                                                        onChange={handleDefenderChange}
                                                        value={defenderValues.stars || ""} 
                                                        placeholder="0"
                                                        autoComplete="off"
                                                    />
                                                }
                                            </td>
                                        </tr>
                                        <tr>
                                            <td>Spy Shields</td>
                                            <td style={{textAlign: "right"}}>
                                                {   targetKdInfo.hasOwnProperty("shields")
                                                    ? <InputGroup className="mb-3 spy-input-group">
                                                        <Form.Control
                                                            className="unit-form"
                                                            id="spy-shields-input"
                                                            name="shields"
                                                            value={targetKdInfo.shields.spy * 100 || ""} 
                                                            placeholder="0"
                                                            disabled
                                                            autoComplete="off"
                                                        />
                                                        <InputGroup.Text id="basic-addon2" className="drones-input-group-text">%</InputGroup.Text>
                                                    </InputGroup>
                                                    : <InputGroup className="mb-3 spy-input-group">
                                                        <Form.Control
                                                            className="unit-form"
                                                            id="spy-shields-input"
                                                            name="shields"
                                                            onChange={handleDefenderChange}
                                                            value={defenderValues.shields || ""} 
                                                            placeholder="0"
                                                            autoComplete="off"
                                                        />
                                                        <InputGroup.Text id="basic-addon2" className="spy-input-group-text">%</InputGroup.Text>
                                                    </InputGroup>
                                                }
                                            </td>
                                        </tr>
                                    </tbody>
                                </Table>
                                <div className="operation-details">
                                    <h3>Operation Details</h3>
                                    <Table striped bordered hover size="sm" className="operation-table">
                                        <thead>
                                            <tr>
                                                <th>Type</th>
                                                <th style={{textAlign: "right"}}>Value</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td>Stars-based defense</td>
                                                <td style={{textAlign: "right"}}>{(calcMessage.stars_defense || 0).toLocaleString()}</td>
                                            </tr>
                                            <tr>
                                                <td>Drones-based defense</td>
                                                <td style={{textAlign: "right"}}>{Math.floor(calcMessage.drones_defense || 0)?.toLocaleString()}</td>
                                            </tr>
                                            <tr>
                                                <td>Max success threshold</td>
                                                <td style={{textAlign: "right"}}>{Math.floor(calcMessage.total_defense || 0)?.toLocaleString()}</td>
                                            </tr>
                                        </tbody>
                                    </Table>
                                </div>
                            </Accordion.Body>
                        </Accordion.Item>
                    </Accordion>
                </div>
                <div className="spy-attacker-stats">
                    <h3>{kdFullLabel(props.data.kingdom.kdId)}</h3>
                    <InputGroup className="mb-3 drones-input-group">
                        <InputGroup.Text id="basic-addon2" className="drones-input-group-text">Drones (Max {Math.floor(props.data.kingdom?.drones).toLocaleString()})</InputGroup.Text>
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
                    {
                        (props.data.state.reveal_operations || []).includes(selectedOperation)
                        ? <Form>
                            <Form.Check 
                                type="switch"
                                id="share-switch"
                                label="Share To Galaxy?"
                                onChange={handleShareChange}
                            />
                        </Form>
                        : null
                    }
                    {
                        (props.data.state.reveal_operations || []).includes(selectedOperation)
                        ? <InputGroup className="mb-3 drones-input-group">
                            <InputGroup.Text id="basic-addon2" className="drones-input-group-text">Cut</InputGroup.Text>
                            <Form.Control
                                className="unit-form"
                                id="cut-input"
                                name="cut"
                                value={cut || ""} 
                                onChange={handleCutChange}
                                placeholder="0"
                                autoComplete="off"
                            />
                            <InputGroup.Text id="basic-addon2" className="drones-input-group-text">%</InputGroup.Text>
                        </InputGroup>
                        : null
                    }
                    
                    <div className="text-box spy-results-box">
                        <span className="box-span">{calcMessage.message}</span>
                    </div>
                    <span>Spy Attempts Remaining: {props.data.kingdom["spy_attempts"]}</span>
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
                                Spy
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
                </div>
            </div>
            <HelpButton scrollTarget={"spy"}/>
        </div>
        </>
    )
}

export default Spy;