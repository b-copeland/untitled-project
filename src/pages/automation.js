import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Form from "react-bootstrap/Form";
import Tab from "react-bootstrap/Tab";
import Tabs from "react-bootstrap/Tabs";
import { authFetch } from "../auth";
import { ResultToasts, safeJson } from "../components/results";
import HelpButton from "../components/helpbutton";
import { displayPercent } from "../format";
import { Spending } from "./home/spending";
import { AllocateStructures } from "./build/structures";
import { Allocate as UnitTargets, trainableUnits } from "./build/military";
import { Allocate as ProjectTargets } from "./build/projects";
import { AutoAttack, AutoRob } from "./conquer/primitives";
import { Queue } from "./conquer/schedule";
import { useProjectsFollowKingdom } from "../data/gameData";
import "./automation.css";

/** The Project targets tab shows each project's bonus and time left, so it keeps them current while it is open. */
function ProjectTargetsTab({ data, loading, updateData }) {
    useProjectsFollowKingdom(data.kingdom, updateData);
    return (
        <ProjectTargets state={data.state} kdInfo={data.kingdom} engineersInfo={data.engineers || {}}
            projectsInfo={data.projects || {}} loading={loading} updateData={updateData} />
    );
}

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
            links: [["spending", "Spending split"], ["structures", "Structure targets"], ["units", "Unit targets"]],
        },
        {
            key: "projects", title: "Engineers on projects", path: "api/projects/target",
            enabled: !!kingdom.auto_assign_projects,
            what: "Sends new engineers to the projects you picked.",
            summary: "Follows your project targets",
            links: [["projects", "Project targets"]],
        },
        {
            key: "attack", title: "Attack primitives", path: "api/attackprimitives/auto",
            enabled: !!kingdom.auto_attack_enabled,
            what: "Sends a share of your army against primitives whenever generals are free.",
            summary: attack.pure || attack.flex
                ? `Sends ${displayPercent(attack.pure || 0)} of attackers and ${displayPercent(attack.flex || 0)} of flexers`
                : "Set the share of units to send first",
            needs: !(attack.pure || attack.flex) && "Set the share of units to send before turning this on",
            links: [["primitives", "Attack settings"]],
        },
        {
            key: "rob", title: "Rob primitives", path: "api/robprimitives/auto",
            enabled: !!kingdom.auto_rob_enabled,
            what: "Sends drones to rob primitives, keeping some spy attempts back.",
            summary: rob.drones
                ? `Sends ${displayPercent(rob.drones)} of drones${rob.shielded ? " shielded" : ""}, keeps ${rob.keep || 0} spy attempts`
                : "Set the share of drones to send first",
            needs: !rob.drones && "Set the share of drones to send before turning this on",
            links: [["primitives", "Rob settings"]],
        },
        {
            key: "schedule", title: "Scheduled actions",
            what: "Attacks, spying and missiles you queued for a set time.",
            summary: queued ? `${queued} waiting` : "Nothing queued",
            links: queued ? [["schedule", "See the queue"], ["/schedule", "Schedule something"]] : [["/schedule", "Schedule something"]],
        },
    ];
}

// The tabs after the overview: each automatic feature's settings, the same forms as on their own pages.
const TABS = [
    ["spending", "Spending"],
    ["structures", "Structure targets"],
    ["units", "Unit targets"],
    ["projects", "Project targets"],
    ["primitives", "Primitives"],
    ["schedule", "Schedule"],
];

/** The overview: every automatic feature, whether it is on, what it will do, and the tab with its settings. */
function Overview({ data, loading, updateData, openTab }) {
    const [results, setResults] = useState([]);
    const items = automations(data.kingdom);
    const switches = items.filter((item) => item.path);
    const active = switches.filter((item) => item.enabled).length;

    const toggle = (item, enabled) => {
        const updateFunc = () => authFetch(item.path, { method: "post", body: JSON.stringify({ enabled }) })
            .then(safeJson).then((r) => setResults((previous) => previous.concat(r)));
        updateData(["kingdom"], [updateFunc]);
    };

    return (
        <div className="automation">
            <p className="automation-lead">
                {active} of {switches.length} automatic features are on. Turn them on or off here; the tabs above
                hold their settings.
            </p>
            <div className="automation-items" data-tour="automation-items">
            {items.map((item) => (
                <section className="automation-item" key={item.key} aria-label={item.title}>
                    <div className="automation-head">
                        <h3>{item.title}</h3>
                        {item.path ? (
                            <Form.Check type="switch" id={"automation-" + item.key} label={item.enabled ? "On" : "Off"}
                                aria-label={item.title} checked={item.enabled}
                                disabled={!!loading?.kingdom || (!item.enabled && !!item.needs)}
                                onChange={(event) => toggle(item, event.target.checked)} />
                        ) : null}
                    </div>
                    <p className="automation-what">{item.what}</p>
                    <p className="automation-summary">{item.summary}</p>
                    {item.needs && !item.enabled ? <p className="automation-needs">{item.needs}</p> : null}
                    <p className="automation-links">
                        {item.links.map(([to, label]) => (to.startsWith("/")
                            ? <Link key={label} to={to}>{label}</Link>
                            : <button key={label} type="button" className="btn btn-link automation-tab-link" onClick={() => openTab(to)}>{label}</button>))}
                    </p>
                </section>
            ))}
            </div>
            <ResultToasts title="Automation" results={results} setResults={setResults} />
        </div>
    );
}

/** The Automation page: the overview, then a tab for each feature's settings, so nothing needs another page. */
function Automation(props) {
    const [params, setParams] = useSearchParams();
    const tab = TABS.some(([key]) => key === params.get("tab")) ? params.get("tab") : "overview";
    const openTab = (key) => setParams(key === "overview" ? {} : { tab: key }, { replace: true });
    const { data, loading, updateData } = props;
    const shared = { data, loading, updateData };
    const units = data.mobis && Object.keys(data.mobis).length ? trainableUnits(data.mobis, data.state) : [];

    return (
        <>
            <Tabs id="automation-tabs" data-tour="automation-tabs" activeKey={tab} onSelect={(key) => openTab(key)} variant="tabs" mountOnEnter>
                <Tab eventKey="overview" title="Overview"><Overview {...shared} openTab={openTab} /></Tab>
                <Tab eventKey="spending" title="Spending">
                    <Spending kingdom={data.kingdom} loading={loading} updateData={updateData} />
                </Tab>
                <Tab eventKey="structures" title="Structure targets"><AllocateStructures {...shared} /></Tab>
                <Tab eventKey="units" title="Unit targets">
                    {units.length ? <UnitTargets units={units} kdInfo={data.kingdom} mobisInfo={data.mobis} loading={loading} updateData={updateData} /> : null}
                </Tab>
                <Tab eventKey="projects" title="Project targets">
                    <ProjectTargetsTab {...shared} />
                </Tab>
                <Tab eventKey="primitives" title="Primitives">
                    <div className="panel-grid automation-primitives">
                        <AutoAttack {...shared} />
                        <AutoRob {...shared} />
                    </div>
                </Tab>
                <Tab eventKey="schedule" title="Schedule">
                    <Queue {...shared} />
                    <div className="form-actions"><Link className="btn btn-outline-primary" to="/schedule">Schedule something</Link></div>
                </Tab>
            </Tabs>
            <HelpButton scrollTarget={"automation"} />
        </>
    );
}

export default Automation;
