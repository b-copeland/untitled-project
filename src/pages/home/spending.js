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
    const post = (body) => {
        const updateFunc = () => authFetch('api/spending', { method: 'post', body: JSON.stringify(body) })
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
            </Panel>
        </div>
    );
}
