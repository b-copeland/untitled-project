import React, { useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./structures.css"
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { AmountInput, SubmitButton, useFormValues, useSliders } from "../../components/forms";
import Button from "react-bootstrap/Button";
import { displayPercent } from "../../format";
import { anyFilled, checkCount, checkTotal, firstError } from "../../validation";

const STRUCTURES = [
    ["homes", "Homes"],
    ["mines", "Mines"],
    ["fuel_plants", "Fuel Plants"],
    ["hangars", "Hangars"],
    ["drone_factories", "Drone Factories"],
    ["missile_silos", "Missile Silos"],
    ["workshops", "Workshops"],
];

const noneYet = Object.fromEntries(STRUCTURES.map(([key]) => [key, ""]));

const whole = (value) => Math.floor(value || 0).toLocaleString();

function Structures(props) {
    const shared = { loading: props.loading, updateData: props.updateData, data: props.data };
    return (
        <>
            <Tabs id="controlled-tab-example" defaultActiveKey="build" variant="tabs">
                <Tab eventKey="build" title="Build"><BuildStructures {...shared} /></Tab>
                <Tab eventKey="allocate" title="Allocate"><AllocateStructures {...shared} /></Tab>
                <Tab eventKey="raze" title="Raze" tabClassName="tab-warning"><RazeStructures {...shared} /></Tab>
            </Tabs>
            <HelpButton scrollTarget={"structures"}/>
        </>
    );
}

/** Sends a form to the server, refreshes the data it changes, and keeps the answers to show as toasts. */
function useSubmit(path, refresh, props) {
    const [results, setResults] = useState([]);
    const send = (body, afterSend) => {
        const updateFunc = () => authFetch(path, {
            method: 'post',
            body: JSON.stringify(body),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(refresh, [updateFunc]);
        afterSend();
    };
    return [results, setResults, send];
}

function BuildStructures(props) {
    const form = useFormValues(noneYet);
    const [results, setResults, send] = useSubmit('api/structures', ['structures', 'kingdom'], props);

    if (Object.keys(props.data.structures).length === 0 || Object.keys(props.data.kingdom).length === 0) {
        return null;
    }
    const info = props.data.structures;
    const kingdom = props.data.kingdom;
    const config = props.data.state.game_config || {};

    const available = info.current_available_structures;
    const fieldErrors = Object.fromEntries(STRUCTURES.map(([key]) => [key, checkCount(form.values[key], { max: available })]));
    const totalError = checkTotal(form.values, { max: available, noun: "structures" });
    const stars = STRUCTURES.reduce((sum, [key]) => sum + (parseInt(form.values[key], 10) || 0), 0);
    const blocked = firstError(fieldErrors, totalError) || (anyFilled(form.values) ? null : "Enter how many of each to build");
    // The most of one kind that fits: what is left of the room after the others, and what the money still covers.
    // What one kind could take with nothing else ordered: it sets the slider's length, so the slider holds still.
    const soloMax = Math.max(Math.min(available, info.price > 0 ? Math.floor(kingdom.money / info.price) : available), 0);
    const maxFor = (key) => {
        const others = stars - (parseInt(form.values[key], 10) || 0);
        const room = available - others;
        const affordable = info.price > 0 ? Math.floor((kingdom.money - others * info.price) / info.price) : room;
        return Math.max(Math.min(room, affordable), 0);
    };

    const columns = [
        { header: "Structure", align: "left", cell: ([, label]) => label },
        { header: "% Built", cell: ([key]) => displayPercent((info.current[key] || 0) / kingdom.stars) },
        { header: "# Built", cell: ([key]) => whole(info.current[key]) },
        { header: "# Building", cell: ([key]) => whole(info.queued[key]) },
        {
            header: "To Build", className: "structures-form-data",
            cell: ([key, label]) => <AmountInput name={key} label={label} id={`${key.replace("_", "-")}-input`} value={form.values[key]} onChange={form.onChange} error={fieldErrors[key]} max={maxFor(key)} soloMax={soloMax} />,
        },
    ];

    return (
        <div className="structures">
            <ResultToasts title="Structures Results" results={results} setResults={setResults} />
            <div className="text-box text-box-stats">
                <div className="text-box-item">
                    <span className="text-box-item-title">Average Build Time</span>
                    <span className="text-box-item-value">{config.BASE_EPOCH_SECONDS * (config.BASE_STRUCTURE_TIME_MIN_MULTIPLIER + config.BASE_STRUCTURE_TIME_MAX_MUTLIPLIER) / 2 / 3600}h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Build Cost</span>
                    <span className="text-box-item-value">{info.price.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Structures</span>
                    <span className="text-box-item-value">{info.max_available_structures.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Structures</span>
                    <span className="text-box-item-value">{available.toLocaleString()}</span>
                </div>
            </div>
            <GameTable className="structures-table" columns={columns} rows={STRUCTURES} rowKey={([key]) => key} />
            <div className="form-actions">
                {stars !== 0
                    ? <span className="text-muted">Cost {(stars * info.price).toLocaleString()} · {(info.max_available_structures - stars).toLocaleString()} stars left</span>
                    : null}
                <SubmitButton loading={props.loading.structures} blocked={blocked} onClick={() => send(form.values, form.reset)}>
                    Build
                </SubmitButton>
            </div>
        </div>
    );
}

export function AllocateStructures(props) {
    const kingdom = props.data.kingdom;
    const current = Object.fromEntries(STRUCTURES.map(([key]) => [key, (kingdom.structures_target?.[key] || 0) * 100]));
    const sliders = useSliders(current);
    const [results, setResults, send] = useSubmit('api/structures/target', ['kingdom'], props);

    if (Object.keys(props.data.structures).length === 0 || Object.keys(kingdom).length === 0) {
        return null;
    }
    const info = props.data.structures;
    const keys = STRUCTURES.map(([key]) => key);
    const total = sliders.total(keys);
    const blocked = total > 100 ? "Allocation would total more than 100%"
        : sliders.changed ? null : "Move a slider to change a structure's share";

    const columns = [
        { header: "Structure", align: "left", cell: ([, label]) => label },
        { header: "% Built", cell: ([key]) => displayPercent((info.current[key] || 0) / kingdom.stars) },
        { header: "# Built", cell: ([key]) => whole(info.current[key]) },
        { header: "# Building", cell: ([key]) => whole(info.queued[key]) },
        { header: "Current Allocation", cell: ([key]) => displayPercent(current[key] / 100) },
        {
            header: "New Allocation", className: "structures-form-data",
            cell: ([key, label]) => <AmountInput name={key} label={label} suffix="%" value={String(sliders.value(key))} onChange={sliders.onChange}
                soloMax={100} max={Math.max(100 - (total - sliders.value(key)), 0)} />,
        },
    ];

    return (
        <div className="structures">
            <ResultToasts title="Structures Results" results={results} setResults={setResults} />
            <p className="page-note">Choose the target allocation of structures that you would like the auto-spender to build towards</p>
            <GameTable className="structures-allocation-table" columns={columns} rows={STRUCTURES} rowKey={([key]) => key} />
            <div className="form-actions">
                <span className={total > 100 ? "text-danger" : "text-muted"}>Allocation after this change: {total}% of 100%</span>
                {sliders.changed ? <Button variant="link" size="sm" onClick={sliders.reset}>Undo changes</Button> : null}
                <SubmitButton loading={props.loading.kingdom} blocked={blocked} onClick={() => send(sliders.body(keys), sliders.reset)}>
                    Update
                </SubmitButton>
            </div>
        </div>
    );
}

function RazeStructures(props) {
    const form = useFormValues({});
    const [results, setResults, send] = useSubmit('api/structures/raze', ['kingdom'], props);

    const structures = props.data.kingdom.structures || {};
    const stars = props.data.kingdom.stars || 1;
    const prettyNames = props.data.state.pretty_names || {};
    const keys = Object.keys(structures);

    const fieldErrors = Object.fromEntries(keys.map((key) => [key, checkCount(form.values[key], { max: Math.floor(structures[key] || 0) })]));
    const blocked = firstError(fieldErrors) || (anyFilled(form.values) ? null : "Enter how many of each to raze");

    const columns = [
        { header: "Structure", align: "left", cell: (key) => prettyNames[key] || key },
        { header: "% Built", cell: (key) => displayPercent((structures[key] || 0) / stars) },
        { header: "Available", cell: (key) => structures[key] || 0 },
        {
            header: "To Raze",
            cell: (key) => <AmountInput name={key} label={prettyNames[key] || key} id={"raze-" + key} value={form.values[key]} onChange={form.onChange} error={fieldErrors[key]} max={Math.floor(structures[key] || 0)} />,
        },
    ];

    return (
        <div className="structures structures-raze warning-zone">
            <p className="page-note">Raze structures to destroy them and receive {displayPercent(props.data.structures?.raze_return ?? props.data.state.game_config?.BASE_STRUCTURES_RAZE_RETURN ?? 0)} of the current build cost back</p>
            <ResultToasts title="Raze Results" results={results} setResults={setResults} />
            <GameTable className="structures-table" columns={columns} rows={keys} rowKey={(key) => key} />
            <div className="form-actions">
                <SubmitButton loading={props.loading.kingdom} blocked={blocked} variant="warning" onClick={() => send({ input: form.values }, form.reset)}>
                    Raze
                </SubmitButton>
            </div>
        </div>
    );
}

export default Structures;
