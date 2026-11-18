import React, { useEffect, useRef, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';
import { useNavigate } from "react-router-dom";
import { BsEye, BsClipboardData } from "react-icons/bs";
import "./intel.css";
import Kingdom from "../kingdominfo.js";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { IconButton } from "../../components/iconbutton";
import { Panel, FieldRow, Picker, clockUntil } from "../../components/planner";
import { displayPercent } from "../../format";
import { checkCount, checkPercent, firstError } from "../../validation";

/*
 * The galaxy's intel market (api/untitledapp/intel.py): bounties asking for intel, listings selling it, and the intel
 * you can list or share free. Every rule (who may take what, at what cut) is the server's: each listing and bounty
 * comes with ``problem``, the reason this kingdom could not take it, or null.
 *
 * The pieces take an optional ``target`` so the same tables and forms can show one kingdom's intel (KingdomIntel),
 * wherever a kingdom is shown. With ``onView(kdId, tab)`` the tables offer to open a row's kingdom (KingdomModal, on
 * its "kingdom" or "intel" tab); with ``onAttempt(kdId, operation)`` a bounty you have no intel for offers the spy
 * operation that would get it (by default the Spy page, opened with that target and operation).
 *
 * The kingdom view (kingdominfo.js) takes ``intelActions(category, inline)``: IntelActions for each kind of intel, to
 * spy for it, buy it or ask the galaxy for it when you do not have it, and to share it when you do.
 */

const EMPTY = { listings: [], bounties: [], accepted: [], cuts: {}, my_intel: [], exclusions: [], history: [] };

export function intelOf(data) {
    return { ...EMPTY, ...(data.intel && Array.isArray(data.intel.listings) ? data.intel : {}) };
}

const config = (data) => data.state?.game_config || {};
const maxCutPercent = (data) => (config(data).BASE_MAX_SHARE_CUT || 0) * 100;
const kdName = (data, kdId) => data.kingdoms?.[kdId] || `Kingdom ${kdId}`;
const kdLabel = (data, kdId) => `${kdName(data, kdId)} (${data.galaxies_inverted?.[kdId] || "?"})`;
const myKd = (data) => String(data.kingdomid?.kd_id ?? data.kingdom?.kdId ?? "");
const myGalaxymates = (data) => (data.galaxies?.[data.galaxies_inverted?.[myKd(data)]] || []).map(String);
const forTarget = (items, target) => (target === undefined ? items : items.filter((item) => String(item.target) === String(target)));
const categoriesOf = (data) => (data.state?.reveal_operations || []).map((operation) => operation.replace(/^spy/, ""));
const sameTarget = (item, target) => String(item.target) === String(target);
/** The longest a bounty stays up, in hours (players are not shown epochs). */
const bountyMaxHours = (data) => (config(data).BASE_INTEL_BOUNTY_MAX_EPOCHS || 0) * (config(data).BASE_EPOCH_SECONDS || 0) / 3600;

const TABLE_CLASS = "game-table intel-table";

/** The tables' buttons to open a row's kingdom, on its info or its intel, when the page can show it. */
function ViewButton({ onView, kdId }) {
    return onView ? <>
        <IconButton icon={BsEye} label="View kingdom" onClick={() => onView(kdId, "kingdom")} />
        <IconButton icon={BsClipboardData} label="Intel on this kingdom" onClick={() => onView(kdId, "intel")} />
    </> : null;
}

/** Spy for a bounty's intel: the operation that reveals ``category`` on ``target``. */
function AttemptButton({ target, category, onAttempt, loading, label = "Attempt",
    title = `You have no ${category} intel on them: spy for it, then fulfil the bounty` }) {
    const navigate = useNavigate();
    const operation = "spy" + category;
    const attempt = onAttempt || ((kdId, op) => navigate("/spy", { state: { kdId: String(kdId), operation: op } }));
    return (
        <Button size="sm" variant="outline-primary" className="intel-action" disabled={loading}
            title={title}
            onClick={() => attempt(target, operation)}>
            {label}
        </Button>
    );
}

/** Sends an intel action and keeps the answer for a toast. */
function useIntelAction(props, setResults) {
    return (route, body, keys = ["intel"]) => {
        const updateFunc = () => authFetch("api/intel/" + route, { method: "POST", body: JSON.stringify(body) })
            .then(safeJson).then((r) => setResults((previous) => previous.concat(r)));
        props.updateData(keys, [updateFunc]);
    };
}

function Action({ children, problem, onClick, loading, variant = "primary" }) {
    return (
        <Button size="sm" variant={variant} className="intel-action" onClick={onClick}
            disabled={Boolean(problem) || loading} title={problem || undefined}>
            {children}
        </Button>
    );
}

function CutBox({ id, value, onChange, error }) {
    return (
        <span className="intel-cut">
            <Form.Control id={id} size="sm" inputMode="decimal" placeholder="0" autoComplete="off" aria-label="Cut"
                value={value} onChange={(e) => onChange(e.target.value)} isInvalid={Boolean(error)} />
            <span>%</span>
        </span>
    );
}

/** List one of your intel (``item``, from ``my_intel``) for a cut, share it free, or take its listing down. */
function ShareControls({ item, send, data, loading }) {
    const [value, setValue] = useState("");
    const key = `${item.target}.${item.category}`;
    const error = checkPercent(value, { max: maxCutPercent(data) });
    const positive = parseFloat(value) > 0;
    return (
        <>
            <CutBox id={`cut-${key}`} value={value} onChange={setValue} error={error} />
            <Action loading={loading.intel} problem={error || (positive ? null : "Enter a cut to list it, or share it free")}
                onClick={() => send("share", { target: item.target, category: item.category, cut: value })}>List</Action>
            <Action variant="outline-light" loading={loading.intel}
                onClick={() => send("share", { target: item.target, category: item.category, cut: 0 }, ["intel", "revealed"])}>Share free</Action>
            {item.listing ? <Action variant="outline-danger" loading={loading.intel}
                onClick={() => send("delist", { listing: item.listing })}>Remove</Action> : null}
        </>
    );
}

/** The intel this kingdom has revealed, each with a cut box, List and Share free. */
export function YourIntelTable({ target, send, onView, ...props }) {
    const intel = intelOf(props.data);
    const rows = forTarget(intel.my_intel, target).map((item) => ({ ...item, key: `${item.target}.${item.category}` }));
    if (rows.length === 0) {
        return <p className="planner-hint-line">{target === undefined ? "You have no intel of your own to share." : "You have no intel of your own on this kingdom."}</p>;
    }
    const columns = [
        ...(target === undefined ? [{ header: "Kingdom", align: "left", cell: (row) => kdLabel(props.data, row.target) }] : []),
        { header: "Intel", align: "left", cell: (row) => row.category },
        { header: "Ends in", cell: (row) => clockUntil(row.time) },
        {
            header: "Listed", cell: (row) => (row.received ? <span className="text-muted" title="Intel shared with you can not be passed on">received</span>
                : row.listing ? displayPercent(row.cut) : "--"),
        },
        {
            header: "Share", align: "left", cell: (row) => {
                if (row.received) return <span className="intel-share"><span className="text-muted">can not be passed on</span><ViewButton onView={onView} kdId={row.target} /></span>;
                return (
                    <span className="intel-share">
                        <ShareControls item={row} send={send} data={props.data} loading={props.loading} />
                        <ViewButton onView={onView} kdId={row.target} />
                    </span>
                );
            },
        },
    ];
    return <GameTable className={TABLE_CLASS} columns={columns} rows={rows} />;
}

/** Whether this kingdom already has ``category`` intel on ``target`` from a galaxymate. */
const taken = (intel, target, category) => intel.accepted.some((item) => String(item.target) === String(target) && item.category === category);

/** Listings on the market, each with Buy (or Remove for your own). Intel you have already taken is shaded. */
export function ListingsTable({ target, send, onView, ...props }) {
    const intel = intelOf(props.data);
    const rows = forTarget(intel.listings, target).map((item) => ({ ...item, key: item.id }));
    if (rows.length === 0) {
        return <p className="planner-hint-line">No intel {target === undefined ? "" : "on this kingdom "}is listed by your galaxymates.</p>;
    }
    const me = myKd(props.data);
    const columns = [
        { header: "Seller", align: "left", cell: (row) => kdName(props.data, row.seller) },
        ...(target === undefined ? [{ header: "Kingdom", align: "left", cell: (row) => kdLabel(props.data, row.target) }] : []),
        {
            header: "Intel", align: "left", cell: (row) => <>{row.category}{taken(intel, row.target, row.category)
                ? <span className="status-tag tag-optional" title="You already have this intel from a galaxymate">taken</span> : null}</>,
        },
        { header: "Cut", cell: (row) => displayPercent(row.cut) },
        { header: "Ends in", cell: (row) => clockUntil(row.time) },
        {
            header: "", align: "left", cell: (row) => (
                <span className="intel-share">
                    {String(row.seller) === me
                        ? <Action variant="outline-danger" loading={props.loading.intel} onClick={() => send("delist", { listing: row.id })}>Remove</Action>
                        : <Action loading={props.loading.intel} problem={row.problem} onClick={() => send("buy", { listing: row.id }, ["intel", "revealed"])}>Buy</Action>}
                    <ViewButton onView={onView} kdId={row.target} />
                </span>
            ),
        },
    ];
    return <GameTable className={TABLE_CLASS} columns={columns} rows={rows}
        rowClassName={(row) => (taken(intel, row.target, row.category) ? "intel-row-taken" : undefined)} />;
}

/**
 * Open bounties, each with Fulfil (or Withdraw for your own). A bounty for intel you do not have offers Attempt
 * instead, the spy operation that would get it.
 */
export function BountiesTable({ target, send, onView, onAttempt, ...props }) {
    const intel = intelOf(props.data);
    const rows = forTarget(intel.bounties, target).map((item) => ({ ...item, key: item.id }));
    if (rows.length === 0) {
        return <p className="planner-hint-line">No open bounties{target === undefined ? "" : " for this kingdom"}.</p>;
    }
    const me = myKd(props.data);
    const columns = [
        { header: "Asked by", align: "left", cell: (row) => kdName(props.data, row.requester) },
        ...(target === undefined ? [{ header: "Kingdom", align: "left", cell: (row) => kdLabel(props.data, row.target) }] : []),
        { header: "Intel", align: "left", cell: (row) => row.category },
        { header: "Cut", cell: (row) => displayPercent(row.cut) },
        { header: "Ends in", cell: (row) => clockUntil(row.time) },
        {
            header: "", align: "left", cell: (row) => (
                <span className="intel-share">
                    {String(row.requester) === me
                        ? <Action variant="outline-danger" loading={props.loading.intel} onClick={() => send("cancelbounty", { bounty: row.id })}>Withdraw</Action>
                        : row.have === false
                        ? <AttemptButton target={row.target} category={row.category} onAttempt={onAttempt} loading={props.loading.intel} />
                        : <Action loading={props.loading.intel} problem={row.problem} onClick={() => send("fulfil", { bounty: row.id })}>Fulfil</Action>}
                    <ViewButton onView={onView} kdId={row.target} />
                </span>
            ),
        },
    ];
    return <GameTable className={TABLE_CLASS} columns={columns} rows={rows} />;
}

/**
 * The form to ask the galaxy for intel. With ``target`` it asks about that kingdom only. ``ask`` ({category, key}, a new
 * key each time) fills in the intel asked for from the kingdom view, and brings the form into sight.
 */
export function BountyForm({ target, send, ask, ...props }) {
    const [chosen, setChosen] = useState(target);
    const [category, setCategory] = useState(ask?.category);
    const [cut, setCut] = useState("");
    const [hours, setHours] = useState("");
    const form = useRef(null);
    const askKey = ask?.key;
    useEffect(() => {
        if (askKey !== undefined) {
            setCategory(ask.category);
            form.current?.scrollIntoView?.({ behavior: "smooth", block: "center" });
            form.current?.querySelector("#bounty-cut")?.focus();
        }
    }, [askKey]);  // eslint-disable-line react-hooks/exhaustive-deps
    const maxHours = bountyMaxHours(props.data);
    const mates = new Set(myGalaxymates(props.data));
    const kingdomOptions = Object.keys(props.data.kingdoms || {}).filter((kdId) => !mates.has(String(kdId)))
        .map((kdId) => ({ value: kdId, label: kdLabel(props.data, kdId) }));
    const categoryOptions = categoriesOf(props.data).map((name) => ({ value: name, label: name }));
    const cutError = checkPercent(cut, { max: maxCutPercent(props.data) });
    const hoursError = checkCount(hours, { max: maxHours, noun: "hours" });
    const blocked = firstError(
        chosen === undefined ? "Choose a kingdom" : null,
        category === undefined ? "Choose the intel you want" : null,
        cutError,
        hoursError,
        String(hours).trim() !== "" && !(parseFloat(hours) > 0) ? "A bounty stays up for at least 1 hour" : null,
    );
    return (
        <div className="intel-form" ref={form}>
            {target === undefined ? (
                <FieldRow label="Kingdom" htmlFor="bounty-kingdom">
                    <Picker id="bounty-kingdom" options={kingdomOptions} value={chosen} onChange={setChosen} placeholder="Choose a kingdom" />
                </FieldRow>
            ) : null}
            <FieldRow label="Intel" htmlFor="bounty-category">
                <Picker id="bounty-category" options={categoryOptions} value={category} onChange={setCategory} placeholder="Choose" searchable={false} />
            </FieldRow>
            <FieldRow label="Cut you offer" hint={`Of your spoils from each win, at most ${maxCutPercent(props.data)}%`} htmlFor="bounty-cut">
                <CutBox id="bounty-cut" value={cut} onChange={setCut} error={cutError} />
                {cutError ? <div className="amount-input-error">{cutError}</div> : null}
            </FieldRow>
            <FieldRow label="Stays up for" hint={`Hours, 1 to ${maxHours}; blank for ${maxHours}`} htmlFor="bounty-hours">
                <span className="intel-cut">
                    <Form.Control id="bounty-hours" size="sm" inputMode="numeric" placeholder={String(maxHours)} autoComplete="off" className="intel-hours"
                        value={hours} onChange={(e) => setHours(e.target.value)} isInvalid={Boolean(hoursError)} />
                    <span>hours</span>
                </span>
                {hoursError ? <div className="amount-input-error">{hoursError}</div> : null}
            </FieldRow>
            <Button size="sm" disabled={Boolean(blocked) || props.loading.intel} title={blocked || undefined}
                onClick={() => send("bounty", { target: chosen, category, cut: cut === "" ? 0 : cut, ...(String(hours).trim() === "" ? {} : { hours }) })}>Post bounty</Button>
            {blocked ? <div className="planner-why">{blocked}</div> : null}
        </div>
    );
}

/** The intel this kingdom has taken from galaxymates, and what it gives up for it per target. */
export function AcceptedTable({ target, ...props }) {
    const intel = intelOf(props.data);
    const rows = forTarget(intel.accepted, target).map((item) => ({ ...item, key: `${item.target}.${item.category}` }));
    if (rows.length === 0) {
        return <p className="planner-hint-line">You have taken no intel from galaxymates{target === undefined ? "" : " on this kingdom"}.</p>;
    }
    const columns = [
        ...(target === undefined ? [{ header: "Kingdom", align: "left", cell: (row) => kdLabel(props.data, row.target) }] : []),
        { header: "Intel", align: "left", cell: (row) => row.category },
        { header: "From", align: "left", cell: (row) => kdName(props.data, row.sharer) },
        { header: "Cut", cell: (row) => (row.cut > 0 ? displayPercent(row.cut) : "free") },
        { header: "All cuts on it", cell: (row) => displayPercent(intel.cuts[row.target] || 0) },
        { header: "Ends in", cell: (row) => clockUntil(row.time) },
    ];
    return <GameTable className={TABLE_CLASS} columns={columns} rows={rows} />;
}

/** Recent purchases, fulfilled bounties and free shares, of the given ``kinds``. */
export function HistoryTable({ kinds, ...props }) {
    const rows = intelOf(props.data).history.filter((item) => kinds.includes(item.kind)).map((item, i) => ({ ...item, key: i }));
    if (rows.length === 0) {
        return <p className="planner-hint-line">Nothing yet.</p>;
    }
    const columns = [
        { header: "When", align: "left", cell: (row) => `${clockUntil(row.time)} ago` },
        {
            header: "What", align: "left", cell: (row) => (row.kind === "free"
                ? `${kdName(props.data, row.from)} shared free with the galaxy`
                : row.kind === "purchase" ? `${kdName(props.data, row.to)} bought from ${kdName(props.data, row.from)}`
                : `${kdName(props.data, row.from)} answered ${kdName(props.data, row.to)}`),
        },
        { header: "Kingdom", align: "left", cell: (row) => kdLabel(props.data, row.target) },
        { header: "Intel", align: "left", cell: (row) => row.category },
        { header: "Cut", cell: (row) => (row.cut > 0 ? displayPercent(row.cut) : "free") },
    ];
    return <GameTable className={TABLE_CLASS} columns={columns} rows={rows} />;
}

/** Which galaxymates may not see or take your intel. */
export function ExclusionsForm({ send, ...props }) {
    const intel = intelOf(props.data);
    const me = myKd(props.data);
    const mates = myGalaxymates(props.data).filter((kdId) => kdId !== me);
    const saved = intel.exclusions.map(String);
    const savedKey = saved.join(",");
    const [excluded, setExcluded] = useState(saved);
    useEffect(() => setExcluded(savedKey ? savedKey.split(",") : []), [savedKey]);
    if (mates.length === 0) {
        return <p className="planner-hint-line">You have no galaxymates.</p>;
    }
    const toggle = (kdId) => setExcluded(excluded.includes(kdId) ? excluded.filter((k) => k !== kdId) : excluded.concat(kdId));
    const unchanged = [...excluded].sort().join(",") === [...saved].sort().join(",");
    return (
        <div className="intel-form">
            {mates.map((kdId) => (
                <Form.Check key={kdId} type="switch" id={`exclude-${kdId}`} label={kdName(props.data, kdId)}
                    checked={excluded.includes(kdId)} onChange={() => toggle(kdId)} />
            ))}
            <Button size="sm" className="mt-2" disabled={unchanged || props.loading.intel} title={unchanged ? "Nothing changed" : undefined}
                onClick={() => send("exclusions", { excluded })}>Save</Button>
        </div>
    );
}

/**
 * One kingdom's details, as far as you have revealed them (the server filters them). It asks again when your reveals
 * of it change (a purchase, a free share, a spy). ``actions`` is passed on as the view's ``intelActions``.
 */
export function KingdomView({ kdId, data, actions }) {
    const [info, setInfo] = useState(undefined);
    const reveals = JSON.stringify(data.revealed?.revealed?.[kdId] || {});
    useEffect(() => {
        let current = true;
        authFetch("api/kingdom/" + kdId).then(safeJson).then((r) => { if (current) setInfo(r); });
        return () => { current = false; };
    }, [kdId, reveals]);
    if (info === undefined) {
        return <h3>Loading...</h3>;
    }
    return <Kingdom intelActions={actions}
        data={{ kingdom: info, kingdoms: data.kingdoms, galaxies_inverted: data.galaxies_inverted, shields: data.shields, state: data.state, kdId }} />;
}

/**
 * What you can do about one kind of intel on ``target``, for the kingdom view. Without it: spy for it, buy the
 * cheapest listing you can take, or ask the galaxy (``onAsk(category)``). With intel of your own: share it (inline,
 * since the view is itself shown in a dialog). Intel a galaxymate gave you can not be passed on. ``inline`` is the
 * short form, next to a single value.
 */
export function IntelActions({ target, category, inline = false, send, onAsk, onAttempt, ...props }) {
    const [sharing, setSharing] = useState(false);
    if (!tradable(props.data, target)) {
        return null;
    }
    const intel = intelOf(props.data);
    const me = myKd(props.data);
    const mine = intel.my_intel.find((item) => sameTarget(item, target) && item.category === category);
    const asked = intel.bounties.find((item) => String(item.requester) === me && sameTarget(item, target) && item.category === category);
    const forSale = intel.listings.filter((item) => sameTarget(item, target) && item.category === category && item.problem === null)
        .sort((a, b) => a.cut - b.cut)[0];
    const loading = props.loading.intel;
    let content;
    if (mine?.received) {
        if (inline) return null;
        content = <span className="text-muted">A galaxymate gave you this intel; it can not be passed on.</span>;
    } else if (mine) {
        content = <>
            {inline ? null : <span className="text-muted">Your {category} intel lasts {clockUntil(mine.time)}{mine.listing ? `, listed at ${displayPercent(mine.cut)}` : ""}.</span>}
            <Button size="sm" variant="outline-light" className="intel-action" onClick={() => setSharing(!sharing)} aria-expanded={sharing}>
                {sharing ? "Close" : `Share ${category} intel`}
            </Button>
            {sharing ? <span className="intel-share"><ShareControls item={mine} send={send} data={props.data} loading={props.loading} /></span> : null}
        </>;
    } else {
        content = <>
            {inline ? null : <span className="text-muted">No {category} intel on them.</span>}
            <AttemptButton target={target} category={category} onAttempt={onAttempt} loading={loading} label={`Spy on ${category}`}
                title={`Open the Spy page with spy on ${category} chosen`} />
            {forSale ? <Action variant="outline-primary" loading={loading} onClick={() => send("buy", { listing: forSale.id }, ["intel", "revealed"])}>
                Buy it ({displayPercent(forSale.cut)})</Action> : null}
            {asked
                ? <span className="text-muted">You asked for it ({displayPercent(asked.cut)})</span>
                : <Action variant="outline-primary" loading={loading} onClick={() => onAsk(category)}>Ask the galaxy</Action>}
        </>;
    }
    return <div className={"intel-actions" + (inline ? " inline" : "")}>{content}</div>;
}

/** The kingdom view's ``intelActions`` for ``target``, with these props (data, loading, send, onAsk, onAttempt). */
const intelActionsFor = (props) => (category, inline) => <IntelActions {...props} category={category} inline={inline} />;

/** Everything about one kingdom's intel: yours to share, what is on the market, bounties, and asking for more. */
/**
 * Everything about one kingdom's intel. ``onView`` switches to the kingdom's info (KingdomModal's other tab); without
 * it the info opens here. ``ask`` fills in the bounty form (see BountyForm).
 */
export function KingdomIntel({ onView, ask: askedFor, ...props }) {
    const [results, setResults] = useState([]);
    const [viewing, setViewing] = useState(false);
    const [askedHere, setAskedHere] = useState(null);
    const send = useIntelAction(props, setResults);
    const shared = { ...props, send };
    const ask = askedFor ?? askedHere;
    if (props.loading.intel && !props.data.intel?.listings) {
        return <h3>Loading...</h3>;
    }
    const onAsk = (category) => { setAskedHere({ category, key: Date.now() }); setViewing(false); };
    return (
        <div className="kingdom-intel">
            <ResultToasts title="Intel" results={results} setResults={setResults} />
            <div className="kingdom-intel-head">
                <h4>Intel on {kdName(props.data, props.target)}</h4>
                <Button size="sm" variant="outline-light" onClick={() => (onView ? onView() : setViewing(!viewing))} aria-expanded={onView ? undefined : viewing}>
                    {viewing ? "Hide kingdom" : "View kingdom"}
                </Button>
            </div>
            {viewing ? <Panel><KingdomView kdId={props.target} data={props.data} actions={intelActionsFor({ ...shared, onAsk })} /></Panel> : null}
            <Panel title="Your intel"><YourIntelTable {...shared} /></Panel>
            <Panel title="On the market"><ListingsTable {...shared} /></Panel>
            <Panel title="Bounties"><BountiesTable {...shared} /></Panel>
            <Panel title="Ask the galaxy for intel" className="intel-form-panel"><BountyForm {...shared} ask={ask} /></Panel>
            <Panel title="Intel you have taken"><AcceptedTable {...shared} /></Panel>
        </div>
    );
}

/** Whether intel on ``kdId`` can be traded here: not your own kingdom, nor a galaxymate. */
export function tradable(data, kdId) {
    return kdId !== undefined && kdId !== null && !myGalaxymates(data).includes(String(kdId)) && String(kdId) !== myKd(data);
}

/**
 * One kingdom in a dialog, on two tabs: its info (the View dialogs) and its intel (KingdomIntel), opened on ``tab``.
 * Asking the galaxy from the info moves to the intel with the bounty form filled in; View kingdom on the intel moves
 * back. A kingdom whose intel can not be traded (yours, a galaxymate's) shows only its info.
 */
export function KingdomModal({ show, onHide, target, tab = "kingdom", ...props }) {
    const [active, setActive] = useState(tab);
    const [ask, setAsk] = useState(null);
    const [results, setResults] = useState([]);
    const send = useIntelAction(props, setResults);
    useEffect(() => {
        if (show) {
            setActive(tab);
            setAsk(null);
        }
    }, [show, target, tab]);
    const withIntel = tradable(props.data, target);
    const onAsk = (category) => { setAsk({ category, key: Date.now() }); setActive("intel"); };
    const view = target !== undefined
        ? <KingdomView kdId={target} data={props.data} actions={withIntel ? intelActionsFor({ ...props, target, send, onAsk }) : undefined} />
        : null;
    return (
        <Modal show={show} onHide={onHide} animation={false} dialogClassName="intel-modal">
            <Modal.Header closeButton><Modal.Title>{target !== undefined ? kdLabel(props.data, target) : ""}</Modal.Title></Modal.Header>
            <Modal.Body>
                <ResultToasts title="Intel" results={results} setResults={setResults} />
                {withIntel ? (
                    <Tabs id="kingdom-modal-tabs" activeKey={active} onSelect={(key) => setActive(key)} justify className="kingdom-modal-tabs">
                        <Tab eventKey="kingdom" title="Kingdom info">{view}</Tab>
                        <Tab eventKey="intel" title="Intel market">
                            <KingdomIntel {...props} target={target} ask={ask} onView={() => setActive("kingdom")} />
                        </Tab>
                    </Tabs>
                ) : view}
            </Modal.Body>
            <Modal.Footer><Button variant="secondary" onClick={onHide}>Close</Button></Modal.Footer>
        </Modal>
    );
}

/** KingdomModal opened on the kingdom's intel, for the tables that list kingdoms. */
export function IntelModal(props) {
    return <KingdomModal {...props} tab="intel" />;
}

/**
 * One line on a planner page about intel on the chosen target: the cuts you already give up on it, and what the
 * market has. It opens KingdomIntel in place (these pages are themselves shown in dialogs, so not another dialog).
 */
export function TargetIntel({ target, ...props }) {
    const [open, setOpen] = useState(false);
    if (!tradable(props.data, target)) {
        return null;
    }
    const intel = intelOf(props.data);
    const taken = forTarget(intel.accepted, target);
    const listings = forTarget(intel.listings, target).filter((item) => item.problem === null).length;
    const bounties = forTarget(intel.bounties, target).length;
    const cut = intel.cuts[target] || 0;
    return (
        <div className="target-intel">
            <span className="planner-hint-line">
                {taken.length
                    ? <>Intel taken: {taken.map((item) => `${item.category} from ${kdName(props.data, item.sharer)}${item.cut > 0 ? ` (${displayPercent(item.cut)})` : ""}`).join(", ")}.
                        {cut > 0 ? <> Your galaxymates get <strong>{displayPercent(cut)}</strong> of what you win from them.</> : null}</>
                    : "No intel taken from galaxymates on them."}
                {" "}{listings} for sale, {bounties} {bounties === 1 ? "bounty" : "bounties"}.
            </span>
            <Button size="sm" variant="outline-light" className="ms-2" onClick={() => setOpen(!open)} aria-expanded={open}>
                {open ? "Hide intel market" : "Intel market"}
            </Button>
            {open ? <KingdomIntel {...props} target={target} /> : null}
        </div>
    );
}

function IntelMarket(props) {
    const [results, setResults] = useState([]);
    const [opened, setOpened] = useState({ show: false });
    const send = useIntelAction(props, setResults);
    const shared = { ...props, send, onView: (target, tab) => setOpened({ show: true, target, tab }) };
    const notifs = parseInt(props.data.notifs?.shared || 0, 10);
    const { updateData } = props;
    useEffect(() => {
        if (notifs > 0) {
            updateData(["notifs"], [() => authFetch("api/clearnotifs", { method: "POST", body: JSON.stringify({ categories: ["shared"] }) })]);
        }
    }, [notifs, updateData]);
    if (props.loading.intel && !props.data.intel?.listings) {
        return <h2>Loading...</h2>;
    }
    const intel = intelOf(props.data);
    return (
        <>
            <Header data={props.data} />
            <div className="intel-market">
                <ResultToasts title="Intel" results={results} setResults={setResults} />
                <KingdomModal show={opened.show} onHide={() => setOpened({ ...opened, show: false })} target={opened.target} tab={opened.tab}
                    data={props.data} loading={props.loading} updateData={props.updateData} />
                <Tabs id="intel-tabs" defaultActiveKey="bounties" justify fill variant="tabs">
                    <Tab eventKey="bounties" title={`Bounties (${intel.bounties.length})`}>
                        <Panel title="Open bounties"><BountiesTable {...shared} /></Panel>
                        <Panel title="Ask the galaxy for intel" className="intel-form-panel"><BountyForm {...shared} /></Panel>
                        <Panel title="Recently answered"><HistoryTable kinds={["bounty"]} {...props} /></Panel>
                    </Tab>
                    <Tab eventKey="market" title={`Market (${intel.listings.length})`}>
                        <Panel title="Intel for sale"><ListingsTable {...shared} /></Panel>
                        <Panel title="Intel you have taken"><AcceptedTable {...shared} /></Panel>
                        <Panel title="Recent purchases and free shares"><HistoryTable kinds={["purchase", "free"]} {...props} /></Panel>
                    </Tab>
                    <Tab eventKey="yours" title="Your intel">
                        <Panel title="Your intel"><YourIntelTable {...shared} /></Panel>
                        <Panel title="Keep your intel from" className="intel-form-panel"
                            hint="They will not see your listings or bounties, nor get the intel you share free."><ExclusionsForm {...shared} /></Panel>
                    </Tab>
                </Tabs>
            </div>
            <HelpButton scrollTarget={"intel"} />
        </>
    );
}

export default IntelMarket;
