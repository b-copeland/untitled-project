import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import Alert from 'react-bootstrap/Alert';
import "./attack.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput } from "../../components/forms";
import { Panel, FieldRow, Stats, VersusBar, Picker, useDebounced, clockUntil } from "../../components/planner";
import { displayPercent } from "../../format";

// What is known about the other side's army when it has not been revealed: typed in as an estimate.
const initialDefenderValues = { recruits: "", defense: "", flex: "", big_flex: "", military_bonus: "25", shields: "10" };
const initialAttackerValues = { attack: "", flex: "", big_flex: "", generals: "", buffer: "1.0" };

// [key in the units, name, key of the attacker's own field]. Defenders and recruits only matter on the defending side.
const ATTACK_UNITS = [["attack", "Attackers"], ["flex", "Flexers"], ["big_flex", "Big flexers"]];
const DEFENDER_UNITS = [["recruits", "Recruits"], ["defense", "Defenders"], ["flex", "Flexers"], ["big_flex", "Big flexers"]];

const whole = (value) => Math.floor(value || 0).toLocaleString();

function Attack(props) {
    const [defenderValues, setDefenderValues] = useState(initialDefenderValues);
    const [attackerValues, setAttackerValues] = useState(initialAttackerValues);
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [forecast, setForecast] = useState({});
    const [forecasting, setForecasting] = useState(false);
    const [suggesting, setSuggesting] = useState(false);
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [attackResults, setAttackResults] = useState([]);
    const [confirming, setConfirming] = useState(false);

    const loadTarget = (kdId) => authFetch("api/kingdom/" + kdId).then(safeJson).then(r => setTargetKdInfo(r));
    useEffect(() => {
        if (props.initialKd !== undefined) {
            loadTarget(props.initialKd);
        }
    }, []);
    const onPickTarget = (kdId) => {
        setSelected(kdId);
        setForecast({});
        setTargetKdInfo({});
        loadTarget(kdId);
    };

    const kingdom = props.data.kingdom;
    const unitsDesc = props.data.mobis?.units_desc || {};
    const myUnits = kingdom.units || {};
    const known = targetKdInfo.hasOwnProperty("units");  // their army has been revealed to us

    const onDefender = (event) => setDefenderValues((previous) => ({ ...previous, [event.target.name]: event.target.value }));
    const onAttacker = (event) => setAttackerValues((previous) => ({ ...previous, [event.target.name]: event.target.value }));

    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const options = Object.keys(props.data.kingdoms).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));

    const sending = ATTACK_UNITS.reduce((sum, [key]) => sum + (parseInt(attackerValues[key], 10) || 0), 0);
    const generals = parseInt(attackerValues.generals, 10) || 0;

    // The forecast follows what is typed: ask the server once the player has stopped typing.
    const request = useDebounced(JSON.stringify({ selected, attackerValues, defenderValues, known }), 700);
    useEffect(() => {
        const { selected: target, attackerValues: mine, defenderValues: theirs } = JSON.parse(request);
        const count = ATTACK_UNITS.reduce((sum, [key]) => sum + (parseInt(mine[key], 10) || 0), 0);
        if (target === undefined || count === 0) {
            setForecast({});
            return;
        }
        let current = true;
        setForecasting(true);
        authFetch('api/calculate/' + target, {
            method: 'POST',
            body: JSON.stringify({ attackerValues: mine, defenderValues: theirs }),
        }).then(safeJson).then(r => { if (current) setForecast(r); }).finally(() => { if (current) setForecasting(false); });
        return () => { current = false; };
    }, [request]);

    const onSuggest = async () => {
        if (selected === undefined) {
            return;
        }
        setSuggesting(true);
        const body = { buffer: attackerValues.buffer, generals: attackerValues.generals || "1", defenderValues };
        const answer = await authFetch('api/autofill/' + selected, { method: 'POST', body: JSON.stringify(body) }).then(safeJson);
        setSuggesting(false);
        if (answer.attacker_units) {
            setAttackerValues((previous) => ({ ...previous, generals: previous.generals || "1", ...answer.attacker_units }));
            setForecast(answer);
        } else {
            setForecast({ error: answer.message });
        }
    };
    const onClear = () => { setAttackerValues((previous) => ({ ...previous, attack: "", flex: "", big_flex: "", generals: "" })); setForecast({}); };

    const send = () => {
        setConfirming(false);
        const updateFunc = async () => authFetch('api/attack/' + selected, {
            method: 'POST',
            body: JSON.stringify({ attackerValues }),
        }).then(safeJson).then(r => { setAttackResults((previous) => previous.concat(r)); setForecast({}); });
        props.updateData(['kingdom', 'projects', 'attackhistory', 'mobis', 'settle', 'structures', 'projects', 'galaxynews'], [updateFunc]);
    };

    // What the forecast says, and what is left at home once the units are away.
    const hasForecast = forecast.attacker_offense !== undefined;
    const wins = hasForecast && forecast.attacker_offense > forecast.defender_defense;
    const ratio = hasForecast && forecast.defender_defense > 0 ? forecast.attacker_offense / forecast.defender_defense : 0;
    const rawDefense = (units) => Object.keys(unitsDesc).reduce((sum, key) => sum + (units[key] || 0) * (unitsDesc[key].defense || 0), 0);
    const afterUnits = Object.fromEntries(Object.keys(myUnits).map((key) => [key, (myUnits[key] || 0) - (parseInt(attackerValues[key], 10) || 0)]));
    const defenseNow = props.data.mobis?.units?.current_total?.defense;
    const rawNow = rawDefense(myUnits);
    const defenseAfter = rawNow > 0 && defenseNow !== undefined ? defenseNow * rawDefense(afterUnits) / rawNow : rawDefense(afterUnits);
    const homeNow = defenseNow !== undefined ? defenseNow : rawNow;

    const intel = Object.entries((props.data.revealed?.revealed || {})[selected] || {});

    const problems = [];
    if (selected === undefined) problems.push("Choose a target");
    if (sending === 0) problems.push("Choose units to send");
    if (generals < 1) problems.push("Send at least 1 general");
    ATTACK_UNITS.forEach(([key, name]) => {
        if ((parseInt(attackerValues[key], 10) || 0) > (myUnits[key] || 0)) problems.push(`You only have ${whole(myUnits[key])} ${name.toLowerCase()}`);
    });
    if (generals > (kingdom.generals_available || 0)) problems.push(`You only have ${kingdom.generals_available} generals`);
    const blocked = problems[0];

    return (
        <>
            <Header data={props.data} />
            <div className="planner attack">
                <ResultToasts title="Attack Results" results={attackResults} setResults={setAttackResults} />
                <h2>Attack</h2>

                <Panel title="1. Choose a target">
                    <Picker id="attack-target" options={options} value={selected} onChange={onPickTarget}
                        placeholder="Type a kingdom to filter" autoFocus={selected === undefined} />
                    {intel.length > 0
                        ? <Stats items={intel.map(([what, until]) => ({ label: `${what} revealed for`, value: clockUntil(until) }))} />
                        : null}
                </Panel>

                <div className="planner-grid">
                    <Panel title="2. Their defense"
                        hint={known ? "Revealed to you, so these are exact." : "Not revealed to you: enter what you think they have. A spy operation reveals it."}>
                        {DEFENDER_UNITS.map(([key, name]) => (
                            <FieldRow key={key} label={name} hint={unitsDesc[key]?.defense ? `${unitsDesc[key].defense} defense each` : undefined} htmlFor={"def-" + key}>
                                {known
                                    ? <strong>{whole(targetKdInfo.units[key])}</strong>
                                    : <Form.Control id={"def-" + key} name={key} size="sm" inputMode="numeric" placeholder="0" autoComplete="off"
                                        value={defenderValues[key]} onChange={onDefender} />}
                            </FieldRow>
                        ))}
                        <FieldRow label="Military efficiency" htmlFor="def-military_bonus">
                            {targetKdInfo.current_bonuses
                                ? <strong>{displayPercent(targetKdInfo.current_bonuses.military_bonus)}</strong>
                                : <Form.Control id="def-military_bonus" name="military_bonus" size="sm" inputMode="decimal" placeholder="25" autoComplete="off"
                                    value={defenderValues.military_bonus} onChange={onDefender} />}
                        </FieldRow>
                        <FieldRow label="Shields" htmlFor="def-shields">
                            {targetKdInfo.shields
                                ? <strong>{displayPercent(targetKdInfo.shields.military)}</strong>
                                : <Form.Control id="def-shields" name="shields" size="sm" inputMode="decimal" placeholder="10" autoComplete="off"
                                    value={defenderValues.shields} onChange={onDefender} />}
                        </FieldRow>
                    </Panel>

                    <Panel title="3. Your attack"
                        hint="Pick what to send, or let us suggest an attack that should win. Nothing is sent until you press Send.">
                        {ATTACK_UNITS.map(([key, name]) => (
                            (key !== "big_flex" || myUnits.big_flex > 0 || attackerValues.big_flex)
                                ? <FieldRow key={key} label={name} hint={`${whole(myUnits[key])} available, ${unitsDesc[key]?.offense || "--"} offense each`} htmlFor={"att-" + key}>
                                    <AmountInput name={key} id={"att-" + key} label={name} value={attackerValues[key]} onChange={onAttacker} max={myUnits[key] || 0} />
                                </FieldRow>
                                : null
                        ))}
                        <FieldRow label="Generals" hint={`${kingdom.generals_available ?? 0} available`} htmlFor="att-generals">
                            <AmountInput name="generals" id="att-generals" label="Generals" value={attackerValues.generals} onChange={onAttacker} max={kingdom.generals_available || 0} />
                        </FieldRow>
                        <FieldRow label="Suggestion margin" hint="Extra offense the suggestion adds" htmlFor="att-buffer">
                            <div className="attack-buffer">
                                <Form.Control id="att-buffer" name="buffer" size="sm" inputMode="decimal" autoComplete="off" value={attackerValues.buffer} onChange={onAttacker} />
                                <span>%</span>
                            </div>
                        </FieldRow>
                        <div className="planner-actions">
                            <Button variant="outline-primary" onClick={onSuggest} disabled={selected === undefined || suggesting}
                                title="Fills in units that should beat the defense on the left. Does not send anything.">
                                {suggesting ? "Working..." : "Suggest an attack"}
                            </Button>
                            <Button variant="link" onClick={onClear}>Clear</Button>
                        </div>
                    </Panel>
                </div>

                <Panel title="4. Forecast" hint={hasForecast ? undefined : "Choose a target and some units to see how it would go."}>
                    {forecast.error ? <Alert variant="warning">{forecast.error}</Alert> : null}
                    {hasForecast ? <>
                        <div className={"planner-verdict " + (wins ? "good" : "bad")}>
                            {wins ? "This attack should succeed" : "This attack would fail"}
                            {forecasting ? " (updating...)" : ""}
                        </div>
                        <VersusBar ratio={ratio} yours="Your offense" theirs="their defense" />
                        <Stats items={[
                            { label: "Your offense", value: whole(forecast.attacker_offense) },
                            { label: "Their defense", value: whole(forecast.defender_defense) },
                            { label: wins ? "Margin" : "Short by", value: whole(Math.abs(forecast.attacker_offense - forecast.defender_defense)), tone: wins ? "good" : "bad" },
                        ]} />
                        <div className="planner-notes">{forecast.message}</div>
                        <table className="planner-table table table-sm">
                            <thead><tr><th>Units lost</th><th>You</th><th>Them</th></tr></thead>
                            <tbody>
                                {[["attack", "Attackers"], ["flex", "Flexers"], ["big_flex", "Big flexers"], ["defense", "Defenders"], ["recruits", "Recruits"]].map(([key, name]) => {
                                    const yours = forecast.attacker_losses?.[key];
                                    const theirs = forecast.defender_losses?.[key];
                                    return (yours || theirs)
                                        ? <tr key={key}><td>{name}</td><td>{yours ? whole(yours) : "--"}</td><td>{theirs ? whole(theirs) : "--"}</td></tr>
                                        : null;
                                })}
                                <tr><td>Loss rate</td><td>{displayPercent(forecast.attacker_unit_losses_rate)}</td><td>{displayPercent(forecast.defender_unit_losses_rate)}</td></tr>
                            </tbody>
                        </table>
                    </> : null}
                    {sending > 0 ? <>
                        <h4 className="planner-subtitle">Your kingdom while they are away</h4>
                        <Stats items={[
                            { label: "Home defense now", value: whole(homeNow) },
                            { label: "Home defense after", value: whole(defenseAfter), tone: defenseAfter < homeNow * 0.8 ? "bad" : undefined },
                            { label: "Generals left", value: whole((kingdom.generals_available || 0) - generals) },
                        ]} />
                    </> : null}
                </Panel>

                <Panel title="5. Send">
                    <Button variant={wins || !hasForecast ? "primary" : "danger"} size="lg" disabled={Boolean(blocked) || props.loading.kingdom}
                        title={blocked} onClick={() => setConfirming(true)}>
                        Send attack
                    </Button>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>

                <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                    <Modal.Header closeButton><Modal.Title>Send this attack?</Modal.Title></Modal.Header>
                    <Modal.Body>
                        <p>
                            Send {whole(sending)} units and {generals} general{generals === 1 ? "" : "s"} at <strong>{selected !== undefined ? kdLabel(selected) : ""}</strong>.
                        </p>
                        {hasForecast
                            ? <Alert variant={wins ? "success" : "danger"}>
                                {wins ? "Forecast: it should succeed." : "Forecast: it would fail."} Your {whole(forecast.attacker_offense)} offense against their {whole(forecast.defender_defense)} defense.
                            </Alert>
                            : <Alert variant="warning">There is no forecast for this attack yet.</Alert>}
                        {!known && !DEFENDER_UNITS.some(([key]) => parseInt(defenderValues[key], 10) > 0)
                            ? <Alert variant="warning">You have entered nothing about their army, so the forecast is a guess.</Alert>
                            : null}
                        <p className="mb-0">Home defense goes from {whole(homeNow)} to about {whole(defenseAfter)} while they are away.</p>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
                        <Button variant={wins ? "primary" : "danger"} onClick={send}>Send attack</Button>
                    </Modal.Footer>
                </Modal>
                <HelpButton scrollTarget={"attack"}/>
            </div>
        </>
    );
}

export default Attack;
