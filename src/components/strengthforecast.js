import React, { useState } from "react";
import Table from "react-bootstrap/Table";
import { authFetch } from "../auth";
import { displayPercent } from "../format";
import { NumberControl } from "./forms";
import { safeJson } from "./results";
import { Panel, FieldRow, clockUntil, useServerForecast } from "./planner";
import { horizonLabel, wholeNumber } from "./forecast";
import "./strengthforecast.css";

/*
 * Offense and defense over time (POST /api/strengthforecast): as generals come home, as training lands, and both
 * together. ``target`` is another kingdom's id, or left out for your own kingdom. The military shields and military
 * efficiency start at what the kingdom has (as far as you know it, else the most there can be) and can be changed to see
 * what they would do. Every number is the server's.
 */

const TIMELINES = [
    ["generals", "As generals come home"],
    ["production", "As training lands"],
    ["combined", "Generals and training together"],
];

const ROWS = [["offense", "Offense"], ["defense", "Defense"], ["generals_home", "Generals home"]];

function ask(plan) {
    return authFetch("api/strengthforecast", { method: "POST", body: JSON.stringify(plan) }).then(safeJson);
}

/** A column's heading: now, the time until a general is home, or a forecast horizon. */
function heading(point, cfg) {
    if (point.kind === "general") {
        return <>{clockUntil(point.time)}<small className="strength-kind">general home</small></>;
    }
    if (point.kind === "horizon") {
        return horizonLabel(point.epochs, cfg);
    }
    return "Now";
}

function Timeline({ points, cfg, title }) {
    return (
        <div className="strength-timeline">
            <h4>{title}</h4>
            <div className="table-scroll">
                <Table hover size="sm" className="strength-table">
                    <thead>
                        <tr>
                            <th />
                            {points.map((point, index) => <th key={index} style={{textAlign: "right"}}>{heading(point, cfg)}</th>)}
                        </tr>
                    </thead>
                    <tbody>
                        {ROWS.map(([key, label]) => (
                            <tr key={key}>
                                <td style={{textAlign: "left"}}>{label}</td>
                                {points.map((point, index) => <td key={index} style={{textAlign: "right"}}>{wholeNumber(point[key])}</td>)}
                            </tr>
                        ))}
                    </tbody>
                </Table>
            </div>
        </div>
    );
}

/** Where a setting's number comes from, as a status tag. Your own kingdom's values need no tag. */
function tagOf(typed, known, other) {
    if (typed !== "") return "estimate";
    if (!other) return undefined;
    return known === null || known === undefined ? "needed" : "revealed";
}

export function StrengthForecast({ target, state }) {
    const cfg = state?.game_config || {};
    const [values, setValues] = useState({ shields: "", military_bonus: "" });
    const other = target !== undefined && target !== null;
    const plan = { ...(other ? { target: String(target) } : {}), ...values };
    const [answer, pending] = useServerForecast(plan, ask, 500);
    const onChange = (event) => setValues({ ...values, [event.target.name]: event.target.value });

    const setting = (name, label, assumed) => {
        const info = answer[name] || {};
        const tag = tagOf(values[name], info.known, other);
        const hint = info.max !== undefined ? `Up to ${displayPercent(info.max)}` : undefined;
        return (
            <FieldRow label={label} hint={tag === "needed" ? assumed : hint} status={tag} htmlFor={`strength-${name}`}>
                <div className="attack-buffer">
                    <NumberControl id={`strength-${name}`} name={name} size="sm" placeholder={info.value !== undefined ? String(Math.round(info.value * 1000) / 10) : ""}
                        autoComplete="off" value={values[name]} onChange={onChange} /><span>%</span>
                </div>
            </FieldRow>
        );
    };

    const timelines = answer.timelines || {};
    return (
        <Panel title="Strength over time" className="strength-forecast">
            <div className="strength-settings">
                {setting("shields", "Military shields", "Not revealed: the most there can be")}
                {setting("military_bonus", "Military efficiency", "Not revealed: the most there can be")}
            </div>
            {answer.message ? <p className="page-note">{answer.message}</p> : null}
            {answer.fuelless ? <p className="page-note">Out of fuel: weaker until it has fuel again.</p> : null}
            {other && answer.timelines && !answer.fuel_known ? <p className="planner-hint-line">Fuel not revealed: counted as having fuel.</p> : null}
            {TIMELINES.map(([key, title]) => (timelines[key] ? <Timeline key={key} points={timelines[key]} cfg={cfg} title={title} /> : null))}
            {other && answer.timelines && !answer.production_known
                ? <p className="planner-hint-line">Spy on production to see their training as it lands.</p> : null}
            {pending ? <p className="planner-hint-line">Updating…</p> : null}
        </Panel>
    );
}
