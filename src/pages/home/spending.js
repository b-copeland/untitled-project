import React, { useState } from "react";
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import { authFetch } from "../../auth";
import { AmountInput, SubmitButton, useSliders } from "../../components/forms";
import { ResultToasts, safeJson } from "../../components/results";
import { Panel, FieldRow, Stats } from "../../components/planner";
import "./spending.css";

const CATEGORIES = [
    ["settle", "Settle"],
    ["structures", "Structures"],
    ["military", "Military"],
    ["engineers", "Engineers"],
];

const PLACES = [["money", "Money"], ...CATEGORIES];

/** Why a move can not be sent yet (null if it can). The server makes the same checks against the kingdom as it is. */
export function moveProblem({ from, to, amount, kingdom }) {
    if (from === to) return "Choose two different places";
    if (to !== "money" && !kingdom.auto_spending_enabled) return "Turn auto spending on first: funding is only spent while it is on";
    const have = Math.max(Math.floor(from === "money" ? kingdom.money || 0 : kingdom.funding?.[from] || 0), 0);
    if (have < 1) return "There is nothing to move";
    const wanted = parseInt(amount, 10) || 0;
    if (wanted < 1) return "Choose how much to move";
    if (wanted > have) return `There is only ${have.toLocaleString()} to move`;
    return null;
}

/**
 * Move money between money and the four funding categories: funding back to money, from one category to another, or
 * money into a category for the auto spender to spend. Money and funding count the same for networth and spoils.
 */
export function MoveFunding({ kingdom, loading, post }) {
    const [from, setFrom] = useState("military");
    const [to, setTo] = useState("money");
    const [amount, setAmount] = useState("");
    const have = Math.max(Math.floor(from === "money" ? kingdom.money || 0 : kingdom.funding?.[from] || 0), 0);
    const blocked = moveProblem({ from, to, amount, kingdom });
    const send = () => { post({ from, to, amount: parseInt(amount, 10) }); setAmount(""); };
    const choose = (id, label, value, onChange) => (
        <FieldRow label={label} htmlFor={id}>
            <Form.Select id={id} size="sm" value={value} onChange={(e) => { onChange(e.target.value); setAmount(""); }}>
                {PLACES.map(([key, name]) => <option key={key} value={key}>{name}{key === "money" ? "" : " funding"}</option>)}
            </Form.Select>
        </FieldRow>
    );
    return (
        <div className="spending-move" data-testid="move-funding">
            <h3 className="panel-title">Move funding</h3>
            <p className="text-muted small">
                Take funding back as money, move it to another category, or put money into a category for the auto
                spender to spend. Nothing is lost either way.
            </p>
            {choose("move-from", "From", from, setFrom)}
            {choose("move-to", "To", to, setTo)}
            <FieldRow label="Amount" hint={`${have.toLocaleString()} to move`} htmlFor="move-amount">
                <AmountInput box name="amount" id="move-amount" label="Amount" value={amount}
                    onChange={(e) => setAmount(e.target.value)} max={have} />
            </FieldRow>
            <div className="form-actions">
                <SubmitButton loading={loading.kingdom} onClick={send} blocked={blocked}>Move</SubmitButton>
            </div>
        </div>
    );
}

/**
 * Automation's Spending tab (it has no page of its own; /spending redirects there): the auto spending switch, a slider
 * per category (the four add up to at most 100%), and the funding each holds. Update sends only the moved shares.
 */
export function Spending(props) {
    const spendingInfo = props.kingdom?.auto_spending || {};
    const current = Object.fromEntries(CATEGORIES.map(([key]) => [key, Math.round((spendingInfo[key] || 0) * 100)]));
    const sliders = useSliders(current);
    const [results, setResults] = useState([]);

    if (props.kingdom?.auto_spending === undefined) {
        return null;
    }
    const post = (body, path = 'api/spending') => {
        const updateFunc = () => authFetch(path, { method: 'post', body: JSON.stringify(body) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };
    const total = CATEGORIES.reduce((sum, [key]) => sum + sliders.value(key), 0);
    const onUpdate = () => {
        post(sliders.body(CATEGORIES.map(([key]) => key)));
        sliders.reset();
    };

    return (
        <div className="spending panel-grid">
            <ResultToasts title="Auto spending" results={results} setResults={setResults} />
            <Panel title="Auto spending" hint="While it is on, these shares of the money you make are set aside for each category and spent on it.">
                <Form.Check
                    type="switch"
                    id="enable-auto-spending-switch"
                    label={props.kingdom.auto_spending_enabled ? "On" : "Off"}
                    checked={!!props.kingdom.auto_spending_enabled}
                    onChange={(e) => post({ enabled: e.target.checked })}
                    disabled={!!props.loading.kingdom}
                />
                {CATEGORIES.map(([key, name]) => (
                    <FieldRow key={key} label={name} hint={`Now ${current[key]}%`} htmlFor={`${key}-percent`}>
                        <AmountInput name={key} id={`${key}-percent`} label={`${name} share`} suffix="%"
                            value={String(sliders.value(key))} onChange={sliders.onChange}
                            max={Math.max(100 - (total - sliders.value(key)), 0)} soloMax={100} />
                    </FieldRow>
                ))}
                <div className="form-actions">
                    <span className="text-muted">{100 - total}% of income kept as money</span>
                    {sliders.changed ? <Button variant="link" size="sm" onClick={sliders.reset}>Undo changes</Button> : null}
                    <SubmitButton loading={props.loading.kingdom} onClick={onUpdate}
                        blocked={total > 100 ? "The shares add up to more than 100%"
                            : sliders.changed ? null : "Move a slider to change a share"}>
                        Update
                    </SubmitButton>
                </div>
            </Panel>
            <Panel title="Funding set aside">
                <Stats items={CATEGORIES.map(([key, name]) => ({
                    label: name,
                    value: Math.floor(props.kingdom.funding?.[key] || 0).toLocaleString(),
                }))} />
                <MoveFunding kingdom={props.kingdom} loading={props.loading} post={(body) => post(body, "api/funding/move")} />
            </Panel>
        </div>
    );
}
