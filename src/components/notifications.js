import React, { useEffect, useState } from "react";
import useWebSocket from "react-use-websocket";
import Toast from "react-bootstrap/Toast";
import ToastContainer from "react-bootstrap/ToastContainer";

import { useInterval } from "../hooks";
import "./notifications.css";

const MAX_TOASTS = 10;

/** The websocket address of this server: the Flask dev server on 8000 locally, the same host in production. */
export function socketUrl() {
  const hostname = window.location.hostname;
  const port = hostname === 'localhost' ? ':8000' : '';
  const protocolPrefix = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return protocolPrefix + '//' + hostname + port + '/ws/listen';
}

/**
 * Listens for the server's push messages, shows each as a toast, and tells the caller which parts of the game data to
 * refresh. Registers the player's token on connect and every minute after, so the server keeps the socket mapped to them.
 */
export function useNotifications({ logged, session, updateData }) {
  const [messages, setMessages] = useState([]);
  const { sendMessage, lastMessage } = useWebSocket(socketUrl());

  const register = () => sendMessage(JSON.stringify({ "jwt": session.accessToken }));

  useEffect(() => {
    if (lastMessage !== null) {
      const message = JSON.parse(lastMessage.data);
      if ((message.update || []).length > 0) {
        updateData(message.update);
      }
      setMessages((previous) => [message, ...previous.slice(0, MAX_TOASTS - 1)]);
    }
  }, [lastMessage]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (logged) {
      register();
    }
  }, [logged]); // eslint-disable-line react-hooks/exhaustive-deps

  useInterval(register, 60000);

  return { messages, dismiss: (index) => setMessages((previous) => previous.filter((_, i) => i !== index)) };
}

/**
 * One notification. Clicking the text copies it (so a result or an error can be pasted somewhere); the toast closes on
 * its own timer or with its close button, not on that click, and the text can be selected normally.
 */
function Notification({ message, onClose }) {
  const [copied, setCopied] = useState(false);

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
    <Toast
      onClose={onClose}
      show={true}
      bg={message.status === "warning" ? "warning" : "info"}
      delay={message.delay || 5000}
      autohide
    >
      <Toast.Header>
        <strong className="me-auto">Notification - {message.category}</strong>
        {copied ? <small className="copied">Copied</small> : null}
      </Toast.Header>
      <Toast.Body className="text-black notification-text" onClick={copy} title="Click to copy">
        {message.message}
      </Toast.Body>
    </Toast>
  );
}

export function Notifications({ messages, dismiss }) {
  return (
    <ToastContainer position="top-end">
      {messages.map((message, index) => (
        <Notification key={index} message={message} onClose={() => dismiss(index)} />
      ))}
    </ToastContainer>
  );
}
