import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import Alert from 'react-bootstrap/Alert';
import "./launchmissiles.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput, useFormValues } from "../../components/forms";
import { Panel, FieldRow, Stats, Picker, useServerForecast } from "../../components/planner";
import { checkPercent } from "../../validation";
import { displayNumber } from "../../format";

const MISSILES = [
    { key: "planet_busters", label: "Planet Buster" },
    { key: "star_busters", label: "Star Buster" },
    { key: "galaxy_busters", label: "Galaxy Buster" },
];
const noneYet = Object.fromEntries(MISSILES.map(({ key }) => [key, ""]));

function LaunchMissiles(props) {
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [targetKdInfo, setTargetKdInfo] = useState({});
    const [results, setResults] = useState([]);
    const [shields, setShields] = useState("");
    const [confirming, setConfirming] = useState(false);
    const form = useFormValues(noneYet);

    const loadTarget = (kdId) => authFetch("api/kingdom/" + kdId).then(safeJson).then(setTargetKdInfo);
    useEffect(() => {
        if (props.initialKd !== undefined) loadTarget(props.initialKd);
    }, []);
    const onPickTarget = (kdId) => { setSelected(kdId); setTargetKdInfo({}); loadTarget(kdId); };

    const have = props.data.kingdom.missiles || {};
    const desc = props.data.missiles?.desc || {};
    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const options = Object.keys(props.data.kingdoms).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));

    const shieldsKnown = targetKdInfo.shields !== undefined;
    const shieldsError = shieldsKnown ? null : checkPercent(shields);
    const sending = Object.fromEntries(MISSILES.map(({ key }) => [key, parseInt(form.values[key], 10) || 0]));
    const total = MISSILES.reduce((sum, { key }) => sum + sending[key], 0);
    const fieldError = (key) => (sending[key] > (have[key] || 0) ? `You only have ${displayNumber(have[key])}` : null);

    // What the missiles will do comes from the server, a moment after the player stops changing things.
    const [forecast, forecasting] = useServerForecast(
        selected !== undefined && total > 0 ? { selected, shields, values: form.values } : null,
        (plan) => authFetch('api/calculatemissiles/' + plan.selected, {
            method: 'POST',
            body: JSON.stringify({ attackerValues: plan.values, defenderShields: plan.shields }),
        }).then(safeJson),
    );

    const problems = [];
    if (selected === undefined) problems.push("Choose a target");
    if (total < 1) problems.push("Choose at least one missile");
    MISSILES.forEach(({ key }) => { const error = fieldError(key); if (error) problems.push(error); });
    if (shieldsError) problems.push(shieldsError);
    const blocked = problems[0];

    const send = () => {
        setConfirming(false);
        const updateFunc = async () => authFetch('api/launchmissiles/' + selected, {
            method: 'POST',
            body: JSON.stringify({ attackerValues: form.values }),
        }).then(safeJson).then((r) => { setResults((previous) => previous.concat(r)); form.reset(); });
        props.updateData(['kingdom', 'missilehistory'], [updateFunc]);
    };

    return (
        <>
            <Header data={props.data} />
            <div className="planner wide launch-missiles">
                <ResultToasts title="Missile Results" results={results} setResults={setResults} bg="primary" />
                <h2>Missiles</h2>
                <div className="wide-layout missiles-layout">
                    <Panel title="1. Target">
                        <FieldRow label="Target" htmlFor="missile-target">
                            <Picker id="missile-target" options={options} value={selected} onChange={onPickTarget}
                                placeholder="Type a kingdom to filter" autoFocus={selected === undefined} />
                        </FieldRow>
                        <FieldRow label="Their missile shields" status={shieldsKnown ? "revealed" : shields !== "" ? "estimate" : "optional"} htmlFor="missile-shields">
                            {shieldsKnown
                                ? <span className="known-value">{Math.round(targetKdInfo.shields.missiles * 100)}%</span>
                                : <div className="attack-buffer">
                                    <input id="missile-shields" className="form-control form-control-sm" inputMode="decimal" placeholder="unknown"
                                        autoComplete="off" value={shields} onChange={(e) => setShields(e.target.value)} />
                                    <span>%</span>
                                </div>}
                        </FieldRow>
                        {shieldsError ? <div className="amount-input-error">{shieldsError}</div> : null}
                    </Panel>

                    <Panel title="2. Missiles to send">
                        {MISSILES.map(({ key, label }) => (
                            <FieldRow key={key} label={label}
                                tip={`Damages ${desc[key]?.stars_damage || 0} stars, ${desc[key]?.fuel_damage || 0} fuel and ${desc[key]?.pop_damage || 0} population each (before shields)`}
                                htmlFor={`${key}-input`}>
                                <AmountInput name={key} label={label} value={form.values[key]} onChange={form.onChange}
                                    max={have[key] || 0} error={fieldError(key)} />
                            </FieldRow>
                        ))}
                    </Panel>

                    <Panel title="3. Forecast">
                        {total < 1 ? <p className="planner-why">Choose some missiles to see what they would do.</p> : null}
                        {total > 0 && forecast.damage ? <>
                            <Stats items={[
                                { label: "Stars destroyed", value: displayNumber(forecast.damage.stars) },
                                { label: "Fuel destroyed", value: displayNumber(forecast.damage.fuel) },
                                { label: "Population killed", value: displayNumber(forecast.damage.pop) },
                            ]} />
                            {forecasting ? <div className="planner-why">updating...</div> : null}
                        </> : null}
                        {total > 0 && !forecast.damage && forecast.message ? <Alert variant="warning">{forecast.message}</Alert> : null}
                        {total > 0 && !shieldsKnown && shields === "" ? <Alert variant="secondary">
                            Their shields are not revealed and not entered, so this assumes none.
                        </Alert> : null}
                    </Panel>

                    <Panel title="4. Launch">
                        <Button size="lg" disabled={Boolean(blocked) || props.loading.kingdom} title={blocked} onClick={() => setConfirming(true)}>
                            Launch missiles
                        </Button>
                        {blocked ? <div className="planner-why">{blocked}</div> : null}
                    </Panel>
                </div>

                <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                    <Modal.Header closeButton><Modal.Title>Launch these missiles?</Modal.Title></Modal.Header>
                    <Modal.Body>
                        <p>At <strong>{selected !== undefined ? kdLabel(selected) : ""}</strong>. Missiles that are launched are used up.</p>
                        <Stats items={MISSILES.filter(({ key }) => sending[key] > 0).map(({ key, label }) => ({ label, value: displayNumber(sending[key]) }))} />
                        {forecast.damage ? <Stats items={[
                            { label: "Stars", value: displayNumber(forecast.damage.stars) },
                            { label: "Fuel", value: displayNumber(forecast.damage.fuel) },
                            { label: "Population", value: displayNumber(forecast.damage.pop) },
                        ]} /> : null}
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
                        <Button onClick={send}>Launch</Button>
                    </Modal.Footer>
                </Modal>
                <HelpButton scrollTarget={"launchmissiles"} />
            </div>
        </>
    );
}

export default LaunchMissiles;
