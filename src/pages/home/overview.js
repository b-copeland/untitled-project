import React from "react";
import { Link } from "react-router-dom";
import { displayNumber, displayPercent, fundingBreakdown, totalFunding } from "../../format";
import { rateTip } from "../../components/header";
import { Stats } from "../../components/planner";
import { authFetch } from "../../auth";
import { inOrder } from "../../order";
import Advisors from "./advisors";
import { TourReminder } from "../../components/tour";
import "./overview.css";

const SUMMARY_SERIES = [["stars", "Stars"], ["networth", "Networth"], ["population", "Population"],
    ["drones", "Drones"], ["engineers", "Engineers"]];
const EVENT_KINDS = [["attack", "attack", "attacks"], ["spy", "spy operation", "spy operations"],
    ["missiles", "missile strike", "missile strikes"]];

const fetchSummary = () => authFetch("api/history/summary").then((response) => (response.ok ? response.json() : null));

/**
 * The summary, fetched when the card opens and again whenever the tab is shown after being hidden: the server records
 * the visit and decides what to count from, so a tab left open in the background starts a new visit when it comes back.
 */
function useSummary(load) {
    const [summary, setSummary] = React.useState(undefined);
    React.useEffect(() => {
        let live = true;
        const fetch = () => Promise.resolve().then(load)
            .then((result) => { if (live) setSummary(result || null); })
            .catch(() => { if (live) setSummary(null); });
        const onShow = () => { if (document.visibilityState === "visible") fetch(); };
        fetch();
        document.addEventListener("visibilitychange", onShow);
        return () => { live = false; document.removeEventListener("visibilitychange", onShow); };
    }, [load]);
    return summary;
}

/** "+12" or "-3" for a change in a count. */
function change({ from, to }) {
    const difference = (to || 0) - (from || 0);
    return (difference >= 0 ? "+" : "-") + displayNumber(Math.abs(difference));
}

/** Later than ``since`` by more than a minute: the history does not go back that far. */
const startsLater = (from, since) => !!from && Date.parse(from) > Date.parse(since) + 60 * 1000;

