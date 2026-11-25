import React, { useState } from "react";
import Form from "react-bootstrap/Form";
import Button from "react-bootstrap/Button";
import { authFetch } from "../../auth";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput } from "../../components/forms";
import { Panel, FieldRow } from "../../components/planner";
import { KingdomPicker } from "../../components/kingdompicker";
import { displayPercent } from "../../format";

// The intel operations a repeating entry can run. The server holds the same list (REVEAL_OPERATIONS).
export const INTEL_OPERATIONS = [
    { value: "spymilitary", label: "Spy on military" }, { value: "spykingdom", label: "Spy on kingdom" },
    { value: "spyshields", label: "Spy on shields" }, { value: "spyprojects", label: "Spy on projects" },
    { value: "spystructures", label: "Spy on structures" }, { value: "spydrones", label: "Spy on drones" },
    { value: "spyall", label: "Full infiltration (everything)" },
];
const START = { type: "siphon", target: null, operation: null, drones_pct: "", shielded: false, share_to_galaxy: false, cut: "", stop_after_fails: "3", until: "" };
const STATUS = { success: "Worked", failure: "Failed", refused: "Refused", dead: "Target dead" };

/** Everything wrong with a repeating request, in the order the player would fix it. The server still decides. */
export function recurringProblems(options, me, maxCut) {
    const found = [];
    if (options.target === null) found.push("Choose a target");
    else if (String(options.target) === String(me)) found.push("You can not spy on yourself");
    if (options.type === "intel" && !options.operation) found.push("Choose an operation");
    const drones = parseFloat(options.drones_pct);
    if (!(drones > 0 && drones <= 100)) found.push("Send between 1% and 100% of your drones");
    const stop = parseInt(options.stop_after_fails, 10);
    if (!(stop >= 0 && stop <= 10)) found.push("Stop after 0 to 10 failures in a row (0 never stops)");
    if (options.type === "intel" && options.share_to_galaxy) {
        const cut = parseFloat(options.cut || 0);
        if (!(cut >= 0 && cut <= maxCut)) found.push(`The cut is 0% to ${maxCut}%`);
    }
    if (options.until && new Date(options.until).getTime() <= Date.now()) found.push("The end time has passed");
    return found;
}

