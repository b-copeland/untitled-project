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
import "./universe.css";

/*
 * The Universe page: every galaxy as a bubble inside a bigger one, grouped either by cluster (and coloured by empire)
 * or by empire (and coloured by cluster), sized by its kingdoms still alive or its networth. Everything on it is
 * public: the galaxies, the empires, and each galaxy's networth and kingdoms alive from the scores.
 */

const SIZE = 600;

// The categorical palette, dark steps (the app is always dark), checked with the dataviz validator against the page's
// surface. Slots go by id (an empire's or a cluster's), never by size or position, so a colour never changes hands.
export const COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
export const OTHER_COLOR = "#8a8f98";
export const NO_EMPIRE = "none";

const clusterOf = (galaxyId) => String(galaxyId).split(":")[0];
const byNumber = (a, b) => {
    const [x, y] = [Number(a), Number(b)];
    return Number.isNaN(x) || Number.isNaN(y) ? String(a).localeCompare(String(b)) : x - y;
};
const galaxyOrder = (a, b) => byNumber(clusterOf(a), clusterOf(b)) || byNumber(a.split(":")[1], b.split(":")[1]);

/** Id to colour, the first eight ids in order each getting their own, the rest sharing the "other" grey. */
export function colorsFor(ids) {
    const colors = {};
    [...ids].sort(byNumber).forEach((id, index) => { colors[id] = index < COLORS.length ? COLORS[index] : OTHER_COLOR; });
    return colors;
}

/** Galaxy id to the empire it is in, from ``/api/empires``. */
export function galaxyEmpires(empires) {
    const result = {};
    Object.entries(empires || {}).forEach(([empireId, empire]) => (empire.galaxies || []).forEach((galaxy) => { result[galaxy] = empireId; }));
    return result;
}

/**
 * One row per galaxy: its cluster, kingdoms still alive, networth and empire, from the scores' ``galaxy_networth``
 * (a list of ``[galaxy, networth]``) and ``galaxy_kingdoms_alive`` (galaxy to count). Until the refresh has counted
 * the kingdoms alive, every kingdom in the galaxy counts.
 */
export function galaxyRows(galaxies, empires, scores) {
    const networth = Object.fromEntries((scores?.galaxy_networth || []).map(([galaxy, value]) => [galaxy, value]));
    const alive = scores?.galaxy_kingdoms_alive;
    const counted = alive && Object.keys(alive).length > 0;
    const empireOf = galaxyEmpires(empires);
    return Object.keys(galaxies || {}).sort(galaxyOrder).map((galaxy) => ({
        key: galaxy,
        galaxy,
        cluster: clusterOf(galaxy),
        kingdoms: counted ? alive[galaxy] || 0 : (galaxies[galaxy] || []).length,
        networth: networth[galaxy] || 0,
        empire: empireOf[galaxy] ?? null,
    }));
}

const empireLabel = (empires, empireId) => (empireId == null || empireId === NO_EMPIRE
    ? "No empire" : empires?.[empireId]?.name || `Empire ${empireId}`);

/** How each grouping puts galaxies together, names its groups, and colours its galaxies. */
export function grouping(groupBy, rows, empires) {
    if (groupBy === "empire") {
        const colors = colorsFor(new Set(rows.map((row) => row.cluster)));
        return {
            groupOf: (row) => (row.empire == null ? NO_EMPIRE : row.empire),
            // Empires in id order, galaxies in no empire last.
            groupOrder: (a, b) => (a === NO_EMPIRE) - (b === NO_EMPIRE) || byNumber(a, b),
            groupLabel: (id) => empireLabel(empires, id),
            colorOf: (row) => colors[row.cluster],
            legend: Object.keys(colors).sort(byNumber).map((cluster) => ({ key: cluster, label: `Cluster ${cluster}`, color: colors[cluster] })),
        };
    }
    const colors = colorsFor(Object.keys(empires || {}));
    const present = new Set(rows.map((row) => row.empire));
    const named = Object.keys(colors).sort(byNumber).filter((id) => present.has(id) && colors[id] !== OTHER_COLOR);
    const others = Object.keys(colors).some((id) => present.has(id) && colors[id] === OTHER_COLOR);
    return {
        groupOf: (row) => row.cluster,
        groupOrder: byNumber,
        groupLabel: (id) => `Cluster ${id}`,
        colorOf: (row) => (row.empire == null ? null : colors[row.empire]),
        legend: [
            ...named.map((id) => ({ key: id, label: empireLabel(empires, id), color: colors[id] })),
            ...(others ? [{ key: "other", label: "Other empires", color: OTHER_COLOR }] : []),
            ...(present.has(null) ? [{ key: NO_EMPIRE, label: "No empire", color: null }] : []),
        ],
    };
}

