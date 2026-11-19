import React, { useMemo, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import ToggleButton from 'react-bootstrap/ToggleButton';
import ToggleButtonGroup from 'react-bootstrap/ToggleButtonGroup';
import { hierarchy, pack } from "d3-hierarchy";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { GameTable } from "../../components/gametable";
import { Panel } from "../../components/planner";
import { displayNumber } from "../../format";
import "./universemap.css";

const SIZE = 600;

// The categorical palette, dark steps (the app is always dark), checked with the dataviz validator against the page's
// surface. An empire keeps its colour for the round: slots go by empire id, not by size or order on screen.
export const EMPIRE_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
export const OTHER_EMPIRE = "#8a8f98";

const clusterOf = (galaxyId) => String(galaxyId).split(":")[0];
const byNumber = (a, b) => {
    const [x, y] = [Number(a), Number(b)];
    return Number.isNaN(x) || Number.isNaN(y) ? String(a).localeCompare(String(b)) : x - y;
};
const galaxyOrder = (a, b) => byNumber(clusterOf(a), clusterOf(b)) || byNumber(a.split(":")[1], b.split(":")[1]);

/** Empire id to its colour, by the order of the ids, so a colour never moves to another empire. */
export function empireColors(empires) {
    const colors = {};
    Object.keys(empires || {}).sort(byNumber).forEach((empireId, index) => {
        colors[empireId] = index < EMPIRE_COLORS.length ? EMPIRE_COLORS[index] : OTHER_EMPIRE;
    });
    return colors;
}

/** Galaxy id to the empire it is in, from ``/api/empires``. */
export function galaxyEmpires(empires) {
    const result = {};
    Object.entries(empires || {}).forEach(([empireId, empire]) => (empire.galaxies || []).forEach((galaxy) => { result[galaxy] = empireId; }));
    return result;
}

/**
 * One row per galaxy: its cluster, kingdoms, networth (public, from the scores) and empire. ``galaxyNetworth`` is the
 * scores' list of ``[galaxy, networth]``.
 */
export function galaxyRows(galaxies, empires, galaxyNetworth) {
    const networth = Object.fromEntries((galaxyNetworth || []).map(([galaxy, value]) => [galaxy, value]));
    const empireOf = galaxyEmpires(empires);
    return Object.keys(galaxies || {}).sort(galaxyOrder).map((galaxy) => ({
        key: galaxy,
        galaxy,
        cluster: clusterOf(galaxy),
        kingdoms: (galaxies[galaxy] || []).length,
        networth: networth[galaxy] || 0,
        empire: empireOf[galaxy] ?? null,
    }));
}

/**
 * The circles of the map: each cluster a circle holding its galaxies, each galaxy sized by ``sizeBy`` ("kingdoms" or
 * "networth"). An empty galaxy still gets a small circle, so every galaxy is on the map.
 */
export function layout(rows, sizeBy, size = SIZE) {
    const largest = Math.max(1, ...rows.map((row) => row[sizeBy]));
    const clusters = {};
    rows.forEach((row) => { (clusters[row.cluster] = clusters[row.cluster] || []).push(row); });
    const root = hierarchy({
        children: Object.keys(clusters).sort(byNumber).map((cluster) => ({
            cluster,
            children: clusters[cluster].map((row) => ({ row, value: Math.max(row[sizeBy], largest * 0.02) })),
        })),
    }).sum((node) => node.value || 0);
    pack().size([size, size]).padding((node) => (node.depth === 0 ? 14 : 4))(root);
    return {
        clusters: (root.children || []).map((node) => ({ cluster: node.data.cluster, x: node.x, y: node.y, r: node.r })),
        galaxies: root.leaves().filter((node) => node.data.row).map((node) => ({ ...node.data.row, x: node.x, y: node.y, r: node.r })),
    };
}

function Legend({ empires, colors, rows }) {
    const present = new Set(rows.map((row) => row.empire));
    const shown = Object.keys(empires || {}).sort(byNumber).filter((empireId) => present.has(empireId));
    const named = shown.filter((empireId) => colors[empireId] !== OTHER_EMPIRE);
    return (
        <ul className="universe-map-legend" aria-label="Empires">
            {named.map((empireId) => (
                <li key={empireId}><span className="universe-map-swatch" style={{ background: colors[empireId] }} />{empires[empireId].name}</li>
            ))}
            {shown.length > named.length
                ? <li><span className="universe-map-swatch" style={{ background: OTHER_EMPIRE }} />Other empires</li>
                : null}
            {present.has(null) ? <li><span className="universe-map-swatch universe-map-swatch-none" />No empire</li> : null}
            <li><span className="universe-map-swatch universe-map-swatch-mine" />Your galaxy</li>
        </ul>
    );
}

const describe = (row, empires, sizeBy) => [
    `Galaxy ${row.galaxy}`,
    `Cluster ${row.cluster}`,
    `${row.kingdoms} ${row.kingdoms === 1 ? "kingdom" : "kingdoms"}`,
    `networth ${displayNumber(row.networth)}`,
    row.empire != null ? empires?.[row.empire]?.name || `Empire ${row.empire}` : "no empire",
].join(" · ");

function BubbleMap({ rows, sizeBy, empires, colors, myGalaxy }) {
    const [focus, setFocus] = useState(null);
    const circles = useMemo(() => layout(rows, sizeBy), [rows, sizeBy]);
    const focused = rows.find((row) => row.galaxy === focus);
    return (
        <>
            <svg className="universe-map-svg" viewBox={`0 0 ${SIZE} ${SIZE}`} role="img"
                aria-label={`Map of ${circles.clusters.length} clusters and ${rows.length} galaxies, sized by ${sizeBy}`}>
                {circles.clusters.map((cluster) => (
                    <g key={`c${cluster.cluster}`}>
                        <circle className="universe-map-cluster" cx={cluster.x} cy={cluster.y} r={cluster.r} />
                        <text className="universe-map-cluster-label" x={cluster.x} y={cluster.y - cluster.r + 13} textAnchor="middle">
                            Cluster {cluster.cluster}
                        </text>
                    </g>
                ))}
                {circles.galaxies.map((galaxy) => {
                    const mine = galaxy.galaxy === myGalaxy;
                    const fill = galaxy.empire != null ? colors[galaxy.empire] : "none";
                    return (
                        <g key={galaxy.galaxy} className="universe-map-galaxy" tabIndex={0}
                            onMouseEnter={() => setFocus(galaxy.galaxy)} onFocus={() => setFocus(galaxy.galaxy)}
                            onClick={() => setFocus(galaxy.galaxy)} data-testid={`galaxy-${galaxy.galaxy}`}>
                            <title>{describe(galaxy, empires, sizeBy)}</title>
                            <circle cx={galaxy.x} cy={galaxy.y} r={Math.max(galaxy.r, 3)} fill={fill}
                                className={(galaxy.empire == null ? "universe-map-no-empire" : "") + (mine ? " universe-map-mine" : "")} />
                            {galaxy.r >= 14
                                ? <text className="universe-map-galaxy-label" x={galaxy.x} y={galaxy.y + 4} textAnchor="middle">{galaxy.galaxy}</text>
                                : null}
                        </g>
                    );
                })}
            </svg>
            <p className="universe-map-focus" aria-live="polite">
                {focused ? describe(focused, empires, sizeBy) : "Point at or tap a galaxy to see it."}
            </p>
        </>
    );
}

function GalaxyTable({ rows, empires, myGalaxy }) {
    return (
        <GameTable
            className="game-table universe-map-table"
            rows={rows}
            rowClassName={(row) => (row.galaxy === myGalaxy ? "universe-map-row-mine" : undefined)}
            columns={[
                { header: "Cluster", align: "left", cell: (row) => row.cluster },
                { header: "Galaxy", align: "left", cell: (row) => (row.galaxy === myGalaxy ? `${row.galaxy} (yours)` : row.galaxy) },
                { header: "Kingdoms", cell: (row) => row.kingdoms },
                { header: "Networth", cell: (row) => displayNumber(row.networth) },
                { header: "Empire", align: "left", cell: (row) => (row.empire != null ? empires?.[row.empire]?.name || `Empire ${row.empire}` : "None") },
            ]}
        />
    );
}

// A phone starts on the table, which reads better than a 375px map; anything wider starts on the map.
const wide = () => typeof window === "undefined" || !window.matchMedia || window.matchMedia("(min-width: 576px)").matches;

function UniverseMap(props) {
    const [sizeBy, setSizeBy] = useState("kingdoms");
    const [view, setView] = useState(wide() ? "map" : "table");
    const { galaxies, empires, scores, galaxies_inverted: galaxiesInverted, kingdomid } = props.data;
    const rows = useMemo(() => galaxyRows(galaxies, empires, scores?.galaxy_networth), [galaxies, empires, scores]);
    const colors = useMemo(() => empireColors(empires), [empires]);
    const myGalaxy = (galaxiesInverted || {})[kingdomid?.kd_id];
    const clusterCount = new Set(rows.map((row) => row.cluster)).size;
    return (
        <>
            <Header data={props.data} />
            <div className="universe-map">
                <Panel title="The universe"
                    hint={`${clusterCount} ${clusterCount === 1 ? "cluster" : "clusters"} of ${rows.length} galaxies, coloured by empire.`}>
                    <div className="universe-map-controls">
                        <ToggleButtonGroup type="radio" name="universe-map-view" value={view} onChange={setView} size="sm">
                            <ToggleButton id="universe-map-view-map" value="map" variant="outline-secondary">Map</ToggleButton>
                            <ToggleButton id="universe-map-view-table" value="table" variant="outline-secondary">Table</ToggleButton>
                        </ToggleButtonGroup>
                        {view === "map"
                            ? <ToggleButtonGroup type="radio" name="universe-map-size" value={sizeBy} onChange={setSizeBy} size="sm">
                                <ToggleButton id="universe-map-size-kingdoms" value="kingdoms" variant="outline-secondary">Size by kingdoms</ToggleButton>
                                <ToggleButton id="universe-map-size-networth" value="networth" variant="outline-secondary">Size by networth</ToggleButton>
                            </ToggleButtonGroup>
                            : null}
                    </div>
                    {rows.length === 0
                        ? <p>There are no galaxies yet.</p>
                        : view === "map"
                            ? <>
                                <Legend empires={empires} colors={colors} rows={rows} />
                                <BubbleMap rows={rows} sizeBy={sizeBy} empires={empires} colors={colors} myGalaxy={myGalaxy} />
                            </>
                            : <GalaxyTable rows={rows} empires={empires} myGalaxy={myGalaxy} />}
                </Panel>
            </div>
            <HelpButton scrollTarget={"clusterpolitics"} />
        </>
    );
}

export default UniverseMap;
