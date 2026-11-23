import React, { useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Alert from 'react-bootstrap/Alert';
import { GiCrossedSwords, GiSpaceship, GiMagnifyingGlass, GiNinjaHeroicStance, GiMissileLauncher } from "react-icons/gi";
import "./schedule.css";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput } from "../../components/forms";
import { Panel, FieldRow, Picker } from "../../components/planner";
import { displayPercent } from "../../format";
import { availableOperations } from "./spy";
import { Repeating } from "./recurring";
import { Reactions } from "./rules";

function Schedule(props) {
    return (
        <>
            <div className="planner schedule">
                <Tabs id="schedule-tabs" defaultActiveKey="add" variant="tabs">
                    <Tab eventKey="add" title="Add">
                        <Add loading={props.loading} updateData={props.updateData} data={props.data} />
                    </Tab>
                    <Tab eventKey="queue" title={`Queue${props.data.kingdom.schedule?.length ? ` (${props.data.kingdom.schedule.length})` : ""}`}>
                        <Queue loading={props.loading} updateData={props.updateData} data={props.data} />
                    </Tab>
                    <Tab eventKey="repeating" title={`Repeating${props.data.kingdom.recurring?.length ? ` (${props.data.kingdom.recurring.length})` : ""}`}>
                        <Repeating loading={props.loading} updateData={props.updateData} data={props.data} />
                    </Tab>
                    <Tab eventKey="reactions" title={`Reactions${props.data.kingdom.rules?.length ? ` (${props.data.kingdom.rules.length})` : ""}`}>
                        <Reactions loading={props.loading} updateData={props.updateData} data={props.data} />
                    </Tab>
                </Tabs>
                <HelpButton scrollTarget={"schedule"}/>
            </div>
        </>
    );
}

// What each kind of action needs, and the limits the server holds it to. Percent fields are typed as 0-100.
const KINDS = {
    attack: {
        title: "Attack", icon: GiCrossedSwords, blurb: "Attack a kingdom at a set time.",
        start: {
            prefer_autofill: true, autofill_buffer: "1", send_without_intel: true, target: null,
            units_mode: "send", pure_offense: "", flex_offense: "", generals: "1",
        },
    },
    attackprimitives: {
        title: "Attack primitives", icon: GiSpaceship, blurb: "Send part of your army at the primitives.",
        start: { units_mode: "up_to", pure_offense: "", flex_offense: "", generals: "1" },
    },
    intelspy: {
        title: "Gather intel", icon: GiMagnifyingGlass, blurb: "Spy on a kingdom to learn about it, retrying if it fails.",
        start: { target: null, operation: null, drones_pct: "", shielded: false, max_tries: "1", share_to_galaxy: false },
    },
    aggressivespy: {
        title: "Hostile operation", icon: GiNinjaHeroicStance, blurb: "Siphon, bomb, sabotage or kidnap at a set time.",
        start: { target: null, operation: null, drones_pct: "", shielded: false, attempts: "1" },
    },
    missiles: {
        title: "Launch missiles", icon: GiMissileLauncher, blurb: "Launch missiles at a kingdom at a set time.",
        start: { target: null, planet_busters: "", star_busters: "", galaxy_busters: "" },
    },
};

// How an attack counts the share of attackers and flexers it sends (options.units_mode). The server holds the same two.
export const UNITS_MODES = [
    {
        value: "send", label: "Send X% of total units",
        hint: "Each attack sends that share of your whole army, as far as the units at home allow. Four attacks at 25% send four waves.",
    },
    {
        value: "up_to", label: "Send up to X% of total units, including units already out on generals",
        hint: "With 30% already out and 50% set, it sends 20%. With 50% or more out, it sends nothing.",
    },
];

const INTEL_OPERATIONS = [
    { value: "spymilitary", label: "Spy on military" }, { value: "spykingdom", label: "Spy on kingdom" },
    { value: "spyshields", label: "Spy on shields" }, { value: "spyprojects", label: "Spy on projects" },
    { value: "spystructures", label: "Spy on structures" }, { value: "spydrones", label: "Spy on drones" },
    { value: "spyall", label: "Full infiltration (everything)" },
];
const HOSTILE_OPERATIONS = [
    { value: "siphonfunds", label: "Siphon funds" }, { value: "bombhomes", label: "Bomb homes" },
    { value: "sabotagefuelplants", label: "Sabotage fuel plants" }, { value: "kidnappopulation", label: "Kidnap population" },
    { value: "suicidedrones", label: "Suicide drones" },
];

