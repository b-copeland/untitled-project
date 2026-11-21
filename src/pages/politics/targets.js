import React, { useState } from "react";
import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import Modal from "react-bootstrap/Modal";
import Tab from "react-bootstrap/Tab";
import Tabs from "react-bootstrap/Tabs";
import { BsXLg } from "react-icons/bs";
import { authFetch } from "../../auth";
import { GameTable } from "../../components/gametable";
import { NumberControl, SubmitButton } from "../../components/forms";
import { IconButton } from "../../components/iconbutton";
import { Panel, Picker, Stats } from "../../components/planner";
import { ResultToasts, safeJson } from "../../components/results";
import { displayNumber, displayPercent } from "../../format";
import { checkDecimal, checkPercent, firstError } from "../../validation";
import Attack from "../conquer/attack.js";
import Spy from "../conquer/spy.js";
import LaunchMissiles from "../conquer/launchmissiles.js";
import "./targets.css";

/*
 * The empire's targets (api/untitledapp/targets.py), on the Empire page under Politics. A target is a kingdom of an empire
 * yours is at war with, and actions on it count only while that war lasts. Every member sees the targets,
 * what each is marked for, its spoils fund and who has earned what; the emperor and their delegates also add, change
 * and remove targets, and the emperor names the delegates. A fund is paid out only when its target ends. Points, funds and limits all come from the server
 * (`data.empiretargets`).
 */

const myKd = (data) => String(data.kingdomid?.kd_id ?? data.kingdom?.kdId ?? "");
const kdName = (data, kdId) => data.kingdoms?.[kdId] || `Kingdom ${kdId}`;
const kdLabel = (data, kdId) => `${kdName(data, kdId)} (${data.galaxies_inverted?.[kdId] || "?"})`;
const dateText = (iso) => (iso ? new Date(iso).toLocaleString() : "");

/** The kingdoms that can be targeted: in an empire yours is at war with (``targets.at_war_with``). */
export const warKingdoms = (data, targets) => {
    const enemies = (targets.at_war_with || []).map(String);
    return Object.entries(data.empires_inverted?.empires_inverted || {})
        .filter(([, kdEmpire]) => enemies.includes(String(kdEmpire)))
        .map(([kdId]) => String(kdId));
};

/** The kingdoms in the player's empire. */
export const empireKingdoms = (data, empire) =>
    Object.entries(data.empires_inverted?.empires_inverted || {})
        .filter(([, kdEmpire]) => String(kdEmpire) === String(empire))
        .map(([kdId]) => String(kdId));

/** "0.01 points a civilian, 1 point a star" for an action at a multiplier. */
export function pointsText(action, multiplier = 1) {
    return (action?.points || [])
        .map((measure) => {
            const points = measure.points * multiplier;
            return `${+points.toPrecision(3)} point${points === 1 ? "" : "s"} a ${measure.name}`;
        })
        .join(", ");
}

/** Where each marked action is done, as a button: the planner it opens, and the operation it starts with. */
const ACTION_BUTTONS = {
    successful_attacks: { label: "Attack", open: "attack" },
    failed_attacks: { label: "Attack", open: "attack" },
    missiles: { label: "Launch missiles", open: "missiles" },
    intel: { label: "Spy for intel", open: "spy" },
    kidnap: { label: "Kidnap", open: "spy", operation: "kidnappopulation" },
    bomb_homes: { label: "Bomb homes", open: "spy", operation: "bombhomes" },
    sabotage_fuel_plants: { label: "Sabotage fuel plants", open: "spy", operation: "sabotagefuelplants" },
};

/** The buttons a target's marked actions call for, without repeats (both kinds of attack open the Attack planner). */
export function actionButtons(target) {
    const seen = new Set();
    return Object.keys(target.actions || {})
        .map((key) => ACTION_BUTTONS[key])
        .filter((button) => {
            if (!button) return false;
            const id = button.open + (button.operation || "");
            if (seen.has(id)) return false;
            seen.add(id);
            return true;
        });
}

/** The problems with a target form, field by field, mirroring the server's limits. */
export function targetFormErrors(form, targets) {
    const errors = { fund_share: checkPercent(form.fund_share, { max: (targets.max_fund_share || 0) * 100 }) };
    const chosen = Object.entries(form.actions || {}).filter(([, value]) => value.on);
    for (const [key, value] of chosen) {
        errors[key] = checkDecimal(value.multiplier, { max: targets.max_multiplier || 0 });
    }
    errors.none = chosen.length ? null : "Mark the target for at least one action";
    return errors;
}

