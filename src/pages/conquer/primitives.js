import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Modal from 'react-bootstrap/Modal';
import Alert from 'react-bootstrap/Alert';
import "./primitives.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput } from "../../components/forms";
import { Panel, FieldRow, Stats, useDebounced } from "../../components/planner";
import { displayPercent } from "../../format";

const whole = (value) => Math.floor(value || 0).toLocaleString();
const percentOf = (fraction) => (fraction === undefined || fraction === null ? "" : Math.round(fraction * 1000) / 10);

function Primitives(props) {
    return (
        <>
            <Header data={props.data} />
            <div className="planner primitives">
                <h2>Primitives</h2>
                <Tabs id="primitives-tabs" defaultActiveKey="attack" justify fill variant="tabs">
                    <Tab eventKey="attack" title="Attack">
                        <AttackPrimitives loading={props.loading} updateData={props.updateData} data={props.data} />
                    </Tab>
                    <Tab eventKey="rob" title="Rob">
                        <RobPrimitives loading={props.loading} updateData={props.updateData} data={props.data} />
                    </Tab>
                </Tabs>
                <HelpButton scrollTarget={"primitives"}/>
            </div>
        </>
    );
}

const ATTACK_UNITS = [["attack", "Attackers"], ["flex", "Flexers"], ["big_flex", "Big flexers"]];
const initialAttackerValues = { recruits: "", attack: "", flex: "", big_flex: "", military_bonus: "", generals: "" };

/** An on/off switch with the settings under it, for the automatic version of an action. */
function AutoPanel({ title, hint, enabled, onToggle, disabled, children, onSave, saveLabel = "Save settings" }) {
    return (
        <Panel title={title} hint={hint}>
            <Form.Check type="switch" id={"auto-" + title.replace(/\s+/g, "-").toLowerCase()} label={enabled ? "On" : "Off"}
                checked={enabled} onChange={onToggle} disabled={disabled} />
            {children}
            <div className="planner-actions">
                <Button variant="outline-primary" onClick={onSave} disabled={disabled}>{saveLabel}</Button>
            </div>
        </Panel>
    );
}