// "2026-11-12T14:30", in the player's own time zone, which is what a datetime-local box wants.
const localInput = (date) => {
    const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return shifted.toISOString().slice(0, 16);
};
const inFuture = (hours) => localInput(new Date(Date.now() + hours * 3600000));

const percentProblem = (value, label) => {
    const number = parseFloat(value);
    if (value === "" || value === undefined) return `${label}: enter a percentage`;
    if (!(number >= 0 && number <= 100)) return `${label} must be between 0% and 100%`;
    return null;
};
const intProblem = (value, label, min, max) => {
    const number = parseInt(value, 10);
    if (!(number >= min && number <= max)) return `${label} must be between ${min} and ${max}`;
    return null;
};

/** Everything wrong with a schedule request, in the order the player would fix it. The server still decides. */
function problemsWith(kind, options, when, me) {
    const found = [];
    if (kind === undefined) return ["Choose what to schedule"];
    const date = new Date(when);
    if (!when || isNaN(date)) found.push("Choose when it should happen");
    else if (date.getTime() < Date.now()) found.push("That time has already passed");
    if ("target" in options) {
        if (options.target === null) found.push("Choose a target");
        else if (String(options.target) === String(me)) found.push("You can not target yourself");
    }
    if ("operation" in options && !options.operation) found.push("Choose an operation");
    if ("generals" in options) found.push(intProblem(options.generals, "Generals", 1, 4));
    if (kind === "attack") {
        found.push(percentProblem(options.autofill_buffer, "Suggestion margin"));
    }
    if ("pure_offense" in options) {
        // A slider at 0 leaves the box empty, which the server reads as 0%: only both at 0 is a problem.
        const share = (value) => parseFloat(value) || 0;
        found.push(percentProblem(share(options.pure_offense), "Attackers to send"), percentProblem(share(options.flex_offense), "Flexers to send"));
        if (share(options.pure_offense) === 0 && share(options.flex_offense) === 0) found.push("Send some attackers or flexers");
    }
    if ("drones_pct" in options) found.push(percentProblem(options.drones_pct, "Drones to send"));
    if ("max_tries" in options) found.push(intProblem(options.max_tries, "Max tries", 1, 10));
    if ("attempts" in options) found.push(intProblem(options.attempts, "Attempts", 1, 10));
    if (kind === "missiles" && !["planet_busters", "star_busters", "galaxy_busters"].some((key) => parseInt(options[key], 10) > 0)) {
        found.push("Choose how many missiles to launch");
    }
    return found.filter(Boolean);
}

