import React from "react";
import { Topic } from "../util";

function Message() {
    return (
        <Topic id="message" title="Message" lead="Write to any kingdom.">
            <p>
                Pick a conversation from the list, or press the new-message button and choose who to write to. The
                Message button on a kingdom opens a conversation with it. A number next to Message in the menu is how
                many messages you have not read.
            </p>
        </Topic>
    );
}

export default Message;
