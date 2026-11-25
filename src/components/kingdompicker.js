import React from "react";
import { Picker } from "./planner";
import { targetOptions, teamOptionLabel, TeammateWarning } from "./teammates";

/**
 * The one way to choose a kingdom: a type-to-filter picker of every kingdom but your own, as "Name (1:3)", with your
 * galaxymates and empire-mates tagged and shaded (components/teammates.js).
 *
 * ``only`` limits it to those kingdom ids (a war's kingdoms, your empire's members). ``harm`` is what the page does to
 * the chosen kingdom ("Attacking them"): when set, choosing a teammate puts a warning under the picker. Leave it out
 * where choosing a teammate does no harm (a message, a delegate).
 */
export function KingdomPicker({ data, id, value, onChange, placeholder = "Type a kingdom to filter", autoFocus = false,
    only, harm }) {
    const allowed = only ? new Set(only.map(String)) : null;
    const options = targetOptions(data).filter((option) => !allowed || allowed.has(option.value));
    return (
        <>
            <Picker id={id} options={options} value={value === undefined || value === null ? value : String(value)}
                onChange={onChange} placeholder={placeholder} autoFocus={autoFocus} formatOptionLabel={teamOptionLabel} />
            {harm ? <TeammateWarning data={data} target={value} doing={harm} /> : null}
        </>
    );
}
