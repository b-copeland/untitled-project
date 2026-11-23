// When the player last had the game open, kept in this browser so the Status page can say what changed since. Each
// device keeps its own. Storage can be blocked or empty (a private window): then there is no last visit, and the
// summary falls back to the last hour.
const KEY = "FARSTEEL_LAST_VISIT";
const TICK_MS = 60 * 1000;

let previous;  // the last visit before this page load, read once
let started = false;

function read() {
    try {
        const value = window.localStorage.getItem(KEY);
        return value && !Number.isNaN(Date.parse(value)) ? value : null;
    } catch (e) {
        return null;
    }
}

function stamp() {
    try {
        window.localStorage.setItem(KEY, new Date().toISOString());
    } catch (e) { /* not remembered */ }
}

export const VISIT_EVENT = "farsteel-visit";

/**
 * Start marking the game as open: now, then every minute while the tab is shown, and when it is hidden. A tab shown
 * again after being hidden counts as a new visit: the last visit becomes when it was hidden, and VISIT_EVENT fires.
 */
export function startVisitClock() {
    if (started) return;
    started = true;
    previous = read();
    stamp();
    window.setInterval(() => { if (document.visibilityState !== "hidden") stamp(); }, TICK_MS);
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") {
            stamp();
            return;
        }
        previous = read();
        stamp();
        window.dispatchEvent(new Event(VISIT_EVENT));
    });
}

/** When the game was last open before this page load, as an ISO time, or null. */
export function previousVisit() {
    return previous === undefined ? read() : previous;
}

/** For tests: forget what was read. */
export function resetVisitClock() {
    previous = undefined;
    started = false;
}
