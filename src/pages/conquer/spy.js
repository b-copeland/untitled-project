import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import Alert from 'react-bootstrap/Alert';
import "./spy.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput } from "../../components/forms";
import { Panel, FieldRow, Stats, VersusBar, Picker, useDebounced, clockUntil } from "../../components/planner";

const initialDefenderValues = { drones: "", stars: "", shields: "" };

// Learning something about them, as opposed to doing something to them.
const OPERATIONS = [
    { value: "spymilitary", label: "Spy on military", group: "Gather intel" },
    { value: "spykingdom", label: "Spy on kingdom", group: "Gather intel" },
    { value: "spyshields", label: "Spy on shields", group: "Gather intel" },
    { value: "spyprojects", label: "Spy on projects", group: "Gather intel" },
    { value: "spystructures", label: "Spy on structures", group: "Gather intel" },
    { value: "spydrones", label: "Spy on drones", group: "Gather intel" },
    { value: "siphonfunds", label: "Siphon funds", group: "Hostile" },
    { value: "bombhomes", label: "Bomb homes", group: "Hostile" },
    { value: "sabotagefuelplants", label: "Sabotage fuel plants", group: "Hostile" },
    { value: "kidnappopulation", label: "Kidnap population", group: "Hostile" },
    { value: "suicidedrones", label: "Suicide drones", group: "Hostile" },
];

const whole = (value) => Math.floor(value || 0).toLocaleString();

