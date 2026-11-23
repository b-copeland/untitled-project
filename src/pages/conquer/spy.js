import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import { useLocation, useSearchParams } from "react-router-dom";
import Alert from 'react-bootstrap/Alert';
import ProgressBar from 'react-bootstrap/ProgressBar';
import "./spy.css";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { flourishResult } from "../../components/flourish";
import { AmountInput, NumberControl } from "../../components/forms";
import { Panel, FieldRow, Stats, Picker, useServerForecast, clockUntil } from "../../components/planner";
import { alreadyRevealed, checkPercent } from "../../validation";
import { TargetIntel } from "./intel.js";
import { useTour, TOUR_NO_SEND } from "../../components/tour";

const initialDefenderValues = { drones: "", stars: "", shields: "" };

// Learning something about them, as opposed to doing something to them.
const OPERATIONS = [
    { value: "spymilitary", label: "Spy on military", group: "Gather intel" },
    { value: "spykingdom", label: "Spy on kingdom", group: "Gather intel" },
    { value: "spyshields", label: "Spy on shields", group: "Gather intel" },
    { value: "spyprojects", label: "Spy on projects", group: "Gather intel" },
    { value: "spystructures", label: "Spy on structures", group: "Gather intel" },
    { value: "spydrones", label: "Spy on drones", group: "Gather intel" },
    // Only for kingdoms that have completed the project (state.operation_projects says which).
    { value: "spyall", label: "Full infiltration (everything)", group: "Gather intel" },
    { value: "siphonfunds", label: "Siphon funds", group: "Hostile" },
    { value: "bombhomes", label: "Bomb homes", group: "Hostile" },
    { value: "sabotagefuelplants", label: "Sabotage fuel plants", group: "Hostile" },
    { value: "kidnappopulation", label: "Kidnap population", group: "Hostile" },
    { value: "suicidedrones", label: "Suicide drones", group: "Hostile" },
];

const whole = (value) => Math.floor(value || 0).toLocaleString();

/**
 * The operations to offer this kingdom: one that needs a project (``state.operation_projects``) only once it is done,
 * and none that a completed project replaces (``state.operations_replaced_by_project``).
 */
export function availableOperations(operations, kingdom, state) {
    const needs = state?.operation_projects || {};
    const done = kingdom?.completed_projects || [];
    const replaced = new Set(Object.entries(state?.operations_replaced_by_project || {})
        .filter(([project]) => done.indexOf(project) >= 0)
        .flatMap(([, replacedOperations]) => replacedOperations));
    return operations.filter((op) => (!needs[op.value] || done.indexOf(needs[op.value]) >= 0) && !replaced.has(op.value));
}

/**
 * Spies are sent straight away, hostile operations too. The player is asked first only when the chance of success is
 * known and below 40%.
 */
export function spyNeedsConfirmation({ hasForecast, guessing, chance, warning }) {
    // A warning from the forecast (a siphon of yours already on this kingdom, #220) always asks first.
    return Boolean(warning) || (hasForecast && !guessing && chance < 0.4);
}