const actionsBody = (form) => Object.fromEntries(
    Object.entries(form.actions || {})
        .filter(([, value]) => value.on)
        .map(([key, value]) => [key, value.multiplier === "" || value.multiplier === undefined ? 1 : parseFloat(value.multiplier)]),
);

const formFor = (target, targets) => ({
    actions: Object.fromEntries((targets.actions || []).map((action) => [action.key, {
        on: target ? action.key in (target.actions || {}) : false,
        multiplier: target && action.key in (target.actions || {}) ? String(target.actions[action.key]) : "1",
    }])),
    fund_share: String(+(((target ? target.fund_share : targets.default_fund_share) || 0) * 100).toFixed(2)),
});

/** Which actions to mark a target for, each with its points multiplier, and the fund's share of attacks. */
function TargetFields({ form, setForm, targets, errors, idPrefix }) {
    const setAction = (key, change) => setForm((previous) => ({
        ...previous, actions: { ...previous.actions, [key]: { ...previous.actions[key], ...change } },
    }));
    return (
        <>
            <GameTable
                className="game-table targets-actions-table"
                rows={(targets.actions || []).map((action) => ({ ...action }))}
                columns={[
                    {
                        header: "Mark for", align: "left",
                        cell: (row) => (
                            <Form.Check id={`${idPrefix}-${row.key}`} type="checkbox" label={row.name} title={row.desc}
                                checked={Boolean(form.actions[row.key]?.on)}
                                onChange={(event) => setAction(row.key, { on: event.target.checked })} />
                        ),
                    },
                    {
                        header: "Points x", className: "targets-multiplier",
                        cell: (row) => (
                            <>
                                <NumberControl size="sm" inputMode="decimal" aria-label={`${row.name} points multiplier`}
                                    value={form.actions[row.key]?.multiplier ?? ""} disabled={!form.actions[row.key]?.on}
                                    isInvalid={Boolean(errors[row.key])}
                                    onChange={(event) => setAction(row.key, { multiplier: event.target.value })} />
                                <Form.Control.Feedback type="invalid">{errors[row.key]}</Form.Control.Feedback>
                            </>
                        ),
                    },
                    {
                        header: "Earns", align: "left",
                        cell: (row) => pointsText(row, parseFloat(form.actions[row.key]?.multiplier) || 0),
                    },
                ]}
            />
            <Form.Group className="targets-fund-share">
                <Form.Label htmlFor={`${idPrefix}-fund-share`}>Spoils fund share of successful attacks</Form.Label>
                <div className="targets-fund-share-input">
                    <NumberControl id={`${idPrefix}-fund-share`} size="sm" inputMode="decimal" value={form.fund_share}
                        isInvalid={Boolean(errors.fund_share)}
                        onChange={(event) => setForm((previous) => ({ ...previous, fund_share: event.target.value }))} />
                    <span>%</span>
                    <Form.Control.Feedback type="invalid">{errors.fund_share}</Form.Control.Feedback>
                </div>
            </Form.Group>
        </>
    );
}

function AddTarget({ data, targets, members, send, loading }) {
    const [target, setTarget] = useState(undefined);
    const [form, setForm] = useState(() => formFor(null, targets));
    // Kingdoms already targets, or removed too recently to be marked again (``removed``: kingdom to when it can be), are not offered.
    const taken = new Set((targets.targets || []).map((item) => String(item.target))
        .concat(Object.keys(targets.removed || {}).filter((kdId) => Date.parse(targets.removed[kdId]) > Date.now())));
    const options = warKingdoms(data, targets)
        .filter((kdId) => !members.includes(kdId) && !taken.has(kdId))
        .map((kdId) => ({ value: kdId, label: kdLabel(data, kdId) }));
    const errors = targetFormErrors(form, targets);
    const noWar = (targets.at_war_with || []).length ? null
        : "Your empire is not at war. Only kingdoms of an empire you are at war with can be targets";
    const full = (targets.targets || []).length >= (targets.max_targets || 0)
        ? `Your empire can have at most ${targets.max_targets} target(s): one per galaxy in it` : null;
    const blocked = noWar || full || (target ? null : "Choose a kingdom to target") || firstError(errors);
    const submit = (event) => {
        event.preventDefault();
        send("add", { target, actions: actionsBody(form), fund_share: form.fund_share }, () => setTarget(undefined));
    };
    return (
        <Form onSubmit={submit} className="targets-form">
            <Form.Label htmlFor="targets-new-target">Kingdom</Form.Label>
            <Picker id="targets-new-target" options={options} value={target} onChange={setTarget} placeholder="Choose a kingdom" />
            <TargetFields form={form} setForm={setForm} targets={targets} errors={errors} idPrefix="targets-new" />
            <SubmitButton loading={loading} blocked={blocked}>Mark as a target</SubmitButton>
            {blocked && (target || noWar) ? <p className="planner-why">{blocked}</p> : null}
        </Form>
    );
}

