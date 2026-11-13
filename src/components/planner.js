import React, { useEffect, useRef, useState } from "react";
import Select from "react-select";
import ProgressBar from "react-bootstrap/ProgressBar";
import { GiCrossedSwords, GiShield } from "react-icons/gi";
import "./planner.css";

/*
 * Building blocks for the pages where you plan an action against someone (Attack, Spy, Primitives): a titled card, a
 * label-and-control row, a few numbers side by side, the kingdom picker, and a bar that compares two numbers.
 */

/** A titled card. ``hint`` is a line of explanation under the title. */
export function Panel({ title, hint, children, className = "" }) {
    return (
        <section className={"panel " + className}>
            {title ? <h3 className="panel-title">{title}</h3> : null}
            {hint ? <p className="panel-hint">{hint}</p> : null}
            {children}
        </section>
    );
}

const TAGS = {
    revealed: ["Revealed", "tag-revealed", "You have intel on this, so the number is exact."],
    needed: ["Estimate needed", "tag-needed", "Not revealed to you, and it matters. Check the starting estimate and change it if you know better."],
    estimate: ["Your estimate", "tag-estimate", "You are using your own figure."],
    optional: ["Optional", "tag-optional", "Not needed. Fill it in to sharpen the forecast."],
};

/** A small badge saying where a number comes from: revealed (exact), needed (estimate it), or optional. */
export function StatusTag({ kind }) {
    const [text, className, title] = TAGS[kind];
    return <span className={"status-tag " + className} title={title}>{text}</span>;
}

/** A label (and optional small ``hint``) on the left and its control on the right; stacks on a narrow screen. ``status`` adds a StatusTag, ``tip`` puts a detail in a tooltip instead of on the page. */
const UNIT_STATS = { offense: [GiCrossedSwords, "offense each"], defense: [GiShield, "defense each"] };

/** A unit's offense or defense as a small icon and number, e.g. a sword and 5. The icon is the column header. */
export function UnitStat({ kind, value }) {
    const [Icon, words] = UNIT_STATS[kind];
    if (!value) return null;
    return <span className="unit-stat" title={`${value} ${words}`} aria-label={`${value} ${words}`}><Icon aria-hidden="true" />{value}</span>;
}

export function FieldRow({ label, hint, tip, stat, htmlFor, status, children }) {
    return (
        <div className="field-row">
            <label className={"field-row-label" + (tip ? " has-tip" : "")} htmlFor={htmlFor} title={tip}>
                <span>{label} {stat} {status ? <StatusTag kind={status} /> : null}</span>
                {hint ? <small>{hint}</small> : null}
            </label>
            <div className="field-row-control">{children}</div>
        </div>
    );
}

/** A row of numbers, each with a small caption. ``items`` are {label, value, tone} where tone is "good" or "bad". */
export function Stats({ items }) {
    return (
        <dl className="stats">
            {items.map(({ label, value, tone }) => (
                <div key={label} className={"stat" + (tone ? " stat-" + tone : "")}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                </div>
            ))}
        </dl>
    );
}

/**
 * Your number against theirs as a bar, with a mark where the two are equal. Ahead of it is green (you win), behind
 * it is red. ``ratio`` is yours divided by theirs.
 */
export function VersusBar({ ratio, yours = "Yours", theirs = "Theirs" }) {
    const shown = Math.max(Math.min(ratio || 0, 2), 0);
    return (
        <div className="versus" aria-label={`${yours} is ${Math.round((ratio || 0) * 100)}% of ${theirs}`}>
            <ProgressBar now={shown * 50} variant={ratio > 1 ? "success" : "danger"} />
            <span className="versus-mark" title={`Equal: ${theirs} would hold`} />
            <div className="versus-caption">
                <span>0</span>
                <span>{yours} = {Math.round((ratio || 0) * 100)}% of {theirs}</span>
                <span>2x</span>
            </div>
        </div>
    );
}

