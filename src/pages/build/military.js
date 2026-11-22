import { displayPercent } from "../../format";
import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import { AmountInput, NumberControl, SubmitButton, useSliders } from "../../components/forms";
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import ProgressBar from 'react-bootstrap/ProgressBar';
import "./military.css";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { checkCount } from "../../validation";
import { entriesInOrder } from "../../order";

/**
 * The units you train, in the server's order: every unit with a cost (not recruits or engineers). A unit with a
 * project can only be trained once that project is done.
 */
export function trainableUnits(mobisInfo, state) {
    return entriesInOrder(mobisInfo?.units_desc, state?.order?.units)
        .filter(([, unit]) => unit.cost !== undefined)
        .map(([key, unit]) => ({
            key,
            label: state?.pretty_names?.[key] || key,
            project: unit.project,
            projectName: state?.projects?.[unit.project]?.name || unit.project,
        }));
}
const blankInput = (units) => Object.fromEntries(units.map(({ key }) => [key, ""]));
const MODES = [
    { key: "train", label: "Train" },
    { key: "upgrade", label: "Upgrade" },
    { key: "allocate", label: "Allocate" },
    { key: "disband", label: "Disband" },
];

/**
 * Recruits at the top, then one units table. The switch (Train / Upgrade / Allocate / Disband) changes only the last
 * columns and the button, so the table stays the same while you move between them.
 */
function MilitaryContent(props) {
    const [mode, setMode] = useState("train");
    const kdInfo = props.data.kingdom;
    const mobisInfo = props.data.mobis;
    if (Object.keys(mobisInfo || {}).length === 0 || Object.keys(kdInfo || {}).length === 0) {
        return null;
    }
    const units = trainableUnits(mobisInfo, props.data.state);
    const used = mobisInfo.current_hangar_capacity || 0;
    const room = mobisInfo.max_hangar_capacity || 0;
    return (
    <>
        <div className="military">
            <Recruits kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/>
            <div className="military-capacity" title="Units take hangar space. Once the hangars are full, more units cannot be trained.">
                <div className="military-capacity-label">
                    <span>Hangar space</span>
                    <span>{used.toLocaleString()} / {room.toLocaleString()} ({room > 0 ? displayPercent(used / room) : "0%"})</span>
                </div>
                <ProgressBar now={room > 0 ? Math.min((used / room) * 100, 100) : 0} variant={room > 0 && used / room > 0.9 ? "danger" : "info"} />
            </div>
            {/* Shown as tabs (styles/shared.css); Disband is marked as the one that loses something. */}
            <div className="nav nav-tabs military-modes" role="group" aria-label="What to do with units">
                {MODES.map(({ key, label }) => (
                    <button key={key} type="button" aria-pressed={mode === key} onClick={() => setMode(key)}
                        className={"nav-link" + (mode === key ? " active" : "") + (key === "disband" ? " tab-warning" : "")}>{label}</button>
                ))}
            </div>
            {mode === "train" ? <Specialists units={units} kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/> : null}
            {mode === "upgrade" ? <Upgrade units={units} kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData} state={props.data.state}/> : null}
            {mode === "allocate" ? <Allocate units={units} kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/> : null}
            {mode === "disband" ? <Disband units={units} kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData} state={props.data.state}/> : null}
        </div>
        <HelpButton scrollTarget={"military"}/>
    </>
    )
}

/**
 * The one units table: what each unit costs and does, how many you have and have training, and a last column that is
 * whatever the mode asks for, after any ``extra`` columns. ``omit`` drops columns by header (Upgrade shows only what an
 * upgrade needs). A unit whose project is not done shows why in place of its numbers.
 */
function UnitsTable({ kdInfo, mobisInfo, units, lastHeader, last, extra = [], omit = [], className = "" }) {
    const desc = mobisInfo.units_desc || {};
    const locked = (unit) => Boolean(unit.project) && (kdInfo.completed_projects || []).indexOf(unit.project) < 0;
    const whole = (value) => Math.floor(value || 0).toLocaleString();
    const columns = [
        { header: "Unit", align: "left", cell: (unit) => unit.label },
        { header: "Cost", cell: (unit) => whole(desc[unit.key]?.cost) },
        { header: "Off / Def", cell: (unit) => `${desc[unit.key]?.offense || 0} / ${desc[unit.key]?.defense || 0}` },
        { header: "Fuel", cell: (unit) => desc[unit.key]?.fuel || 0 },
        { header: "Have", cell: (unit) => (locked(unit) ? `Research "${unit.projectName}" to unlock` : whole(mobisInfo.units.current_total?.[unit.key])),
          span: (unit) => (locked(unit) && !omit.includes("Training") ? 2 : 1) },
        { header: "Training", cell: (unit) => whole(mobisInfo.units.hour_24?.[unit.key]) },
        ...extra,
        { header: lastHeader, cell: (unit) => last(unit, locked(unit)) },
    ].filter((column) => !omit.includes(column.header));
    return <GameTable className={"game-table specialists-table " + className} columns={columns} rows={units} rowKey={(unit) => unit.key}
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
            <div className="text-box text-box-stats recruits-box">
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
                <div className="summary-form">
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
                        ? <span className="text-muted">Recruits Cost: {(parseInt(recruitsInput) * props.mobisInfo.recruit_price).toLocaleString()}</span>
                        : null
                    }
                </div>
            </div>
        </div>
        )
}