function EditTarget({ target, targets, send, loading }) {
    const [form, setForm] = useState(() => formFor(target, targets));
    const errors = targetFormErrors(form, targets);
    const submit = (event) => {
        event.preventDefault();
        send(`${target.target}/update`, { actions: actionsBody(form), fund_share: form.fund_share });
    };
    return (
        <Form onSubmit={submit} className="targets-form">
            <TargetFields form={form} setForm={setForm} targets={targets} errors={errors} idPrefix={`targets-${target.target}`} />
            <SubmitButton loading={loading} blocked={firstError(errors)}>Save changes</SubmitButton>
        </Form>
    );
}

function Leadership({ target, targets, send, loading }) {
    const [confirming, setConfirming] = useState(false);
    const fund = `${displayNumber(target.fund?.stars)} stars and ${displayNumber(target.fund?.money)} money`;
    return (
        <div className="targets-leadership">
            <div className="targets-buttons">
                {confirming
                    ? <>
                        <span className="targets-confirm">
                            Remove {target.name}? Its fund ({fund}) is paid out to the participants now, and it can not
                            be marked again for {targets.remark_cooldown_hours} hours.
                        </span>
                        <Button className="game-button" variant="danger" disabled={loading}
                            onClick={() => { setConfirming(false); send(`${target.target}/remove`, {}); }}>
                            Remove
                        </Button>
                        <Button className="game-button" variant="secondary" onClick={() => setConfirming(false)}>Keep</Button>
                    </>
                    : <Button className="game-button" variant="outline-danger" disabled={loading} onClick={() => setConfirming(true)}>
                        Remove target
                    </Button>}
            </div>
            <details className="targets-edit">
                <summary>Change what it is marked for</summary>
                <EditTarget key={JSON.stringify([target.actions, target.fund_share])} target={target} targets={targets}
                    send={send} loading={loading} />
            </details>
        </div>
    );
}

function TargetCard({ target, targets, data, send, loading, open }) {
    const catalog = Object.fromEntries((targets.actions || []).map((action) => [action.key, action]));
    return (
        <Panel title={`${target.name} (${target.galaxy || "?"})`} className="targets-card">
            <Stats items={[
                { label: "Spoils fund", value: `${displayNumber(target.fund?.stars)} stars, ${displayNumber(target.fund?.money)} money` },
                { label: "Fund share of attacks", value: displayPercent(target.fund_share || 0) },
                { label: "Your points", value: `${displayNumber(target.my_points)} (${displayPercent(target.my_share || 0)})` },
                { label: "Its land and money if it dies", value: `${displayPercent(target.remains_share || 0)} to the fund` },
                { label: "Intel shared", value: Object.keys(target.intel || {}).join(", ") || "None" },
            ]} />
            {target.at_war === false ? (
                <p className="planner-why">
                    Your empire is not at war with this kingdom's empire, so nothing done to it counts. Remove it to pay
                    out its fund.
                </p>
            ) : null}
            <ul className="targets-marked">
                {Object.entries(target.actions || {}).map(([key, multiplier]) => (
                    <li key={key}><strong>{catalog[key]?.name || key}</strong>: {pointsText(catalog[key], multiplier)}</li>
                ))}
            </ul>
            <div className="targets-buttons">
                {actionButtons(target).map((button) => (
                    <Button key={button.label} size="sm" variant="primary" className="game-button"
                        onClick={() => open(button.open, target.target, button.operation)}>
                        {button.label}
                    </Button>
                ))}
            </div>
            <GameTable
                className="game-table targets-table"
                rows={(target.participants || []).map((row) => ({ ...row, key: row.kd_id }))}
                rowClassName={(row) => (String(row.kd_id) === myKd(data) ? "targets-row-mine" : undefined)}
                columns={[
                    { header: "Participant", align: "left", cell: (row) => row.name },
                    { header: "Points", cell: (row) => displayNumber(row.points) },
                    { header: "Share", cell: (row) => displayPercent(row.share || 0) },
                    { header: "Paid out", cell: (row) => `${displayNumber(row.paid?.stars)} stars, ${displayNumber(row.paid?.money)} money` },
                ]}
            >
                {(target.participants || []).length ? null : (
                    <tr><td colSpan={4} style={{ textAlign: "left" }}>Nobody has earned points on this target yet.</td></tr>
                )}
            </GameTable>
            {targets.can_manage ? <Leadership target={target} targets={targets} send={send} loading={loading} /> : null}
        </Panel>
    );
}

