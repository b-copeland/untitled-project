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

/** The Settings page: the player's own preferences, saved to their account. The colour theme for now. */
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
            <HelpButton scrollTarget={"settings"} />
        </div>
    );
}

export default Settings;
