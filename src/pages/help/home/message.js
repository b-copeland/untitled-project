import React from "react";
import { Topic, config, num } from "../util";

function Message(props) {
    const cfg = config(props.state);
    return (
        <Topic id="message" title="Message" lead="Write to any kingdom, or to everyone in your galaxy.">
            <h4>Messages</h4>
            <p>
                Pick a conversation from the list, or press the new-message button and choose who to write to. The
                Message button on a kingdom opens a conversation with it.
            </p>
            <h4>Galaxy Board</h4>
            <p>A board for the kingdoms in your galaxy to coordinate, for example to share a Discord invite.</p>
            <ul>
                <li>Only kingdoms in your galaxy can read it, and it starts empty each round.</li>
                <li>A post is at most {num(cfg.GALAXY_BOARD_MAX_LENGTH)} characters. Web addresses become links.</li>
                <li>The board keeps the newest {num(cfg.GALAXY_BOARD_KEEP_POSTS)} posts.</li>
                <li>You can delete your own posts. The galaxy leader can delete any post, and can pin one to the top so it stays there.</li>
            </ul>
            <p>
                A number next to Message in the menu is how many messages and board posts you have not seen; each tab
                shows its own.
            </p>
        </Topic>
    );
}

export default Message;