function Add(props) {
    const [kind, setKind] = useState(undefined);
    const [options, setOptions] = useState({});
    const [when, setWhen] = useState(inFuture(1));
    const [results, setResults] = useState([]);

    const me = props.data.kingdomid?.kd_id;
    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));

    const choose = (key) => { setKind(key); setOptions(JSON.parse(JSON.stringify(KINDS[key].start))); };
    const set = (name, value) => setOptions((previous) => ({ ...previous, [name]: value }));
    const onText = (event) => set(event.target.name, event.target.value);

    const problems = problemsWith(kind, options, when, me);
    const blocked = problems[0];
    const date = new Date(when);
    const minutes = Math.round((date.getTime() - Date.now()) / 60000);
    const away = isNaN(minutes) ? "" : minutes < 1 ? "now" : minutes < 90 ? `in ${minutes} minutes` : `in ${(minutes / 60).toFixed(1)} hours`;

    const submit = () => {
        // The server wants the same options the old form sent: percentages and counts as the player typed them.
        const body = { type: kind, time: date.toISOString(), options };
        const updateFunc = async () => authFetch('api/schedule', { method: 'POST', body: JSON.stringify(body) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };

    const percentRow = (name, label, hint) => (
        <FieldRow label={label} hint={hint} htmlFor={"sched-" + name}>
            <AmountInput name={name} id={"sched-" + name} label={label} suffix="%" value={options[name]} onChange={onText} max={100} />
        </FieldRow>
    );
    const targetRow = (
        <FieldRow label="Target" htmlFor="sched-target">
            <Picker id="sched-target" options={kingdomOptions} value={options.target} onChange={(value) => set("target", value)} placeholder="Type a kingdom to filter" />
        </FieldRow>
    );
    const unitsModeRow = (
        <FieldRow label="How much to send">
            <div role="radiogroup" aria-label="How much to send">
                {UNITS_MODES.map((mode) => (
                    <Form.Check key={mode.value} type="radio" name="units_mode" id={"sched-units-mode-" + mode.value}
                        checked={options.units_mode === mode.value} onChange={() => set("units_mode", mode.value)}
                        label={<>{mode.label}<div className="planner-hint-line">{mode.hint}</div></>} />
                ))}
            </div>
        </FieldRow>
    );
    const generalsRow = (
        <FieldRow label="Generals" hint="1 to 4" htmlFor="sched-generals">
            <AmountInput name="generals" id="sched-generals" label="Generals" value={options.generals} onChange={onText} max={4} />
        </FieldRow>
    );

    return (
        <div className="schedule-add">
            <ResultToasts title="Schedule Results" results={results} setResults={setResults} />
            <Panel title="1. What to schedule">
                <div className="schedule-kinds" role="radiogroup" aria-label="What to schedule">
                    {Object.entries(KINDS).map(([key, { title, icon: Icon, blurb }]) => (
                        <button type="button" key={key} role="radio" aria-checked={kind === key}
                            className={"schedule-kind" + (kind === key ? " selected" : "")} onClick={() => choose(key)}>
                            <Icon aria-hidden="true" className="schedule-kind-icon" />
                            <strong>{title}</strong>
                            <small>{blurb}</small>
                        </button>
                    ))}
                </div>
            </Panel>

            {kind !== undefined ? <>
                <div className="planner-grid">
                    <Panel title="2. When">
                        <FieldRow label="Date and time" hint={away} htmlFor="sched-time">
                            <Form.Control id="sched-time" type="datetime-local" size="sm" value={when} min={localInput(new Date())}
                                onChange={(e) => setWhen(e.target.value)} isInvalid={Boolean(when) && date.getTime() < Date.now()} />
                        </FieldRow>
                        <div className="planner-actions">
                            {[1, 4, 12, 24].map((hours) => (
                                <Button key={hours} variant="outline-secondary" size="sm" onClick={() => setWhen(inFuture(hours))}>In {hours}h</Button>
                            ))}
                        </div>
                    </Panel>

                    <Panel title="3. Details">
                        {kind === "attack" ? <>
                            {targetRow}
                            <FieldRow label="Suggest the army" hint="Pick units that should win when it happens">
                                <Form.Check type="switch" id="prefer-autofill-input" checked={Boolean(options.prefer_autofill)} onChange={(e) => set("prefer_autofill", e.target.checked)} />
                            </FieldRow>
                            {options.prefer_autofill ? <>
                                {percentRow("autofill_buffer", "Suggestion margin", "Extra offense the suggestion adds")}
                                <FieldRow label="Without military intel, send the share anyway" hint="Off: with no military intel when it runs, nothing is sent" htmlFor="sched-send-without-intel">
                                    <Form.Check type="switch" id="sched-send-without-intel" checked={Boolean(options.send_without_intel)} onChange={(e) => set("send_without_intel", e.target.checked)} />
                                </FieldRow>
                            </> : null}
                            {unitsModeRow}
                            {percentRow("pure_offense", "Attackers to send", options.prefer_autofill ? "The most the suggested army may use" : undefined)}
                            {percentRow("flex_offense", "Flexers to send")}
                            {generalsRow}
                        </> : null}
                        {kind === "attackprimitives" ? <>
                            {unitsModeRow}
                            {percentRow("pure_offense", "Attackers to send")}
                            {percentRow("flex_offense", "Flexers to send")}
                            {generalsRow}
                        </> : null}
                        {kind === "intelspy" || kind === "aggressivespy" ? <>
                            {targetRow}
                            <FieldRow label="Operation" htmlFor="sched-operation">
                                <Picker id="sched-operation" options={kind === "intelspy" ? availableOperations(INTEL_OPERATIONS, props.data.kingdom, props.data.state) : HOSTILE_OPERATIONS}
                                    value={options.operation} onChange={(value) => set("operation", value)} placeholder="Choose an operation" searchable={false} />
                            </FieldRow>
                            {percentRow("drones_pct", "Drones to send", "Share of the drones you have then")}
                            <FieldRow label="Shield the drones">
                                <Form.Check type="switch" id="sched-shielded" checked={Boolean(options.shielded)} onChange={(e) => set("shielded", e.target.checked)} />
                            </FieldRow>
                            {kind === "intelspy" ? <>
                                <FieldRow label="Max tries" hint="Retries if it fails, 1 to 10" htmlFor="sched-max_tries">
                                    <AmountInput name="max_tries" id="sched-max_tries" label="Max tries" value={options.max_tries} onChange={onText} max={10} />
                                </FieldRow>
                                <FieldRow label="Share with your galaxy" hint="Free: every galaxymate gets it at once">
                                    <Form.Check type="switch" id="sched-share" checked={Boolean(options.share_to_galaxy)} onChange={(e) => set("share_to_galaxy", e.target.checked)} />
                                </FieldRow>
                            </> : (
                                <FieldRow label="Attempts" hint="1 to 10" htmlFor="sched-attempts">
                                    <AmountInput name="attempts" id="sched-attempts" label="Attempts" value={options.attempts} onChange={onText} max={10} />
                                </FieldRow>
                            )}
                        </> : null}
                        {kind === "missiles" ? <>
                            {targetRow}
                            {[["planet_busters", "Planet busters"], ["star_busters", "Star busters"], ["galaxy_busters", "Galaxy busters"]].map(([name, label]) => (
                                <FieldRow key={name} label={label} hint={`${(props.data.missiles?.current?.[name] || 0).toLocaleString()} built now`} htmlFor={"sched-" + name}>
                                    <AmountInput name={name} id={"sched-" + name} label={label} value={options[name]} onChange={onText}
                                        max={Math.max(props.data.missiles?.capacity || 0, props.data.missiles?.current?.[name] || 0)} />
                                </FieldRow>
                            ))}
                        </> : null}
                    </Panel>
                </div>

                <Panel title="4. Check and schedule">
                    {!blocked
                        ? <Alert variant="info" className="mb-3">
                            <strong>{KINDS[kind].title}</strong>{options.target ? <> against <strong>{props.data.kingdoms[parseInt(options.target)]}</strong></> : null}
                            {" "}on <strong>{date.toLocaleString()}</strong> ({away}).
                            {" "}It uses whatever you have at that time, so check your army and drones are still what you expect.
                        </Alert>
                        : null}
                    <Button size="lg" onClick={submit} disabled={Boolean(blocked) || props.loading.kingdom} title={blocked}>Schedule it</Button>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>
            </> : null}
        </div>
    );
}

export function Queue(props) {
    const [results, setResults] = useState([]);
    const cancel = (id) => {
        const updateFunc = async () => authFetch('api/schedule/cancel', { method: 'POST', body: JSON.stringify({ id }) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };

    const prettyNames = {
        ...(props.data.state.pretty_names || {}),
        attack: "Attack", attackprimitives: "Attack primitives", spy: "Spy", intelspy: "Gather intel", aggressivespy: "Hostile operation", missiles: "Launch missiles",
        target: "Target", pure_offense: "Attackers", flex_offense: "Flexers", generals: "Generals", operation: "Operation", drones_pct: "Drones",
        shielded: "Shielded", max_tries: "Max tries", share_to_galaxy: "Share with galaxy", repeat: "Repeat", prefer_autofill: "Suggest the army",
        autofill_buffer: "Suggestion margin", attempts: "Attempts",
        units_mode: "How much to send", send_without_intel: "Without military intel, send the share anyway",
    };
    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const show = (key, value) => {
        if (key === "target") return kdLabel(value);
        if (key === "units_mode") return UNITS_MODES.find((mode) => mode.value === value)?.label || value;
        if (["drones_pct", "pure_offense", "flex_offense", "autofill_buffer"].includes(key)) return displayPercent(value);
        if (typeof value === "boolean") return value ? "Yes" : "No";
        return String(prettyNames[value] || value);
    };

    const queue = [...(props.data.kingdom.schedule || [])].sort((a, b) => new Date(a.time) - new Date(b.time));
    return (
        <div className="schedule-queue">
            <ResultToasts title="Schedule Results" results={results} setResults={setResults} />
            {queue.length === 0 ? <p className="planner-hint-line">Nothing is scheduled. Use the Add tab to plan an action.</p> : null}
            {queue.map((item) => (
                <Panel key={item.id} className="schedule-item">
                    <div className="schedule-item-head">
                        <div>
                            <h3 className="panel-title">{prettyNames[item.type] || item.type}</h3>
                            <div className="planner-hint-line">{new Date(item.time).toLocaleString()}</div>
                        </div>
                        <Button variant="outline-danger" size="sm" onClick={() => cancel(item.id)} disabled={props.loading.kingdom}>Cancel</Button>
                    </div>
                    <dl className="schedule-options">
                        {Object.entries(item.options).map(([key, value]) => (
                            <div key={key}><dt>{prettyNames[key] || key}</dt><dd>{show(key, value)}</dd></div>
                        ))}
                    </dl>
                </Panel>
            ))}
        </div>
    );
}

export default Schedule;
