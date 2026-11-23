import React, { useState } from "react";
import Form from "react-bootstrap/Form";
import Button from "react-bootstrap/Button";
import { authFetch } from "../../auth";
import { ResultToasts, safeJson } from "../../components/results";
import { AmountInput } from "../../components/forms";
import { Panel, FieldRow } from "../../components/planner";

const WHEN = [
    { value: "attacked", label: "I am attacked" },
    { value: "spied", label: "I am spied on" },
    { value: "missiles", label: "Missiles hit me" },
    { value: "fuel_low", label: "My fuel will run out soon" },
];
const THEN = [
    { value: "settings", label: "Switch settings for a while" },
    { value: "spy_sender", label: "Spy on whoever did it" },
    { value: "missiles_sender", label: "Fire missiles at whoever did it" },
];
const SHIELDS = [["military", "Military"], ["spy", "Spy"], ["spy_radar", "Spy radar"], ["missiles", "Missiles"]];
const SPENDING = [["settle", "Settle"], ["structures", "Structures"], ["military", "Military"], ["engineers", "Engineers"]];
// The build targets a rule can switch: each is a whole split, so any box left empty is 0.
export const TARGETS = [["structures_target", "Structure targets"], ["units_target", "Unit targets"], ["projects_target", "Project targets"]];
const MISSILES = [["planet_busters", "Planet busters"], ["star_busters", "Star busters"], ["galaxy_busters", "Galaxy busters"]];
const INTEL = [
    { value: "spymilitary", label: "Spy on military" }, { value: "spykingdom", label: "Spy on kingdom" },
    { value: "spyshields", label: "Spy on shields" }, { value: "spydrones", label: "Spy on drones" },
    { value: "spyall", label: "Full infiltration (everything)" },
];
const START = {
    when: "attacked", lost_only: false, fuel_hours: "6", then: "settings", hours: "12", cooldown: "6",
    use: { shields: false, auto_spending: false, auto_attack_enabled: false, auto_rob_enabled: false,
        structures_target: false, units_target: false, projects_target: false },
    targets: { structures_target: {}, units_target: {}, projects_target: {} },
    shields: { military: "", spy: "", spy_radar: "", missiles: "" },
    spending: { settle: "", structures: "", military: "", engineers: "" },
    auto_attack_enabled: false, auto_rob_enabled: false,
    operation: "spymilitary", drones_pct: "", missiles: { planet_busters: "", star_busters: "", galaxy_busters: "" },
};

/** The request the server takes, from the form. */
export function ruleRequest(form) {
    const when = { kind: form.when, lost_only: form.lost_only };
    if (form.when === "fuel_low") when.hours = form.fuel_hours;
    let then = { kind: form.then };
    if (form.then === "settings") {
        const settings = {};
        if (form.use.shields) settings.shields = Object.fromEntries(Object.entries(form.shields).filter(([, v]) => v !== ""));
        if (form.use.auto_spending) settings.auto_spending = form.spending;
        if (form.use.auto_attack_enabled) settings.auto_attack_enabled = form.auto_attack_enabled;
        if (form.use.auto_rob_enabled) settings.auto_rob_enabled = form.auto_rob_enabled;
        TARGETS.forEach(([field]) => {
            if (form.use[field]) settings[field] = Object.fromEntries(Object.entries(form.targets[field]).filter(([, v]) => v !== ""));
        });
        then = { ...then, settings, hours: form.hours };
    } else if (form.then === "spy_sender") {
        then = { ...then, operation: form.operation, drones_pct: form.drones_pct };
    } else {
        then = { ...then, ...form.missiles };
    }
    return { when, then, cooldown_hours: form.cooldown };
}