function Delegates({ data, targets, members, send, loading }) {
    const [choice, setChoice] = useState(undefined);
    const current = (targets.delegates || []).map((delegate) => String(delegate.kd_id));
    const options = members.filter((kdId) => kdId !== myKd(data) && !current.includes(kdId))
        .map((kdId) => ({ value: kdId, label: kdLabel(data, kdId) }));
    const full = current.length >= (targets.max_delegates || 0) ? `You can name at most ${targets.max_delegates} delegate(s)` : null;
    const save = (delegates, after) => send("delegates", { delegates }, after);
    return (
        <>
            <GameTable
                rows={(targets.delegates || []).map((delegate) => ({ ...delegate, key: delegate.kd_id }))}
                columns={[
                    { header: "Delegate", align: "left", cell: (row) => kdLabel(data, row.kd_id) },
                    {
                        header: "", cell: (row) => (
                            <IconButton icon={BsXLg} label={`Remove ${row.name} as a delegate`} disabled={loading}
                                onClick={() => save(current.filter((kdId) => kdId !== String(row.kd_id)))} />
                        ),
                    },
                ]}
            >
                {current.length ? null : <tr><td colSpan={2} style={{ textAlign: "left" }}>No delegates yet.</td></tr>}
            </GameTable>
            <Form className="targets-form" onSubmit={(event) => { event.preventDefault(); save(current.concat(choice), () => setChoice(undefined)); }}>
                <Form.Label htmlFor="targets-new-delegate">Name a delegate</Form.Label>
                <Picker id="targets-new-delegate" options={options} value={choice} onChange={setChoice} placeholder="Choose a kingdom in your empire" />
                <SubmitButton loading={loading} blocked={full || (choice ? null : "Choose a kingdom")}>Add delegate</SubmitButton>
            </Form>
        </>
    );
}

const OUTCOMES = { killed: "Destroyed", removed: "Removed", war_ended: "War ended" };

function History({ targets }) {
    const catalog = Object.fromEntries((targets.actions || []).map((action) => [action.key, action]));
    const rows = (targets.history || []).map((record, index) => ({ ...record, key: `${record.target}-${record.ended_at}-${index}` }));
    const paid = (record, key) => Object.values(record.paid || {}).reduce((sum, part) => sum + (part[key] || 0), 0);
    return (
        <GameTable
            className="game-table targets-table"
            rows={rows}
            columns={[
                { header: "Target", align: "left", cell: (row) => row.name },
                { header: "Marked for", align: "left", cell: (row) => Object.keys(row.actions || {}).map((key) => catalog[key]?.name || key).join(", ") },
                { header: "Ended", align: "left", cell: (row) => dateText(row.ended_at) },
                { header: "Outcome", align: "left", cell: (row) => OUTCOMES[row.reason] || "Removed" },
                { header: "Paid out", cell: (row) => `${displayNumber(paid(row, "stars"))} stars, ${displayNumber(paid(row, "money"))} money` },
                { header: "Left the game", cell: (row) => `${displayNumber(row.lost?.stars)} stars, ${displayNumber(row.lost?.money)} money` },
                {
                    header: "Top participants", align: "left",
                    cell: (row) => (row.participants || []).slice(0, 3).map((participant) => participant.name).join(", ") || "Nobody",
                },
            ]}
        >
            {rows.length ? null : <tr><td colSpan={7} style={{ textAlign: "left" }}>No target has ended yet.</td></tr>}
        </GameTable>
    );
}