function Breakdown({ title, changes, names, order, from, since }) {
    const keys = inOrder(Object.keys(changes || {}), order);
    if (keys.length === 0) return null;
    return (
        <div className="overview-breakdown">
            <h4 className="overview-subtitle">
                {title}{startsLater(from, since) ? <span className="overview-muted"> (since {ago(from)})</span> : null}
            </h4>
            <ul className="overview-changes">
                {keys.map((key) => (
                    <li key={key}>
                        <span>{names[key] || key}</span>
                        <span className={(changes[key].to || 0) < (changes[key].from || 0) ? "overview-down" : "overview-up"}>
                            {change(changes[key])}
                        </span>
                        <span className="overview-muted">now {displayNumber(changes[key].to)}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

/**
 * "Since you were last here": what changed in the kingdom (stars, networth, population, drones, engineers, then each
 * military unit and structure that changed) and what other kingdoms did to it. The server decides the time to count
 * from (the end of the last visit, or an hour ago) and compares the history point nearest before it with the kingdom
 * now; the events come from the news.
 */
export function SinceLastVisit({ data, load = fetchSummary }) {
    const summary = useSummary(load);
    const since = summary?.since;
    const sinceVisit = !!summary?.since_visit;

    const names = data.state?.pretty_names || {};
    const order = data.state?.order || {};
    const events = since ? (data.news || []).filter((item) => Date.parse(item.time) > Date.parse(since)) : [];
    const counts = EVENT_KINDS.map(([kind, one, many]) => {
        const count = events.filter((item) => item.kind === kind).length;
        return count > 0 ? `${count} ${count === 1 ? one : many}` : null;
    }).filter(Boolean);
    const latest = [...events].sort((a, b) => Date.parse(b.time) - Date.parse(a.time)).slice(0, 3);

    const changes = summary?.changes || {};
    const shown = SUMMARY_SERIES.filter(([key]) => changes[key]);
    const anyChange = shown.some(([key]) => changes[key].from !== changes[key].to)
        || Object.keys(summary?.units || {}).length > 0 || Object.keys(summary?.structures || {}).length > 0;

    return (
        <Card title={sinceVisit ? `Since you were last here (${ago(since)})` : "The last hour"} className="overview-since">
            {summary === undefined ? <p className="overview-line overview-muted">Loading...</p> : null}
            {summary === null ? <p className="overview-line overview-muted">Could not load what changed.</p> : null}
            {summary && shown.length === 0
                ? <p className="overview-line overview-muted">Your kingdom has no history yet. It is recorded every half hour.</p>
                : null}
            {summary && shown.length > 0 ? (
                <>
                    {startsLater(summary.from, since)
                        ? <p className="overview-line overview-muted">Your kingdom's history starts {ago(summary.from)}.</p>
                        : null}
                    <Stats items={shown.map(([key, label]) => ({
                        label, value: change(changes[key]),
                        tone: changes[key].to < changes[key].from ? "bad" : undefined,
                    }))} />
                    <div className="overview-breakdowns">
                        <Breakdown title="Military units" changes={summary.units} names={names} order={order.units}
                            from={summary.units_from} since={since} />
                        <Breakdown title="Structures" changes={summary.structures} names={names} order={order.structures}
                            from={summary.structures_from} since={since} />
                    </div>
                    {!anyChange ? <p className="overview-line overview-muted">Nothing in your kingdom changed.</p> : null}
                </>
            ) : null}
            {summary ? (
                <p className="overview-line">
                    {counts.length > 0
                        ? <>Against you: {counts.join(", ")}. <Link to="/news">See the news</Link></>
                        : "No attacks, spy operations or missiles against you."}
                </p>
            ) : null}
            {latest.length > 0 ? (
                <ul className="overview-news">
                    {latest.map((item, i) => <li key={i}>{item.news} <span className="overview-muted">({ago(item.time)})</span></li>)}
                </ul>
            ) : null}
        </Card>
    );
}

/** "in 2h 05m" until ``date``, or "now" if it has passed. */
function until(date, now = Date.now()) {
    const seconds = Math.max((Date.parse(date) - now) / 1000, 0);
    if (seconds < 60) return "now";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return hours > 0 ? `in ${hours}h ${String(minutes).padStart(2, "0")}m` : `in ${minutes}m`;
}

function ago(date, now = Date.now()) {
    const hours = (now - Date.parse(date)) / 3.6e6;
    if (hours < 1) return `${Math.max(Math.round(hours * 60), 0)}m ago`;
    if (hours < 48) return `${Math.floor(hours)}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

/** A card on the dashboard: a title that links to where you act on it, then a few numbers and lines. */
function Card({ title, to, className = "", tour, children }) {
    return (
        <section className={`overview-card ${className}`.trim()} data-tour={tour}>
            <h3 className="overview-card-title">
                {to ? <Link to={to}>{title}</Link> : title}
            </h3>
            {children}
        </section>
    );
}

/**
 * The Status page's first tab: the advisors' notes on what may need fixing (advisors.js, from the server), then the four questions a returning player
 * asks (is my economy healthy, am I safe and what is out, am I growing, is anyone after me), each a card that links to
 * where to act. Built only from data the other tabs already load.
 */
export function Overview({ data, loadSummary }) {
    const kingdom = data.kingdom || {};
    const mobis = data.mobis || {};
    const structures = data.structures || {};
    const epoch = data.state?.game_config?.BASE_EPOCH_SECONDS;
    if (Object.keys(kingdom).length === 0) {
        return null;
    }
    const perHour = (perEpoch) => (epoch && perEpoch !== undefined ? (perEpoch * 3600) / epoch : undefined);
    const signed = (value) => (value === undefined ? "--" : (value >= 0 ? "+" : "-") + displayNumber(Math.abs(value)));

    // Economy
    const fuelTip = rateTip(kingdom.fuel, kingdom.income?.fuel?.net, epoch, "fuel");
    const fuelFalling = (kingdom.income?.fuel?.net || 0) < 0;

    // Military: defense and offense at home, and the generals that are out.
    const units = mobis.units || {};
    const out = [0, 1, 2, 3].map((i) => units[`general_${i}`]).filter((general) => general?.return_time);
    const nextBack = out.map((general) => general.return_time).sort()[0];

    // Growth: how many stars have a structure, and what is still being built.
    const built = Object.values(structures.current || {}).reduce((sum, value) => sum + (value || 0), 0);
    const building = Object.values(structures.queued || {}).reduce((sum, value) => sum + (value || 0), 0);
    const stars = kingdom.stars || 0;

    // Threats: siphons on you, your shields, and the latest thing that happened to your kingdom.
    // data.siphonsout is the siphons other kingdoms run on you; kingdom.siphons is what your own siphons paid you (#223).
    const siphons = data.siphonsout || [];
    const shields = kingdom.shields || {};
    const latest = [...(data.news || [])].sort((a, b) => Date.parse(b.time) - Date.parse(a.time))[0];

    return (
        <div className="overview">
            <TourReminder className="overview-wide" />

            <Card title="Advisors" className="overview-advisors" tour="status-advisors">
                <Advisors />
            </Card>

            <SinceLastVisit data={data} {...(loadSummary ? { load: loadSummary } : {})} />

            <Card title="Economy" to="/automation?tab=spending">
                <Stats items={[
                    { label: "Money", value: displayNumber(kingdom.money), tone: kingdom.money < 0 ? "bad" : undefined },
                    { label: "Income / h", value: signed(perHour(kingdom.income?.money?.net)) },
                    { label: "Funding", value: displayNumber(totalFunding(kingdom.funding)) },
                    { label: "Fuel", value: displayNumber(kingdom.fuel), tone: kingdom.fuel <= 0 ? "bad" : undefined },
                    { label: "Fuel / h", value: signed(perHour(kingdom.income?.fuel?.net)), tone: fuelFalling ? "bad" : undefined },
                    { label: "Population", value: displayNumber(kingdom.population) },
                    { label: "Pop / h", value: signed(perHour(kingdom.income?.population)) },
                ]} />
                {fuelFalling && fuelTip ? <p className="overview-warning">Fuel: {fuelTip}</p> : null}
                <p className="overview-line">
                    Auto spending is <strong>{kingdom.auto_spending_enabled ? "on" : "off"}</strong>.
                    {totalFunding(kingdom.funding) > 0 ? <> Funding set aside: {fundingBreakdown(kingdom.funding)}.</> : null}
                </p>
            </Card>

            <Card title="Military" to="/military">
                <Stats items={[
                    { label: "Defense at home", value: displayNumber(mobis.now?.defense) },
                    { label: "Offense at home", value: displayNumber(mobis.now?.offense) },
                    { label: "Generals home", value: kingdom.generals_available ?? "--" },
                    { label: "Hangar", value: mobis.max_hangar_capacity ? displayPercent((mobis.current_hangar_capacity || 0) / mobis.max_hangar_capacity) : "--" },
                ]} />
                <p className="overview-line">
                    {out.length > 0 ? <>{out.length} general{out.length > 1 ? "s" : ""} out, the next back {until(nextBack)}.</> : "No generals out."}
                </p>
            </Card>

            <Card title="Growth" to="/structures">
                <Stats items={[
                    { label: "Stars", value: displayNumber(stars) },
                    { label: "Built on", value: stars ? displayPercent(built / stars) : "--" },
                    { label: "Being built", value: displayNumber(building) },
                    { label: "Engineers", value: displayNumber(kingdom.units?.engineers) },
                ]} />
                {stars > built + building ? <p className="overview-warning">{displayNumber(stars - built - building)} stars have nothing on them.</p> : null}
            </Card>

            <Card title="Threats" to="/news">
                <Stats items={[
                    { label: "Military shields", value: displayPercent(shields.military || 0) },
                    { label: "Spy shields", value: displayPercent(shields.spy || 0) },
                    { label: "Siphons on you", value: siphons.length, tone: siphons.length > 0 ? "bad" : undefined },
                ]} />
                <p className="overview-line">
                    {latest ? <>Latest: {latest.news} <span className="overview-muted">({ago(latest.time)})</span></> : "Nothing has happened to your kingdom yet."}
                </p>
            </Card>
        </div>
    );
}

export default Overview;
