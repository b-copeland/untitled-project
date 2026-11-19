import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import "./intel.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { Panel, FieldRow, Picker, clockUntil } from "../../components/planner";
import { displayPercent } from "../../format";
import { checkCount, checkPercent, firstError } from "../../validation";

/*
 * The galaxy's intel market (api/untitledapp/intel.py): bounties asking for intel, listings selling it, and the intel
 * you can list or share free. Every rule (who may take what, at what cut) is the server's: each listing and bounty
 * comes with ``problem``, the reason this kingdom could not take it, or null.
 *
 * The pieces take an optional ``target`` so the same tables and forms can show one kingdom's intel (KingdomIntel),
 * wherever a kingdom is shown.
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
// Full Infiltration reveals every kind at once; it is not a kind of its own.
const categoriesOf = (data) => (data.state?.reveal_operations || []).filter((operation) => operation !== "spyall").map((operation) => operation.replace(/^spy/, ""));

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

/** The intel this kingdom has revealed, each with a cut box, List and Share free. */
export function YourIntelTable({ target, send, ...props }) {
    const intel = intelOf(props.data);
    const [cuts, setCuts] = useState({});
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
                if (row.received) return <span className="text-muted">can not be passed on</span>;
                const value = cuts[row.key] ?? "";
                const error = checkPercent(value, { max: maxCutPercent(props.data) });
                const positive = parseFloat(value) > 0;
                return (
                    <span className="intel-share">
                        <CutBox id={`cut-${row.key}`} value={value} onChange={(v) => setCuts({ ...cuts, [row.key]: v })} error={error} />
                        <Action loading={props.loading.intel} problem={error || (positive ? null : "Enter a cut to list it, or share it free")}
                            onClick={() => send("share", { target: row.target, category: row.category, cut: value })}>List</Action>
                        <Action variant="outline-light" loading={props.loading.intel}
                            onClick={() => send("share", { target: row.target, category: row.category, cut: 0 }, ["intel", "revealed"])}>Share free</Action>
                        {row.listing ? <Action variant="outline-danger" loading={props.loading.intel}
                            onClick={() => send("delist", { listing: row.listing })}>Remove</Action> : null}
                    </span>
                );
            },
        },
    ];
    return <GameTable columns={columns} rows={rows} />;
}

/** Listings on the market, each with Buy (or Remove for your own). */
export function ListingsTable({ target, send, ...props }) {
    const intel = intelOf(props.data);
    const rows = forTarget(intel.listings, target).map((item) => ({ ...item, key: item.id }));
    if (rows.length === 0) {
        return <p className="planner-hint-line">No intel {target === undefined ? "" : "on this kingdom "}is listed by your galaxymates.</p>;
    }
    const me = myKd(props.data);
    const columns = [
        { header: "Seller", align: "left", cell: (row) => kdName(props.data, row.seller) },
        ...(target === undefined ? [{ header: "Kingdom", align: "left", cell: (row) => kdLabel(props.data, row.target) }] : []),
        { header: "Intel", align: "left", cell: (row) => row.category },
        { header: "Cut", cell: (row) => displayPercent(row.cut) },
        { header: "Ends in", cell: (row) => clockUntil(row.time) },
        {
            header: "", align: "left", cell: (row) => (String(row.seller) === me
                ? <Action variant="outline-danger" loading={props.loading.intel} onClick={() => send("delist", { listing: row.id })}>Remove</Action>
                : <Action loading={props.loading.intel} problem={row.problem} onClick={() => send("buy", { listing: row.id }, ["intel", "revealed"])}>Buy</Action>),
        },
    ];
    return <GameTable columns={columns} rows={rows} />;
}

/** Open bounties, each with Fulfil (or Withdraw for your own). */
export function BountiesTable({ target, send, ...props }) {
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
            header: "", align: "left", cell: (row) => (String(row.requester) === me
                ? <Action variant="outline-danger" loading={props.loading.intel} onClick={() => send("cancelbounty", { bounty: row.id })}>Withdraw</Action>
                : <Action loading={props.loading.intel} problem={row.problem} onClick={() => send("fulfil", { bounty: row.id })}>Fulfil</Action>),
        },
    ];
    return <GameTable columns={columns} rows={rows} />;
}

