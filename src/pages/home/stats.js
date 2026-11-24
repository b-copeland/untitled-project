import React from "react";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "../../auth";
import { GameTable } from "../../components/gametable";
import { Panel } from "../../components/planner";
import { displayDuration, displayNumber, displayPercent } from "../../format";
import "./stats.css";

/** Fetched when the Stats tab opens, not with the rest of the game data on every page. Cleared with it at logout. */
export const STATS_KEY = ["game", "kingdomstats"];

const fetchStats = () => authFetch("api/kingdomstats").then((r) => {
    if (r.status >= 500) {
        throw new Error(`api/kingdomstats answered ${r.status}`);
    }
    return r.json();
});

/** A figure as the server says to write it; "--" when there is nothing to show (nothing to divide by). */
export function formatStat(value, format) {
    if (value === null || value === undefined) return "--";
    if (format === "percent") return displayPercent(value);
    if (format === "hours") return displayDuration(value * 3600);
    if (format === "decimal") {
        return Number(value).toLocaleString(undefined, { maximumFractionDigits: Math.abs(value) >= 100 ? 0 : 2 });
    }
    return displayNumber(value);
}

/**
 * The figures the advisors and the bots work from, for the player's own kingdom (``GET /api/kingdomstats``): strength
 * by role and per star, income per building, and the lines the advisors and the bots draw. All from the server; a
 * row's tip says how it is counted.
 */
export function KingdomStats() {
    const { data, isError } = useQuery({ queryKey: STATS_KEY, queryFn: fetchStats, staleTime: 0, refetchOnMount: "always" });
    if (isError) return <p className="page-note">The stats could not be loaded. Try again in a moment.</p>;
    if (!data) return <p className="page-note">Working out your stats...</p>;
    const sections = data.sections || [];
    if (sections.length === 0) return <p className="page-note">Your stats show once the round has started.</p>;
    const columns = [
        { header: "", align: "left", cell: (row) => (
            <span className={"stats-label" + (row.label === "Per star" ? " stats-sub" : "") + (row.tip ? " has-tip" : "")} title={row.tip || undefined}>
                {row.label}
            </span>
        ) },
        { header: "", cell: (row) => formatStat(row.value, row.format) },
    ];
    return (
        <div className="panel-grid kingdom-stats">
            {sections.map((section) => (
                <Panel key={section.title} title={section.title}>
                    <GameTable columns={columns} rows={section.rows} className="game-table stats-table" />
                </Panel>
            ))}
        </div>
    );
}