function Specialists(props) {
    const initialInput = blankInput(props.units);
    const [results, setResults] = useState([]);
    const [input, setInput] = useState(initialInput);
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput((previous) => ({ ...previous, [name]: value }));
    };
    const desc = props.mobisInfo.units_desc;
    const cost = props.units.reduce((total, { key }) => total + (parseInt(input[key] || 0) || 0) * (desc[key]?.cost || 0), 0);
    const recruitsUsed = props.units.reduce((total, { key }) => total + (parseInt(input[key] || 0) || 0), 0);
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
            <UnitsTable kdInfo={props.kdInfo} mobisInfo={props.mobisInfo} units={props.units} lastHeader="To Train"
                last={(unit, locked) => <AmountInput name={unit.key} id={`${unit.key}-train-input`} label={`${unit.label} to train`}
                    value={input[unit.key]} onChange={handleInputChange} max={maxTrain(unit.key)} soloMax={soloTrain(unit.key)} disabled={locked} />} />
            <div className="form-actions">
                <span className="military-summary text-muted">
                    <span>Cost: {cost.toLocaleString()}</span>
                    <span>Recruits left: {(recruits - recruitsUsed).toLocaleString()}</span>
                </span>
                <SubmitButton loading={props.loading.mobis} blocked={blocked} onClick={onSubmitClick} className="specialists-button">Train units</SubmitButton>
            </div>
        </div>
    );
}

/**
 * The units that can be made from others, each from the one below it in its line. Upgrading takes units at home, so
 * the most for one unit is what is at home of the unit it comes from (less what the other rows already take from it)
 * and what the money covers. The cost of each upgrade is the server's.
 */
export function upgradeLimits(units, desc, home, money, input) {
    const count = (key) => parseInt(input[key] || 0) || 0;
    const cost = units.reduce((total, { key }) => total + count(key) * (desc[key]?.upgrade_cost || 0), 0);
    const taken = (source) => units.reduce((total, { key }) => total + (desc[key]?.upgrades_from === source ? count(key) : 0), 0);
    const max = (key) => {
        const source = desc[key]?.upgrades_from;
        const each = desc[key]?.upgrade_cost || 0;
        const sourceLeft = Math.floor(home[source] || 0) - (taken(source) - count(key));
        const moneyLeft = each > 0 ? Math.floor((money - (cost - count(key) * each)) / each) : Infinity;
        return Math.max(Math.min(sourceLeft, moneyLeft), 0);
    };
    const soloMax = (key) => {
        const each = desc[key]?.upgrade_cost || 0;
        return Math.max(Math.min(Math.floor(home[desc[key]?.upgrades_from] || 0), each > 0 ? Math.floor(money / each) : Infinity), 0);
    };
    const short = Object.keys(desc).filter((key) => taken(key) > Math.floor(home[key] || 0));
    return { cost, max, soloMax, short, chosen: units.reduce((total, { key }) => total + count(key), 0) };
}

function Upgrade(props) {
    const rows = props.units.filter(({ key }) => props.mobisInfo.units_desc?.[key]?.upgrades_from);
    const [results, setResults] = useState([]);
    const [input, setInput] = useState(blankInput(rows));
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput((previous) => ({ ...previous, [name]: value }));
    };
    const desc = props.mobisInfo.units_desc;
    const home = props.kdInfo.units || {};
    const money = props.kdInfo.money || 0;
    const names = props.state?.pretty_names || {};
    const limits = upgradeLimits(rows, desc, home, money, input);
    const blocked = limits.chosen < 1 ? "Choose some units to upgrade"
        : limits.short.length > 0 ? `You have ${Math.floor(home[limits.short[0]] || 0).toLocaleString()} ${names[limits.short[0]] || limits.short[0]} at home`
        : limits.cost > money ? `Costs ${Math.ceil(limits.cost).toLocaleString()}, you have ${Math.floor(money).toLocaleString()}` : null;
    const onSubmitClick = () => {
        const updateFunc = () => authFetch('api/mobis/upgrade', {
            method: 'post',
            body: JSON.stringify({ "input": input }),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['mobis', 'kingdom'], [updateFunc]);
        setInput(blankInput(rows));
    };
    return (
        <div className="specialists">
            <ResultToasts title="Upgrade Results" results={results} setResults={setResults} />
            <p className="military-note">
                Upgrade units at home to the next unit of their line, one step at a time, for the difference in cost.
                They train like new units and do not fight until they are done.
            </p>
            {/* Only what an upgrade needs (the unit's price, fuel and training are on Train). On a phone each row is a
                small block (military.css), which counts on these columns in this order. */}
            <UnitsTable kdInfo={props.kdInfo} mobisInfo={props.mobisInfo} units={rows} lastHeader="To Upgrade"
                omit={["Cost", "Fuel", "Training"]} className="upgrade-table"
                extra={[
                    { header: "From", align: "left", cell: (unit) => {
                        const source = desc[unit.key].upgrades_from;
                        return <span className="upgrade-from">{names[source] || source}
                            <span className="upgrade-from-home">{Math.floor(home[source] || 0).toLocaleString()} at home</span></span>;
                    } },
                    { header: "Upgrade Cost", cell: (unit) => Math.ceil(desc[unit.key].upgrade_cost || 0).toLocaleString() },
                ]}
                last={(unit, locked) => <AmountInput name={unit.key} id={`${unit.key}-upgrade-input`} label={`${unit.label} to upgrade to`}
                    value={input[unit.key]} onChange={handleInputChange} max={limits.max(unit.key)} soloMax={limits.soloMax(unit.key)} disabled={locked} />} />
            <div className="form-actions">
                <span className="military-summary text-muted">
                    <span>Cost: {Math.ceil(limits.cost).toLocaleString()}</span>
                </span>
                <SubmitButton loading={props.loading.mobis} blocked={blocked} onClick={onSubmitClick} className="specialists-button">Upgrade units</SubmitButton>
            </div>
        </div>
    );
}