/** The form to ask the galaxy for intel. With ``target`` it asks about that kingdom only. */
export function BountyForm({ target, send, ...props }) {
    const [chosen, setChosen] = useState(target);
    const [category, setCategory] = useState(undefined);
    const [cut, setCut] = useState("");
    const [epochs, setEpochs] = useState("");
    const maxEpochs = config(props.data).BASE_INTEL_BOUNTY_MAX_EPOCHS || 0;
    const mates = new Set(myGalaxymates(props.data));
    const kingdomOptions = Object.keys(props.data.kingdoms || {}).filter((kdId) => !mates.has(String(kdId)))
        .map((kdId) => ({ value: kdId, label: kdLabel(props.data, kdId) }));
    const categoryOptions = categoriesOf(props.data).map((name) => ({ value: name, label: name }));
    const cutError = checkPercent(cut, { max: maxCutPercent(props.data) });
    const epochsError = checkCount(epochs, { max: maxEpochs, noun: "epochs" });
    const blocked = firstError(
        chosen === undefined ? "Choose a kingdom" : null,
        category === undefined ? "Choose the intel you want" : null,
        cutError,
        epochsError,
        String(epochs).trim() === "" || parseInt(epochs, 10) < 1 ? "Choose how many epochs it stays up" : null,
    );
    return (
        <div className="intel-form">
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
            <FieldRow label="Stays up for" hint={`Epochs, 1 to ${maxEpochs}`} htmlFor="bounty-epochs">
                <Form.Control id="bounty-epochs" size="sm" inputMode="numeric" placeholder="0" autoComplete="off" className="intel-epochs"
                    value={epochs} onChange={(e) => setEpochs(e.target.value)} isInvalid={Boolean(epochsError)} />
                {epochsError ? <div className="amount-input-error">{epochsError}</div> : null}
            </FieldRow>
            <Button size="sm" disabled={Boolean(blocked) || props.loading.intel} title={blocked || undefined}
                onClick={() => send("bounty", { target: chosen, category, cut: cut === "" ? 0 : cut, epochs })}>Post bounty</Button>
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
    return <GameTable columns={columns} rows={rows} />;
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
    return <GameTable columns={columns} rows={rows} />;
}

/** Which galaxymates may not see or take your intel. */
export function ExclusionsForm({ send, ...props }) {
    const intel = intelOf(props.data);
    const me = myKd(props.data);
    const mates = myGalaxymates(props.data).filter((kdId) => kdId !== me);
    const saved = intel.exclusions.map(String);
    const [excluded, setExcluded] = useState(saved);
    useEffect(() => setExcluded(saved), [saved.join(",")]);
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

/** Everything about one kingdom's intel: yours to share, what is on the market, bounties, and asking for more. */
export function KingdomIntel(props) {
    const [results, setResults] = useState([]);
    const send = useIntelAction(props, setResults);
    const shared = { ...props, send };
    if (props.loading.intel && !props.data.intel?.listings) {
        return <h3>Loading...</h3>;
    }
    return (
        <div className="kingdom-intel">
            <ResultToasts title="Intel" results={results} setResults={setResults} />
            <h4>Intel on {kdName(props.data, props.target)}</h4>
            <Panel title="Your intel"><YourIntelTable {...shared} /></Panel>
            <Panel title="On the market"><ListingsTable {...shared} /></Panel>
            <Panel title="Bounties"><BountiesTable {...shared} /></Panel>
            <Panel title="Ask the galaxy for intel"><BountyForm {...shared} /></Panel>
            <Panel title="Intel you have taken"><AcceptedTable {...shared} /></Panel>
        </div>
    );
}

function IntelMarket(props) {
    const [results, setResults] = useState([]);
    const send = useIntelAction(props, setResults);
    const shared = { ...props, send };
    const notifs = parseInt(props.data.notifs?.shared || 0, 10);
    useEffect(() => {
        if (notifs > 0) {
            props.updateData(["notifs"], [() => authFetch("api/clearnotifs", { method: "POST", body: JSON.stringify({ categories: ["shared"] }) })]);
        }
    }, [notifs]);
    if (props.loading.intel && !props.data.intel?.listings) {
        return <h2>Loading...</h2>;
    }
    const intel = intelOf(props.data);
    return (
        <>
            <Header data={props.data} />
            <div className="intel-market">
                <ResultToasts title="Intel" results={results} setResults={setResults} />
                <Tabs id="intel-tabs" defaultActiveKey="bounties" justify fill variant="tabs">
                    <Tab eventKey="bounties" title={`Bounties (${intel.bounties.length})`}>
                        <Panel title="Open bounties"><BountiesTable {...shared} /></Panel>
                        <Panel title="Ask the galaxy for intel"><BountyForm {...shared} /></Panel>
                        <Panel title="Recently answered"><HistoryTable kinds={["bounty"]} {...props} /></Panel>
                    </Tab>
                    <Tab eventKey="market" title={`Market (${intel.listings.length})`}>
                        <Panel title="Intel for sale"><ListingsTable {...shared} /></Panel>
                        <Panel title="Intel you have taken"><AcceptedTable {...shared} /></Panel>
                        <Panel title="Recent purchases and free shares"><HistoryTable kinds={["purchase", "free"]} {...props} /></Panel>
                    </Tab>
                    <Tab eventKey="yours" title="Your intel">
                        <Panel title="Your intel"><YourIntelTable {...shared} /></Panel>
                        <Panel title="Keep your intel from"><ExclusionsForm {...shared} /></Panel>
                    </Tab>
                </Tabs>
            </div>
            <HelpButton scrollTarget={"intel"} />
        </>
    );
}

export default IntelMarket;
