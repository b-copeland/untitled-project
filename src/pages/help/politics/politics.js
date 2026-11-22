import React from "react";
import { Topic, HelpTable, config, duration } from "../util";

function Politics(props) {
    const cfg = config(props.state);
    const all = props.state?.galaxy_policies_desc || {};
    const order = props.state?.order?.galaxy_policies || Object.keys(all);
    const playing = new Set(props.state?.state?.galaxy_policies || []);
    const rows = order.filter((key) => all[key]).map((key) => {
        const options = Object.values(all[key].options || {});
        return [
            <>{all[key].name}{playing.has(key) ? <b> (this round)</b> : null}</>,
            ...options.map((option) => <><b>{option.name}</b>: {option.desc}</>),
        ];
    });
    return (
        <Topic id="politics" title="Galaxy politics" lead="Choose your galaxy's leader and its policies.">
            <ul>
                <li><b>Leader</b>: every kingdom votes for one galaxymate. The kingdom with the most votes leads, and a tie keeps the current leader. The leader casts the galaxy's vote in cluster politics, and acts for the galaxy in empire politics: founding, joining or leaving an empire. Once you change your vote for leader, it stays for {duration(cfg.BASE_GALAXY_VOTE_COOLDOWN_EPOCHS, cfg)}, and the page says when you can change it again. Your first vote, and voting again for the same kingdom, start no wait.</li>
                <li><b>Policies</b>: each round plays {cfg.GALAXY_POLICIES_PER_ROUND} of the policies below, drawn when the round is made, for the whole round. Each has two options, and each kingdom may vote for one of them or none.</li>
                <li><b>Tallies</b>: a policy changes only at a tally, every {duration(cfg.GALAXY_POLICY_TALLY_EPOCHS, cfg)} from the start of the round. A tally counts how long each vote was held since the last one, and the option with the most time is active until the next. A vote switched just before a tally counts for little; a tie, or no votes, keeps the active option.</li>
                <li>So you can change a policy vote whenever you like: it counts from the moment you cast it. The Policies tab shows the active option, the votes, and how the time held so far is shared.</li>
                <li>Every option only helps your galaxy's own kingdoms. The pages show prices and times after them.</li>
            </ul>
            <HelpTable columns={[["Policy"], ["One option"], ["The other"]]} rows={rows} />
        </Topic>
    );
}

export default Politics;
