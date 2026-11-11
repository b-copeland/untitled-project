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