/**
 * The circles: a circle per group holding its galaxies, each sized by ``sizeBy`` ("kingdoms" or "networth"). An empty
 * galaxy still gets a small circle, so every galaxy is on the chart.
 */
export function layout(rows, sizeBy, { groupOf, groupOrder }, size = SIZE) {
    const largest = Math.max(1, ...rows.map((row) => row[sizeBy]));
    const groups = {};
    rows.forEach((row) => { (groups[groupOf(row)] = groups[groupOf(row)] || []).push(row); });
    const root = hierarchy({
        children: Object.keys(groups).sort(groupOrder).map((group) => ({
            group,
            children: groups[group].map((row) => ({ row, value: Math.max(row[sizeBy], largest * 0.02) })),
        })),
    }).sum((node) => node.value || 0);
    pack().size([size, size]).padding((node) => (node.depth === 0 ? 14 : 4))(root);
    return {
        groups: (root.children || []).map((node) => ({ group: node.data.group, x: node.x, y: node.y, r: node.r })),
        galaxies: root.leaves().filter((node) => node.data.row).map((node) => ({ ...node.data.row, x: node.x, y: node.y, r: node.r })),
    };
}

function Legend({ items }) {
    return (
        <ul className="universe-legend" aria-label="Colours">
            {items.map((item) => (
                <li key={item.key}>
                    <span className={"universe-swatch" + (item.color ? "" : " universe-swatch-none")} style={item.color ? { background: item.color } : undefined} />
                    {item.label}
                </li>
            ))}
            <li><span className="universe-swatch universe-swatch-mine" />Your galaxy</li>
        </ul>
    );
}

const describe = (row, empires) => [
    `Galaxy ${row.galaxy}`,
    `Cluster ${row.cluster}`,
    `${row.kingdoms} ${row.kingdoms === 1 ? "kingdom" : "kingdoms"} alive`,
    `networth ${displayNumber(row.networth)}`,
    empireLabel(empires, row.empire),
].join(" · ");

function BubbleChart({ rows, sizeBy, groups, empires, myGalaxy, label }) {
    const [focus, setFocus] = useState(null);
    const circles = useMemo(() => layout(rows, sizeBy, groups), [rows, sizeBy, groups]);
    const focused = rows.find((row) => row.galaxy === focus);
    return (
        <>
            <svg className="universe-svg" viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={label}>
                {circles.groups.map((group) => (
                    <g key={`g${group.group}`}>
                        <circle className="universe-group" cx={group.x} cy={group.y} r={group.r} />
                        <text className="universe-group-label" x={group.x} y={group.y - group.r + 13} textAnchor="middle">
                            {groups.groupLabel(group.group)}
                        </text>
                    </g>
                ))}
                {circles.galaxies.map((galaxy) => {
                    const mine = galaxy.galaxy === myGalaxy;
                    const fill = groups.colorOf(galaxy);
                    return (
                        <g key={galaxy.galaxy} className="universe-galaxy" tabIndex={0}
                            onMouseEnter={() => setFocus(galaxy.galaxy)} onFocus={() => setFocus(galaxy.galaxy)}
                            onClick={() => setFocus(galaxy.galaxy)} data-testid={`galaxy-${galaxy.galaxy}`}>
                            <title>{describe(galaxy, empires)}</title>
                            <circle cx={galaxy.x} cy={galaxy.y} r={Math.max(galaxy.r, 3)} fill={fill || "none"}
                                className={(fill ? "" : "universe-no-color") + (mine ? " universe-mine" : "")} />
                            {galaxy.r >= 14
                                ? <text className="universe-galaxy-label" x={galaxy.x} y={galaxy.y + 4} textAnchor="middle">{galaxy.galaxy}</text>
                                : null}
                        </g>
                    );
                })}
            </svg>
            <p className="universe-focus" aria-live="polite">
                {focused ? describe(focused, empires) : "Point at or tap a galaxy to see it."}
            </p>
        </>
    );
}