/** The first thing wrong with the form, or null. The server still decides. */
export function ruleProblem(form) {
    if (form.when === "fuel_low" && form.then !== "settings") return "Low fuel has nobody to react against: switch settings instead";
    if (form.then === "settings") {
        if (!Object.values(form.use).some(Boolean)) return "Choose at least one setting to switch";
        const hours = parseFloat(form.hours);
        if (!(hours >= 0.5 && hours <= 72)) return "How long must be 0.5 to 72 hours";
        if (form.use.shields && Object.values(form.shields).every((v) => v === "")) return "Choose the shields to set";
        if (form.use.auto_spending && SPENDING.reduce((sum, [key]) => sum + (parseFloat(form.spending[key]) || 0), 0) > 100) {
            return "The spending shares add up to more than 100%";
        }
        for (const [field, name] of TARGETS) {
            if (form.use[field] && Object.values(form.targets[field]).reduce((sum, v) => sum + (parseFloat(v) || 0), 0) > 100) {
                return `The ${name.toLowerCase()} add up to more than 100%`;
            }
        }
    }
    if (form.then === "spy_sender") {
        const drones = parseFloat(form.drones_pct);
        if (!(drones > 0 && drones <= 100)) return "Send between 1% and 100% of your drones";
    }
    if (form.then === "missiles_sender" && !MISSILES.some(([key]) => parseInt(form.missiles[key], 10) > 0)) {
        return "Choose how many missiles to fire";
    }
    const cooldown = parseFloat(form.cooldown);
    if (!(cooldown >= 0 && cooldown <= 72)) return "Cooldown must be 0 to 72 hours";
    return null;
}

const pct = (share) => `${Math.round(share * 1000) / 10}%`;

/** One line saying what a stored rule does. */
export function describeRule(rule, prettyNames = {}) {
    const phrases = { attacked: "I am attacked", spied: "I am spied on", missiles: "missiles hit me" };
    const condition = rule.when.kind === "fuel_low" ? `my fuel will run out within ${rule.when.hours} hours`
        : (phrases[rule.when.kind] || rule.when.kind) + (rule.when.lost_only ? " and it works against me" : "");
    const then = rule.then;
    let action;
    if (then.kind === "settings") {
        const parts = [];
        const s = then.settings;
        if (s.shields) parts.push("shields " + Object.entries(s.shields).map(([k, v]) => `${SHIELDS.find(([key]) => key === k)?.[1] || k} ${pct(v)}`).join(", "));
        if (s.auto_spending) parts.push("spending " + SPENDING.map(([k, name]) => `${name} ${pct(s.auto_spending[k] || 0)}`).join(", "));
        if ("auto_attack_enabled" in s) parts.push(`auto attack ${s.auto_attack_enabled ? "on" : "off"}`);
        if ("auto_rob_enabled" in s) parts.push(`auto rob ${s.auto_rob_enabled ? "on" : "off"}`);
        TARGETS.forEach(([field, name]) => {
            if (!s[field]) return;
            const shares = Object.entries(s[field]).filter(([, v]) => v > 0).map(([k, v]) => `${prettyNames[k] || k} ${pct(v)}`);
            parts.push(`${name.toLowerCase()} ${shares.length ? shares.join(", ") : "all 0%"}`);
        });
        action = `switch ${parts.join("; ")} for ${then.hours} hours`;
    } else if (then.kind === "spy_sender") {
        action = `${(INTEL.find((op) => op.value === then.operation)?.label || then.operation).toLowerCase()} on whoever did it, with ${then.drones_pct}% of drones`;
    } else {
        action = "fire " + MISSILES.filter(([key]) => then[key] > 0).map(([key, name]) => `${then[key]} ${name.toLowerCase()}`).join(", ") + " at whoever did it";
    }
    return `When ${condition}: ${action}.`;
}

