import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Accordion from 'react-bootstrap/Accordion';
import Select from 'react-select';
import "./schedule.css";
import Header from "../../components/header";

function Schedule(props) {
    const [key, setKey] = useState('add');
    return (
        <>
            <Header data={props.data} />
            <Tabs
                id="controlled-tab-example"
                defaultActiveKey="add"
                justify
                fill
                variant="tabs"
            >
                <Tab eventKey="add" title="Add">
                <Add
                    loading={props.loading}
                    updateData={props.updateData}
                    data={props.data}
                    />
                </Tab>
                <Tab eventKey="queue" title="Queue">
                <Queue
                    loading={props.loading}
                    updateData={props.updateData}
                    data={props.data}/>
                </Tab>
            </Tabs>
        </>
    )
}

function getCurrentHour() {
    const initialDate = new Date();
    initialDate.setSeconds(0);
    return initialDate;
}

const initialScheduleOptions = {
    "attack": {
        "target": null,
        "pure_offense": 0.0,
        "flex_offense": 0.0,
        "generals": 1,
    },
    "attackprimitives": {
        "pure_offense": 0.0,
        "flex_offense": 0.0,
        "generals": 1,
    },
    "intelspy": {
        "target": null,
        "operation": null,
        "drones_pct": 0.0,
        "shielded": false,
        "max_tries": 1,
        "share_to_galaxy": false,
    },
    "aggressivespy": {
        "target": null,
        "operation": null,
        "drones_pct": 0.0,
        "shielded": false,
        "attempts": 1,
    },
    "missiles": {
        "target": null,
        "planet_busters": 0,
        "star_busters": 0,
        "galaxy_busters": 0,
    },
}

