import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Message(props) {
    return (
        <div id="message" className="help-section">
            <h2>Message</h2>
            <p>
                Select a kingdom to view your message history. Only the latest 100 messages (to/from all kingdoms) are saved.
            </p>
        </div>
    )
}

export default Message;