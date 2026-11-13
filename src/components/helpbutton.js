import React, { useState } from "react";
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import { FiHelpCircle } from "react-icons/fi";
import Help from '../pages/help/help.js';
import "./helpbutton.css";

/**
 * A round floating help button at the bottom-right of the screen (the usual place for one). It opens the help on the
 * topic for the page it is on (``scrollTarget``).
 */
function HelpButton(props) {
    const [showHelp, setShowHelp] = useState(false);

    return (
        <>
            <button type="button" className="help-fab" onClick={() => setShowHelp(true)} aria-label="Help" title="Help for this page">
                <FiHelpCircle aria-hidden="true" />
                <span className="help-fab-label">Help</span>
            </button>
            <Modal
                show={showHelp}
                onHide={() => setShowHelp(false)}
                animation={false}
                dialogClassName="help-modal"
                scrollable
            >
                <Modal.Header closeButton>
                    <Modal.Title>Help</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Help scrollTarget={props.scrollTarget} />
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowHelp(false)}>Close</Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}

export default HelpButton;