/** The Schedule page's Reactions tab (issue #35). */
export function Reactions(props) {
    const [form, setForm] = useState(START);
    const [results, setResults] = useState([]);
    const set = (name, value) => setForm((previous) => ({ ...previous, [name]: value }));
    const setIn = (group, name, value) => setForm((previous) => ({ ...previous, [group]: { ...previous[group], [name]: value } }));
    const blocked = ruleProblem(form);
    const rules = props.data.kingdom.rules || [];
    const prettyNames = props.data.state?.pretty_names || {};
    const setTarget = (field, key, value) => setForm((previous) => ({
        ...previous, targets: { ...previous.targets, [field]: { ...previous.targets[field], [key]: value } } }));

    const send = (path, body) => {
        const updateFunc = async () => authFetch(path, { method: "POST", body: JSON.stringify(body) })
            .then(safeJson).then((r) => setResults((previous) => previous.concat(r)));
        props.updateData(["kingdom"], [updateFunc]);
    };
    const submit = () => { send("api/rules", ruleRequest(form)); setForm(START); };

    return (
        <div className="schedule-reactions">
            <ResultToasts title="Reactions" results={results} setResults={setResults} />
            <p className="planner-hint-line">
                A reaction is a rule for when something happens to you while you are away. It fires once for each new
                event, and not again within its cooldown.
            </p>
            <div className="planner-grid">
                <Panel title="Add a reaction">
                    <FieldRow label="When" htmlFor="rule-when">
                        <Form.Select id="rule-when" size="sm" value={form.when} onChange={(e) => set("when", e.target.value)}>
                            {WHEN.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
                        </Form.Select>
                    </FieldRow>
                    {form.when === "fuel_low" ? (
                        <FieldRow label="Fuel left, in hours" hint="At your fuel income now" htmlFor="rule-fuel-hours">
                            <AmountInput name="fuel_hours" id="rule-fuel-hours" label="Fuel left, in hours" value={form.fuel_hours} onChange={(e) => set("fuel_hours", e.target.value)} max={72} />
                        </FieldRow>
                    ) : (
                        <FieldRow label="Only when it works against me" htmlFor="rule-lost-only">
                            <Form.Check type="switch" id="rule-lost-only" checked={form.lost_only} onChange={(e) => set("lost_only", e.target.checked)} />
                        </FieldRow>
                    )}
                    <FieldRow label="Then" htmlFor="rule-then">
                        <Form.Select id="rule-then" size="sm" value={form.then} onChange={(e) => set("then", e.target.value)}>
                            {THEN.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </Form.Select>
                    </FieldRow>
                    {form.then === "settings" ? <>
                        <FieldRow label="Shields" htmlFor="rule-use-shields">
                            <Form.Check type="switch" id="rule-use-shields" checked={form.use.shields} onChange={(e) => setIn("use", "shields", e.target.checked)} />
                        </FieldRow>
                        {form.use.shields ? SHIELDS.map(([key, name]) => (
                            <FieldRow key={key} label={`${name} shields`} hint="Leave empty to keep it" htmlFor={`rule-shield-${key}`}>
                                <AmountInput name={key} id={`rule-shield-${key}`} label={`${name} shields`} suffix="%" value={form.shields[key]} onChange={(e) => setIn("shields", key, e.target.value)} max={100} />
                            </FieldRow>
                        )) : null}
                        <FieldRow label="Auto spending" htmlFor="rule-use-spending">
                            <Form.Check type="switch" id="rule-use-spending" checked={form.use.auto_spending} onChange={(e) => setIn("use", "auto_spending", e.target.checked)} />
                        </FieldRow>
                        {form.use.auto_spending ? SPENDING.map(([key, name]) => (
                            <FieldRow key={key} label={`${name} share`} htmlFor={`rule-spending-${key}`}>
                                <AmountInput name={key} id={`rule-spending-${key}`} label={`${name} share`} suffix="%" value={form.spending[key]} onChange={(e) => setIn("spending", key, e.target.value)} max={100} />
                            </FieldRow>
                        )) : null}
                        {[["auto_attack_enabled", "Auto attack"], ["auto_rob_enabled", "Auto rob"]].map(([key, name]) => (
                            <FieldRow key={key} label={name} htmlFor={`rule-use-${key}`}>
                                <Form.Check type="switch" id={`rule-use-${key}`} label="Change it" checked={form.use[key]} onChange={(e) => setIn("use", key, e.target.checked)} />
                                {form.use[key] ? <Form.Check type="switch" id={`rule-${key}`} label={form[key] ? "On" : "Off"} checked={form[key]} onChange={(e) => set(key, e.target.checked)} /> : null}
                            </FieldRow>
                        ))}
                        {TARGETS.map(([field, name]) => (
                            <React.Fragment key={field}>
                                <FieldRow label={name} hint="The whole split: boxes left empty are 0%" htmlFor={`rule-use-${field}`}>
                                    <Form.Check type="switch" id={`rule-use-${field}`} checked={form.use[field]} onChange={(e) => setIn("use", field, e.target.checked)} />
                                </FieldRow>
                                {form.use[field] ? Object.keys(props.data.kingdom[field] || {}).map((key) => (
                                    <FieldRow key={key} label={prettyNames[key] || key} htmlFor={`rule-${field}-${key}`}>
                                        <AmountInput name={key} id={`rule-${field}-${key}`} label={`${prettyNames[key] || key} ${name.toLowerCase()}`} suffix="%"
                                            value={form.targets[field][key] ?? ""} onChange={(e) => setTarget(field, key, e.target.value)} max={100} />
                                    </FieldRow>
                                )) : null}
                            </React.Fragment>
                        ))}
                        <FieldRow label="For how many hours" hint="Then they go back, except any you changed yourself" htmlFor="rule-hours">
                            <AmountInput name="hours" id="rule-hours" label="For how many hours" value={form.hours} onChange={(e) => set("hours", e.target.value)} max={72} />
                        </FieldRow>
                    </> : null}
                    {form.then === "spy_sender" ? <>
                        <FieldRow label="Operation" htmlFor="rule-operation">
                            <Form.Select id="rule-operation" size="sm" value={form.operation} onChange={(e) => set("operation", e.target.value)}>
                                {INTEL.map((op) => <option key={op.value} value={op.value}>{op.label}</option>)}
                            </Form.Select>
                        </FieldRow>
                        <FieldRow label="Drones to send" htmlFor="rule-drones">
                            <AmountInput name="drones_pct" id="rule-drones" label="Drones to send" suffix="%" value={form.drones_pct} onChange={(e) => set("drones_pct", e.target.value)} max={100} />
                        </FieldRow>
                    </> : null}
                    {form.then === "missiles_sender" ? MISSILES.map(([key, name]) => (
                        <FieldRow key={key} label={name} htmlFor={`rule-missile-${key}`}>
                            <AmountInput name={key} id={`rule-missile-${key}`} label={name} value={form.missiles[key]} onChange={(e) => setIn("missiles", key, e.target.value)} />
                        </FieldRow>
                    )) : null}
                    {form.then !== "settings" ? <p className="planner-hint-line">Only when you know who it was: an attack always says, a spy operation only when it failed or your spy radar caught it.</p> : null}
                    <FieldRow label="Cooldown, in hours" hint="It will not fire again sooner" htmlFor="rule-cooldown">
                        <AmountInput name="cooldown" id="rule-cooldown" label="Cooldown, in hours" value={form.cooldown} onChange={(e) => set("cooldown", e.target.value)} max={72} />
                    </FieldRow>
                    <Button onClick={submit} disabled={Boolean(blocked) || props.loading.kingdom} title={blocked || undefined}>Add reaction</Button>
                    {blocked ? <div className="planner-why">{blocked}</div> : null}
                </Panel>

                <Panel title={`Your reactions (${rules.length})`}>
                    {rules.length === 0 ? <p className="planner-hint-line">No reactions yet.</p> : null}
                    {rules.map((rule) => (
                        <div key={rule.id} className="schedule-item">
                            <div className="schedule-item-head">
                                <div>
                                    <div>{describeRule(rule, prettyNames)}</div>
                                    <div className="planner-hint-line">
                                        Fired {rule.state?.fires || 0} times
                                        {rule.state?.last ? `; last ${new Date(rule.state.last.time).toLocaleString()}: ${rule.state.last.outcome}` : ""}
                                        {rule.state?.until ? `. Settings go back at ${new Date(rule.state.until).toLocaleString()}` : ""}
                                    </div>
                                </div>
                                <Button variant="outline-danger" size="sm" onClick={() => send("api/rules/cancel", { id: rule.id })} disabled={props.loading.kingdom}>Remove</Button>
                            </div>
                        </div>
                    ))}
                </Panel>
            </div>
        </div>
    );
}
