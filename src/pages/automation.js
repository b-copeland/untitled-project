import React, { useState } from "react";
import { Link } from "react-router-dom";
import Form from "react-bootstrap/Form";
import { authFetch } from "../auth";
import Header from "../components/header";
import { ResultToasts, safeJson } from "../components/results";
import { displayPercent } from "../format";
import "./automation.css";

const SPENDING_NAMES = { settle: "settling", structures: "structures", military: "military", engineers: "engineers" };

/** "60.0% military, 20.0% structures", biggest first, leaving out what gets nothing. */
export function spendingSummary(spending = {}) {
    const parts = Object.entries(spending)
        .filter(([, share]) => share > 0)
        .sort((a, b) => b[1] - a[1])
        .map(([key, share]) => `${displayPercent(share)} ${SPENDING_NAMES[key] || key}`);
    return parts.length ? parts.join(", ") : "No share set for anything yet";
}

/** Everything the kingdom does by itself, as one list: whether it is on, what it will do, and where to change it. */
export function automations(kingdom) {
    const attack = kingdom.auto_attack_settings || {};
    const rob = kingdom.auto_rob_settings || {};
    const queued = (kingdom.schedule || []).length;
    return [
        {
            key: "spending", title: "Auto spending", path: "api/spending",
            enabled: !!kingdom.auto_spending_enabled,
            what: "Spends your funding on settling, structures, military and engineers, towards the targets you set.",
            summary: spendingSummary(kingdom.auto_spending),
            links: [["/status", "Spending split"], ["/structures", "Structure targets"], ["/military", "Unit targets"]],
        },
        {
            key: "projects", title: "Engineers on projects", path: "api/projects/target",
            enabled: !!kingdom.auto_assign_projects,
            what: "Sends new engineers to the projects you picked.",
            summary: "Follows your project targets",
            links: [["/projects", "Project targets"]],
        },
        {
            key: "attack", title: "Attack primitives", path: "api/attackprimitives/auto",
            enabled: !!kingdom.auto_attack_enabled,
            what: "Sends a share of your army against primitives whenever generals are free.",
            summary: attack.pure || attack.flex
                ? `Sends ${displayPercent(attack.pure || 0)} of attackers and ${displayPercent(attack.flex || 0)} of flexers`
                : "Set the share of units to send first",
            needs: !(attack.pure || attack.flex) && "Set the share of units to send before turning this on",
            links: [["/primitives", "Attack settings"]],
        },
        {
            key: "rob", title: "Rob primitives", path: "api/robprimitives/auto",
            enabled: !!kingdom.auto_rob_enabled,
            what: "Sends drones to rob primitives, keeping some spy attempts back.",
            summary: rob.drones
                ? `Sends ${displayPercent(rob.drones)} of drones${rob.shielded ? " shielded" : ""}, keeps ${rob.keep || 0} spy attempts`
                : "Set the share of drones to send first",
            needs: !rob.drones && "Set the share of drones to send before turning this on",
            links: [["/primitives", "Rob settings"]],
        },
        {
            key: "schedule", title: "Scheduled actions",
            what: "Attacks, spying and missiles you queued for a set time.",
            summary: queued ? `${queued} waiting` : "Nothing queued",
            links: [["/schedule", queued ? "See the queue" : "Schedule something"]],
        },
    ];
}

function Automation(props) {
    const [results, setResults] = useState([]);
    const kingdom = props.data.kingdom;
    const items = automations(kingdom);
    const switches = items.filter((item) => item.path);
    const active = switches.filter((item) => item.enabled).length;

    const toggle = (item, enabled) => {
        const updateFunc = () => authFetch(item.path, { method: "post", body: JSON.stringify({ enabled }) })
            .then(safeJson).then((r) => setResults((previous) => previous.concat(r)));
        props.updateData(["kingdom"], [updateFunc]);
    };

    return (
        <>
            <Header data={props.data} />
            <div className="automation">
                <h2>Automation</h2>
                <p className="automation-lead">
                    {active} of {switches.length} automatic features are on. Turn them on or off here; each
                    links to the page where its settings live.
                </p>
                {items.map((item) => (
                    <section className="automation-item" key={item.key} aria-label={item.title}>
                        <div className="automation-head">
                            <h3>{item.title}</h3>
                            {item.path ? (
                                <Form.Check type="switch" id={"automation-" + item.key} label={item.enabled ? "On" : "Off"}
                                    aria-label={item.title} checked={item.enabled}
                                    disabled={!!props.loading?.kingdom || (!item.enabled && !!item.needs)}
                                    onChange={(event) => toggle(item, event.target.checked)} />
                            ) : null}
                        </div>
                        <p className="automation-what">{item.what}</p>
                        <p className="automation-summary">{item.summary}</p>
                        {item.needs && !item.enabled ? <p className="automation-needs">{item.needs}</p> : null}
                        <p className="automation-links">
                            {item.links.map(([to, label]) => <Link key={label} to={to}>{label}</Link>)}
                        </p>
                    </section>
                ))}
            </div>
            <ResultToasts title="Automation" results={results} setResults={setResults} />
        </>
    );
}

export default Automation;
