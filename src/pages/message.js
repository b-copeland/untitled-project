import React, { useEffect, useRef, useState } from "react";
import { authFetch } from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import { FiSend, FiArrowLeft, FiEdit } from "react-icons/fi";
import Header from "../components/header";
import "./message.css";
import HelpButton from "../components/helpbutton";
import { ResultToasts, safeJson } from "../components/results";
import { Picker } from "../components/planner";

const shortTime = (time) => {
    const date = new Date(time);
    const sameDay = date.toDateString() === new Date().toDateString();
    return sameDay ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : date.toLocaleDateString([], { month: "short", day: "numeric" });
};

/**
 * Messages as a chat: your conversations on the left (newest first, with a preview), the chosen one on the right as
 * bubbles with a box to write in at the bottom. On a phone it shows one at a time, with a back arrow.
 */
function Message(props) {
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const [draft, setDraft] = useState("");
    const [results, setResults] = useState([]);
    const [composing, setComposing] = useState(false);  // picking someone new to write to
    const thread = useRef(null);

    useEffect(() => {
        const updateFunc = () => authFetch("api/clearnotifs", { method: "POST", body: JSON.stringify({ categories: ["messages"] }) });
        props.updateData(['notifs'], [updateFunc]);
    }, []);

    const kdLabel = (kdId) => props.data.kingdoms[parseInt(kdId)] + " (" + props.data.galaxies_inverted[kdId] + ")";
    const options = Object.keys(props.data.kingdoms).map((kdId) => ({ value: kdId, label: kdLabel(kdId) }));

    // Group every message by who it was with, oldest first inside a conversation, newest conversation first.
    const byPerson = {};
    (props.data.messages || []).forEach((message) => { (byPerson[message.with] = byPerson[message.with] || []).push(message); });
    Object.values(byPerson).forEach((list) => list.sort((a, b) => new Date(a.time) - new Date(b.time)));
    const people = Object.keys(byPerson).sort((a, b) => new Date(byPerson[b].at(-1).time) - new Date(byPerson[a].at(-1).time));
    if (selected !== undefined && !byPerson[selected]) {
        byPerson[selected] = [];  // a conversation that has not started yet
    }
    const shown = selected !== undefined ? byPerson[selected] : [];

    useEffect(() => {
        if (thread.current) thread.current.scrollTop = thread.current.scrollHeight;
    }, [selected, shown.length]);

    const send = () => {
        const text = draft.trim();
        if (!text || selected === undefined) return;
        const body = { message: text, time: new Date().toISOString() };
        const updateFunc = async () => authFetch('api/messages/' + selected, { method: 'POST', body: JSON.stringify(body) })
            .then(safeJson).then(r => { setResults((previous) => previous.concat(r)); if (r.status === "success") setDraft(""); });
        props.updateData(['messages'], [updateFunc]);
    };
    const onKeyDown = (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            send();
        }
    };
    const open = (kdId) => { setSelected(kdId); setComposing(false); setDraft(""); };

    return (
        <>
            <Header data={props.data} />
            <div className={"messenger" + (selected !== undefined ? " messenger-open" : "")}>
                <ResultToasts title="Message Results" results={results} setResults={setResults} />
                <aside className="messenger-list">
                    <div className="messenger-list-head">
                        <h2>Messages</h2>
                        <Button variant="outline-primary" size="sm" onClick={() => setComposing(!composing)} title="Write to someone new">
                            <FiEdit aria-hidden="true" /> New
                        </Button>
                    </div>
                    {composing
                        ? <div className="messenger-new"><Picker id="message-new" options={options} onChange={open} placeholder="Who to write to?" autoFocus /></div>
                        : null}
                    <ul className="messenger-people">
                        {people.length === 0 && !composing ? <li className="messenger-empty">No messages yet. Press New to write to someone.</li> : null}
                        {people.map((kdId) => {
                            const last = byPerson[kdId].at(-1);
                            return (
                                <li key={kdId}>
                                    <button type="button" className={"messenger-person" + (kdId === selected ? " active" : "")} onClick={() => open(kdId)}>
                                        <span className="messenger-avatar" aria-hidden="true">{String(props.data.kingdoms[parseInt(kdId)] || "?").charAt(0).toUpperCase()}</span>
                                        <span className="messenger-person-text">
                                            <span className="messenger-person-name">{props.data.kingdoms[parseInt(kdId)]}<small>{shortTime(last.time)}</small></span>
                                            <span className="messenger-preview">{last.from ? "You: " : ""}{last.message}</span>
                                        </span>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                </aside>

                <section className="messenger-thread">
                    {selected === undefined
                        ? <div className="messenger-placeholder">Choose a conversation, or press New to start one.</div>
                        : <>
                            <header className="messenger-thread-head">
                                <button type="button" className="messenger-back" onClick={() => setSelected(undefined)} aria-label="Back to conversations"><FiArrowLeft /></button>
                                <div>
                                    <strong>{props.data.kingdoms[parseInt(selected)]}</strong>
                                    <small>{props.data.galaxies_inverted[selected]}</small>
                                </div>
                            </header>
                            <div className="messenger-bubbles" ref={thread}>
                                {shown.length === 0 ? <div className="messenger-placeholder">No messages yet. Say hello.</div> : null}
                                {shown.map((message, index) => (
                                    <div key={index} className={"bubble-row " + (message.from ? "mine" : "theirs")}>
                                        <div className="bubble">
                                            <span className="bubble-text">{message.message}</span>
                                            <time>{new Date(message.time).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}</time>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <div className="messenger-compose">
                                <Form.Control as="textarea" rows={1} value={draft} placeholder="Write a message (Enter to send, Shift+Enter for a new line)"
                                    onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown} aria-label="Message" />
                                <Button onClick={send} disabled={!draft.trim() || props.loading.messages} aria-label="Send"><FiSend aria-hidden="true" /></Button>
                            </div>
                        </>}
                </section>
                <HelpButton scrollTarget={"message"}/>
            </div>
        </>
    );
}

export default Message;