function GalaxyTable({ rows, empires, myGalaxy }) {
    return (
        <GameTable
            className="game-table universe-table"
            rows={rows}
            rowClassName={(row) => (row.galaxy === myGalaxy ? "universe-row-mine" : undefined)}
            columns={[
                { header: "Cluster", align: "left", cell: (row) => row.cluster },
                { header: "Galaxy", align: "left", cell: (row) => (row.galaxy === myGalaxy ? `${row.galaxy} (yours)` : row.galaxy) },
                { header: "Kingdoms alive", cell: (row) => row.kingdoms },
                { header: "Networth", cell: (row) => displayNumber(row.networth) },
                { header: "Empire", align: "left", cell: (row) => empireLabel(empires, row.empire) },
            ]}
        />
    );
}

function Choice({ name, value, onChange, options }) {
    return (
        <ToggleButtonGroup type="radio" name={name} value={value} onChange={onChange} size="sm">
            {options.map(([key, label]) => (
                <ToggleButton key={key} id={`${name}-${key}`} value={key} variant="outline-secondary">{label}</ToggleButton>
            ))}
        </ToggleButtonGroup>
    );
}

// A phone starts on the table, which reads better than a 375px chart; anything wider starts on the chart.
const wide = () => typeof window === "undefined" || !window.matchMedia || window.matchMedia("(min-width: 576px)").matches;

function Universe(props) {
    const [groupBy, setGroupBy] = useState("cluster");
    const [sizeBy, setSizeBy] = useState("kingdoms");
    const [view, setView] = useState(wide() ? "chart" : "table");
    const { galaxies, empires, scores, galaxies_inverted: galaxiesInverted, kingdomid } = props.data;
    const rows = useMemo(() => galaxyRows(galaxies, empires, scores), [galaxies, empires, scores]);
    const groups = useMemo(() => grouping(groupBy, rows, empires), [groupBy, rows, empires]);
    const myGalaxy = (galaxiesInverted || {})[kingdomid?.kd_id];
    const clusterCount = new Set(rows.map((row) => row.cluster)).size;
    const empireCount = new Set(rows.map((row) => row.empire).filter((empire) => empire != null)).size;
    const hint = groupBy === "empire"
        ? `${rows.length} galaxies in ${empireCount} ${empireCount === 1 ? "empire" : "empires"}, coloured by cluster.`
        : `${rows.length} galaxies in ${clusterCount} ${clusterCount === 1 ? "cluster" : "clusters"}, coloured by empire.`;
    return (
        <>
            <Header data={props.data} />
            <div className="universe">
                <Panel title={groupBy === "empire" ? "Galaxies by empire" : "Galaxies by cluster"} hint={hint}>
                    <div className="universe-controls">
                        <Choice name="universe-view" value={view} onChange={setView} options={[["chart", "Chart"], ["table", "Table"]]} />
                        {view === "chart"
                            ? <>
                                <Choice name="universe-group" value={groupBy} onChange={setGroupBy}
                                    options={[["cluster", "By cluster"], ["empire", "By empire"]]} />
                                <Choice name="universe-size" value={sizeBy} onChange={setSizeBy}
                                    options={[["kingdoms", "Size by kingdoms alive"], ["networth", "Size by networth"]]} />
                            </>
                            : null}
                    </div>
                    {rows.length === 0
                        ? <p>There are no galaxies yet.</p>
                        : view === "chart"
                            ? <>
                                <Legend items={groups.legend} />
                                <BubbleChart rows={rows} sizeBy={sizeBy} groups={groups} empires={empires} myGalaxy={myGalaxy}
                                    label={`Galaxies grouped by ${groupBy}, sized by ${sizeBy === "kingdoms" ? "kingdoms alive" : "networth"}`} />
                            </>
                            : <GalaxyTable rows={rows} empires={empires} myGalaxy={myGalaxy} />}
                </Panel>
            </div>
            <HelpButton scrollTarget={"clusterpolitics"} />
        </>
    );
}

export default Universe;
