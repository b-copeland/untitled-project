import React, { useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./structures.css"
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { AmountInput, SubmitButton, useFormValues } from "../../components/forms";
import { displayPercent } from "../../format";
import { anyFilled, checkCount, checkPercent, checkTotal, firstError } from "../../validation";

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
            <Header data={props.data} />
            <Tabs id="controlled-tab-example" defaultActiveKey="build" justify fill variant="tabs">
                <Tab eventKey="build" title="Build"><BuildStructures {...shared} /></Tab>
                <Tab eventKey="allocate" title="Allocate"><AllocateStructures {...shared} /></Tab>
                <Tab eventKey="raze" title="Raze"><RazeStructures {...shared} /></Tab>
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
        { header: "# Building", cell: ([key]) => whole(info.hour_24[key]) },
        {
            header: "To Build", className: "structures-form-data",
            cell: ([key, label]) => <AmountInput name={key} label={label} id={`${key.replace("_", "-")}-input`} value={form.values[key]} onChange={form.onChange} error={fieldErrors[key]} max={maxFor(key)} soloMax={soloMax} />,
        },
    ];

    return (
        <div className="structures">
            <ResultToasts title="Structures Results" results={results} setResults={setResults} />
            <div className="text-box box-tight structures-box">
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
            <SubmitButton loading={props.loading.structures} blocked={blocked} className="structures-button"
                onClick={() => send(form.values, form.reset)}>
                Build
            </SubmitButton>
            {stars !== 0
                ? <div>
                    <h3>Structures Cost: {(stars * info.price).toLocaleString()}</h3>
                    <h3>Stars Remaining: {(info.max_available_structures - stars).toLocaleString()}</h3>
                </div>
                : null}
        </div>
    );
}

function AllocateStructures(props) {
    const form = useFormValues(noneYet);
    const [results, setResults, send] = useSubmit('api/structures/target', ['kingdom'], props);

    if (Object.keys(props.data.structures).length === 0 || Object.keys(props.data.kingdom).length === 0) {
        return null;
    }
    const info = props.data.structures;
    const kingdom = props.data.kingdom;
    const current = kingdom.structures_target || {};

    // What the targets would be after this change: what is typed replaces what is there, the rest stays.
    const afterChange = Object.fromEntries(STRUCTURES.map(([key]) => [
        key,
        form.values[key] !== "" ? form.values[key] : (current[key] || 0) * 100,
    ]));
    const fieldErrors = Object.fromEntries(STRUCTURES.map(([key]) => [key, checkPercent(form.values[key])]));
    const totalError = firstError(fieldErrors) ? null : checkTotal(afterChange, { max: 100 });
    const blocked = firstError(fieldErrors, totalError ? "Allocation would total more than 100%" : null)
        || (anyFilled(form.values) ? null : "Enter the new percent for at least one structure");

    const columns = [
        { header: "Structure", align: "left", cell: ([, label]) => label },
        { header: "% Built", cell: ([key]) => displayPercent((info.current[key] || 0) / kingdom.stars) },
        { header: "# Built", cell: ([key]) => whole(info.current[key]) },
        { header: "# Building", cell: ([key]) => whole(info.hour_24[key]) },
        { header: "Current Allocation", cell: ([key]) => displayPercent(current[key] || 0) },
        {
            header: "New Allocation", className: "structures-form-data",
            cell: ([key, label]) => <AmountInput name={key} label={label} suffix="%" value={form.values[key]} onChange={form.onChange} error={fieldErrors[key]}
                soloMax={100} max={Math.max(100 - Object.entries(afterChange).filter(([other]) => other !== key).reduce((sum, [, value]) => sum + (parseFloat(value) || 0), 0), 0)} />,
        },
    ];
    const total = Object.values(afterChange).reduce((sum, value) => sum + (parseFloat(value) || 0), 0);

    return (
        <div className="structures">
            <ResultToasts title="Structures Results" results={results} setResults={setResults} />
            <div className="text-box box-tight structures-box">
                <span>Choose the target allocation of structures that you would like the auto-spender to build towards</span>
            </div>
            <GameTable className="structures-allocation-table" columns={columns} rows={STRUCTURES} rowKey={([key]) => key} />
            <div className={totalError ? "text-danger" : "text-muted"}>Allocation after this change: {total.toFixed(1)}% of 100%</div>
            <SubmitButton loading={props.loading.kingdom} blocked={blocked} className="structures-button"
                onClick={() => send(form.values, form.reset)}>
                Update
            </SubmitButton>
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
        <div className="col-center structures-raze">
            <h2>Raze Structures</h2>
            <div className="text-box box-tight structures-box">
                <span>Raze structures to destroy them and receive {displayPercent(props.data.state.game_config?.BASE_STRUCTURES_RAZE_RETURN || 0)} of the current build cost back</span>
            </div>
            <ResultToasts title="Raze Results" results={results} setResults={setResults} />
            <GameTable className="structures-table" columns={columns} rows={keys} rowKey={(key) => key} />
            <SubmitButton loading={props.loading.kingdom} blocked={blocked} variant="warning" className="structures-button"
                onClick={() => send({ input: form.values }, form.reset)}>
                Raze
            </SubmitButton>
        </div>
    );
}

export default Structures;
