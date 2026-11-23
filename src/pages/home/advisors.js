import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "../../auth";
import { ResultToasts, safeJson } from "../../components/results";

/** The advisors' answer is fetched each time the Status page is opened (so a change in Settings shows at once),
 * not with the rest of the game data on every page. It is cleared with the game data at logout. */
export const ADVISORS_KEY = ["game", "advisors-card"];

const fetchAdvisors = () => authFetch("api/advisors").then((r) => {
    if (r.status >= 500) {
        throw new Error(`api/advisors answered ${r.status}`);
    }
    return r.json();
});

function AdviceItem({ item, onHide, busy }) {
    return (
        <li className={`advice advice-${item.kind}`}>
            <span className="advice-text">{item.text}</span>
            {" "}
            {item.links.map((link) => (
                <Link key={link.to + link.label} className="advice-link" to={link.to}>{link.label}</Link>
            ))}
            {item.hideable ? (
                <button type="button" className="advice-hide" disabled={busy} onClick={() => onHide(item.id, !item.hidden)}>
                    {item.hidden ? "Show again" : "Hide"}
                </button>
            ) : null}
        </li>
    );
}

/**
 * The list the server's advisors give (``GET /api/advisors``, docs/advisors.md): most serious first, each with links to
 * where it is fixed. Any advice can be hidden for good; hidden advice waits behind a small toggle.
 */
export function AdvisorsList({ answer, onHide, busy = false }) {
    const [showHidden, setShowHidden] = useState(false);
    if (!answer) {
        return <p className="overview-line overview-muted">Your advisors are looking over your kingdom.</p>;
    }
    if (answer.enabled === false) {
        return (
            <p className="overview-line overview-muted">
                Your advisors are off. <Link to="/settings">Turn them on in Settings.</Link>
            </p>
        );
    }
    const advice = answer.advice || [];
    const shown = advice.filter((item) => !item.hidden);
    const hidden = advice.filter((item) => item.hidden);
    return (
        <>
            {shown.length > 0
                ? <ul className="overview-advice">{shown.map((item) => <AdviceItem key={item.id} item={item} onHide={onHide} busy={busy} />)}</ul>
                : <p className="overview-line overview-muted">Your advisors have nothing to report.</p>}
            {hidden.length > 0 ? (
                <>
                    <button type="button" className="advice-toggle" onClick={() => setShowHidden(!showHidden)}>
                        {showHidden ? "Close hidden advice" : `Show hidden advice (${hidden.length})`}
                    </button>
                    {showHidden
                        ? <ul className="overview-advice advice-hidden-list">{hidden.map((item) => <AdviceItem key={item.id} item={item} onHide={onHide} busy={busy} />)}</ul>
                        : null}
                </>
            ) : null}
        </>
    );
}

/** The Advisors card's contents: fetches the advice and hides or shows one when asked. */
export function Advisors() {
    const queryClient = useQueryClient();
    const [results, setResults] = useState([]);
    const [busy, setBusy] = useState(false);
    const { data } = useQuery({ queryKey: ADVISORS_KEY, queryFn: fetchAdvisors, staleTime: 0, refetchOnMount: "always" });

    const onHide = (id, hidden) => {
        setBusy(true);
        authFetch("api/advisors/hide", { method: "post", body: JSON.stringify({ id, hidden }) })
            .then(safeJson)
            .then((r) => {
                if (r.status !== "success") {
                    setResults((previous) => previous.concat(r));
                }
                return queryClient.invalidateQueries({ queryKey: ADVISORS_KEY });
            })
            .finally(() => setBusy(false));
    };

    return (
        <>
            <ResultToasts title="Advisors" results={results} setResults={setResults} />
            <AdvisorsList answer={data} onHide={onHide} busy={busy} />
        </>
    );
}

export default Advisors;
