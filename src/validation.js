/*
 * Checks a form field before it is sent, so the player hears "that will not work" straight away instead of from the
 * server afterwards (issue #50). These mirror what the server enforces; the server still decides, these only save the
 * round trip. Each returns an error message, or null if the value is fine. An empty field is fine on its own: it means
 * "none", and whether at least one field must be filled is the form's concern (see `anyFilled`).
 */

const isEmpty = (value) => value === undefined || value === null || String(value).trim() === "";

/** A whole number from 0 up, at most ``max`` if given. */
export function checkCount(value, { max, noun = "" } = {}) {
    if (isEmpty(value)) {
        return null;
    }
    const text = String(value).trim();
    if (!/^\d+$/.test(text)) {
        return "Enter a whole number, 0 or more";
    }
    if (max !== undefined && parseInt(text, 10) > max) {
        return `At most ${Math.floor(max).toLocaleString()}${noun ? " " + noun : ""}`;
    }
    return null;
}

/** A percentage from 0 to ``max`` (100 by default), decimals allowed. */
export function checkPercent(value, { max = 100 } = {}) {
    if (isEmpty(value)) {
        return null;
    }
    const text = String(value).trim();
    if (!/^\d+(\.\d+)?$/.test(text)) {
        return "Enter a percentage, such as 12.5";
    }
    if (parseFloat(text) > max) {
        return `At most ${max}%`;
    }
    return null;
}

/** The numbers in these fields must add up to no more than ``max``. Returns an error for the group, or null. */
export function checkTotal(values, { max, noun = "" }) {
    const total = Object.values(values).reduce((sum, value) => sum + (parseFloat(value) || 0), 0);
    if (total > max) {
        return `Total ${Math.floor(total).toLocaleString()} is over the limit of ${Math.floor(max).toLocaleString()}${noun ? " " + noun : ""}`;
    }
    return null;
}

/** True if at least one of the fields has something in it. */
export function anyFilled(values) {
    return Object.values(values).some((value) => !isEmpty(value) && parseFloat(value) !== 0);
}

/** The first error among field errors (an object of name -> error or null) and group errors, or null. */
export function firstError(...errors) {
    for (const group of errors) {
        const list = group && typeof group === "object" && !Array.isArray(group) ? Object.values(group) : [group];
        const found = list.find((error) => error);
        if (found) {
            return found;
        }
    }
    return null;
}
