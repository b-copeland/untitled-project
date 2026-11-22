import React, { useEffect } from "react";
import "./toasts.css";

const HIDE_SUCCESS_MS = 6000;

// A stable key for each result object, so closing one does not hand its timer to the next.
const ids = new WeakMap();
let nextId = 0;
const idOf = (result) => {
    if (typeof result !== "object" || result === null) return String(result);
    if (!ids.has(result)) ids.set(result, ++nextId);
    return ids.get(result);
};

/** How a result looks: worked (green, closes itself), refused (amber, stays until closed). */
const kindOf = (result) => (result.status === "success" ? "success" : "warning");

/** One result: a card with a coloured edge, the page's title, the server's message and a close button. */
function Result({ title, result, onClose }) {
    const kind = kindOf(result);
    useEffect(() => {
        if (kind !== "success") {
            return undefined;
        }
        const timer = setTimeout(onClose, HIDE_SUCCESS_MS);
        return () => clearTimeout(timer);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps
    return (
        <div className={`game-toast game-toast-${kind}`} role={kind === "success" ? "status" : "alert"}>
            <div className="game-toast-text">
                <strong className="game-toast-title">{title}</strong>
                <div className="game-toast-message">{result.message}</div>
            </div>
            <button type="button" className="btn-close game-toast-close" aria-label="Close" onClick={onClose} />
        </div>
    );
}

/**
 * The results of the actions a page has sent (built a structure, attacked, ...), as cards in the bottom corner, above
 * the help button. Green when the server said it worked, and those close themselves after a few seconds; amber when it
 * did not, and those stay until closed. With several, one button closes them all.
 *
 *     const [results, setResults] = useState([]);
 *     ... .then(r => setResults(results.concat(r)))
 *     <ResultToasts title="Settle Results" results={results} setResults={setResults} />
 */
export function ResultToasts({ title, results, setResults }) {
    if (!results.length) {
        return null;
    }
    // Results are closed by identity, not by position: one closing on its timer must not close its neighbour.
    const close = (result) => setResults((previous) => previous.filter((other) => other !== result));
    return (
        <div className="game-toasts result-toasts" aria-live="polite">
            {results.length > 2 ? (
                <button type="button" className="btn btn-sm btn-secondary game-toasts-clear" onClick={() => setResults([])}>
                    Close all {results.length}
                </button>
            ) : null}
            {results.map((result) => (
                <Result key={idOf(result)} title={title} result={result} onClose={() => close(result)} />
            ))}
        </div>
    );
}

/** Reads a response as JSON; a server error that sends back a web page instead becomes a message the player can see. */
export const safeJson = (response) => response.json().catch(() => ({
    status: "error",
    message: `Something went wrong with that request (${response.status}). Try again.`,
}));
