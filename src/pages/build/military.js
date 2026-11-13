import { displayPercent } from "../../format";
import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import { AmountInput, SubmitButton } from "../../components/forms";
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import ProgressBar from 'react-bootstrap/ProgressBar';
import "./military.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { checkCount } from "../../validation";

// The units you train, in the order they are shown. Big flexers need their project first.
const UNITS = [
    { key: "attack", label: "Attackers" },
    { key: "defense", label: "Defenders" },
    { key: "flex", label: "Flexers" },
    { key: "big_flex", label: "Big Flexers", project: "big_flexers", projectName: "Big Flexers" },
];
const MODES = [
    { key: "train", label: "Train" },
    { key: "allocate", label: "Allocate" },
    { key: "disband", label: "Disband" },
];

/**
 * Recruits at the top, then one units table. The switch (Train / Allocate / Disband) changes only the last column and
 * the button, so the table stays the same while you move between them.
 */
function MilitaryContent(props) {
    const [mode, setMode] = useState("train");
    const kdInfo = props.data.kingdom;
    const mobisInfo = props.data.mobis;
    if (Object.keys(mobisInfo || {}).length === 0 || Object.keys(kdInfo || {}).length === 0) {
        return <Header data={props.data} />;
    }
    const used = mobisInfo.current_hangar_capacity || 0;
    const room = mobisInfo.max_hangar_capacity || 0;
    return (
    <>
        <Header data={props.data} />
        <div className="military">
            <Recruits kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/>
            <div className="military-capacity" title="Units take hangar space. Once the hangars are full, more units cannot be trained.">
                <div className="military-capacity-label">
                    <span>Hangar space</span>
                    <span>{used.toLocaleString()} / {room.toLocaleString()} ({room > 0 ? displayPercent(used / room) : "0%"})</span>
                </div>
                <ProgressBar now={room > 0 ? Math.min((used / room) * 100, 100) : 0} variant={room > 0 && used / room > 0.9 ? "danger" : "info"} />
            </div>
            <ButtonGroup className="military-modes" aria-label="What to do with units">
                {MODES.map(({ key, label }) => (
                    <Button key={key} variant={mode === key ? "primary" : "outline-secondary"} aria-pressed={mode === key} onClick={() => setMode(key)}>{label}</Button>
                ))}
            </ButtonGroup>
            {mode === "train" ? <Specialists kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/> : null}
            {mode === "allocate" ? <Allocate kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/> : null}
            {mode === "disband" ? <Disband kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData} state={props.data.state}/> : null}
        </div>
        <HelpButton scrollTarget={"military"}/>
    </>
    )
}

/**
 * The one units table: what each unit costs and does, how many you have and have training, and a last column that is
 * whatever the mode asks for. A unit whose project is not done shows why in place of its numbers.
 */
function UnitsTable({ kdInfo, mobisInfo, units = UNITS, lastHeader, last, extra = [] }) {
    const desc = mobisInfo.units_desc || {};
    const locked = (unit) => Boolean(unit.project) && kdInfo.completed_projects.indexOf(unit.project) < 0;
    const whole = (value) => Math.floor(value || 0).toLocaleString();
    const columns = [
        { header: "Unit", align: "left", cell: (unit) => unit.label },
        { header: "Cost", cell: (unit) => whole(desc[unit.key]?.cost) },
        { header: "Off / Def", cell: (unit) => `${desc[unit.key]?.offense || 0} / ${desc[unit.key]?.defense || 0}` },
        { header: "Fuel", cell: (unit) => desc[unit.key]?.fuel || 0 },
        { header: "Have", cell: (unit) => (locked(unit) ? `Research "${unit.projectName}" to unlock` : whole(mobisInfo.units.current_total?.[unit.key])),
          span: (unit) => (locked(unit) ? 2 : 1) },
        { header: "Training", cell: (unit) => whole(mobisInfo.units.hour_24?.[unit.key]) },
        ...extra,
        { header: lastHeader, cell: (unit) => last(unit, locked(unit)) },
    ];
    return <GameTable className="game-table specialists-table" columns={columns} rows={units} rowKey={(unit) => unit.key}
        rowClassName={(unit) => (locked(unit) ? "disabled-table-row" : undefined)} />;
}

