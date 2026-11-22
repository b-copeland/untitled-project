import React from "react";
import { Link } from "react-router-dom";
import { useFromHere } from "./pagehead";

/*
 * A kingdom's name, wherever it is shown, links to its page (pages/kingdom.js). The page it opens offers the way back.
 */

/** "Name (1:3)": a kingdom's name and its galaxy. */
export const kingdomLabel = (data, kdId) =>
    `${data?.kingdoms?.[kdId] || `Kingdom ${kdId}`} (${data?.galaxies_inverted?.[kdId] || "?"})`;

/** The kingdom page's path; ``tab`` opens it on a tab ("intel"). */
export const kingdomPath = (kdId, tab) => `/kingdom/${kdId}${tab ? `?tab=${tab}` : ""}`;

/** The path of a planner page (/attack, /spy, /launchmissiles) with ``kdId`` already chosen as the target. */
export const targetPath = (page, kdId, extra = {}) =>
    `${page}?${new URLSearchParams({ target: String(kdId), ...extra }).toString()}`;

/** A link to a kingdom's page. Shows ``children``, or the kingdom's name and galaxy. */
export function KingdomLink({ kdId, data, tab, children }) {
    const state = useFromHere();
    if (kdId === undefined || kdId === null || kdId === "") {
        return children ?? null;
    }
    return <Link className="kingdom-link" to={kingdomPath(kdId, tab)} state={state}>{children ?? kingdomLabel(data, kdId)}</Link>;
}
