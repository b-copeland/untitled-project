import React from "react";
import Button from "react-bootstrap/Button";

/**
 * A small button showing only an icon, to save room in tables. The name goes in the tooltip and the accessible label,
 * so it is still clear (and readable by a screen reader) what it does.
 *
 *     <IconButton icon={BsEye} label="View" onClick={...} />
 */
export function IconButton({ icon: Icon, label, onClick, disabled, variant = "primary", active = false }) {
    return (
        <Button
            className="icon-button"
            variant={active ? "success" : variant}
            size="sm"
            onClick={onClick}
            disabled={disabled}
            title={label}
            aria-label={label}
        >
            <Icon aria-hidden="true" />
        </Button>
    );
}
