import React, { useEffect, useState } from "react";
import useWebSocket from "react-use-websocket";

import { useInterval } from "../hooks";
import { useSwipeToDismiss } from "./swipe";
import "./toasts.css";

const MAX_KEPT = 50;
let nextId = 0;

/** The websocket address of this server: the Flask dev server on 8000 locally, the same host in production. */
export function socketUrl() {
  const hostname = window.location.hostname;
  const port = hostname === 'localhost' ? ':8000' : '';
  const protocolPrefix = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return protocolPrefix + '//' + hostname + port + '/ws/listen';
}

/**
 * Listens for the server's push messages, collects them for the Notifications panel, and tells the caller which parts of the game data to
 * refresh. Registers the player's token on connect and every minute after, so the server keeps the socket mapped to them.
 *
 * ``muted`` is the kinds the player turned off in Settings (their preferences): those still refresh the data they name,
 * but are not shown.
 */
export function useNotifications({ logged, session, updateData, muted = [] }) {
  const [messages, setMessages] = useState([]);
  const { sendMessage, lastMessage } = useWebSocket(socketUrl());

  const register = () => sendMessage(JSON.stringify({ "jwt": session.accessToken }));

  useEffect(() => {
    if (lastMessage !== null) {
      const message = JSON.parse(lastMessage.data);
      if ((message.update || []).length > 0) {
        updateData(message.update);
      }
      if (!muted.includes(message.kind)) {
        setMessages((previous) => [{ ...message, id: ++nextId, received: Date.now() }, ...previous.slice(0, MAX_KEPT - 1)]);
      }
    }
  }, [lastMessage]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (logged) {
      register();
    }
  }, [logged]); // eslint-disable-line react-hooks/exhaustive-deps

  useInterval(register, 60000);

  return {
    messages,
    clear: () => setMessages([]),
    remove: (id) => setMessages((previous) => previous.filter((message) => message.id !== id)),
  };
}

/** "just now", "4 min ago", "2 h ago": how long ago a notification came in. */
export function ago(time, now = Date.now()) {
  const minutes = Math.floor((now - time) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  return `${Math.floor(minutes / 60)} h ago`;
}

/**
 * One notification in the list. Clicking the text copies it (so a result or an error can be pasted somewhere); the text
 * can still be selected normally. On a touch screen, swiping it sideways removes it.
 */
function Notification({ message, now, onDismiss }) {
  const [copied, setCopied] = useState(false);
  const swipe = useSwipeToDismiss(onDismiss);

  const copy = () => {
    // Selecting text to copy by hand is not a click to copy.
    if (window.getSelection && window.getSelection().toString() !== "") {
      return;
    }
    const done = () => setCopied(true);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(message.message).then(done).catch(() => {});
    }
  };

  return (
    <li className={`notification notification-${message.status === "warning" ? "warning" : "info"} swipeable`}
      {...swipe.handlers} style={swipe.style}>
      <div className="notification-meta">
        <span className="notification-category">{message.category}</span>
        <span className="notification-time">{copied ? <span className="copied">Copied</span> : ago(message.received, now)}</span>
      </div>
      <div className="notification-text" onClick={copy} title="Click to copy">{message.message}</div>
    </li>
  );
}

const SHOWN = 3;

/**
 * Every notification since the player last closed them, in one panel in the top corner, those needing attention first
 * and then newest first: the first few,
 * and the rest behind "Show all". It closes itself a while after the last one came in (as long as the longest
 * notification asks to stay, at least 8 seconds), unless the pointer is over it or one of them needs attention (an
 * attack on you, say), in which case it stays until closed. Closing it clears the list; swiping one away removes just that
 * one.
 */
export function Notifications({ messages, clear, remove = () => {} }) {
  const [expanded, setExpanded] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [now, setNow] = useState(Date.now());
  const newest = messages[0]?.received || 0;
  const stay = Math.max(8000, ...messages.map((message) => message.delay || 5000));

  useEffect(() => {
    if (!messages.length || hovered || messages.some((message) => message.status === "warning")) {
      return undefined;
    }
    const timer = setTimeout(() => { clear(); setExpanded(false); }, Math.max(newest + stay - Date.now(), 1000));
    return () => clearTimeout(timer);
  }, [newest, hovered, messages.length]); // eslint-disable-line react-hooks/exhaustive-deps
  useInterval(() => setNow(Date.now()), messages.length ? 30000 : null);

  if (!messages.length) {
    return null;
  }
  // What needs attention (an attack on you) first, then the rest; each newest first.
  const ordered = [...messages.filter((m) => m.status === "warning"), ...messages.filter((m) => m.status !== "warning")];
  const shown = expanded ? ordered : ordered.slice(0, SHOWN);
  const warnings = messages.filter((message) => message.status === "warning").length;
  return (
    <section className="game-toasts notifications-panel" aria-label="Notifications" aria-live="polite"
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <header className="notifications-head">
        <strong>Notifications</strong>
        <span className="notifications-count">
          {messages.length}{warnings ? `, ${warnings} needing attention` : ""}
        </span>
        <button type="button" className="btn-close" aria-label="Close notifications" onClick={() => { clear(); setExpanded(false); }} />
      </header>
      <ul className="notifications-list">
        {shown.map((message) => <Notification key={message.id} message={message} now={now} onDismiss={() => remove(message.id)} />)}
      </ul>
      {messages.length > SHOWN ? (
        <button type="button" className="btn btn-link btn-sm notifications-more" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Show the latest" : `Show all ${messages.length}`}
        </button>
      ) : null}
    </section>
  );
}
