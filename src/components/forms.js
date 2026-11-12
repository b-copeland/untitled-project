import React, { useState } from "react";
import Form from "react-bootstrap/Form";
import InputGroup from "react-bootstrap/InputGroup";
import Button from "react-bootstrap/Button";

/**
 * The state of a form of named text fields: ``values``, an ``onChange`` for the inputs (it reads the input's name), and
 * ``reset``. ``set`` changes one field.
 */
export function useFormValues(initial = {}) {
    const [values, setValues] = useState(initial);
    return {
        values,
        set: (name, value) => setValues((previous) => ({ ...previous, [name]: value })),
        onChange: (event) => {
            const { name, value } = event.target;
            setValues((previous) => ({ ...previous, [name]: value }));
        },
        reset: () => setValues(initial),
    };
}

/**
 * A text input for a number in a table cell or a form, which shows the reason in red under the box when ``error`` is
 * set (so the player sees why before sending). ``suffix`` adds a unit after the box, such as "%".
 */
export function NumberField({ name, value, onChange, error, suffix, id, placeholder = "0", className = "game-field", disabled = false }) {
    const control = (
        <Form.Control
            className={className}
            id={id || `${name}-input`}
            name={name}
            onChange={onChange}
            value={value || ""}
            placeholder={placeholder}
            autoComplete="off"
            inputMode="decimal"
            isInvalid={Boolean(error)}
            disabled={disabled}
        />
    );
    return (
        <>
            {suffix
                ? <InputGroup className="game-field-group" hasValidation>
                    {control}
                    <InputGroup.Text className="game-field-suffix">{suffix}</InputGroup.Text>
                    <Form.Control.Feedback type="invalid">{error}</Form.Control.Feedback>
                </InputGroup>
                : <>
                    {control}
                    <Form.Control.Feedback type="invalid">{error}</Form.Control.Feedback>
                </>}
        </>
    );
}

/**
 * The button that sends a form. It is disabled, with the reason as its tooltip, while the data is still loading or
 * the form would not be accepted (``blocked`` is the reason, or null).
 */
export function SubmitButton({ loading, blocked, onClick, children, variant = "primary", className = "game-button" }) {
    if (loading) {
        return <Button className={className} variant={variant} type="submit" disabled>Loading...</Button>;
    }
    return (
        <Button className={className} variant={variant} type="submit" onClick={onClick} disabled={Boolean(blocked)} title={blocked || undefined}>
            {children}
        </Button>
    );
}

/**
 * A number input with a slider and a "Max" button, for spending from something shared (money, a pool of recruits,
 * 100%) across several boxes at once.
 *
 * ``soloMax`` is the most this box could take if nothing else were using the shared pool, and it sets the slider's
 * scale, so the slider never changes length as the other boxes are filled in. ``max`` is what is left for this box
 * right now; the part of the slider past it is greyed out and the thumb will not go there. Without ``soloMax`` the two
 * are the same. ``onChange`` gets an event-like ``{target: {name, value}}`` so it works with ``useFormValues``.
 * ``suffix`` adds a unit, such as "%".
 */
export function AmountInput({ name, id, value, onChange, max = 0, soloMax, error, suffix, disabled = false, label }) {
    const whole = (n) => (Number.isFinite(n) ? Math.max(Math.floor(n), 0) : (n === Infinity ? 1e9 : 0));
    const available = whole(max);
    const scale = Math.max(whole(soloMax === undefined ? max : soloMax), available);
    const number = parseFloat(value) || 0;
    const set = (next) => onChange({ target: { name, value: next === 0 ? "" : String(next) } });
    const none = disabled || scale < 1;
    const free = scale > 0 ? (available / scale) * 100 : 0;
    return (
        <div className="amount-input">
            <div className="amount-input-row">
                <Form.Control
                    className="amount-input-box"
                    id={id || `${name}-input`}
                    name={name}
                    aria-label={label || name}
                    value={value || ""}
                    onChange={onChange}
                    placeholder="0"
                    autoComplete="off"
                    inputMode="decimal"
                    isInvalid={Boolean(error)}
                    disabled={disabled}
                />
                {suffix ? <span className="amount-input-suffix">{suffix}</span> : null}
                <Button variant="outline-secondary" size="sm" className="amount-input-max" disabled={disabled || available < 1}
                    onClick={() => set(available)} title={`Fill in the most you can: ${available.toLocaleString()}`}>
                    Max
                </Button>
            </div>
            <div className="amount-input-track">
                <Form.Range
                    className="amount-input-slider"
                    style={{ "--avail": `${free}%`, "--val": `${scale > 0 ? (Math.min(number, scale) / scale) * 100 : 0}%` }}
                    aria-label={`${label || name} slider`}
                    min={0} max={scale} step={1}
                    value={Math.min(number, scale)}
                    disabled={none}
                    onChange={(event) => set(Math.min(parseInt(event.target.value, 10), available))}
                />
                <span className="amount-input-cap" title="The most you can choose">{available.toLocaleString()}</span>
            </div>
            {error ? <div className="amount-input-error">{error}</div> : null}
        </div>
    );
}