/** The Attack, Spy or Launch Missiles planner in a dialog, opened on a target. */
function PlannerModal({ planner, data, loading, updateData, onHide }) {
    const titles = { attack: "Attack", spy: "Spy", missiles: "Launch Missiles" };
    const shared = { data, loading, updateData, initialKd: planner?.target };
    return (
        <Modal show={Boolean(planner)} onHide={onHide} animation={false} dialogClassName="attack-modal">
            <Modal.Header closeButton><Modal.Title>{planner ? titles[planner.open] : ""}</Modal.Title></Modal.Header>
            <Modal.Body>
                {planner?.open === "attack" ? <Attack {...shared} /> : null}
                {planner?.open === "spy" ? <Spy {...shared} initialOperation={planner.operation} /> : null}
                {planner?.open === "missiles" ? <LaunchMissiles {...shared} /> : null}
            </Modal.Body>
            <Modal.Footer><Button variant="secondary" onClick={onHide}>Close</Button></Modal.Footer>
        </Modal>
    );
}

export default function Targets(props) {
    const [results, setResults] = useState([]);
    const [planner, setPlanner] = useState(null);
    const targets = props.data.empiretargets || {};
    const loading = Boolean(props.loading.empiretargets);
    if (!targets.empire) {
        if (loading) return <p className="targets">Loading...</p>;
        return <p className="targets">Your galaxy is not in an empire. An empire's emperor marks targets for its members to take apart together.</p>;
    }
    const members = empireKingdoms(props.data, targets.empire);
    const send = (route, body, after) => {
        const request = () => authFetch("api/empiretargets/" + route, { method: "POST", body: JSON.stringify(body) })
            .then(safeJson).then((result) => {
                setResults((previous) => previous.concat(result));
                if (after && result.status === "success") after();
            });
        props.updateData(["empiretargets", "kingdom"], [request]);
    };
    const role = targets.is_emperor ? "Emperor" : targets.can_manage ? "Delegate" : "Member";
    const list = targets.targets || [];
    return (
        <div className="targets">
            <ResultToasts title="Targets" results={results} setResults={setResults} />
            <PlannerModal planner={planner} data={props.data} loading={props.loading} updateData={props.updateData}
                onHide={() => setPlanner(null)} />
            <Stats items={[
                { label: "Targets", value: `${list.length} of ${targets.max_targets}` },
                { label: "Your role", value: role },
                { label: "Funds paid out", value: "When the target ends" },
                { label: "Most stars a kingdom gets from a target", value: `${displayPercent(targets.max_payout_stars_share || 0)} of its land` },
            ]} />
            <Tabs id="targets-tabs" defaultActiveKey="targets" justify fill variant="tabs">
                <Tab eventKey="targets" title={`Targets (${list.length})`}>
                    {list.length ? list.map((target) => (
                        <TargetCard key={target.target} target={target} targets={targets} data={props.data}
                            send={send} loading={loading}
                            open={(open, kdId, operation) => setPlanner({ open, target: kdId, operation })} />
                    )) : <p className="targets-empty">Your empire has no targets right now.</p>}
                </Tab>
                {targets.can_manage ? (
                    <Tab eventKey="manage" title="Manage">
                        <Panel title="Mark a new target"
                            hint="Targets are kingdoms of empires you are at war with. A target's fund is paid out when it ends: when you remove it, when it dies, or when the war ends. A kingdom you remove can not be marked again for a while. Members earn points for the actions you mark, by the damage they do. Successful attacks put the fund share of their stars and money into the target's spoils fund, missiles every star they destroy, and the target's death its remaining stars and money.">
                            <AddTarget data={props.data} targets={targets} members={members} send={send} loading={loading} />
                        </Panel>
                        {targets.is_emperor ? (
                            <Panel title="Delegates" hint="Delegates manage targets with you. Only you name them.">
                                <Delegates data={props.data} targets={targets} members={members} send={send} loading={loading} />
                            </Panel>
                        ) : null}
                    </Tab>
                ) : null}
                <Tab eventKey="history" title="History">
                    <History targets={targets} />
                </Tab>
            </Tabs>
        </div>
    );
}
