import React, { useEffect, useState } from "react";
import Select from "react-select";
import ProgressBar from "react-bootstrap/ProgressBar";
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

/** A label (and optional small ``hint``) on the left and its control on the right; stacks on a narrow screen. */
export function FieldRow({ label, hint, htmlFor, children }) {
    return (
        <div className="field-row">
            <label className="field-row-label" htmlFor={htmlFor}>
                {label}
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