export function Allocate(props) {
    const [results, setResults] = useState([]);
    const keys = props.units.map(({ key }) => key);
    const sliders = useSliders(Object.fromEntries(keys.map((key) => [key, (props.kdInfo.units_target?.[key] || 0) * 100])));
    const [maxRecruits, setMaxRecruits] = useState(props.kdInfo.max_recruits ?? "");
    const [recruitsBeforeUnits, setRecruitsBeforeUnits] = useState(props.kdInfo?.recruits_before_units);
    const onSubmitClick = () => {
        const updateFunc = () => authFetch('api/mobis/target', {
            method: 'post',
            body: JSON.stringify({ "max_recruits": maxRecruits, "targets": sliders.body(keys) }),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
        sliders.reset();
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
    // A unit's slider can go as far as is left of 100% once the other units' shares are counted.
    const total = sliders.total(keys);
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
                <NumberControl id="max-recruits-input" inputMode="numeric" aria-label="Max recruits" onChange={(e) => setMaxRecruits(e.target.value)}
                    value={maxRecruits ?? ""} placeholder="0" autoComplete="off" isInvalid={Boolean(maxRecruitsError)} />
            </InputGroup>
            <UnitsTable kdInfo={props.kdInfo} mobisInfo={props.mobisInfo} units={props.units} lastHeader="New Share"
                extra={[{ header: "Share Now", cell: (unit) => displayPercent(props.kdInfo.units_target?.[unit.key] || 0) }]}
                last={(unit, locked) => <AmountInput name={unit.key} id={`${unit.key}-allocate-input`} label={`${unit.label} share`}
                    value={String(sliders.value(unit.key))} onChange={sliders.onChange} suffix="%"
                    max={Math.max(100 - (total - sliders.value(unit.key)), 0)} soloMax={100} disabled={locked && !sliders.value(unit.key)} />} />
            <div className="form-actions">
                <span className={total > 100 ? "text-danger" : "text-muted"}>{total}% of 100%</span>
                {sliders.changed ? <Button variant="link" size="sm" onClick={sliders.reset}>Undo changes</Button> : null}
                <SubmitButton loading={props.loading.kingdom} blocked={blocked} onClick={onSubmitClick} className="specialists-button">Save shares</SubmitButton>
            </div>
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
    const rows = [{ key: "recruits", label: prettyNames.recruits || "Recruits" }, ...props.units].filter(({ key }) => key in units);
    const chosen = Object.values(input).reduce((sum, value) => sum + (parseInt(value) || 0), 0);
    return (
        <div className="specialists warning-zone">
            <ResultToasts title="Disband Results" results={results} setResults={setResults} />
            <p className="military-note">Disbanded units go back to your population, and you get {displayPercent(props.state?.game_config?.BASE_DISBAND_COST_RETURN || 0)} of their training cost back.</p>
            <UnitsTable kdInfo={props.kdInfo} mobisInfo={props.mobisInfo} units={rows} lastHeader="To Disband"
                last={(unit) => <AmountInput name={unit.key} id={`disband-${unit.key}`} label={`${unit.label} to disband`}
                    value={input[unit.key]} onChange={handleInputChange} max={Math.floor(units[unit.key] || 0)} />} />
            <div className="form-actions">
                <SubmitButton loading={props.loading.kingdom} blocked={chosen < 1 ? "Choose some units to disband" : null}
                    onClick={onSubmitClick} variant="warning" className="specialists-button">Disband units</SubmitButton>
            </div>
        </div>
    );
}

export default MilitaryContent;