/** The Schedule page's Repeating tab: spy operations that run again whenever a spy attempt is free (issue #137). */
export function Repeating(props) {
    const [options, setOptions] = useState(START);
    const [results, setResults] = useState([]);
    const config = props.data.state?.game_config || {};
    const maxCut = (config.BASE_MAX_SHARE_CUT || 0) * 100;
    const siphonHours = (config.BASE_DRONES_SIPHON_TIME_MULTIPLIER || 0) * (config.BASE_EPOCH_SECONDS || 0) / 3600;
    const me = props.data.kingdomid?.kd_id;
    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const set = (name, value) => setOptions((previous) => ({ ...previous, [name]: value }));
    const onText = (event) => set(event.target.name, event.target.value);
    const blocked = recurringProblems(options, me, maxCut)[0];
    const entries = props.data.kingdom.recurring || [];

    const send = (path, body) => {
        const updateFunc = async () => authFetch(path, { method: "POST", body: JSON.stringify(body) })
            .then(safeJson).then((r) => setResults((previous) => previous.concat(r)));
        props.updateData(["kingdom"], [updateFunc]);
    };
    const submit = () => {
        send("api/recurring", { ...options, until: options.until ? new Date(options.until).toISOString() : null });
        setOptions(START);
    };
    const operationLabel = (entry) => entry.type === "siphon" ? "Siphon funds"
        : (INTEL_OPERATIONS.find((op) => op.value === entry.operation)?.label || entry.operation);

    return (
        <div className="schedule-repeating">
            <ResultToasts title="Repeating" results={results} setResults={setResults} />
            <p className="planner-hint-line">
                A repeating operation runs again by itself whenever a spy attempt is free: a siphon once its last siphon
                has run its {siphonHours} hours, intel once what it revealed runs out. Repeating operations get your spy
                attempts before the automatic rob, which only uses the ones left over.
            </p>
            <div className="planner-grid">
                <Panel title="Add a repeating operation">
                    <FieldRow label="What">
                        <div role="radiogroup" aria-label="What to repeat">
                            {[["siphon", "Siphon funds"], ["intel", "Gather intel"]].map(([value, label]) => (
                                <Form.Check key={value} inline type="radio" name="recurring-type" id={"recurring-type-" + value}
                                    label={label} checked={options.type === value} onChange={() => set("type", value)} />
                            ))}
                        </div>
                    </FieldRow>
                    <FieldRow label="Target" htmlFor="recurring-target">
                        {/* A repeating siphon on a teammate takes their money; intel on them does no harm. */}
                        <KingdomPicker id="recurring-target" data={props.data} value={options.target} onChange={(value) => set("target", value)}
                            harm={options.type === "siphon" ? "Siphoning their income" : null} />
                    </FieldRow>
                    {options.type === "intel" ? (
                        <FieldRow label="Operation" htmlFor="recurring-operation">
                            <Form.Select id="recurring-operation" size="sm" value={options.operation || ""} onChange={(e) => set("operation", e.target.value || null)}>
                                <option value="">Choose an operation</option>
                                {INTEL_OPERATIONS.map((op) => <option key={op.value} value={op.value}>{op.label}</option>)}
                            </Form.Select>
                        </FieldRow>
                    ) : null}
                    <FieldRow label="Drones to send" hint="A share of your drones at home each time it runs" htmlFor="recurring-drones_pct">
                        <AmountInput name="drones_pct" id="recurring-drones_pct" label="Drones to send" suffix="%" value={options.drones_pct} onChange={onText} max={100} />
                    </FieldRow>
                    <FieldRow label="Shield the drones" htmlFor="recurring-shielded">
                        <Form.Check type="switch" id="recurring-shielded" checked={options.shielded} onChange={(e) => set("shielded", e.target.checked)} />
                    </FieldRow>
                    {options.type === "intel" ? <>
                        <FieldRow label="Share with your galaxy" htmlFor="recurring-share">
                            <Form.Check type="switch" id="recurring-share" checked={options.share_to_galaxy} onChange={(e) => set("share_to_galaxy", e.target.checked)} />
                        </FieldRow>
                        {options.share_to_galaxy ? (
                            <FieldRow label="Your cut" hint={`0 shares it free; up to ${maxCut}% lists it on the galaxy's market`} htmlFor="recurring-cut">
                                <AmountInput name="cut" id="recurring-cut" label="Your cut" suffix="%" value={options.cut} onChange={onText} max={maxCut} />
                            </FieldRow>
                        ) : null}
                    </> : null}
                    <FieldRow label="Stop after this many failures in a row" hint="0 never stops" htmlFor="recurring-stop">
                        <AmountInput name="stop_after_fails" id="recurring-stop" label="Stop after this many failures in a row" value={options.stop_after_fails} onChange={onText} max={10} />
                    </FieldRow>
                    <FieldRow label="Stop at (optional)" htmlFor="recurring-until">
                        <Form.Control id="recurring-until" type="datetime-local" size="sm" value={options.until} onChange={(e) => set("until", e.target.value)} />
                    </FieldRow>
                    <Button onClick={submit} disabled={Boolean(blocked) || props.loading.kingdom} title={blocked}>Repeat it</Button>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>

                <Panel title={`Repeating now (${entries.length})`}>
                    {entries.length === 0 ? <p className="planner-hint-line">Nothing repeats yet.</p> : null}
                    {entries.map((entry) => (
                        <div key={entry.id} className="schedule-item">
                            <div className="schedule-item-head">
                                <div>
                                    <h3 className="panel-title">{operationLabel(entry)} on {entry.target_name || kdLabel(entry.target)}</h3>
                                    <div className="planner-hint-line">
                                        {displayPercent(entry.drones_pct)} of drones{entry.shielded ? ", shielded" : ""}
                                        {entry.share_to_galaxy ? `, shared${entry.cut ? ` for a ${entry.cut}% cut` : " free"}` : ""}
                                        {". "}Next: {new Date(entry.next).toLocaleString()}
                                        {entry.until ? `. Stops at ${new Date(entry.until).toLocaleString()}` : ""}
                                    </div>
                                    <div className="planner-hint-line">
                                        Ran {entry.runs || 0} times
                                        {entry.last ? `; last ${new Date(entry.last.time).toLocaleString()}: ${STATUS[entry.last.status] || entry.last.status}. ${entry.last.message}` : ""}
                                        {entry.fails ? ` (${entry.fails} failed in a row)` : ""}
                                    </div>
                                </div>
                                <Button variant="outline-danger" size="sm" onClick={() => send("api/recurring/cancel", { id: entry.id })} disabled={props.loading.kingdom}>Stop</Button>
                            </div>
                        </div>
                    ))}
                </Panel>
            </div>
        </div>
    );
}
