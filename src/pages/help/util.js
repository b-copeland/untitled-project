import React from "react";
import Table from "react-bootstrap/Table";
import { displayPercent } from "../../format";

/*
 * Small helpers the help topics share. Every number comes from /api/state (``state.game_config`` and friends), so the
 * help always matches the rules. The game counts time in epochs; players read hours and minutes, never "epoch".
 */

export const config = (state) => state?.game_config || {};

const round = (value, places) => Math.round(value * 10 ** places) / 10 ** places;

/** A length of time given in epochs, as "6 hours", "1 hour" or "45 minutes". */
export function duration(epochs, cfg) {
    const seconds = (epochs || 0) * (cfg.BASE_EPOCH_SECONDS || 0);
    if (seconds > 0 && seconds < 3600) {
        const minutes = Math.round(seconds / 60);
        return `${minutes} minute${minutes === 1 ? "" : "s"}`;
    }
    const hours = round(seconds / 3600, 1);
    return `${hours} hour${hours === 1 ? "" : "s"}`;
}

/** The average of a random min-max time multiplier pair, as a duration. */
export const averageDuration = (min, max, cfg) => duration(((min || 0) + (max || 0)) / 2, cfg);

/** An amount per epoch, as an amount per hour (unrounded: ``num`` and ``pct`` round it for display). */
export const perHour = (perEpoch, cfg) => (cfg.BASE_EPOCH_SECONDS ? ((perEpoch || 0) * 3600) / cfg.BASE_EPOCH_SECONDS : 0);

/** A number with thousands separators and at most two decimals, or "?" before the state has loaded. */
export const num = (value) => (value == null || Number.isNaN(Number(value)) ? "?" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 }));

/** A fraction as a percentage, or "?" before the state has loaded. */
export const pct = (fraction) => (fraction == null ? "?" : displayPercent(fraction));

/** A compact table for a help topic: ``columns`` are [header, "left" | "right"], ``rows`` arrays of cells. */
export function HelpTable({ columns, rows, className = "" }) {
    return (
        <div className="table-scroll">
            <Table size="sm" hover className={`game-table help-table ${className}`.trim()}>
                <thead>
                    <tr>{columns.map(([header, align = "left"]) => <th key={header} style={{ textAlign: align }}>{header}</th>)}</tr>
                </thead>
                <tbody>
                    {rows.map((cells, row) => (
                        <tr key={row}>
                            {cells.map((cell, index) => <td key={index} style={{ textAlign: columns[index]?.[1] || "left" }}>{cell}</td>)}
                        </tr>
                    ))}
                </tbody>
            </Table>
        </div>
    );
}

/** A topic: the title, a one-line summary of what the page is for, then the body. */
export function Topic({ id, title, lead, children }) {
    return (
        <div id={id} className="help-section">
            <h2>{title}</h2>
            {lead ? <p className="help-lead">{lead}</p> : null}
            {children}
        </div>
    );
}