function Spy(props) {
    const [defenderValues, setDefenderValues] = useState(initialDefenderValues);
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [operation, setOperation] = useState("");
    const [forecast, setForecast] = useState({});
    const [forecasting, setForecasting] = useState(false);
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [results, setResults] = useState([]);
    const [drones, setDrones] = useState("");
    const [shieldDrones, setShieldDrones] = useState(false);
    const [cut, setCut] = useState("");
    const [share, setShare] = useState(false);
    const [confirming, setConfirming] = useState(false);

    const loadTarget = (kdId) => authFetch("api/kingdom/" + kdId).then(safeJson).then(r => setTargetKdInfo(r));
    useEffect(() => {
        if (props.initialKd !== undefined) {
            loadTarget(props.initialKd);
        }
    }, []);
    const onPickTarget = (kdId) => { setSelected(kdId); setForecast({}); setTargetKdInfo({}); loadTarget(kdId); };

    const kingdom = props.data.kingdom;
    const maxDrones = Math.floor(kingdom.drones || 0);
    const sharesResult = (props.data.state.reveal_operations || []).includes(operation);
    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const options = Object.keys(props.data.kingdoms).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));

    // The forecast follows what is typed.
    const request = useDebounced(JSON.stringify({ selected, operation, drones, shieldDrones, defenderValues }), 700);
    useEffect(() => {
        const asked = JSON.parse(request);
        if (asked.selected === undefined || !asked.operation) {
            setForecast({});
            return;
        }
        let current = true;
        setForecasting(true);
        authFetch('api/calculatespy/' + asked.selected, {
            method: 'POST',
            body: JSON.stringify({ drones: asked.drones, shielded: asked.shieldDrones, defenderValues: asked.defenderValues, operation: asked.operation }),
        }).then(safeJson).then(r => { if (current) setForecast(r); }).finally(() => { if (current) setForecasting(false); });
        return () => { current = false; };
    }, [request]);

    const send = () => {
        setConfirming(false);
        const body = { drones, shielded: shieldDrones, operation, share_to_galaxy: share, cut: cut === "" ? 0 : cut };
        const updateFunc = async () => authFetch('api/spy/' + selected, { method: 'POST', body: JSON.stringify(body) })
            .then(safeJson).then(r => { setResults((previous) => previous.concat(r)); setForecast({}); });
        props.updateData(['kingdom', 'spyhistory', 'revealed', 'shared'], [updateFunc]);
    };

    const sendingDrones = parseInt(drones, 10) || 0;
    const hasForecast = forecast.total_defense !== undefined;
    // Drones count against the "max success threshold": above it the operation is certain to work.
    const ratio = hasForecast && forecast.total_defense > 0 ? sendingDrones / forecast.total_defense : 0;
    // The server's own rule: drones against the threshold (never below a minimum), less the target's spy shields.
    const minChance = props.data.state.game_config?.BASE_SPY_MIN_SUCCESS_CHANCE ?? 0;
    const theirShields = targetKdInfo.shields ? targetKdInfo.shields.spy : (parseFloat(defenderValues.shields) || 0) / 100;
    const chance = hasForecast ? Math.min(Math.max(ratio, minChance), 1) * (1 - theirShields) : 0;
    const problems = [];
    if (selected === undefined) problems.push("Choose a target");
    if (!operation) problems.push("Choose an operation");
    if (sendingDrones < 1) problems.push("Send at least 1 drone");
    if (sendingDrones > maxDrones) problems.push(`You only have ${whole(maxDrones)} drones`);
    if ((kingdom.spy_attempts || 0) < 1) problems.push("You have no spy attempts left");
    const blocked = problems[0];
    const intel = Object.entries((props.data.revealed?.revealed || {})[selected] || {});
    const chosen = OPERATIONS.find((op) => op.value === operation);

    const knownField = (key, shown) => targetKdInfo.hasOwnProperty(key)
        ? <strong>{shown}</strong>
        : <Form.Control id={"spy-def-" + key} name={key} size="sm" inputMode="decimal" placeholder="0" autoComplete="off"
            value={defenderValues[key]} onChange={(e) => setDefenderValues((previous) => ({ ...previous, [key]: e.target.value }))} />;

    return (
        <>
            <Header data={props.data} />
            <div className="planner spy">
                <ResultToasts title="Spy Results" results={results} setResults={setResults} />
                <h2>Spy</h2>

                <div className="planner-grid">
                    <Panel title="1. Target and operation">
                        <FieldRow label="Target" htmlFor="spy-target">
                            <Picker id="spy-target" options={options} value={selected} onChange={onPickTarget}
                                placeholder="Type a kingdom to filter" autoFocus={selected === undefined} />
                        </FieldRow>
                        <FieldRow label="Operation" htmlFor="spy-operation">
                            <Picker id="spy-operation" options={OPERATIONS} value={operation} onChange={setOperation}
                                placeholder="Choose an operation" searchable={false} />
                        </FieldRow>
                        {chosen ? <p className="planner-hint-line">{chosen.group === "Hostile" ? "A hostile operation: the target is told it was you if it is caught." : "Gathers information. It does not harm the target."}</p> : null}
                        {intel.length > 0
                            ? <Stats items={intel.map(([what, until]) => ({ label: `${what} revealed for`, value: clockUntil(until) }))} />
                            : null}
                    </Panel>

                    <Panel title="2. Your drones" hint={`You have ${whole(maxDrones)} drones and ${kingdom.spy_attempts ?? 0} spy attempt${kingdom.spy_attempts === 1 ? "" : "s"}.`}>
                        <FieldRow label="Drones to send" htmlFor="spy-drones">
                            <AmountInput name="drones" id="spy-drones" label="Drones to send" value={drones}
                                onChange={(e) => setDrones(e.target.value)} max={maxDrones} />
                        </FieldRow>
                        <FieldRow label="Shield the drones" hint="Protects them if the operation fails">
                            <Form.Check type="switch" id="shield-drones-switch" checked={shieldDrones} onChange={(e) => setShieldDrones(e.target.checked)} />
                        </FieldRow>
                        {sharesResult ? <>
                            <FieldRow label="Share with your galaxy" hint="Galaxymates see what you learn">
                                <Form.Check type="switch" id="share-switch" checked={share} onChange={(e) => setShare(e.target.checked)} />
                            </FieldRow>
                            <FieldRow label="Your cut" hint="Share of any gains you keep" htmlFor="spy-cut">
                                <div className="attack-buffer">
                                    <Form.Control id="spy-cut" name="cut" size="sm" inputMode="decimal" placeholder="0" autoComplete="off"
                                        value={cut} onChange={(e) => setCut(e.target.value)} />
                                    <span>%</span>
                                </div>
                            </FieldRow>
                        </> : null}
                    </Panel>
                </div>

                <Panel title="3. What you know about them"
                    hint={targetKdInfo.drones !== undefined ? "Revealed to you, so these are exact." : "Not revealed to you: enter what you think they have, to improve the forecast."}>
                    <FieldRow label="Drones" htmlFor="spy-def-drones">{knownField("drones", whole(targetKdInfo.drones))}</FieldRow>
                    <FieldRow label="Stars" htmlFor="spy-def-stars">{knownField("stars", whole(targetKdInfo.stars))}</FieldRow>
                    <FieldRow label="Spy shields (%)" htmlFor="spy-def-shields">{knownField("shields", targetKdInfo.shields ? Math.round(targetKdInfo.shields.spy * 100) + "%" : "")}</FieldRow>
                </Panel>

                <Panel title="4. Forecast" hint={hasForecast ? undefined : "Choose a target and an operation to see your chances."}>
                    {forecast.message && !hasForecast ? <Alert variant="warning">{forecast.message}</Alert> : null}
                    {hasForecast ? <>
                        <div className={"planner-verdict " + (chance >= 0.75 ? "good" : "bad")}>
                            About a {Math.round(chance * 100)}% chance of success
                            {forecasting ? " (updating...)" : ""}
                        </div>
                        <VersusBar ratio={ratio} yours="Your drones" theirs="the full-success threshold" />
                        <Stats items={[
                            { label: "Success chance", value: Math.round(chance * 100) + "%", tone: chance >= 0.75 ? "good" : chance < 0.4 ? "bad" : undefined },
                            { label: "Stars-based defense", value: whole(forecast.stars_defense) },
                            { label: "Drone-based defense", value: whole(forecast.drones_defense) },
                            { label: "Success threshold", value: whole(forecast.total_defense) },
                        ]} />
                        <div className="planner-notes">{forecast.message}</div>
                    </> : null}
                </Panel>

                <Panel title="5. Send">
                    <Button size="lg" disabled={Boolean(blocked) || props.loading.kingdom} title={blocked} onClick={() => setConfirming(true)}>
                        Send spies
                    </Button>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>

                <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                    <Modal.Header closeButton><Modal.Title>Run this operation?</Modal.Title></Modal.Header>
                    <Modal.Body>
                        <p>{chosen?.label} on <strong>{selected !== undefined ? kdLabel(selected) : ""}</strong> with {whole(sendingDrones)} drones{shieldDrones ? " (shielded)" : ""}. It uses one spy attempt.</p>
                        {hasForecast && chance < 1 ? <Alert variant={chance < 0.4 ? "danger" : "warning"}>About a {Math.round(chance * 100)}% chance of success with this many drones.</Alert> : null}
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
