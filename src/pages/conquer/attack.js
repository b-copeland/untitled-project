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
import { Panel, FieldRow, Stats, VersusBar, Picker, useServerForecast, clockUntil } from "../../components/planner";
import { displayPercent } from "../../format";

/*
 * Every figure on this page that is a projection (offense, defense, losses, spoils, what is left at home) comes from
 * the server (/api/calculate, /api/autofill, /api/attackcontext). The page only holds what the player typed and asks
 * again, after a pause, when it changes.
 */

const noDefender = { recruits: "", defense: "", flex: "", big_flex: "", military_bonus: "", shields: "" };
const noAttacker = { attack: "", flex: "", big_flex: "", generals: "", buffer: "1.0" };

const ATTACK_UNITS = [["attack", "Attackers"], ["flex", "Flexers"], ["big_flex", "Big flexers"]];
const DEFENDER_UNITS = [["recruits", "Recruits"], ["defense", "Defenders"], ["flex", "Flexers"], ["big_flex", "Big flexers"]];

const whole = (value) => Math.floor(value || 0).toLocaleString();
const text = (value) => (value ? String(value) : "");

// The plan the server is asked about: fixed order and plain strings, so the same plan is always the same question.
const planFor = (selected, attacker, defender) => ({
    selected,
    attacker: { attack: text(attacker.attack), flex: text(attacker.flex), big_flex: text(attacker.big_flex), generals: text(attacker.generals) },
    defender,
});

