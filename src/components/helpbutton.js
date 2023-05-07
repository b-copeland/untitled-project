import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';
import Help from '../pages/help/help.js';
import "./helpbutton.css";

function HelpButton(props) {
    const [showHelp, setShowHelp] = useState(false);


    return (
        <div className="help-button-container">
            <Button
                className="help-button"
                variant="secondary"
                type="submit"
                onClick={() => setShowHelp(true)}
            >
                Help
            </Button>
            <Modal
                show={showHelp}
                onHide={() => setShowHelp(false)}
                animation={false}
                dialogClassName="help-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Help</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Help 
                        scrollTarget={props.scrollTarget}
                    />
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowHelp(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </div>
    )
}

export default HelpButton;