const pick = {
    control: (base, state) => ({
        ...base,
        borderColor: state.isFocused ? "var(--bs-body-color)" : "var(--bs-border-color)",
        backgroundColor: "var(--bs-body-bg)",
    }),
    placeholder: (base) => ({ ...base, color: "var(--bs-secondary-color)" }),
    input: (base) => ({ ...base, color: "var(--bs-body-color)" }),
    option: (base, state) => ({
        ...base,
        backgroundColor: state.isFocused ? "var(--bs-primary-bg-subtle)" : "var(--bs-body-bg)",
        color: "var(--bs-body-color)",
    }),
    menu: (base) => ({ ...base, zIndex: 1050 }),
    menuList: (base) => ({ ...base, backgroundColor: "var(--bs-body-bg)" }),
    singleValue: (base) => ({ ...base, color: "var(--bs-body-color)" }),
};

/** The type-to-filter picker, in the page's colours. ``options`` are {value, label}. */
export function Picker({ options, value, onChange, placeholder, autoFocus = false, searchable = true, id }) {
    return (
        <Select
            inputId={id}
            className="picker"
            options={options}
            value={options.find((option) => option.value === value) || null}
            onChange={(option) => onChange(option.value)}
            placeholder={placeholder}
            autoFocus={autoFocus}
            isSearchable={searchable}
            menuPortalTarget={typeof document !== "undefined" ? document.body : undefined}
            styles={{ ...pick, menuPortal: (base) => ({ ...base, zIndex: 2000 }) }}
        />
    );
}

/**
 * Asks the server about a plan, but only after the player has stopped changing it for ``ms`` (so dragging a slider is
 * one request, not hundreds), never twice for the same plan, and ignoring an answer that has been overtaken by a newer
 * question. ``plan`` is the thing to ask about, or null for nothing to ask; ``ask(plan)`` returns a promise of the answer.
 * Returns ``[answer, pending, setAnswer]``: ``pending`` is true from the first change until the answer is back, and
 * ``setAnswer`` lets the page put in an answer it got some other way.
 */
export function useServerForecast(plan, ask, ms = 700) {
    const wanted = plan === null ? "" : JSON.stringify(plan);
    const settled = useDebounced(wanted, ms);
    const [answer, setAnswerState] = useState({});
    const [inflight, setInflight] = useState(false);
    const given = useRef("");  // the plan an answer was handed to us for, so it is not asked again
    useEffect(() => {
        if (!settled) {
            setAnswerState({});
            setInflight(false);
            return;
        }
        if (settled === given.current) {
            given.current = "";
            setInflight(false);
            return;
        }
        let current = true;
        setInflight(true);
        Promise.resolve(ask(JSON.parse(settled)))
            .then((result) => { if (current) { setAnswerState(result); setInflight(false); } })
            .catch(() => { if (current) setInflight(false); });
        return () => { current = false; };
    }, [settled]);
    // Put in an answer got some other way. ``forPlan`` is the plan it answers, if it is also the page's next plan.
    const setAnswer = (result, forPlan) => {
        given.current = forPlan === undefined || forPlan === null ? "" : JSON.stringify(forPlan);
        setAnswerState(result);
        setInflight(false);
    };
    // Waiting out the pause, or waiting for an answer: nothing else, so it cannot get stuck on.
    const pending = (wanted !== settled && wanted !== given.current) || inflight;
    return [answer, pending, setAnswer];
}

/** ``value``, but only after it has stopped changing for ``ms``. For asking the server about what is being typed. */
export function useDebounced(value, ms = 700) {
    const [settled, setSettled] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setSettled(value), ms);
        return () => clearTimeout(timer);
    }, [value, ms]);
    return settled;
}

/** "03:12:09" for the time until (or since) ``date``; "--" if there is none. */
export function clockUntil(date) {
    if (date === undefined) {
        return "--";
    }
    const seconds = Math.abs(Date.parse(date) - Date.now()) / 1000;
    const pad = (n) => String(Math.floor(n)).padStart(2, "0");
    return `${pad(seconds / 3600)}:${pad((seconds / 60) % 60)}:${pad(seconds % 60)}`;
}
