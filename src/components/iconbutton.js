import React from "react";

/**
 * A button showing only an icon, in the link colour with no button box, to save room in tables. The name goes in the
 * tooltip and the accessible label, so it is still clear (and readable by a screen reader) what it does.
 *
 *     <IconButton icon={BsEye} label="View" onClick={...} />
 */
export function IconButton({ icon: Icon, label, onClick, disabled, active = false }) {
    return (
        <button
            type="button"
            className={"icon-button" + (active ? " is-active" : "")}
            onClick={onClick}
            disabled={disabled}
            title={label}
            aria-label={label}
        >
            <Icon aria-hidden="true" />
        </button>
    );
}
