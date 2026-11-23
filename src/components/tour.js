import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Button from "react-bootstrap/Button";
import CloseButton from "react-bootstrap/CloseButton";
import Modal from "react-bootstrap/Modal";
import { FiChevronDown, FiChevronUp } from "react-icons/fi";
import { IconButton } from "./iconbutton";
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
 * While it runs, the tour lives in this tab only: a card says where you are (above the Help button, or on a phone a
 * sheet along the bottom edge, and it folds to one line), Next and Back open each stop's page, and the element the stop
 * is about is outlined (any element with that `data-tour` name) and scrolled into the space the card leaves free.
 */

const HIGHLIGHT = "data-tour-active";
const FIND_EVERY_MS = 150;
const FIND_FOR_MS = 6000;  // a page that loads its parts later (Attack, after the target) still gets its outline

const TourContext = React.createContext({ running: false, choice: undefined, start: () => {}, answer: () => {} });

/**
 * Why Send attack and Send spies are off while the tour runs: the tour shows them, and a player's first attack should
 * not be one sent on its example target without intel.
 */
export const TOUR_NO_SEND = "Sending is off while the tour runs";

/** The tour's state and actions: `running`, `choice` (the saved answer), `start()`, `answer(choice)`. */
export const useTour = () => React.useContext(TourContext);

/** The tour's controls for the whole app, and its card while it runs. Needs the router (it opens each stop's page). */
export function TourProvider({ data, updateData, stops = TOUR_STOPS, children }) {
    const navigate = useNavigate();
    const location = useLocation();
    const [run, setRun] = React.useState(null);  // { index, context } while the tour runs
    const [folded, setFolded] = React.useState(false);
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
                    folded={folded} onFold={() => setFolded(!folded)}
                    onBack={() => setRun({ ...run, index: run.index - 1 })}
                    onNext={() => (run.index + 1 < stops.length ? setRun({ ...run, index: run.index + 1 }) : end(true))}
                    onShow={() => navigate(path)}
                    onEnd={() => end(false)} />
            ) : null}
        </TourContext.Provider>
    );
}

/**
 * Where the page should scroll so the player sees `rect` (an element's box, relative to the screen): in the free band
 * between the sticky top bar and the tour card. A tall element shows from its top, where its title is; a short one
 * sits a fifth of the way down the band, leaving the rest for what follows it (a tab bar's tab, say). Returns the
 * distance to scroll by.
 */
export function scrollToFrame(rect, { topBar = 0, cardTop, viewport }) {
    const bandTop = topBar + FRAME_GAP;
    const bandBottom = (cardTop ?? viewport) - FRAME_GAP;
    const room = bandBottom - bandTop;
    const offset = rect.height >= room ? 0 : (room - rect.height) * SHORT_TARGET_AT;
    return rect.top - (bandTop + offset);
}

const FRAME_GAP = 12;
const SHORT_TARGET_AT = 0.2;
const REFRAME_AFTER_MS = 800;  // once more, in case the page above it was still loading

function frame(element) {
    const topBar = document.querySelector(".topbar");
    const card = document.querySelector(".tour-card");
    const by = scrollToFrame(element.getBoundingClientRect(), {
        topBar: topBar && getComputedStyle(topBar).display !== "none" ? topBar.getBoundingClientRect().bottom : 0,
        cardTop: card ? card.getBoundingClientRect().top : undefined,
        viewport: window.innerHeight,
    });
    if (Math.abs(by) > 4 && window.scrollTo) window.scrollTo({ top: window.scrollY + by, behavior: "smooth" });
}

/**
 * Outlines the element named `target` while the player is on its page, looking for it a while as the page loads, and
 * scrolls it into the part of the screen the card leaves free.
 */
function useHighlight(target, onPage, here) {
    React.useEffect(() => {
        if (!target || !onPage) return undefined;
        let element = null;
        let waited = 0;
        let again = null;
        const find = () => {
            element = document.querySelector(`[data-tour="${target}"]`);
            if (!element) return false;
            element.setAttribute(HIGHLIGHT, "");
            frame(element);
            again = setTimeout(() => frame(element), REFRAME_AFTER_MS);
            return true;
        };
        const timer = find() ? null : setInterval(() => {
            waited += FIND_EVERY_MS;
            if (find() || waited >= FIND_FOR_MS) clearInterval(timer);
        }, FIND_EVERY_MS);
        return () => {
            if (timer) clearInterval(timer);
            if (again) clearTimeout(again);
            if (element) element.removeAttribute(HIGHLIGHT);
        };
    }, [target, onPage, here]);
}

/**
 * The card: the stop's title and words with Back and Next, or, folded, one line with Next, so the page behind it can
 * be seen (it stays folded from stop to stop until opened again).
 */
function TourCard({ stop, context, index, count, away, folded, onFold, onBack, onNext, onShow, onEnd }) {
    const last = index + 1 === count;
    const next = <Button size="sm" onClick={onNext}>{last ? "Finish" : "Next"}</Button>;
    const fold = <IconButton icon={folded ? FiChevronUp : FiChevronDown} label={folded ? "Show the tour's words" : "Fold the tour away"} onClick={onFold} />;
    const close = <CloseButton aria-label="End the tour" title="End the tour" onClick={onEnd} />;
    if (folded) {
        return (
            <section className="tour-card folded" role="dialog" aria-label="Guided tour" aria-live="polite">
                <div className="tour-card-head">
                    <span className="tour-card-line"><span className="tour-card-step">{index + 1}/{count}</span> {stop.title}</span>
                    {fold}{next}{close}
                </div>
            </section>
        );
    }
    return (
        <section className="tour-card" role="dialog" aria-label="Guided tour" aria-live="polite">
            <div className="tour-card-head">
                <span className="tour-card-step">Stop {index + 1} of {count}</span>
                {fold}{close}
            </div>
            <h3 className="tour-card-title">{stop.title}</h3>
            <p className="tour-card-text">{resolve(stop.text, context)}</p>
            <div className="tour-card-actions">
                {away ? <Button variant="link" size="sm" onClick={onShow}>Back to this stop</Button> : null}
                <Button variant="outline-primary" size="sm" disabled={index === 0} onClick={onBack}>Back</Button>
                {next}
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
