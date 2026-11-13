import React from "react";
import { Link } from "react-router-dom";
import { displayNumber, displayPercent } from "../../format";
import { rateTip } from "../../components/header";
import { Stats } from "../../components/planner";
import "./overview.css";

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
function Card({ title, to, onOpen, children }) {
    return (
        <section className="overview-card">
            <h3 className="overview-card-title">
                {to ? <Link to={to}>{title}</Link> : onOpen ? <button type="button" className="link-button" onClick={onOpen}>{title}</button> : title}
            </h3>
            {children}
        </section>
    );
}

/**
 * The Status page's first tab: the four questions a returning player asks (is my economy healthy, am I safe and what
 * is out, am I growing, is anyone after me), each a card that links to where to act. Built only from data the other
 * tabs already load.
 */
export function Overview({ data, openTab }) {
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
    const building = Object.values(structures.hour_24 || {}).reduce((sum, value) => sum + (value || 0), 0);
    const stars = kingdom.stars || 0;

    // Threats: siphons on you, your shields, and the latest thing that happened to your kingdom.
    const siphons = kingdom.siphons || [];
    const shields = kingdom.shields || {};
    const latest = [...(data.news || [])].sort((a, b) => Date.parse(b.time) - Date.parse(a.time))[0];

    return (
        <div className="overview">
            <Card title="Economy" onOpen={() => openTab("spending")}>
                <Stats items={[
                    { label: "Money", value: displayNumber(kingdom.money), tone: kingdom.money < 0 ? "bad" : undefined },
                    { label: "Income / h", value: signed(perHour(kingdom.income?.money?.net)) },
                    { label: "Fuel", value: displayNumber(kingdom.fuel), tone: kingdom.fuel <= 0 ? "bad" : undefined },
                    { label: "Fuel / h", value: signed(perHour(kingdom.income?.fuel?.net)), tone: fuelFalling ? "bad" : undefined },
                    { label: "Population", value: displayNumber(kingdom.population) },
                    { label: "Pop / h", value: signed(perHour(kingdom.income?.population)) },
                ]} />
                {fuelFalling && fuelTip ? <p className="overview-warning">Fuel: {fuelTip}</p> : null}
                <p className="overview-line">Auto spending is <strong>{kingdom.auto_spending_enabled ? "on" : "off"}</strong>.</p>
            </Card>

            <Card title="Military" to="/military">
                <Stats items={[
                    { label: "Defense at home", value: displayNumber(mobis.maxes?.defense?.current) },
                    { label: "Offense at home", value: displayNumber(mobis.maxes?.offense?.current) },
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
