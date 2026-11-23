import React, { useState } from "react";
import Button from 'react-bootstrap/Button';
import { authFetch } from "../../auth";
import { AmountInput, SubmitButton, useSliders } from "../../components/forms";
import HelpButton from "../../components/helpbutton";
import { ResultToasts, safeJson } from "../../components/results";
import { Panel, FieldRow, Stats } from "../../components/planner";
import "./shields.css";

const SHIELDS = [
    ["military", "Military", "Adds to your defense"],
    ["spy", "Spy", "Gives spy operations on you a chance to fail"],
    ["spy_radar", "Spy radar", "Gives spy operations on you a chance to reveal who sent them"],
    ["missiles", "Missiles", "Cuts the damage of missiles launched at you"],
];

/** The Shields page: the shields the kingdom pays fuel for, and the form to change them. */
function ShieldsPage(props) {
    return (
        <>
            <Shields data={props.data} loading={props.loading} updateData={props.updateData} />
            <HelpButton scrollTarget={"shields"} />
        </>
    );
}

/**
 * One slider per shield, from 0 to its most, starting at what the kingdom runs now, with the fuel it would cost per
 * hour. Update sends all four.
 */
export function Shields(props) {
    const kingdom = props.data.kingdom || {};
    const desc = props.data.shields?.desc || {};
    const climbs = kingdom.shields_climb || {};
    const current = Object.fromEntries(SHIELDS.map(([key]) => [key, (kingdom.shields?.[key] || 0) * 100]));
    // A raise climbs to its level: the slider starts where the shield is heading, so Update does not undo it.
    const heading = Object.fromEntries(SHIELDS.map(([key]) => [key, climbs[key] ? climbs[key].to * 100 : current[key]]));
    const sliders = useSliders(heading);
    const [results, setResults] = useState([]);

    const config = props.data.state?.game_config || {};
    const epochSeconds = config.BASE_EPOCH_SECONDS || 3600;
    const climbSeconds = (config.BASE_SHIELDS_CLIMB_EPOCHS ?? 1) * epochSeconds;
    const reachedAt = (key) => new Date(new Date(climbs[key].since).getTime() + climbSeconds * 1000);
    const clock = (date) => date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    // Fuel per hour for a shield at `percent`: the refresh charges cost x percent x stars every epoch.
    const fuelPerHour = (key, percent) => (desc[key]?.cost || 0) * percent * (kingdom.stars || 0) * 3600 / epochSeconds;
    const percentOf = (key) => (sliders.moved(key) ? sliders.value(key) : heading[key]);
    const totalNow = SHIELDS.reduce((sum, [key]) => sum + fuelPerHour(key, current[key]), 0);
    const totalNew = SHIELDS.reduce((sum, [key]) => sum + fuelPerHour(key, percentOf(key)), 0);
    const fuelNet = (kingdom.income?.fuel?.net || 0) * 3600 / epochSeconds;

    const onUpdate = () => {
        const body = Object.fromEntries(SHIELDS.map(([key]) => [key, percentOf(key)]));
        const updateFunc = () => authFetch('api/shields', { method: 'post', body: JSON.stringify(body) })
            .then(safeJson).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
        sliders.reset();
    };
    const whole = (n) => Math.round(n).toLocaleString();

    return (
        <div className="shields panel-grid">
            <ResultToasts title="Shields" results={results} setResults={setResults} />
            <Panel title="Shields" data-tour="shields-panel">
                {SHIELDS.map(([key, name, what]) => {
                    const most = Math.round((desc[key]?.max || 0) * 100);
                    return (
                        <FieldRow key={key} label={name} htmlFor={`${key}-shield`}
                            hint={`${what}. Now ${Math.round(current[key] * 10) / 10}%, ${whole(fuelPerHour(key, current[key]))} fuel per hour`
                                + (climbs[key] ? `. Rising to ${Math.round(heading[key] * 10) / 10}%, reached at ${clock(reachedAt(key))}` : "")}>
                            <AmountInput name={key} id={`${key}-shield`} label={`${name} shields`} suffix="%"
                                value={String(sliders.value(key))} onChange={sliders.onChange} max={most} />
                        </FieldRow>
                    );
                })}
                <p className="text-muted">
                    A raised shield rises to its new level over {Math.round(climbSeconds / 60)} minutes, and costs more
                    fuel as it rises. A lowered shield drops at once.
                </p>
                <div className="form-actions">
                    <span className="text-muted">
                        {sliders.changed
                            ? `${whole(totalNew)} fuel per hour, from ${whole(totalNow)}`
                            : `${whole(totalNow)} fuel per hour`}
                    </span>
                    {sliders.changed ? <Button variant="link" size="sm" onClick={sliders.reset}>Undo changes</Button> : null}
                    <SubmitButton loading={props.loading.kingdom} onClick={onUpdate}
                        blocked={(kingdom.fuel || 0) <= 0 ? "You can't set shields without fuel"
                            : sliders.changed ? null : "Move a slider to change a shield"}>
                        Update
                    </SubmitButton>
                </div>
            </Panel>
            <Panel title="Fuel" data-tour="shields-fuel">
                <Stats items={[
                    { label: "Fuel", value: whole(kingdom.fuel || 0) },
                    { label: "Net fuel per hour", value: whole(fuelNet) },
                    { label: "Shields per hour", value: whole(totalNow) },
                ]} />
            </Panel>
        </div>
    );
}

export default ShieldsPage;