function Spy(props) {
    // A target and operation come as props, or with the link here: /spy?target=12&op=spymilitary (the Kingdom and
    // Galaxy pages, and Attempt on an intel bounty: the operation that would reveal the intel asked for).
    const arrived = useLocation().state || {};
    const tour = useTour();
    const [query] = useSearchParams();
    const initialKd = props.initialKd ?? query.get("target") ?? arrived.kdId;
    const [defenderValues, setDefenderValues] = useState(initialDefenderValues);
    const [selected, setSelected] = useState(initialKd || undefined);
    const [operation, setOperation] = useState(props.initialOperation ?? query.get("op") ?? arrived.operation ?? "");
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [results, setResults] = useState([]);
    const [drones, setDrones] = useState("");
    const [shieldDrones, setShieldDrones] = useState(false);
    const [cut, setCut] = useState("");
    const [share, setShare] = useState(false);
    const [confirming, setConfirming] = useState(false);

    const loadTarget = (kdId) => authFetch("api/kingdom/" + kdId).then(safeJson).then(r => setTargetKdInfo(r));
    useEffect(() => {
        if (initialKd !== undefined) {
            loadTarget(initialKd);
        }
    }, []);  // eslint-disable-line react-hooks/exhaustive-deps -- the target it opened with, once
    const onPickTarget = (kdId) => { setSelected(kdId); setForecast({}); setTargetKdInfo({}); loadTarget(kdId); };

    const kingdom = props.data.kingdom;
    const maxDrones = Math.floor(kingdom.drones || 0);
    const sharesResult = (props.data.state.reveal_operations || []).includes(operation);
    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const options = Object.keys(props.data.kingdoms).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));

    // The forecast comes from the server, a moment after the player stops changing things.
    const [forecast, forecasting, setForecast] = useServerForecast(
        selected !== undefined && operation ? { selected, operation, drones: String(drones || ""), shieldDrones, defenderValues } : null,
        (plan) => authFetch('api/calculatespy/' + plan.selected, {
            method: 'POST',
            body: JSON.stringify({ drones: plan.drones, shielded: plan.shieldDrones, defenderValues: plan.defenderValues, operation: plan.operation }),
        }).then(safeJson),
    );

    const send = () => {
        setConfirming(false);
        const body = { drones, shielded: shieldDrones, operation, share_to_galaxy: share, cut: cut === "" ? 0 : cut };
        const updateFunc = async () => authFetch('api/spy/' + selected, { method: 'POST', body: JSON.stringify(body) })
            .then(safeJson).then(r => {
                setForecast({});
                return flourishResult("spy", r).then(() => setResults((previous) => previous.concat(r)));
            });
        props.updateData(['kingdom', 'spyhistory', 'revealed', 'intel'], [updateFunc]);
    };

    const sendingDrones = parseInt(drones, 10) || 0;
    const hasForecast = forecast.success_chance !== undefined;
    const chance = hasForecast ? forecast.success_chance : 0;
    // Only for the operation the forecast was made for: a stale siphon warning must not follow a switch to another operation.
    const warning = hasForecast && operation === "siphonfunds" ? forecast.warning : undefined;
    // The server treats anything left blank as zero, which would read as "certain". Say so unless it is known or entered.
    const dronesKnown = targetKdInfo.drones !== undefined;
    const starsKnown = targetKdInfo.stars !== undefined;
    const shieldsKnown = targetKdInfo.shields !== undefined;
    const guessing = !(dronesKnown || String(defenderValues.drones).trim() !== "") || !(starsKnown || String(defenderValues.stars).trim() !== "");
    const problems = [];
    if (selected === undefined) problems.push("Choose a target");
    if (!operation) problems.push("Choose an operation");
    if (sendingDrones < 1) problems.push("Send at least 1 drone");
    if (sendingDrones > maxDrones) problems.push(`You only have ${whole(maxDrones)} drones`);
    if ((kingdom.spy_attempts || 0) < 1) problems.push("You have no spy attempts left");
    const revealedProblem = alreadyRevealed(props.data.state.reveal_operation_stats?.[operation],
        (props.data.revealed?.revealed || {})[selected], (props.data.revealed?.revealed_galaxymates || []).includes(selected));
    if (revealedProblem) problems.push(revealedProblem);
    const cutError = sharesResult && share ? checkPercent(cut, { max: (props.data.state.game_config?.BASE_MAX_SHARE_CUT || 0) * 100 }) : null;
    if (cutError) problems.push(cutError);
    if (tour.running) problems.unshift(TOUR_NO_SEND);
    const blocked = problems[0];
    const intel = Object.entries((props.data.revealed?.revealed || {})[selected] || {});
    const operations = availableOperations(OPERATIONS, kingdom, props.data.state);
    const chosen = operations.find((op) => op.value === operation);

    const setDefender = (key) => (e) => setDefenderValues((previous) => ({ ...previous, [key]: e.target.value }));
    const entered = (key) => String(defenderValues[key]).trim() !== "";
    // Where each of their numbers comes from. None of them is needed to send the spies: they only sharpen the forecast.
    const statusOf = (known, key) => (known ? "revealed" : entered(key) ? "estimate" : "optional");

    return (
        <>
            <div className="planner wide spy">
                <ResultToasts title="Spy Results" results={results} setResults={setResults} />

                <div className="wide-layout spy-layout">
                    <Panel className="area-target" title="1. Target and operation" data-tour="spy-target">
                        <FieldRow label="Target" htmlFor="spy-target">
                            <Picker id="spy-target" options={options} value={selected} onChange={onPickTarget}
                                placeholder="Type a kingdom to filter" autoFocus={selected === undefined} />
                        </FieldRow>
                        <FieldRow label="Operation" htmlFor="spy-operation">
                            <Picker id="spy-operation" options={operations} value={operation} onChange={setOperation}
                                placeholder="Choose an operation" searchable={false} />
                        </FieldRow>
                        {intel.length > 0
                            ? <Stats items={intel.map(([what, until]) => ({ label: `${what} revealed for`, value: clockUntil(until) }))} />
                            : null}
                        <TargetIntel target={selected} data={props.data} loading={props.loading} updateData={props.updateData}
                            onAttempt={(kdId, op) => setOperation(op)} />
                    </Panel>

                    {selected !== undefined ? <>
                    <Panel className="area-drones" title="2. Your drones">
                        <FieldRow label="Drones to send" hint={`${kingdom.spy_attempts ?? 0} spy attempts left`} htmlFor="spy-drones">
                            <AmountInput name="drones" id="spy-drones" label="Drones to send" value={drones}
                                onChange={(e) => setDrones(e.target.value)} max={maxDrones} />
                        </FieldRow>
                        <FieldRow label="Shield the drones" hint="Protects them if the operation fails">
                            <Form.Check type="switch" id="shield-drones-switch" checked={shieldDrones} onChange={(e) => setShieldDrones(e.target.checked)} />
                        </FieldRow>
                        {sharesResult ? <>
                            <FieldRow label="Share with your galaxy" hint={parseFloat(cut) > 0 ? "Listed on the Intel market for your cut" : "Free: every galaxymate gets it at once"}>
                                <Form.Check type="switch" id="share-switch" checked={share} onChange={(e) => setShare(e.target.checked)} />
                            </FieldRow>
                            {share ? <FieldRow label="Your cut" hint={`Of their spoils from each win, at most ${(props.data.state.game_config?.BASE_MAX_SHARE_CUT || 0) * 100}%; blank is free`} htmlFor="spy-cut">
                                <div className="attack-buffer">
                                    <NumberControl id="spy-cut" name="cut" size="sm" inputMode="decimal" placeholder="0" autoComplete="off"
                                        value={cut} onChange={(e) => setCut(e.target.value)} isInvalid={Boolean(cutError)} />
                                    <span>%</span>
                                </div>
                                {cutError ? <div className="amount-input-error">{cutError}</div> : null}
                            </FieldRow> : null}
                        </> : null}
                    </Panel>

                <Panel className="area-know" title="3. What you know about them">
                    <FieldRow label="Drones" status={statusOf(dronesKnown, "drones")} htmlFor="spy-def-drones">
                        {dronesKnown ? <span className="known-value">{whole(targetKdInfo.drones)}</span>
                            : <NumberControl id="spy-def-drones" size="sm" inputMode="numeric" placeholder="unknown" autoComplete="off" value={defenderValues.drones} onChange={setDefender("drones")} />}
                    </FieldRow>
                    <FieldRow label="Stars" status={statusOf(starsKnown, "stars")} htmlFor="spy-def-stars">
                        {starsKnown ? <span className="known-value">{whole(targetKdInfo.stars)}</span>
                            : <NumberControl id="spy-def-stars" size="sm" inputMode="numeric" placeholder="unknown" autoComplete="off" value={defenderValues.stars} onChange={setDefender("stars")} />}
                    </FieldRow>
                    <FieldRow label="Spy shields" status={statusOf(shieldsKnown, "shields")} htmlFor="spy-def-shields">
                        {shieldsKnown ? <span className="known-value">{Math.round(targetKdInfo.shields.spy * 100)}%</span>
                            : <div className="attack-buffer"><NumberControl id="spy-def-shields" size="sm" inputMode="decimal" placeholder="unknown" autoComplete="off" value={defenderValues.shields} onChange={setDefender("shields")} /><span>%</span></div>}
                    </FieldRow>
                </Panel>

                <Panel className="area-forecast" title="4. Forecast and send" data-tour="spy-forecast">
                    {forecast.message && !hasForecast ? <Alert variant="warning">{forecast.message}</Alert> : null}
                    {hasForecast ? <>
                        {guessing
                            ? <Alert variant="secondary">
                                You have not entered their drones and stars and they are not revealed, so the chance below is not meaningful yet. Fill in what you know, or send anyway.
                            </Alert>
                            : <>
                                <div className={"planner-verdict " + (chance >= 0.75 ? "good" : "bad")}>
                                    About a {Math.round(chance * 100)}% chance of success
                                    {forecasting ? " (updating...)" : ""}
                                </div>
                                <ProgressBar now={chance * 100} variant={chance >= 0.75 ? "success" : chance < 0.4 ? "danger" : "warning"} />
                            </>}
                        <Stats items={[
                            { label: "Drones lost if it works", value: whole(forecast.drone_losses?.success) },
                            { label: "Drones lost if it fails", value: whole(forecast.drone_losses?.failure) },
                        ]} />
                        <div className="planner-notes">{forecast.message}</div>
                        {warning ? <Alert variant="warning">{warning}</Alert> : null}
                    </> : null}
                    <div className="planner-send">
                        <Button size="lg" disabled={Boolean(blocked) || props.loading.kingdom} title={blocked} onClick={() => (spyNeedsConfirmation({ hasForecast, guessing, chance, warning }) ? setConfirming(true) : send())}>
                            Send spies
                        </Button>
                        {blocked ? <div className="planner-why">{blocked}</div> : null}
                    </div>
                </Panel>
                    </> : null}

                </div>

                <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                    <Modal.Header closeButton><Modal.Title>Run this operation?</Modal.Title></Modal.Header>
                    <Modal.Body>
                        <p>{chosen?.label} on <strong>{selected !== undefined ? kdLabel(selected) : ""}</strong> with {whole(sendingDrones)} drones{shieldDrones ? " (shielded)" : ""}. It uses one spy attempt.</p>
                        {warning ? <Alert variant="warning">{warning}</Alert> : null}
                        {hasForecast && !guessing && chance < 1 ? <Alert variant={chance < 0.4 ? "danger" : "warning"}>About a {Math.round(chance * 100)}% chance of success with this many drones.</Alert> : null}
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
                        <Button onClick={send}>Send spies</Button>
                    </Modal.Footer>
                </Modal>
                <HelpButton scrollTarget={"spy"}/>
            </div>
        </>
    );
}

export default Spy;
