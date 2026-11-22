import React from "react";
import { Topic, config, duration } from "../util";

function Politics(props) {
    const cfg = config(props.state);
    return (
        <Topic id="politics" title="Galaxy politics" lead="Choose your galaxy's leader and its policies.">
            <ul>
                <li><b>Leader</b>: every kingdom votes for one galaxymate. The kingdom with the most votes leads, and a tie keeps the current leader. The leader casts the galaxy's vote in cluster politics, and acts for the galaxy in empire politics: founding, joining or leaving an empire.</li>
                <li><b>Policies</b>: each doctrine has two policies, and each kingdom votes for one of them. The one with more votes is active for the whole galaxy, and a tie keeps the current one. The tab describes what each policy does.</li>
            </ul>
            <p>
                Once you change a vote, it stays for {duration(cfg.BASE_GALAXY_VOTE_COOLDOWN_EPOCHS, cfg)}, and the page
                says when you can change it again. Your first vote, and voting again for the same choice, start no wait.
            </p>
        </Topic>
    );
}

export default Politics;
