import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Message(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "message") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="message" ref={yourElementRef} className="help-section">
            <h2>Message</h2>
            <p>
                Select a kingdom to view your message history. Only the latest 100 messages (to/from all kingdoms) are saved.
            </p>
        </div>
    )
}

export default Message;