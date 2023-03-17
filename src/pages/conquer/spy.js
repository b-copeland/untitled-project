import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Table from 'react-bootstrap/Table';
import InputGroup from 'react-bootstrap/InputGroup';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer'
import "./spy.css";
import Select from 'react-select';

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
    const onClickAttack = () => {
        if ((selected != undefined) & (selectedOperation != undefined)) {
            const opts = {
                "drones": drones,
                "shielded": shieldDrones,
                "operation": selectedOperation,
            };
            const updateFunc = async () => authFetch('api/spy/' + selected, {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => {setAttackResults(attackResults.concat(r)); setCalcMessage("Press calculate to project results")})
            props.updateData(['kingdom', 'spyhistory', 'revealed'], [updateFunc]);
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
        {value: "spykingdom", "label": "Spy on Kingdom"},
        {value: "spymilitary", "label": "Spy on Military"},
        {value: "spyshields", "label": "Spy on Shields"},
        {value: "spyprojects", "label": "Spy on Projects"},
        {value: "spystructures", "label": "Spy on Structures"},
        {value: "spydrones", "label": "Spy on Drones"},
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
            <Toast.Body>{results.message}</Toast.Body>
        </Toast>
    )
    if (drones > props.data.kingdom["drones"]) {
        setDrones(Math.floor(props.data.kingdom["drones"]))
    }
    return (
        <div className="attack">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <h2>Spy</h2>
            <form className="attack-kingdom-form">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select a target (type to filter)
                </label>
                <Select id="select-kingdom" className="attack-kingdom-select" options={kingdomOptions} onChange={handleChange} autoFocus={true} defaultValue={kingdomOptions.filter(option => option.value === props.initialKd)} />
            </form>
            <div className="battle-stats">
                <div className="spy-defender-stats">
                    <h3>{kdFullLabel(selected)}</h3>
                    <form className="spy-operation-form">
                        <label id="aria-label" htmlFor="aria-example-input">
                            Select a Spy Operation
                        </label>
                        <Select id="select-operation" className="attack-kingdom-select" options={spyOptions} onChange={handleOperationChange} autoFocus={false} />
                    </form>
                    <Table className="defender-table" striped bordered hover size="sm">
                        <thead>
                            <tr>
                                <th>Input</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Drones</td>
                                <td>
                                    {   targetKdInfo.hasOwnProperty("drones")
                                        ? <Form.Control 
                                            className="unit-form"
                                            id="drones-input"
                                            name="drones"
                                            value={targetKdInfo.drones || "0"} 
                                            placeholder="0"
                                            disabled
                                        />
                                        : <Form.Control 
                                            className="unit-form"
                                            id="drones-input"
                                            name="drones"
                                            onChange={handleDefenderChange}
                                            value={defenderValues.drones || ""} 
                                            placeholder="0"
                                        />
                                    }
                                </td>
                            </tr>
                            <tr>
                                <td>Stars</td>
                                <td>
                                    {   targetKdInfo.hasOwnProperty("stars")
                                        ? <Form.Control
                                            className="unit-form"
                                            id="spy-stars-input"
                                            name="stars"
                                            value={targetKdInfo.stars || ""} 
                                            placeholder="0"
                                            disabled
                                        />
                                        : <Form.Control
                                            className="unit-form"
                                            id="spy-stars-input"
                                            name="stars"
                                            onChange={handleDefenderChange}
                                            value={defenderValues.stars || ""} 
                                            placeholder="0"
                                        />
                                    }
                                </td>
                            </tr>
                            <tr>
                                <td>Spy Shields</td>
                                <td>
                                    {   targetKdInfo.hasOwnProperty("shields")
                                        ? <InputGroup className="mb-3">
                                            <Form.Control
                                                className="unit-form"
                                                id="spy-shields-input"
                                                name="shields"
                                                value={targetKdInfo.shields.spy * 100 || ""} 
                                                placeholder="0"
                                                disabled
                                            />
                                            <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                        </InputGroup>
                                        : <InputGroup className="mb-3">
                                            <Form.Control
                                                className="unit-form"
                                                id="spy-shields-input"
                                                name="shields"
                                                onChange={handleDefenderChange}
                                                value={defenderValues.shields || ""} 
                                                placeholder="0"
                                            />
                                            <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                                        </InputGroup>
                                    }
                                </td>
                            </tr>
                        </tbody>
                    </Table>
                    <div className="operation-details">
                        <h3>Operation Details</h3>
                        <Table striped bordered hover>
                            <thead>
                                <tr>
                                    <th>Type</th>
                                    <th>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Stars-based defense</td>
                                    <td>{calcMessage.stars_defense}</td>
                                </tr>
                                <tr>
                                    <td>Drones-based defense</td>
                                    <td>{calcMessage.drones_defense}</td>
                                </tr>
                                <tr>
                                    <td>Max success threshold</td>
                                    <td>{calcMessage.total_defense}</td>
                                </tr>
                            </tbody>
                        </Table>
                    </div>
                </div>
                <div className="spy-attacker-stats">
                    <h3>{kdFullLabel(props.data.kingdom.kdId)}</h3>
                    <InputGroup className="mb-3 drones-input-group">
                        <InputGroup.Text id="basic-addon2">Drones (Max {props.data.kingdom["drones"]})</InputGroup.Text>
                        <Form.Control 
                            className="unit-form"
                            id="drones-input"
                            name="drones"
                            onChange={handleDronesChange}
                            value={drones || ""} 
                            placeholder="0"
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
                </div>
            </div>
        </div>
    )
}

export default Spy;