function Add(props) {
    const [selectedSchedule, setSelectedSchedule] = useState();
    const [options, setOptions] = useState();
    const [selectedScheduleTimeLocal, setSelectedScheduleTimeLocal] = useState(getCurrentHour().toISOString().slice(0, 16));
    const [results, setResults] = useState([]);

    const handleScheduleChange = (selectedOption) => {
        setOptions(
            JSON.parse(JSON.stringify(initialScheduleOptions[selectedOption.value]))
        )
        setSelectedSchedule(selectedOption.value);
    };
    const handleTimeChange = (e) => {
        setSelectedScheduleTimeLocal(e.target.value);
    };
    const handleOptionChange = (e) => {
        const { name, value } = e.target;
        setOptions({
            ...options,
            [name]: value,
        });
      };
    const handleOptionChangeExplicit = (name, value) => {
        setOptions({
            ...options,
            [name]: value,
        });
    };
    const onClickSubmit = () => {
        const opts = {
            "type": selectedSchedule,
            "time": new Date(selectedScheduleTimeLocal).toISOString(),
            "options": options,
        };
        const updateFunc = async () => authFetch('api/schedule', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['kingdom'], [updateFunc]);
    };
    const scheduleOptions = [
        {value: "attack", "label": "Attack"},
        {value: "attackprimitives", "label": "Attack Primitives"},
        {value: "intelspy", "label": "Intel Spy"},
        {value: "aggressivespy", "label": "Aggressive Spy"},
        {value: "missiles", "label": "Launch Missiles"},
    ];
    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")"
        } else {
            return "Defender"
        }
        
    }
    const optionsContent = () => {
        if (selectedSchedule == "attack") {
            const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => {
                return {"value": kdId, "label": kdFullLabel(kdId)}
            })
            const selectedKingdomOption = (options.target != null) ? kingdomOptions.filter(selectOption => selectOption.value == options.target)[0] : null;
            return <>
                <form className="attack-kingdom-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a target (type to filter)
                    </label>
                    <Select
                        className="attack-kingdom-select"
                        value={selectedKingdomOption}
                        options={kingdomOptions}
                        onChange={(selected) => handleOptionChangeExplicit("target", selected.value)}
                        // onChange={handleOptionChange}
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
                <Table className="attacker-table" striped bordered hover size="sm">
                    <thead>
                        <tr>
                            <th>Option</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Pure Offense</td>
                            <td>
                                <InputGroup className="mb-3 unit-input-group">
                                    <Form.Control
                                        className="unit-form"
                                        id="pure-offense-input"
                                        name="pure_offense"
                                        onChange={handleOptionChange}
                                        value={options.pure_offense || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                </InputGroup>
                            </td>
                        </tr>
                        <tr>
                            <td>Flex Offense</td>
                            <td>
                                <InputGroup className="mb-3 unit-input-group">
                                    <Form.Control
                                        className="unit-form"
                                        id="flex-offense-input"
                                        name="flex_offense"
                                        onChange={handleOptionChange}
                                        value={options.flex_offense || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                </InputGroup>
                            </td>
                        </tr>
                        <tr>
                            <td>Generals</td>
                            <td>
                                <Form.Control 
                                    className="unit-form"
                                    id="generals-input"
                                    name="generals"
                                    onChange={handleOptionChange}
                                    value={options.generals || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                    </tbody>
                </Table>
                {
                    props.loading.kingdom
                    ? <Button className="attack-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="attack-button" variant="primary" type="submit" onClick={onClickSubmit}>
                        Submit
                    </Button>
                }
            </>
        } else if (selectedSchedule == "attackprimitives") {
            return <>
                <Table className="attacker-table" striped bordered hover size="sm">
                    <thead>
                        <tr>
                            <th>Option</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Pure Offense</td>
                            <td>
                                <InputGroup className="mb-3 unit-input-group">
                                    <Form.Control
                                        className="unit-form"
                                        id="pure-offense-input"
                                        name="pure_offense"
                                        onChange={handleOptionChange}
                                        value={options.pure_offense || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                </InputGroup>
                            </td>
                        </tr>
                        <tr>
                            <td>Flex Offense</td>
                            <td>
                                <InputGroup className="mb-3 unit-input-group">
                                    <Form.Control
                                        className="unit-form"
                                        id="flex-offense-input"
                                        name="flex_offense"
                                        onChange={handleOptionChange}
                                        value={options.flex_offense || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                </InputGroup>
                            </td>
                        </tr>
                        <tr>
                            <td>Generals</td>
                            <td>
                                <Form.Control 
                                    className="unit-form"
                                    id="generals-input"
                                    name="generals"
                                    onChange={handleOptionChange}
                                    value={options.generals || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                    </tbody>
                </Table>
                {
                    props.loading.kingdom
                    ? <Button className="attack-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="attack-button" variant="primary" type="submit" onClick={onClickSubmit}>
                        Submit
                    </Button>
                }
            </>
        } else if (selectedSchedule == "intelspy") {
            const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => {
                return {"value": kdId, "label": kdFullLabel(kdId)}
            })
            const selectedKingdomOption = (options.target != null) ? kingdomOptions.filter(selectOption => selectOption.value == options.target)[0] : null;
            const spyOptions = [
                {value: "spykingdom", "label": "Spy on Kingdom"},
                {value: "spymilitary", "label": "Spy on Military"},
                {value: "spyshields", "label": "Spy on Shields"},
                {value: "spyprojects", "label": "Spy on Projects"},
                {value: "spystructures", "label": "Spy on Structures"},
                {value: "spydrones", "label": "Spy on Drones"},
            ];
            const selectedOperationOption = (options.operation != null) ? spyOptions.filter(selectOption => selectOption.value == options.operation)[0] : null;
            return <>
                <form className="attack-kingdom-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a target (type to filter)
                    </label>
                    <Select
                        className="attack-kingdom-select"
                        options={kingdomOptions}
                        value={selectedKingdomOption}
                        onChange={(selected) => handleOptionChangeExplicit("target", selected.value)}
                        defaultValue={null}
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
                <form className="spy-operation-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a Spy Operation
                    </label>
                    <Select
                        id="select-operation"
                        className="operation-select"
                        options={spyOptions}
                        value={selectedOperationOption}
                        onChange={(selected) => handleOptionChangeExplicit("operation", selected.value)}
                        autoFocus={false} 
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
                <Table className="attacker-table" striped bordered hover size="sm">
                    <thead>
                        <tr>
                            <th>Option</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Drones %</td>
                            <td>
                                <InputGroup className="mb-3 unit-input-group">
                                    <Form.Control
                                        className="unit-form"
                                        id="drones-pct-input"
                                        name="drones_pct"
                                        onChange={handleOptionChange}
                                        value={options.drones_pct || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                </InputGroup>
                            </td>
                        </tr>
                        <tr>
                            <td>Shielded</td>
                            <td>
                                <Form.Check
                                    id="shielded-input"
                                    name="shielded"
                                    onChange={(e) => handleOptionChangeExplicit("shielded", e.target.checked)}
                                    value={options.shielded || false}
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                        <tr>
                            <td>Max Tries</td>
                            <td>
                                <Form.Control 
                                    className="unit-form"
                                    id="max-tries-input"
                                    name="max_tries"
                                    onChange={handleOptionChange}
                                    value={options.max_tries || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                        <tr>
                            <td>Share to Galaxy</td>
                            <td>
                                <Form.Check
                                    id="share-to-galaxy-input"
                                    name="share_to_galaxy"
                                    onChange={(e) => handleOptionChangeExplicit("share_to_galaxy", e.target.checked)}
                                    value={options.share_to_galaxy || false}
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                    </tbody>
                </Table>
                {
                    props.loading.kingdom
                    ? <Button className="attack-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="attack-button" variant="primary" type="submit" onClick={onClickSubmit}>
                        Submit
                    </Button>
                }
            </>
        } else if (selectedSchedule == "aggressivespy") {
            const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => {
                return {"value": kdId, "label": kdFullLabel(kdId)}
            })
            const selectedKingdomOption = (options.target != null) ? kingdomOptions.filter(selectOption => selectOption.value == options.target)[0] : null;
            const spyOptions = [
                {value: "siphonfunds", "label": "Siphon Funds"},
                {value: "bombhomes", "label": "Bomb Homes"},
                {value: "sabotagefuelplants", "label": "Sabotage Fuel Plants"},
                {value: "kidnappopulation", "label": "Kidnap Population"},
                {value: "suicidedrones", "label": "Suicide Drones"},
            ];
            const selectedOperationOption = (options.operation != null) ? spyOptions.filter(selectOption => selectOption.value == options.operation)[0] : null;
            return <>
                <form className="kingdom-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a target (type to filter)
                    </label>
                    <Select
                        className="kingdom-select"
                        options={kingdomOptions}
                        value={selectedKingdomOption}
                        onChange={(selected) => handleOptionChangeExplicit("target", selected.value)}
                        // onChange={handleOptionChange}
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
                <form className="spy-operation-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a Spy Operation
                    </label>
                    <Select
                        id="select-operation"
                        className="operation-select"
                        options={spyOptions}
                        value={selectedOperationOption}
                        onChange={(selected) => handleOptionChangeExplicit("operation", selected.value)}
                        autoFocus={false} 
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
                <Table className="attacker-table" striped bordered hover size="sm">
                    <thead>
                        <tr>
                            <th>Option</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Drones %</td>
                            <td>
                                <InputGroup className="mb-3 unit-input-group">
                                    <Form.Control
                                        className="unit-form"
                                        id="drones-pct-input"
                                        name="drones_pct"
                                        onChange={handleOptionChange}
                                        value={options.drones_pct || ""} 
                                        placeholder="0"
                                        autoComplete="off"
                                    />
                                    <InputGroup.Text id="basic-addon2" className="unit-input-group-text">%</InputGroup.Text>
                                </InputGroup>
                            </td>
                        </tr>
                        <tr>
                            <td>Shielded</td>
                            <td>
                                <Form.Check
                                    id="shielded-input"
                                    name="shielded"
                                    onChange={(e) => handleOptionChangeExplicit("shielded", e.target.checked)}
                                    value={options.shielded || false}
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                        <tr>
                            <td>Attempts</td>
                            <td>
                                <Form.Control 
                                    className="unit-form"
                                    id="attempts-input"
                                    name="attempts"
                                    onChange={handleOptionChange}
                                    value={options.attempts || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                    </tbody>
                </Table>
                {
                    props.loading.kingdom
                    ? <Button className="attack-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="attack-button" variant="primary" type="submit" onClick={onClickSubmit}>
                        Submit
                    </Button>
                }
            </>
        } else if (selectedSchedule == "missiles") {
            const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => {
                return {"value": kdId, "label": kdFullLabel(kdId)}
            });
            const selectedKingdomOption = (options.target != null) ? kingdomOptions.filter(selectOption => selectOption.value == options.target)[0] : null;
            return <>
                <form className="attack-kingdom-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a target (type to filter)
                    </label>
                    <Select
                        className="attack-kingdom-select"
                        name="target"
                        options={kingdomOptions}
                        value={selectedKingdomOption}
                        onChange={(selected) => handleOptionChangeExplicit("target", selected.value)}
                        // onChange={handleOptionChange}
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
                <Table className="attacker-table" striped bordered hover size="sm">
                    <thead>
                        <tr>
                            <th>Option</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Planet Busters</td>
                            <td>
                                <Form.Control 
                                    className="unit-form"
                                    id="planet-busters-input"
                                    name="planet_busters"
                                    onChange={handleOptionChange}
                                    value={options.planet_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                        <tr>
                            <td>Star Busters</td>
                            <td>
                                <Form.Control 
                                    className="unit-form"
                                    id="star-busters-input"
                                    name="star_busters"
                                    onChange={handleOptionChange}
                                    value={options.star_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                        <tr>
                            <td>Galaxy Busters</td>
                            <td>
                                <Form.Control 
                                    className="unit-form"
                                    id="galaxy-busters-input"
                                    name="galaxy_busters"
                                    onChange={handleOptionChange}
                                    value={options.galaxy_busters || ""} 
                                    placeholder="0"
                                    autoComplete="off"
                                />
                            </td>
                        </tr>
                    </tbody>
                </Table>
                {
                    props.loading.kingdom
                    ? <Button className="attack-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="attack-button" variant="primary" type="submit" onClick={onClickSubmit}>
                        Submit
                    </Button>
                }
            </>
        }
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
            <Toast.Body>{result.message}</Toast.Body>
        </Toast>
    )
    return (
        <div className="add-schedule">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <form className="select-schedule-form">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select an action
                </label>
                <Select
                    id="select-schedule"
                    className="schedule-select"
                    options={scheduleOptions}
                    onChange={handleScheduleChange}
                    autoFocus={true}
                    // defaultValue={kingdomOptions.filter(option => option.value === props.initialKd)} 
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
            <>
                <label id="aria-label" htmlFor="aria-example-input">
                    Choose a time
                </label>
                <Form.Control
                    className="datetime-form"
                    type="datetime-local"
                    min={(new Date()).toISOString().slice(0, 16)}
                    max={props.data.state.state?.game_end.slice(0, 16)}
                    step={60}
                    onChange={handleTimeChange}
                    value={selectedScheduleTimeLocal}
                />
            </>
            {optionsContent()}
        </div>
    )
}

function Queue(props) {
    const [results, setResults] = useState([]);

    const onClickCancel = (id) => {
        const opts = {
            "id": id,
        };
        const updateFunc = async () => authFetch('api/schedule/cancel', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['kingdom'], [updateFunc]);
    };

    const prettyNames = {
        ...(props.data.state.pretty_names || {}),
        "attack": "Attack",
        "attackprimitives": "Attack Primitives",
        "spy": "Spy",
        "intelspy": "Intel Spy",
        "aggressivespy": "Aggressive Spy",
        "missiles": "Missiles",
        "target": "Target",
        "pure_offense": "Pure Offense",
        "flex_offense": "Flex Offense",
        "generals": "Generals",
        "operation": "Operation",
        "drones_pct": "Drones",
        "shielded": "Shielded",
        "max_tries": "Max Tries",
        "share_to_galaxy": "Share to Galaxy",
        "repeat": "Repeat",
    }
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")"
        } else {
            return "Defender"
        }
        
    }
    const queueData = props.data.kingdom.schedule?.map((queueItem, iter) => {
        const options = Object.keys(queueItem.options).map(optionKey => {
            var prettyValue;
            if (optionKey == "target") {
                prettyValue = kdFullLabel(queueItem.options[optionKey])
            } else if (["drones_pct", "pure_offense", "flex_offense"].includes(optionKey)) {
                prettyValue = displayPercent(queueItem.options[optionKey])
            } else {
                prettyValue = (prettyNames[queueItem.options[optionKey]] || queueItem.options[optionKey]).toString()
            }
            return <tr key={queueItem.id + "_" + optionKey}>
                <td style={{textAlign: "left"}}>{prettyNames[optionKey] || optionKey}</td>
                <td style={{textAlign: "right"}}>{prettyValue}</td>
            </tr>
        })
        return <div key={iter} className="schedule-accordion-item">
            <Accordion.Item eventKey={iter}>
                <Accordion.Header>{(prettyNames[queueItem.type] || queueItem.type) + " - " + new Date(queueItem.time).toLocaleString()}</Accordion.Header>
                <Accordion.Body>
                    <Table>
                        <thead>
                            <tr>
                                <th style={{textAlign: "left"}}>Option</th>
                                <th style={{textAlign: "right"}}>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {options}
                        </tbody>
                    </Table>
                    {
                        props.loading.kingdom
                        ? <Button className="cancel-schedule-button" variant="primary" type="submit" disabled>
                            Loading...
                        </Button>
                        : <Button className="cancel-schedule" variant="primary" type="submit" onClick={() => onClickCancel(queueItem.id)}>
                            Cancel
                        </Button>
                    }
                </Accordion.Body>
            </Accordion.Item>
        </div>
    })
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

    return (
        <div className="schedule-queue">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <Accordion className="queue-accordion">
                {queueData}
            </Accordion>
        </div>
    )
}

export default Schedule;