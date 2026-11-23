import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Button from "react-bootstrap/Button";
import CloseButton from "react-bootstrap/CloseButton";
import Modal from "react-bootstrap/Modal";
import { authFetch } from "../auth";
import { TOUR_STOPS, demoTarget, resolve, tourLength } from "../tour";
import "./tour.css";

/*
 * The guided tour for new players (the stops are in src/tour.js). It is offered once, on the first game page a player
 * opens, until they answer; the answer is the `tour` preference (api/untitledapp/preferences.py), so it follows the
 * player to every device and costs one write per answer:
 *   - "offer": not answered yet, so the offer opens;
 *   - "later": Not now, or the tour was left before its end; the Status page keeps a card that starts it;
 *   - "declined" (No thanks) and "done" (finished): only the Settings page starts it again.
 * While it runs, the tour lives in this tab only: a card at the bottom of the screen says where you are, Next and Back
 * open each stop's page, and the element the stop is about is outlined (any element with that `data-tour` name).
 */

const HIGHLIGHT = "data-tour-active";
const FIND_EVERY_MS = 150;
const FIND_FOR_MS = 6000;  // a page that loads its parts later (Attack, after the target) still gets its outline

const TourContext = React.createContext({ running: false, choice: undefined, start: () => {}, answer: () => {} });

/** The tour's state and actions: `running`, `choice` (the saved answer), `start()`, `answer(choice)`. */
export const useTour = () => React.useContext(TourContext);

/** The tour's controls for the whole app, and its card while it runs. Needs the router (it opens each stop's page). */
export function TourProvider({ data, updateData, stops = TOUR_STOPS, children }) {
    const navigate = useNavigate();
    const location = useLocation();
    const [run, setRun] = React.useState(null);  // { index, context } while the tour runs
    const choice = data.preferences?.tour;

    const answer = React.useCallback((tour) => {
        updateData(["preferences"], [() => authFetch("api/preferences", { method: "post", body: JSON.stringify({ tour }) })]);
    }, [updateData]);

    const start = React.useCallback(() => {
        const demo = demoTarget(data);
        setRun({ index: 0, context: { demo, demoName: demo !== undefined ? data.kingdoms?.[demo] : undefined } });
    }, [data]);

    const stop = run ? stops[run.index] : null;
    const path = stop ? resolve(stop.path, run.context) : null;
    const here = location.pathname + location.search;

    // Each stop opens its page once, when the tour gets there; the player can still wander off and come back.
    React.useEffect(() => {
        if (path && path !== here) navigate(path);
    }, [run?.index]);  // eslint-disable-line react-hooks/exhaustive-deps -- only when the stop changes

    React.useEffect(() => {
        if (!run) return undefined;
        document.body.classList.add("tour-running");
        return () => document.body.classList.remove("tour-running");
    }, [!!run]);  // eslint-disable-line react-hooks/exhaustive-deps -- on start and end

    useHighlight(stop?.target, path === here, here);

    const end = (finished) => {
        setRun(null);
        if (finished) {
            answer("done");
        } else if (choice !== "declined" && choice !== "done") {
            answer("later");  // left early: the Status page offers it again
        }
    };

    const value = { running: !!run, choice, start, answer };
    return (
        <TourContext.Provider value={value}>
            {children}
            {stop ? (
                <TourCard stop={stop} context={run.context} index={run.index} count={stops.length} away={path !== here}
                    onBack={() => setRun({ ...run, index: run.index - 1 })}
                    onNext={() => (run.index + 1 < stops.length ? setRun({ ...run, index: run.index + 1 }) : end(true))}
                    onShow={() => navigate(path)}
                    onEnd={() => end(false)} />
            ) : null}
        </TourContext.Provider>
    );
}

/** Outlines the element named `target` while the player is on its page, looking for it a while as the page loads. */
function useHighlight(target, onPage, here) {
    React.useEffect(() => {
        if (!target || !onPage) return undefined;
        let element = null;
        let waited = 0;
        const find = () => {
            element = document.querySelector(`[data-tour="${target}"]`);
            if (!element) return false;
            element.setAttribute(HIGHLIGHT, "");
            if (element.scrollIntoView) element.scrollIntoView({ block: "center", behavior: "smooth" });
            return true;
        };
        const timer = find() ? null : setInterval(() => {
            waited += FIND_EVERY_MS;
            if (find() || waited >= FIND_FOR_MS) clearInterval(timer);
        }, FIND_EVERY_MS);
        return () => {
            if (timer) clearInterval(timer);
            if (element) element.removeAttribute(HIGHLIGHT);
        };
    }, [target, onPage, here]);
}

function TourCard({ stop, context, index, count, away, onBack, onNext, onShow, onEnd }) {
    const last = index + 1 === count;
    return (
        <section className="tour-card" role="dialog" aria-label="Guided tour" aria-live="polite">
            <div className="tour-card-head">
                <span className="tour-card-step">Stop {index + 1} of {count}</span>
                <CloseButton aria-label="End the tour" title="End the tour" onClick={onEnd} />
            </div>
            <h3 className="tour-card-title">{stop.title}</h3>
            <p className="tour-card-text">{resolve(stop.text, context)}</p>
            <div className="tour-card-actions">
                {away ? <Button variant="link" size="sm" onClick={onShow}>Back to this stop</Button> : null}
                <Button variant="outline-primary" size="sm" disabled={index === 0} onClick={onBack}>Back</Button>
                <Button size="sm" onClick={onNext}>{last ? "Finish" : "Next"}</Button>
            </div>
        </section>
    );
}

/**
 * The offer on a player's first visit: take the tour now, later (Not now), or never (No thanks). Closing it counts
 * as Not now. Shown on game pages only, while the saved answer is still "offer".
 */
export function TourOffer() {
    const { running, choice, start, answer } = useTour();
    const [answered, setAnswered] = React.useState(false);  // hidden at once, before the saved answer comes back
    if (choice !== "offer" || running || answered) return null;
    const pick = (tour) => {
        setAnswered(true);
        if (tour) answer(tour); else start();
    };
    return (
        <Modal show onHide={() => pick("later")} animation={false} centered>
            <Modal.Header closeButton><Modal.Title>Take a quick tour?</Modal.Title></Modal.Header>
            <Modal.Body>
                <p>A walk through the main pages of the game and what each is for. It takes {tourLength()}, and
                    nothing is sent or spent while it runs.</p>
                <p className="text-muted mb-0">Not now keeps it on your Status page for later. You can always start it
                    from Settings.</p>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="link" onClick={() => pick("declined")}>No thanks</Button>
                <Button variant="outline-primary" onClick={() => pick("later")}>Not now</Button>
                <Button onClick={() => pick(null)}>Take the tour</Button>
            </Modal.Footer>
        </Modal>
    );
}

/** The Status page's reminder after Not now: start the tour, or say No thanks for good. */
export function TourReminder({ className = "" }) {
    const { running, choice, start, answer } = useTour();
    if (choice !== "later" || running) return null;
    return (
        <section className={`tour-reminder ${className}`.trim()}>
            <div>
                <h3 className="tour-reminder-title">Guided tour</h3>
                <p className="tour-reminder-text">A walk through the main pages, {tourLength()}.</p>
            </div>
            <div className="tour-reminder-actions">
                <Button variant="link" size="sm" onClick={() => answer("declined")}>No thanks</Button>
                <Button size="sm" onClick={start}>Take the tour</Button>
            </div>
        </section>
    );
}
