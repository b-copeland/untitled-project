import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import Select from 'react-select';
import Header from "../components/header";
import "./message.css";
import HelpButton from "../components/helpbutton";

function Message(props) {

    useEffect(() => {
        const updateFunc = () => {
            authFetch("api/clearnotifs", {
                method: "POST",
                body: JSON.stringify({"categories": ["messages"]})
            });
        }
        props.updateData(['notifs'], [updateFunc])
    }, [])

    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [message, setMessage] = useState("");
    const [results, setResults] = useState([]);

    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")"
        } else {
            return "Defender"
        }
        
    }
    const handleChange = (selectedOption) => {
        setSelected(selectedOption?.value || undefined);
    };
    const handleMessageInput = (e) => {
        setMessage(e.target.value);
    };
    const onClickSubmit = () => {
        const opts = {
            "message": message,
            "time": new Date().toISOString(),
        };
        const updateFunc = async () => authFetch('api/messages/' + selected, {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['messages'], [updateFunc]);
    };
    const kingdomOptions = Object.keys(props.data.kingdoms).map((kdId) => {
        return {"value": kdId, "label": kdFullLabel(kdId)}
    })
    const relevantMessages = selected !== undefined ? props.data.messages.filter((message) => message.with === selected) : props.data.messages;
    const messageDivs = relevantMessages.map((message, iter) => {
        if (message.from) {
            return <div className="message" key={"message_" + iter}>
                <span className="title-span">{kdFullLabel(props.data.kingdom.kdId) + "\n" + new Date(message.time).toLocaleString()}</span>
                <div className="text-box message-box">
                    <span className="message-text">{message.message}</span>
                </div>
            </div>
        } else {
            return <div className="message" key={"message_" + iter}>
                <div className="text-box message-box">
                    <span>{message.message}</span>
                </div>
                <span className="title-span" style={{textAlign: "right"}}>{kdFullLabel(message.with) + "\n" + new Date(message.time).toLocaleString()}</span>
            </div>
        }
    });
    const toasts = results.map((result, index) =>
        <Toast
            key={index}
            onClose={(e) => setResults(results.slice(0, index).concat(results.slice(index + 1, 999)))}
            show={true}
            bg={result.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Message Results</strong>
            </Toast.Header>
            <Toast.Body  className="text-black">{result.message}</Toast.Body>
        </Toast>
    );
    return (
        <>
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <Header data={props.data} />
            <div className="messages">
                <form className="attack-kingdom-form">
                    <label id="aria-label" htmlFor="aria-example-input">
                        Select a Kingdom
                    </label>
                    <Select
                        className="attack-kingdom-select"
                        isClearable={true}
                        backspaceRemovesValue={true}
                        options={kingdomOptions}
                        onChange={handleChange}
                        autoFocus={false}
                        defaultValue={kingdomOptions.filter(option => option.value === props.initialKd)}
                        styles={{
                            control: (baseStyles, state) => ({
                                ...baseStyles,
                                borderColor: state.isFocused ? 'var(--bs-body-color)' : 'var(--bs-primary-text)',
                                backgroundColor: 'var(--bs-body-bg)',
                            }),
                            placeholder: (baseStyles, state) => ({
                                ...baseStyles,
                                color: 'var(--bs-primary-text)',
                            }),
                            input: (baseStyles, state) => ({
                                ...baseStyles,
                                color: 'var(--bs-secondary-text)',
                            }),
                            option: (baseStyles, state) => ({
                                ...baseStyles,
                                backgroundColor: state.isFocused ? 'var(--bs-primary-bg-subtle)' : 'var(--bs-secondary-bg-subtle)',
                                color: state.isFocused ? 'var(--bs-primary-text)' : 'var(--bs-secondary-text)',
                            }),
                            menuList: (baseStyles, state) => ({
                                ...baseStyles,
                                backgroundColor: 'var(--bs-secondary-bg)',
                                // borderColor: 'var(--bs-secondary-bg)',
                            }),
                            singleValue: (baseStyles, state) => ({
                                ...baseStyles,
                                color: 'var(--bs-secondary-text)',
                            }),
                        }}
                    />
                </form>
                {
                    selected !== undefined
                    ? <div className="send-message">
                        <h3>Send Message</h3>
                        <Form.Control
                            className="send-message-input" 
                            as="textarea"
                            rows={3}
                            onChange={handleMessageInput}
                            placeholder={"Send a message... be nice"}
                        />
                        {
                            props.loading.messages
                            ? <Button className="message-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="message-button" variant="primary" type="submit" onClick={onClickSubmit}>
                                Send
                            </Button>
                        }
                    </div>
                    : null
                }
                <div className="latest-messages">
                    <h3>Latest Messages</h3>
                    <span>Only last 100 messages are saved</span>
                    {messageDivs}
                </div>
                <HelpButton scrollTarget={"message"}/>
            </div>
        </>
    )
}

export default Message;