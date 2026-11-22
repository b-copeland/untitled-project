import React from "react";
import { Topic, config, num } from "../util";

function GalaxyBoard(props) {
    const cfg = config(props.state);
    return (
        <Topic id="galaxyboard" title="Galaxy Board" lead="A board for the kingdoms in your galaxy to coordinate, for example to share a Discord invite.">
            <ul>
                <li>Only kingdoms in your galaxy can read it, and it starts empty each round.</li>
                <li>A post is at most {num(cfg.GALAXY_BOARD_MAX_LENGTH)} characters. Web addresses become links.</li>
                <li>The board keeps the newest {num(cfg.GALAXY_BOARD_KEEP_POSTS)} posts.</li>
                <li>You can delete your own posts. The galaxy leader can delete any post, and can pin one to the top so it stays there.</li>
                <li>A number next to Galaxy Board in the menu is how many posts you have not seen.</li>
            </ul>
        </Topic>
    );
}

export default GalaxyBoard;
