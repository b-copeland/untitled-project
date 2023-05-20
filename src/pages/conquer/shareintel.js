import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import "./shareintel.css";
import Select from 'react-select';
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";

function ShareIntel(props) {
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [selectedStat, setSelectedStat] = useState(undefined);
    const [selectedShareTo, setSelectedShareTo] = useState(undefined);
    const [shareResults, setShareResults] = useState([]);
    const [cutInput, setCutInput] = useState(0.0);

    const onClickShare = () => {
        if (selected != undefined && selectedStat != undefined && selectedShareTo != undefined) {
            const opts = {
                "shared": selected,
                "shared_to": selectedShareTo,
                "shared_stat": selectedStat,
                "cut": cutInput,
            };
            const updateFunc = async () => authFetch('api/offershared', {
                method: 'POST',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setShareResults(shareResults.concat(r)))
            props.updateData(['shared'], [updateFunc]);
        }
    };

    const handleChange = (selectedOption) => {
        setSelected(selectedOption.value);
    };
    const handleStatChange = (selectedOption) => {
        setSelectedStat(selectedOption.value);
    };
    const handleShareToChange = (selectedOption) => {
        setSelectedShareTo(selectedOption.value);
    };
    const handleCutInput = (e) => {
        setCutInput(e.target.value);
    }
    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")"
        } else {
            return "Defender"
        }
        
    }
    if (props.loading.revealed) {
        return <h2>Loading...</h2>
    }
    if (Object.keys(props.data.revealed).length === 0) {
        return <div className="share-intel"><h2>You do not have any intel to share!</h2></div>
    }
    const kingdomOptions = Object.keys(props.data.revealed["revealed"]).map((kdId) => {
        return {"value": kdId, "label": kdFullLabel(kdId)}
    });
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
        const remainingSpans = Object.keys(revealed[kdId] || {}).map((category) =>
            <div key={kdId.toString() + '_' + category} className="remaining-timer">
                <span className="remaining-time-title">{category}</span>
                <span className="remaining-time-value">{getTimeString(revealed[kdId][category])}</span>
                <br />
            </div>
        )
        return remainingSpans;
    }
    const revealedStats = getRemainingSpans(selected, props.data.revealed["revealed"]);
    const revealedOptions = Object.keys(props.data.revealed["revealed"][selected] || {}).map((stat) => {
        return {"value": stat, "label": stat}
    })
    const shareToOptions = props.data.galaxies[props.data.galaxies_inverted[props.data.kingdomid.kd_id]].map((kdId) => {
        return {"value": kdId, "label": kdFullLabel(kdId)}
    });
    shareToOptions.push({"value": "galaxy", "label": "Your galaxy"})
    
    const toasts = shareResults.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setShareResults(shareResults.slice(0, index).concat(shareResults.slice(index + 1, 999)))}
            show={true}
            bg={results.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Share Intel Results</strong>
            </Toast.Header>
            <Toast.Body  className="text-black">{results.message}</Toast.Body>
        </Toast>
    )
    return (
        <>
        <Header data={props.data} />
        <div className="share-intel">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <label id="aria-label" htmlFor="aria-example-input">
                Kingdom to share
            </label>
            <Select
                className="share-intel-kingdom-select"
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
            {   selected !== undefined
                ? <div className="share-intel-choices">
                    <div className="text-box share-revealed-stats-box">
                        <h3>Revealed Stats</h3>
                        {revealedStats}
                    </div>
                    <div className="share-input">
                        <label id="aria-label" htmlFor="aria-example-input">
                            Select a stat to share
                        </label>
                        <Select
                            className="share-intel-select"
                            options={revealedOptions}
                            onChange={handleStatChange}
                            autoFocus={false}
                            isSearchable={false}
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
                            // defaultValue={revealedOptions.filter(option => option.value === props.initialKd)}
                        />
                    </div>
                    <div className="share-input">
                        <label id="aria-label" htmlFor="aria-example-input">
                            Share to
                        </label>
                        <Select
                            className="share-to-select"
                            options={shareToOptions}
                            onChange={handleShareToChange}
                            autoFocus={true}
                            isSearchable={false}
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
                            // defaultValue={revealedOptions.filter(option => option.value === props.initialKd)}
                        />
                    </div>
                    <div className="share-input">
                        <label id="aria-label" htmlFor="aria-example-input">
                            Select Cut
                        </label>
                        <InputGroup className="mb-3">
                            <Form.Control 
                                className="cut-form"
                                id="cut-input"
                                onChange={handleCutInput}
                                value={cutInput || ""}
                                placeholder="0"
                                autoComplete="off"
                            />
                            <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                        </InputGroup>
                    </div>
                    {
                        props.loading.shared
                        ? <Button className="share-button" variant="primary" type="submit" disabled>
                            Loading...
                        </Button>
                        : <Button className="share-button" variant="primary" type="submit" onClick={onClickShare}>
                            Share
                        </Button>
                    }
                </div>
                : null
            }
            <HelpButton scrollTarget={"shareintel"}/>
        </div>
        </>
    )
}

export default ShareIntel;