import React, { useState } from "react";
import { authFetch } from "../auth";
import HelpButton from "../components/helpbutton";
import { ResultToasts, safeJson } from "../components/results";
import { Panel } from "../components/planner";
import { applyTheme, DEFAULT_THEME } from "../theme";
import "./settings.css";

/**
 * A small picture of a theme: its page, a card on it with a title and a muted line, a link and a button, drawn in the
 * theme's own colours (the data-theme attribute brings that theme's tokens, styles/themes.css).
 */
function ThemePreview({ value }) {
    return (
        <div className="theme-preview" data-theme={value} aria-hidden="true">
            <div className="theme-preview-card">
                <div className="theme-preview-title">Kingdom</div>
                <div className="theme-preview-muted">12,400 stars</div>
                <div className="theme-preview-row">
                    <span className="theme-preview-link">Galaxy 1:3</span>
                    <span className="theme-preview-button">Attack</span>
                </div>
            </div>
        </div>
    );
}

/**
 * Which notifications the panel shows: a switch for each kind, in the server's groups. Turning one off hides it on every
 * device; what it would have refreshed still refreshes. Each change saves the whole list.
 */
function NotificationChoices({ preferences, updateData, setResults }) {
    const options = preferences.options?.muted || [];
    const [chosen, setChosen] = useState(null);
    const muted = chosen || preferences.muted || [];
    const groups = [...new Set(options.map((option) => option.group))];

    const toggle = (kind) => {
        const before = muted;
        const next = muted.includes(kind) ? muted.filter((other) => other !== kind) : muted.concat(kind);
        setChosen(next);
        const updateFunc = () => authFetch("api/preferences", { method: "post", body: JSON.stringify({ muted: next }) })
            .then(safeJson)
            .then((r) => {
                if (r.status !== "success") {
                    setChosen(before);
                    setResults((previous) => previous.concat(r));
                }
            });
        updateData(["preferences"], [updateFunc]);
    };

    return (
        <div className="notification-choices">
            {groups.map((group) => (
                <fieldset key={group} className="notification-group">
                    <legend>{group}</legend>
                    {options.filter((option) => option.group === group).map(({ value, label }) => (
                        <div key={value} className="form-check form-switch">
                            <input className="form-check-input" type="checkbox" role="switch" id={`notify-${value}`}
                                checked={!muted.includes(value)} onChange={() => toggle(value)} />
                            <label className="form-check-label" htmlFor={`notify-${value}`}>{label}</label>
                        </div>
                    ))}
                </fieldset>
            ))}
        </div>
    );
}

/** Whether the Status page's advisors give advice: one switch. */
function AdvisorsChoice({ preferences, updateData, setResults }) {
    const [chosen, setChosen] = useState(null);
    const current = chosen || preferences.advisors || "on";
    const toggle = () => {
        const before = current;
        const next = current === "on" ? "off" : "on";
        setChosen(next);
        const updateFunc = () => authFetch("api/preferences", { method: "post", body: JSON.stringify({ advisors: next }) })
            .then(safeJson)
            .then((r) => {
                if (r.status !== "success") {
                    setChosen(before);
                    setResults((previous) => previous.concat(r));
                }
            });
        updateData(["preferences"], [updateFunc]);
    };
    return (
        <div className="form-check form-switch">
            <input className="form-check-input" type="checkbox" role="switch" id="advisors-on"
                checked={current === "on"} onChange={toggle} />
            <label className="form-check-label" htmlFor="advisors-on">Show advice on the Status page</label>
        </div>
    );
}

/** The Settings page: the player's own preferences, saved to their account. The colour theme, notifications and the
 * advisors. */
function Settings(props) {
    const [results, setResults] = useState([]);
    const preferences = props.data.preferences || {};
    const options = preferences.options?.theme || [];
    const [chosen, setChosen] = useState(null);
    const current = chosen || preferences.theme || DEFAULT_THEME;

    const choose = (theme) => {
        if (theme === current) {
            return;
        }
        const before = current;
        setChosen(theme);
        applyTheme(theme);  // shown at once; saved below
        const updateFunc = () => authFetch("api/preferences", { method: "post", body: JSON.stringify({ theme }) })
            .then(safeJson)
            .then((r) => {
                if (r.status !== "success") {
                    applyTheme(before);
                    setChosen(before);
                }
                setResults((previous) => previous.concat(r));
            });
        props.updateData(["preferences"], [updateFunc]);
    };

    return (
        <div className="settings">
            <ResultToasts title="Settings" results={results} setResults={setResults} />
            <Panel title="Colour theme" hint="Saved to your account, so it follows you to every device.">
                <div className="theme-choices" role="radiogroup" aria-label="Colour theme">
                    {options.map(({ value, label }) => (
                        <button key={value} type="button" role="radio" aria-checked={current === value} aria-label={label}
                            className={"theme-choice" + (current === value ? " selected" : "")}
                            disabled={!!props.loading?.preferences && current !== value}
                            onClick={() => choose(value)}>
                            <ThemePreview value={value} />
                            <span className="theme-choice-label">{label}</span>
                        </button>
                    ))}
                </div>
            </Panel>
            <Panel title="Notifications" hint="Turn off the kinds you do not want to see. The page still updates, and the news still has them.">
                <NotificationChoices preferences={preferences} updateData={props.updateData} setResults={setResults} />
            </Panel>
            <Panel title="Advisors" hint="Your advisors point out what in your kingdom may need fixing. Advice you hide stays hidden; the Status page can show it again.">
                <AdvisorsChoice preferences={preferences} updateData={props.updateData} setResults={setResults} />
            </Panel>
            <HelpButton scrollTarget={"settings"} />
        </div>
    );
}

export default Settings;
