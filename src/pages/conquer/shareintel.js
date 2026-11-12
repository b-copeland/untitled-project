import React, { useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Alert from 'react-bootstrap/Alert';
import "./shareintel.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { Panel, FieldRow, Picker, clockUntil } from "../../components/planner";
import { checkPercent } from "../../validation";

function ShareIntel(props) {
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [stat, setStat] = useState(undefined);
    const [shareTo, setShareTo] = useState(undefined);
    const [cut, setCut] = useState("");
    const [results, setResults] = useState([]);

    if (props.loading.revealed) {
        return <h2>Loading...</h2>;
    }
    if (Object.keys(props.data.revealed).length === 0) {
        return <div className="share-intel"><h2>You do not have any intel to share!</h2></div>;
    }

    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const revealed = props.data.revealed["revealed"];
    const kingdomOptions = Object.keys(revealed).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));
    const statOptions = Object.entries(revealed[selected] || {}).map(([name, until]) => ({ value: name, label: `${name}  (${clockUntil(until)} left)` }));
    const myGalaxy = props.data.galaxies[props.data.galaxies_inverted[props.data.kingdomid.kd_id]] || [];
    const shareToOptions = [{ value: "galaxy", label: "Your whole galaxy" }, ...myGalaxy.map((kdId) => ({ value: kdId, label: kdLabel(kdId) }))];
    const whoName = shareTo === "galaxy" ? "your galaxy" : shareTo !== undefined ? props.data.kingdoms[parseInt(shareTo)] : undefined;

    const cutError = checkPercent(cut);
    const problems = [];
    if (selected === undefined) problems.push("Choose which kingdom's intel to share");
    else if (stat === undefined) problems.push("Choose which stat to share");
    else if (shareTo === undefined) problems.push("Choose who to share it with");
    if (cutError) problems.push(cutError);
    const blocked = problems[0];

    const onShare = () => {
        const body = { shared: selected, shared_to: shareTo, shared_stat: stat, cut: cut === "" ? 0 : cut };
        const updateFunc = async () => authFetch('api/offershared', { method: 'POST', body: JSON.stringify(body) })
            .then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['shared'], [updateFunc]);
    };
    const pickKingdom = (kdId) => { setSelected(kdId); setStat(undefined); };

    return (
        <>
            <Header data={props.data} />
            <div className="planner share-intel">
                <ResultToasts title="Share Intel Results" results={results} setResults={setResults} />
                <h2>Share intel</h2>
                <p className="planner-hint-line">
                    Intel you have revealed on a kingdom can be offered to a galaxymate, who can then plan an attack on it. You can
                    ask for a cut of what they win. They choose whether to accept, and you only get the cut if they do and the attack succeeds.
                </p>

                <div className="planner-grid">
                    <Panel title="1. What to share">
                        <FieldRow label="Kingdom" hint="Ones you have intel on" htmlFor="share-kingdom">
                            <Picker id="share-kingdom" options={kingdomOptions} value={selected} onChange={pickKingdom}
                                placeholder="Choose a kingdom" autoFocus={selected === undefined} />
                        </FieldRow>
                        <FieldRow label="Stat" hint={selected === undefined ? "Choose a kingdom first" : "Shared intel runs out when the reveal does"} htmlFor="share-stat">
                            <Picker id="share-stat" options={statOptions} value={stat} onChange={setStat}
                                placeholder={selected === undefined ? "--" : "Choose a stat"} searchable={false} />
                        </FieldRow>
                    </Panel>

                    <Panel title="2. Who gets it, and your cut">
                        <FieldRow label="Share with" htmlFor="share-to">
                            <Picker id="share-to" options={shareToOptions} value={shareTo} onChange={setShareTo}
                                placeholder="Choose who" searchable={false} />
                        </FieldRow>
                        <FieldRow label="Your cut" hint="Share of their winnings you receive" htmlFor="cut-input">
                            <div className="attack-buffer">
                                <Form.Control id="cut-input" size="sm" inputMode="decimal" placeholder="0" autoComplete="off"
                                    value={cut} onChange={(e) => setCut(e.target.value)} isInvalid={Boolean(cutError)} />
                                <span>%</span>
                            </div>
                            {cutError ? <div className="amount-input-error">{cutError}</div> : null}
                        </FieldRow>
                    </Panel>
                </div>

                <Panel title="3. Check and offer">
                    {selected !== undefined && stat !== undefined && shareTo !== undefined
                        ? <Alert variant="info" className="mb-3">
                            You are offering <strong>{whoName}</strong> your <strong>{stat}</strong> intel on <strong>{props.data.kingdoms[parseInt(selected)]}</strong>.
                            {parseFloat(cut) > 0
                                ? <> If they attack {props.data.kingdoms[parseInt(selected)]} and win, you receive <strong>{cut}%</strong> of the spoils.</>
                                : <> You are asking for nothing in return.</>}
                            {" "}Nothing is shared until they accept.
                        </Alert>
                        : <p className="planner-hint-line">Fill in the steps above to see exactly what you are offering.</p>}
                    <Button size="lg" onClick={onShare} disabled={Boolean(blocked) || props.loading.shared} title={blocked}>Offer intel</Button>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>
                <HelpButton scrollTarget={"shareintel"}/>
            </div>
        </>
    );
}

export default ShareIntel;