function Attack(props) {
    const [defenderValues, setDefenderValues] = useState(noDefender);
    const [attackerValues, setAttackerValues] = useState(noAttacker);
    const [edited, setEdited] = useState({});            // which of their numbers the player has changed from the starting estimate
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [context, setContext] = useState(null);         // revealed flags, an estimate, your own defense
    const [loadingTarget, setLoadingTarget] = useState(false);
    const [suggesting, setSuggesting] = useState(false);
    const [attackResults, setAttackResults] = useState([]);
    const [confirming, setConfirming] = useState(false);
    const [notice, setNotice] = useState(null);

    const kingdom = props.data.kingdom;
    const unitsDesc = props.data.mobis?.units_desc || {};
    const myUnits = kingdom.units || {};

    const sending = ATTACK_UNITS.reduce((sum, [key]) => sum + (parseInt(attackerValues[key], 10) || 0), 0);
    const generals = parseInt(attackerValues.generals, 10) || 0;

    const [forecast, pending, setForecast] = useServerForecast(
        selected !== undefined && sending > 0 ? planFor(selected, attackerValues, defenderValues) : null,
        (plan) => authFetch('api/calculate/' + plan.selected, {
            method: 'POST',
            body: JSON.stringify({ attackerValues: plan.attacker, defenderValues: plan.defender }),
        }).then(safeJson),
    );

    // Ask for a suggested attack against these numbers. It only fills the form in; nothing is sent.
    const suggest = async (target, defender, attacker = attackerValues) => {
        setSuggesting(true);
        setNotice(null);
        const body = { buffer: attacker.buffer, generals: attacker.generals || "1", defenderValues: defender };
        const answer = await authFetch('api/autofill/' + target, { method: 'POST', body: JSON.stringify(body) }).then(safeJson);
        setSuggesting(false);
        if (answer.attacker_units) {
            const next = { ...attacker, generals: attacker.generals || "1" };
            ATTACK_UNITS.forEach(([key]) => { next[key] = text(answer.attacker_units[key]); });
            setAttackerValues(next);
            setForecast(answer, planFor(target, next, defender));
        } else {
            setNotice(answer.message || "No attack could be suggested.");
        }
    };

    // Choosing a target loads what is known about it and about you, fills in estimates for the rest, and suggests an attack.
    const loadTarget = async (kdId) => {
        setLoadingTarget(true);
        setSelected(kdId);
        setTargetKdInfo({});
        setContext(null);
        setEdited({});
        setNotice(null);
        setForecast({});
        const [info, ctx] = await Promise.all([
            authFetch("api/kingdom/" + kdId).then(safeJson),
            authFetch("api/attackcontext/" + kdId).then(safeJson),
        ]);
        setLoadingTarget(false);
        if (!ctx.mine) {
            setNotice(ctx.message || "Could not load that target.");
            return;
        }
        setTargetKdInfo(info);
        setContext(ctx);
        const guess = ctx.estimate;
        const defender = {
            recruits: text(info.units ? "" : guess.units.recruits),
            defense: text(info.units ? "" : guess.units.defense),
            flex: text(info.units ? "" : guess.units.flex),
            big_flex: text(info.units ? "" : guess.units.big_flex),
            military_bonus: String(guess.military_bonus),
            shields: String(guess.shields),
        };
        setDefenderValues(defender);
        suggest(kdId, defender, noAttacker);
    };
    useEffect(() => {
        if (props.initialKd !== undefined) {
            loadTarget(props.initialKd);
        }
    }, []);

    const onDefender = (event) => {
        setEdited((previous) => ({ ...previous, [event.target.name]: true }));
        setDefenderValues((previous) => ({ ...previous, [event.target.name]: event.target.value }));
    };
    const onAttacker = (event) => setAttackerValues((previous) => ({ ...previous, [event.target.name]: event.target.value }));
    const onClear = () => { setAttackerValues((previous) => ({ ...previous, attack: "", flex: "", big_flex: "", generals: "" })); setForecast({}); };

    const send = () => {
        setConfirming(false);
        const updateFunc = async () => authFetch('api/attack/' + selected, {
            method: 'POST',
            body: JSON.stringify({ attackerValues }),
        }).then(safeJson).then(r => { setAttackResults((previous) => previous.concat(r)); setForecast({}); });
        props.updateData(['kingdom', 'projects', 'attackhistory', 'mobis', 'settle', 'structures', 'projects', 'galaxynews'], [updateFunc]);
    };

    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const options = Object.keys(props.data.kingdoms).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));

    const unitsKnown = Boolean(context?.revealed.units);
    const bonusKnown = Boolean(context?.revealed.military_bonus);
    const shieldsKnown = Boolean(context?.revealed.shields);
    const allKnown = unitsKnown && bonusKnown && shieldsKnown;
    const hasForecast = forecast.attacker_offense !== undefined;
    const wins = hasForecast && forecast.attacker_offense > forecast.defender_defense;
    const ratio = hasForecast && forecast.defender_defense > 0 ? forecast.attacker_offense / forecast.defender_defense : 0;
    const homeNow = forecast.attacker_home_defense_before ?? context?.mine.defense_now;
    const homeAfter = forecast.attacker_home_defense_after;
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

    const unitStatus = (key) => (unitsKnown ? "revealed" : edited[key] ? "estimate" : "needed");

    return (
        <>
            <Header data={props.data} />
            <div className="planner wide attack">
                <ResultToasts title="Attack Results" results={attackResults} setResults={setAttackResults} />
                <h2>Attack</h2>
                <div className="wide-layout attack-layout">

                <Panel className="area-target" title="1. Choose a target">
                    <Picker id="attack-target" options={options} value={selected} onChange={loadTarget}
                        placeholder="Type a kingdom to filter" autoFocus={selected === undefined} />
                    {loadingTarget ? <p className="planner-hint-line">Loading what is known about them...</p> : null}
                    {intel.length > 0
                        ? <Stats items={intel.map(([what, until]) => ({ label: `${what} revealed for`, value: clockUntil(until) }))} />
                        : null}
                </Panel>

                {context ? <Panel className="area-matchup" title="The matchup">
                    <div className="matchup">
                        <Stats items={[{ label: "Their defense", value: hasForecast ? whole(forecast.defender_defense) : "--" }]} />
                        <Stats items={[{ label: "Your offense", value: hasForecast ? whole(forecast.attacker_offense) : "--", tone: hasForecast ? (wins ? "good" : "bad") : undefined }]} />
                        <Stats items={[{ label: "Your defense now", value: whole(homeNow) }]} />
                        <Stats items={[{ label: "Your defense after this attack", value: homeAfter !== undefined ? whole(homeAfter) : "--", tone: homeAfter !== undefined && homeAfter < homeNow * 0.8 ? "bad" : undefined }]} />
                        <Stats items={[{ label: "Your defense if you sent everything", value: whole(context.mine.defense_if_all_sent) }]} />
                    </div>
                </Panel> : null}

                {context ? <>
                    <Panel className="area-def" title="2. Their defense">
                        {DEFENDER_UNITS.map(([key, name]) => (
                            <FieldRow key={key} label={name} status={unitStatus(key)} hint={unitsDesc[key]?.defense ? `${unitsDesc[key].defense} defense each` : undefined} htmlFor={"def-" + key}>
                                {unitsKnown
                                    ? <span className="known-value">{whole(targetKdInfo.units[key])}</span>
                                    : <Form.Control id={"def-" + key} name={key} size="sm" inputMode="numeric" placeholder="0" autoComplete="off"
                                        value={defenderValues[key]} onChange={onDefender} />}
                            </FieldRow>
                        ))}
                        <FieldRow label="Military efficiency" status={bonusKnown ? "revealed" : edited.military_bonus ? "estimate" : "needed"} htmlFor="def-military_bonus">
                            {bonusKnown
                                ? <span className="known-value">{displayPercent(targetKdInfo.current_bonuses.military_bonus)}</span>
                                : <div className="attack-buffer"><Form.Control id="def-military_bonus" name="military_bonus" size="sm" inputMode="decimal" placeholder="0" autoComplete="off"
                                    value={defenderValues.military_bonus} onChange={onDefender} /><span>%</span></div>}
                        </FieldRow>
                        <FieldRow label="Shields" status={shieldsKnown ? "revealed" : edited.shields ? "estimate" : "needed"} htmlFor="def-shields">
                            {shieldsKnown
                                ? <span className="known-value">{displayPercent(targetKdInfo.shields.military)}</span>
                                : <div className="attack-buffer"><Form.Control id="def-shields" name="shields" size="sm" inputMode="decimal" placeholder="0" autoComplete="off"
                                    value={defenderValues.shields} onChange={onDefender} /><span>%</span></div>}
                        </FieldRow>
                    </Panel>

                    <Panel className="area-attack" title="3. Your attack">
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
                        <FieldRow label="Suggestion margin" hint="Extra offense a suggestion adds" htmlFor="att-buffer">
                            <div className="attack-buffer">
                                <Form.Control id="att-buffer" name="buffer" size="sm" inputMode="decimal" autoComplete="off" value={attackerValues.buffer} onChange={onAttacker} />
                                <span>%</span>
                            </div>
                        </FieldRow>
                        <div className="planner-actions">
                            <Button variant="outline-primary" onClick={() => suggest(selected, defenderValues)} disabled={suggesting}
                                title="Fills in units that should beat the defense on the left. Does not send anything.">
                                {suggesting ? "Working..." : "Suggest again"}
                            </Button>
                            <Button variant="link" onClick={onClear}>Clear</Button>
                        </div>
                        {notice ? <Alert variant="warning" className="mt-2 mb-0">{notice}</Alert> : null}
                    </Panel>
                </> : null}

                {context ? <Panel className="area-forecast" title="4. Forecast">
                    {forecast.message && !hasForecast ? <Alert variant="warning">{forecast.message}</Alert> : null}
                    {hasForecast ? <>
                        <div className={"planner-verdict " + (wins ? "good" : "bad")}>
                            {wins ? "This attack should succeed" : "This attack would fail"}
                            {pending ? " (updating...)" : ""}
                        </div>
                        <VersusBar ratio={ratio} yours="Your offense" theirs="their defense" />
                        <Stats items={[
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
                </Panel> : null}

                <Panel className="area-send" title="5. Send">
                    <Button variant={wins || !hasForecast ? "primary" : "danger"} size="lg" disabled={Boolean(blocked) || props.loading.kingdom}
                        title={blocked} onClick={() => setConfirming(true)}>
                        Send attack
                    </Button>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>

                </div>

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
                        {!unitsKnown
                            ? <Alert variant="warning">Their army is not revealed to you, so the forecast rests on an estimate.</Alert>
                            : null}
                        {homeAfter !== undefined
                            ? <p className="mb-0">Your home defense goes from {whole(homeNow)} to {whole(homeAfter)} while they are away.</p>
                            : null}
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