function AttackPrimitives(props) {
    const [attackerValues, setAttackerValues] = useState(initialAttackerValues);
    const [forecast, setForecast] = useState({});
    const [forecasting, setForecasting] = useState(false);
    const [results, setResults] = useState([]);
    const [confirming, setConfirming] = useState(false);
    const [autoPure, setAutoPure] = useState("");
    const [autoFlex, setAutoFlex] = useState("");

    const kingdom = props.data.kingdom;
    const unitsDesc = props.data.mobis?.units_desc || {};
    const myUnits = kingdom.units || {};
    const settings = kingdom.auto_attack_settings || {};

    useEffect(() => {
        const bonus = props.data.projects.current_bonuses?.military_bonus;
        if (bonus && attackerValues.military_bonus === "") {
            setAttackerValues((previous) => ({ ...previous, military_bonus: bonus }));
        }
    }, [props.data.projects.current_bonuses?.military_bonus]);

    const onChange = (event) => setAttackerValues((previous) => ({ ...previous, [event.target.name]: event.target.value }));
    const sending = ATTACK_UNITS.reduce((sum, [key]) => sum + (parseInt(attackerValues[key], 10) || 0), 0);
    const generals = parseInt(attackerValues.generals, 10) || 0;

    const request = useDebounced(JSON.stringify(attackerValues), 700);
    useEffect(() => {
        const values = JSON.parse(request);
        if (ATTACK_UNITS.every(([key]) => !(parseInt(values[key], 10) > 0))) {
            setForecast({});
            return;
        }
        let current = true;
        setForecasting(true);
        authFetch('api/calculateprimitives', { method: 'POST', body: JSON.stringify({ attackerValues: values }) })
            .then(safeJson).then(r => { if (current) setForecast(r); }).finally(() => { if (current) setForecasting(false); });
        return () => { current = false; };
    }, [request]);

    const send = () => {
        setConfirming(false);
        const updateFunc = async () => authFetch('api/attackprimitives', { method: 'POST', body: JSON.stringify({ attackerValues }) })
            .then(safeJson).then(r => { setResults((previous) => previous.concat(r)); setForecast({}); });
        props.updateData(['kingdom', 'projects', 'attackhistory', 'mobis', 'settle', 'structures', 'projects'], [updateFunc]);
    };
    const toggleAuto = (event) => {
        const updateFunc = () => authFetch('api/attackprimitives/auto', { method: 'post', body: JSON.stringify({ enabled: event.target.checked }) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };
    const saveAuto = () => {
        const updateFunc = () => authFetch('api/attackprimitives/auto', { method: 'post', body: JSON.stringify({ pure: autoPure, flex: autoFlex }) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };

    const problems = [];
    if (sending === 0) problems.push("Choose units to send");
    if (generals < 1) problems.push("Send at least 1 general");
    ATTACK_UNITS.forEach(([key, name]) => {
        if ((parseInt(attackerValues[key], 10) || 0) > (myUnits[key] || 0)) problems.push(`You only have ${whole(myUnits[key])} ${name.toLowerCase()}`);
    });
    if (generals > (kingdom.generals_available || 0)) problems.push(`You only have ${kingdom.generals_available} generals`);
    const blocked = problems[0];
    const hasForecast = forecast.attacker_offense !== undefined;

    return (
        <div className="primitives-tab">
            <ResultToasts title="Attack Results" results={results} setResults={setResults} />
            <p className="planner-hint-line">
                Your military exploits primitive galaxies to conquer distant stars. The primitives hold
                {" "}{(props.data.state.primitives_defense_per_star || 100).toFixed(2)} defense per star.
            </p>
            <div className="planner-grid">
                <Panel title="Your attack" hint="Choose what to send. The forecast updates as you go; nothing is sent until you press Send.">
                    {ATTACK_UNITS.map(([key, name]) => (
                        (key !== "big_flex" || myUnits.big_flex > 0 || attackerValues.big_flex)
                            ? <FieldRow key={key} label={name} hint={`${whole(myUnits[key])} available, ${unitsDesc[key]?.offense || "--"} offense each`} htmlFor={"prim-" + key}>
                                <AmountInput name={key} id={"prim-" + key} label={name} value={attackerValues[key]} onChange={onChange} max={myUnits[key] || 0} />
                            </FieldRow>
                            : null
                    ))}
                    <FieldRow label="Generals" hint={`${kingdom.generals_available ?? 0} available`} htmlFor="prim-generals">
                        <AmountInput name="generals" id="prim-generals" label="Generals" value={attackerValues.generals} onChange={onChange} max={kingdom.generals_available || 0} />
                    </FieldRow>
                </Panel>
                <Panel title="Forecast" hint={hasForecast ? undefined : "Choose some units to see how it would go."}>
                    {forecast.message && !hasForecast ? <Alert variant="warning">{forecast.message}</Alert> : null}
                    {hasForecast ? <>
                        <Stats items={[{ label: "Your offense", value: whole(forecast.attacker_offense) }, { label: "Unit loss rate", value: displayPercent(forecast.attacker_unit_losses_rate) }]} />
                        <div className="planner-notes">{forecast.message}{forecasting ? " (updating...)" : ""}</div>
                        <table className="planner-table table table-sm">
                            <thead><tr><th>Units lost</th><th>You</th></tr></thead>
                            <tbody>
                                {ATTACK_UNITS.map(([key, name]) => forecast.attacker_losses?.[key]
                                    ? <tr key={key}><td>{name}</td><td>{whole(forecast.attacker_losses[key])}</td></tr>
                                    : null)}
                            </tbody>
                        </table>
                    </> : null}
                    <div className="planner-actions">
                        <Button size="lg" disabled={Boolean(blocked) || props.loading.kingdom} title={blocked} onClick={() => setConfirming(true)}>Send attack</Button>
                    </div>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>
            </div>

            <AutoPanel title="Automatic attacks" hint="Send part of your army at the primitives on its own, whenever it is ready."
                enabled={kingdom.auto_attack_enabled || false} onToggle={toggleAuto} disabled={props.loading.kingdom} onSave={saveAuto}>
                <FieldRow label="Attackers to send" hint={`Now ${percentOf(settings.pure)}%`} htmlFor="pure-percent">
                    <div className="attack-buffer"><Form.Control id="pure-percent" size="sm" inputMode="decimal" autoComplete="off" value={autoPure}
                        placeholder={String(percentOf(settings.pure) || 0)} onChange={(e) => setAutoPure(e.target.value)} /><span>%</span></div>
                </FieldRow>
                <FieldRow label="Flexers to send" hint={`Now ${percentOf(settings.flex)}%`} htmlFor="flex-percent">
                    <div className="attack-buffer"><Form.Control id="flex-percent" size="sm" inputMode="decimal" autoComplete="off" value={autoFlex}
                        placeholder={String(percentOf(settings.flex) || 0)} onChange={(e) => setAutoFlex(e.target.value)} /><span>%</span></div>
                </FieldRow>
            </AutoPanel>

            <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                <Modal.Header closeButton><Modal.Title>Send this attack?</Modal.Title></Modal.Header>
                <Modal.Body>
                    <p>Send {whole(sending)} units and {generals} general{generals === 1 ? "" : "s"} at the primitives.</p>
                    {hasForecast ? <Alert variant="info">Your forecast offense is {whole(forecast.attacker_offense)}.</Alert> : null}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
                    <Button onClick={send}>Send attack</Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}

function RobPrimitives(props) {
    const [results, setResults] = useState([]);
    const [drones, setDrones] = useState("");
    const [shieldDrones, setShieldDrones] = useState(false);
    const [autoDrones, setAutoDrones] = useState("");
    const [autoKeep, setAutoKeep] = useState("");
    const [autoShield, setAutoShield] = useState(props.data.kingdom.auto_rob_settings?.shielded || false);
    const [confirming, setConfirming] = useState(false);

    const kingdom = props.data.kingdom;
    const settings = kingdom.auto_rob_settings || {};
    const maxDrones = Math.floor(kingdom.drones || 0);
    const sending = parseInt(drones, 10) || 0;
    const perDrone = props.data.state.primitives_rob_per_drone || 4;

    const post = (path, body, refresh = ['kingdom']) => {
        const updateFunc = () => authFetch(path, { method: 'post', body: JSON.stringify(body) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(refresh, [updateFunc]);
    };
    const send = () => { setConfirming(false); post('api/robprimitives', { drones, shielded: shieldDrones }, ['kingdom', 'spyhistory']); setDrones(""); };

    const problems = [];
    if (sending < 1) problems.push("Send at least 1 drone");
    if (sending > maxDrones) problems.push(`You only have ${whole(maxDrones)} drones`);
    if ((kingdom.spy_attempts || 0) < 1) problems.push("You have no spy attempts left");
    const blocked = problems[0];

    return (
        <div className="primitives-tab">
            <ResultToasts title="Rob Results" results={results} setResults={setResults} />
            <p className="planner-hint-line">Your drones exploit primitive galaxies to steal resources: about {perDrone.toFixed(2)} money per drone.</p>
            <div className="planner-grid">
                <Panel title="Your drones" hint={`You have ${whole(maxDrones)} drones and ${kingdom.spy_attempts ?? 0} spy attempts.`}>
                    <FieldRow label="Drones to send" htmlFor="rob-drones">
                        <AmountInput name="drones" id="rob-drones" label="Drones to send" value={drones} onChange={(e) => setDrones(e.target.value)} max={maxDrones} />
                    </FieldRow>
                    <FieldRow label="Shield the drones" hint="Protects them if the rob fails">
                        <Form.Check type="switch" id="shield-drones-switch" checked={shieldDrones} onChange={(e) => setShieldDrones(e.target.checked)} />
                    </FieldRow>
                </Panel>
                <Panel title="Forecast">
                    <Stats items={[{ label: "Expected haul", value: whole(sending * perDrone) + " money" }]} />
                    <div className="planner-actions">
                        <Button size="lg" disabled={Boolean(blocked) || props.loading.kingdom} title={blocked} onClick={() => setConfirming(true)}>Send drones</Button>
                    </div>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>
            </div>

            <AutoPanel title="Automatic robs" hint="Send drones on its own whenever you have spy attempts to spare."
                enabled={kingdom.auto_rob_enabled || false} onToggle={(e) => post('api/robprimitives/auto', { enabled: e.target.checked })}
                disabled={props.loading.kingdom}
                onSave={() => post('api/robprimitives/auto', { drones: autoDrones, keep: autoKeep, shielded: autoShield })}>
                <FieldRow label="Drones to send" hint={`Now ${percentOf(settings.drones)}%`} htmlFor="drones-percent">
                    <div className="attack-buffer"><Form.Control id="drones-percent" size="sm" inputMode="decimal" autoComplete="off" value={autoDrones}
                        placeholder={String(percentOf(settings.drones) || 0)} onChange={(e) => setAutoDrones(e.target.value)} /><span>%</span></div>
                </FieldRow>
                <FieldRow label="Spy attempts to keep" hint={`Now ${settings.keep ?? 0}`} htmlFor="keep-attempts">
                    <Form.Control id="keep-attempts" size="sm" inputMode="numeric" autoComplete="off" value={autoKeep}
                        placeholder={String(settings.keep || 0)} onChange={(e) => setAutoKeep(e.target.value)} />
                </FieldRow>
                <FieldRow label="Shield automatic robs">
                    <Form.Check type="switch" id="enable-auto-rob-shields-switch" checked={autoShield} onChange={(e) => setAutoShield(e.target.checked)} />
                </FieldRow>
            </AutoPanel>

            <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                <Modal.Header closeButton><Modal.Title>Send these drones?</Modal.Title></Modal.Header>
                <Modal.Body>Rob the primitives with {whole(sending)} drones{shieldDrones ? " (shielded)" : ""}. It uses one spy attempt.</Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
                    <Button onClick={send}>Send drones</Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}

export default Primitives;
