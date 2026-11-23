import { attackUnits } from "./attack";
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
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput, NumberControl, useSliders } from "../../components/forms";
import { Panel, FieldRow, UnitStat, Stats, useServerForecast } from "../../components/planner";
import { displayPercent } from "../../format";

const whole = (value) => Math.floor(value || 0).toLocaleString();
const percentOf = (fraction) => (fraction === undefined || fraction === null ? "" : Math.round(fraction * 1000) / 10);

function Primitives(props) {
    return (
        <>
            <div className="planner primitives">
                <Tabs id="primitives-tabs" data-tour="primitives-tabs" defaultActiveKey="attack" variant="tabs">
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

const initialAttackerValues = { military_bonus: "", generals: "" };

/** An on/off switch with the settings under it, for the automatic version of an action. */
function AutoPanel({ title, hint, enabled, onToggle, disabled, saveDisabled, children, onSave, saveLabel = "Save settings" }) {
    return (
        <Panel title={title} hint={hint}>
            <Form.Check type="switch" id={"auto-" + title.replace(/\s+/g, "-").toLowerCase()} label={enabled ? "On" : "Off"}
                checked={enabled} onChange={onToggle} disabled={disabled} />
            {children}
            <div className="planner-actions">
                <Button variant="outline-primary" onClick={onSave} disabled={disabled || saveDisabled}>{saveLabel}</Button>
            </div>
        </Panel>
    );
}

function AttackPrimitives(props) {
    const [attackerValues, setAttackerValues] = useState(initialAttackerValues);
    const [results, setResults] = useState([]);
    const [confirming, setConfirming] = useState(false);

    const kingdom = props.data.kingdom;
    const unitsDesc = props.data.mobis?.units_desc || {};
    const myUnits = kingdom.units || {};
    const ATTACK_UNITS = attackUnits(unitsDesc, props.data.state?.pretty_names, props.data.state?.order?.units);

    useEffect(() => {
        const bonus = props.data.projects.current_bonuses?.military_bonus;
        if (bonus && attackerValues.military_bonus === "") {
            setAttackerValues((previous) => ({ ...previous, military_bonus: bonus }));
        }
    }, [props.data.projects.current_bonuses?.military_bonus]);

    const onChange = (event) => setAttackerValues((previous) => ({ ...previous, [event.target.name]: event.target.value }));
    const sending = ATTACK_UNITS.reduce((sum, [key]) => sum + (parseInt(attackerValues[key], 10) || 0), 0);
    const generals = parseInt(attackerValues.generals, 10) || 0;

    // The forecast comes from the server, a moment after the player stops changing things.
    const [forecast, forecasting, setForecast] = useServerForecast(
        sending > 0 ? attackerValues : null,
        (values) => authFetch('api/calculateprimitives', { method: 'POST', body: JSON.stringify({ attackerValues: values }) }).then(safeJson),
    );

    const send = () => {
        setConfirming(false);
        const updateFunc = async () => authFetch('api/attackprimitives', { method: 'POST', body: JSON.stringify({ attackerValues }) })
            .then(safeJson).then(r => { setResults((previous) => previous.concat(r)); setForecast({}); });
        props.updateData(['kingdom', 'projects', 'attackhistory', 'mobis', 'settle', 'structures', 'projects'], [updateFunc]);
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
                        (!unitsDesc[key]?.project || myUnits[key] > 0 || attackerValues[key])
                            ? <FieldRow key={key} label={name} stat={<UnitStat kind="offense" value={unitsDesc[key]?.offense} />} htmlFor={"prim-" + key}>
                                <AmountInput name={key} id={"prim-" + key} label={name} value={attackerValues[key] || ""} onChange={onChange} max={myUnits[key] || 0} />
                            </FieldRow>
                            : null
                    ))}
                    <FieldRow label="Generals" htmlFor="prim-generals">
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


            <AutoAttack data={props.data} loading={props.loading} updateData={props.updateData} />

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

export function RobPrimitives(props) {
    const [results, setResults] = useState([]);
    const [drones, setDrones] = useState("");
    const [shieldDrones, setShieldDrones] = useState(false);
    const [confirming, setConfirming] = useState(false);

    const kingdom = props.data.kingdom;
    const maxDrones = Math.floor(kingdom.drones || 0);
    const sending = parseInt(drones, 10) || 0;
    // The kingdom's own figure, after its policies; the universe's until that has loaded.
    const perDrone = props.data.modifiers?.primitives_rob_per_drone || props.data.state.primitives_rob_per_drone || 4;

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
                    <Stats items={[{ label: "Money per drone", value: perDrone.toFixed(2) }]} />
                    <div className="planner-actions">
                        <Button size="lg" disabled={Boolean(blocked) || props.loading.kingdom} title={blocked} onClick={() => setConfirming(true)}>Send drones</Button>
                    </div>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>
            </div>


            <AutoRob data={props.data} loading={props.loading} updateData={props.updateData} />

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

/** The automatic attack on primitives: on or off, and the share of attackers and flexers it sends. */
export function AutoAttack(props) {
    const kingdom = props.data.kingdom || {};
    const settings = kingdom.auto_attack_settings || {};
    const sliders = useSliders({ pure: (settings.pure || 0) * 100, flex: (settings.flex || 0) * 100 });
    const [results, setResults] = useState([]);
    const post = (body) => {
        const updateFunc = () => authFetch('api/attackprimitives/auto', { method: 'post', body: JSON.stringify(body) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };
    return (
        <>
            <ResultToasts title="Automatic attacks" results={results} setResults={setResults} />
            <AutoPanel title="Automatic attacks" hint="Send part of your army at the primitives on its own, whenever it is ready."
                enabled={kingdom.auto_attack_enabled || false} onToggle={(e) => post({ enabled: e.target.checked })}
                disabled={!!props.loading.kingdom} saveDisabled={!sliders.changed}
                onSave={() => { post(sliders.body(["pure", "flex"])); sliders.reset(); }}>
                <FieldRow label="Attackers to send" hint={`Now ${percentOf(settings.pure) || 0}%`} htmlFor="pure-percent">
                    <AmountInput name="pure" id="pure-percent" label="Attackers to send" suffix="%" max={100}
                        value={String(sliders.value("pure"))} onChange={sliders.onChange} />
                </FieldRow>
                <FieldRow label="Flexers to send" hint={`Now ${percentOf(settings.flex) || 0}%`} htmlFor="flex-percent">
                    <AmountInput name="flex" id="flex-percent" label="Flexers to send" suffix="%" max={100}
                        value={String(sliders.value("flex"))} onChange={sliders.onChange} />
                </FieldRow>
            </AutoPanel>
        </>
    );
}

/** The automatic rob of primitives: on or off, the share of drones it sends, the spy attempts it keeps back. */
export function AutoRob(props) {
    const kingdom = props.data.kingdom || {};
    const settings = kingdom.auto_rob_settings || {};
    const sliders = useSliders({ drones: (settings.drones || 0) * 100 });
    const [autoKeep, setAutoKeep] = useState("");
    const [autoShield, setAutoShield] = useState(settings.shielded || false);
    const [results, setResults] = useState([]);
    const post = (body) => {
        const updateFunc = () => authFetch('api/robprimitives/auto', { method: 'post', body: JSON.stringify(body) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };
    const changed = sliders.changed || autoKeep !== "" || autoShield !== (settings.shielded || false);
    return (
        <>
            <ResultToasts title="Automatic robs" results={results} setResults={setResults} />
            <AutoPanel title="Automatic robs" hint="Send drones on its own whenever you have spy attempts to spare."
                enabled={kingdom.auto_rob_enabled || false} onToggle={(e) => post({ enabled: e.target.checked })}
                disabled={!!props.loading.kingdom} saveDisabled={!changed}
                onSave={() => { post({ ...sliders.body(["drones"]), keep: autoKeep, shielded: autoShield }); sliders.reset(); setAutoKeep(""); }}>
                <FieldRow label="Drones to send" hint={`Now ${percentOf(settings.drones) || 0}%`} htmlFor="drones-percent">
                    <AmountInput name="drones" id="drones-percent" label="Drones to send" suffix="%" max={100}
                        value={String(sliders.value("drones"))} onChange={sliders.onChange} />
                </FieldRow>
                <FieldRow label="Spy attempts to keep" hint={`Now ${settings.keep ?? 0}`} htmlFor="keep-attempts">
                    <NumberControl id="keep-attempts" size="sm" inputMode="numeric" autoComplete="off" value={autoKeep}
                        placeholder={String(settings.keep || 0)} onChange={(e) => setAutoKeep(e.target.value)} />
                </FieldRow>
                <FieldRow label="Shield automatic robs">
                    <Form.Check type="switch" id="enable-auto-rob-shields-switch" checked={autoShield} onChange={(e) => setAutoShield(e.target.checked)} />
                </FieldRow>
            </AutoPanel>
        </>
    );
}

export default Primitives;
