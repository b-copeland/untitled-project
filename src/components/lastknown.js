import React from "react";

/**
 * Last-known intel. The server sends another kingdom's live fields (what is revealed now) and, in ``last_known``, a
 * snapshot of each kind of intel that has ended: ``{category: {ended, values}}``, only for categories not revealed now.
 * ``withLastKnown`` lays the snapshots under the live fields, so a page reads one kingdom object as before, and says
 * which values came from a snapshot and when it ended. Live values always win, down to each nested value.
 */

const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

function overlay(target, source, ended, sources, prefix) {
    Object.entries(source || {}).forEach(([key, value]) => {
        const path = prefix ? `${prefix}.${key}` : key;
        if (isObject(value)) {
            if (!isObject(target[key])) {
                target[key] = {};
            }
            overlay(target[key], value, ended, sources, path);
            return;
        }
        target[key] = value;
        if (ended) {
            sources[path] = ended;
        } else {
            delete sources[path];
        }
    });
}

/**
 * ``{kingdom, endedOf, categories}``: the kingdom with snapshot values where nothing live is known, ``endedOf(path)``
 * (e.g. "drones", "units.attack", or "units" for the earliest of its values) giving when the snapshot a shown value came
 * from ended (undefined for a live value), and ``categories``, each snapshot category's end.
 */
export function withLastKnown(info) {
    const { last_known: lastKnown, ...live } = info || {};
    const kingdom = {};
    const sources = {};
    const categories = {};
    Object.entries(lastKnown || {})
        .sort(([, a], [, b]) => Date.parse(a.ended) - Date.parse(b.ended))
        .forEach(([category, entry]) => {
            categories[category] = entry.ended;
            overlay(kingdom, entry.values, entry.ended, sources, "");
        });
    overlay(kingdom, live, undefined, sources, "");
    const endedOf = (path) => {
        if (sources[path]) {
            return sources[path];
        }
        const nested = Object.keys(sources).filter((key) => key.startsWith(path + ".")).map((key) => sources[key]);
        return nested.length ? nested.sort((a, b) => Date.parse(a) - Date.parse(b))[0] : undefined;
    };
    return { kingdom, endedOf, categories };
}

/** "fresh", "aging" or "stale": how long ago ``ended`` was, against the game's thresholds (in epochs). */
export function staleness(ended, gameConfig, now = Date.now()) {
    const epoch = (gameConfig?.BASE_EPOCH_SECONDS || 3600) * 1000;
    const epochs = (now - Date.parse(ended)) / epoch;
    if (epochs < (gameConfig?.LAST_KNOWN_FRESH_EPOCHS ?? 12)) return "fresh";
    if (epochs < (gameConfig?.LAST_KNOWN_AGING_EPOCHS ?? 24)) return "aging";
    return "stale";
}

/** How long ago, in real time: "40m ago", "5h ago", "2d 3h ago". */
export function ago(ended, now = Date.now()) {
    const minutes = Math.max(Math.floor((now - Date.parse(ended)) / 60000), 0);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 48) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ${hours % 24}h ago`;
}

/**
 * A value as it is shown: plain when live, coloured by how old it is when it comes from a snapshot, with the age in
 * its tooltip. ``ended`` is from ``endedOf``.
 */
export function Known({ ended, gameConfig, children }) {
    if (!ended || children === undefined || children === null || children === "") {
        return <>{children}</>;
    }
    return (
        <span className={`last-known last-known-${staleness(ended, gameConfig)}`} title={`Last known, ${ago(ended)}`}>
            {children}
        </span>
    );
}

/** A line saying the values below are last known, and how old: for a tab or a card whose intel has ended. */
export function LastKnownNote({ ended, gameConfig, what = "These values" }) {
    if (!ended) {
        return null;
    }
    return (
        <div className={`last-known-note last-known-${staleness(ended, gameConfig)}`}>
            {what} are last known, from intel that ended {ago(ended)}.
        </div>
    );
}