function Recruits(props) {
    const [recruitsInput, setRecruitsInput] = useState("");
    const [recruitsResults, setRecruitsResults] = useState([]);
    
    // useEffect(() => {
    //     const fetchData = async () => {
    //         await authFetch("api/settle").then(r => r.json()).then(r => setSettleInfo(r));
    //         setReloading(false);
    //     }
    //     fetchData();
    // }, [reloading])

    const handleRecruitsInput = (e) => {
        setRecruitsInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (recruitsInput > 0) {
            let opts = {
                'recruitsInput': recruitsInput,
            };
            const updateFunc = () => authFetch('api/recruits', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setRecruitsResults(recruitsResults.concat(r)))
            props.updateData(['mobis', 'kingdom'], [updateFunc]);
            setRecruitsInput('');
        }
    }
    if (Object.keys(props.mobisInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    const price = props.mobisInfo.recruit_price || 0;
    const maxRecruitsNow = Math.min(props.mobisInfo.current_available_recruits || 0, price > 0 ? Math.floor((props.kdInfo.money || 0) / price) : Infinity);
    return (
        <div className="recruits">
            <ResultToasts title="Recruits Results" results={recruitsResults} setResults={setRecruitsResults} />
            <div className="text-box recruits-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Recruit Time</span>
                    <span className="text-box-item-value">{(props.mobisInfo.recruit_time / 3600).toFixed(1)}h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Recruit Cost</span>
                    <span className="text-box-item-value">{props.mobisInfo.recruit_price?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.current_total.recruits?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.hour_24.recruits?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.max_available_recruits?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.current_available_recruits?.toLocaleString()}</span>
                </div>
                <div className="amount-field">
                    <label htmlFor="recruits-input">New recruits</label>
                    <AmountInput name="recruits" id="recruits-input" label="New recruits" value={recruitsInput}
                        onChange={handleRecruitsInput} max={maxRecruitsNow} />
                </div>
                {props.loading.mobis
                ? <Button className="recruits-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="recruits-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Recruit
                </Button>
                }
                {
                    recruitsInput !== ""
                    ? <h3>Recruits Cost: {(parseInt(recruitsInput) * props.mobisInfo.recruit_price).toLocaleString()}</h3>
                    : null
                }
            </div>
        </div>
        )
}

const initialInput = {
    "attack": "",
    "defense": "",
    "flex": "",
    "big_flex": "",
};

function Specialists(props) {
    const [results, setResults] = useState([]);
    const [input, setInput] = useState(initialInput);
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput((previous) => ({ ...previous, [name]: value }));
    };
    const desc = props.mobisInfo.units_desc;
    const cost = UNITS.reduce((total, { key }) => total + (parseInt(input[key] || 0) || 0) * (desc[key]?.cost || 0), 0);
    const recruitsUsed = UNITS.reduce((total, { key }) => total + (parseInt(input[key] || 0) || 0), 0);
    const recruits = props.kdInfo.units.recruits || 0;
    const money = props.kdInfo.money || 0;
    // The most of one unit: the recruits left after the others, and what the money covers after the others.
    const soloTrain = (unit) => {
        const each = desc[unit]?.cost || 0;
        return Math.max(Math.min(recruits, each > 0 ? Math.floor(money / each) : Infinity), 0);
    };
    const maxTrain = (unit) => {
        const mine = parseInt(input[unit] || 0) || 0;
        const each = desc[unit]?.cost || 0;
        const recruitsLeft = recruits - (recruitsUsed - mine);
        const moneyLeft = each > 0 ? Math.floor((money - (cost - mine * each)) / each) : Infinity;
        return Math.max(Math.min(recruitsLeft, moneyLeft), 0);
    };
    const blocked = recruitsUsed < 1 ? "Choose some units to train"
        : recruitsUsed > recruits ? `You have ${recruits.toLocaleString()} recruits`
        : cost > money ? `Costs ${cost.toLocaleString()}, you have ${Math.floor(money).toLocaleString()}` : null;
    const onSubmitClick = () => {
        const updateFunc = () => authFetch('api/mobis', {
            method: 'post',
            body: JSON.stringify(input),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['mobis', 'kingdom'], [updateFunc]);
        setInput(initialInput);
    };
    return (
        <div className="specialists">
            <ResultToasts title="Training Results" results={results} setResults={setResults} />
            <UnitsTable kdInfo={props.kdInfo} mobisInfo={props.mobisInfo} lastHeader="To Train"
                last={(unit, locked) => <AmountInput name={unit.key} id={`${unit.key}-train-input`} label={`${unit.label} to train`}
                    value={input[unit.key]} onChange={handleInputChange} max={maxTrain(unit.key)} soloMax={soloTrain(unit.key)} disabled={locked} />} />
            <div className="military-summary">
                <span>Cost: {cost.toLocaleString()}</span>
                <span>Recruits left: {(recruits - recruitsUsed).toLocaleString()}</span>
            </div>
            <SubmitButton loading={props.loading.mobis} blocked={blocked} onClick={onSubmitClick} className="specialists-button">Train units</SubmitButton>
        </div>
    );
}

function Allocate(props) {
    const [results, setResults] = useState([]);
    const [input, setInput] = useState(initialInput);
    const [maxRecruits, setMaxRecruits] = useState(props.kdInfo.max_recruits ?? "");
    const [recruitsBeforeUnits, setRecruitsBeforeUnits] = useState(props.kdInfo?.recruits_before_units);
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput((previous) => ({ ...previous, [name]: value }));
    };
    const onSubmitClick = () => {
        const updateFunc = () => authFetch('api/mobis/target', {
            method: 'post',
            body: JSON.stringify({ "max_recruits": maxRecruits, "targets": input }),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };
    const handleEnabledChange = (e) => {
        const checked = e.target.checked;
        const updateFunc = () => authFetch('api/mobis/target', {
            method: 'post',
            body: JSON.stringify({ 'recruits_before_units': checked }),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
        setRecruitsBeforeUnits(checked);
    };
    // A unit's slider can go as far as is left of 100% once the other units' new numbers are counted.
    const maxAllocate = (unit) => Math.max(100 - Object.entries(input).filter(([other]) => other !== unit).reduce((sum, [, value]) => sum + (parseFloat(value) || 0), 0), 0);
    const total = Object.values(input).reduce((sum, value) => sum + (parseFloat(value) || 0), 0);
    const maxRecruitsError = checkCount(maxRecruits);
    const blocked = total > 100 ? "The shares add up to more than 100%" : maxRecruitsError;
    return (
        <div className="specialists">
            <ResultToasts title="Allocation Results" results={results} setResults={setResults} />
            <p className="military-note">The share of your units the auto spender trains towards.</p>
            <Form.Check type="switch" id="recruits-before-units-switch" label="Train recruits before units"
                defaultChecked={recruitsBeforeUnits} onChange={handleEnabledChange} disabled={props.loading.kingdom} />
            <InputGroup className="max-recruits-input-group">
                <InputGroup.Text id="recruits-input-display">Max Recruits</InputGroup.Text>
                <Form.Control id="max-recruits-input" aria-label="Max recruits" onChange={(e) => setMaxRecruits(e.target.value)}
                    value={maxRecruits ?? ""} placeholder="0" autoComplete="off" isInvalid={Boolean(maxRecruitsError)} />
            </InputGroup>
            <UnitsTable kdInfo={props.kdInfo} mobisInfo={props.mobisInfo} lastHeader="New Share"
                extra={[{ header: "Share Now", cell: (unit) => displayPercent(props.kdInfo.units_target?.[unit.key] || 0) }]}
                last={(unit, locked) => <AmountInput name={unit.key} id={`${unit.key}-allocate-input`} label={`${unit.label} share`}
                    value={input[unit.key]} onChange={handleInputChange} suffix="%" max={maxAllocate(unit.key)} soloMax={100} disabled={locked} />} />
            <SubmitButton loading={props.loading.kingdom} blocked={blocked} onClick={onSubmitClick} className="specialists-button">Save shares</SubmitButton>
        </div>
    );
}

function Disband(props) {
    const [results, setResults] = useState([]);
    const [input, setInput] = useState({});
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput((previous) => ({ ...previous, [name]: value }));
    };
    const onSubmitClick = () => {
        const updateFunc = () => authFetch('api/mobis/disband', {
            method: 'post',
            body: JSON.stringify({ "input": input }),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
        setInput({});
    };
    const units = props.kdInfo.units || {};
    const prettyNames = props.state?.pretty_names || {};
    // Recruits can be disbanded too; engineers are not shown here, as before.
    const rows = [{ key: "recruits", label: prettyNames.recruits || "Recruits" }, ...UNITS].filter(({ key }) => key in units);
    const chosen = Object.values(input).reduce((sum, value) => sum + (parseInt(value) || 0), 0);
    return (
        <div className="specialists">
            <ResultToasts title="Disband Results" results={results} setResults={setResults} />
            <p className="military-note">Disbanded units go back to your population, and you get {displayPercent(props.state?.game_config?.BASE_DISBAND_COST_RETURN || 0)} of their training cost back.</p>
            <UnitsTable kdInfo={props.kdInfo} mobisInfo={props.mobisInfo} units={rows} lastHeader="To Disband"
                last={(unit) => <AmountInput name={unit.key} id={`disband-${unit.key}`} label={`${unit.label} to disband`}
                    value={input[unit.key]} onChange={handleInputChange} max={Math.floor(units[unit.key] || 0)} />} />
            <SubmitButton loading={props.loading.kingdom} blocked={chosen < 1 ? "Choose some units to disband" : null}
                onClick={onSubmitClick} variant="warning" className="specialists-button">Disband units</SubmitButton>
        </div>
    );
}

export default MilitaryContent;
