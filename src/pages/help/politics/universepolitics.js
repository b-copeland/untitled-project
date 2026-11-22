import React from "react";
import { Topic, config, duration, num } from "../util";

function UniversePolitics(props) {
    const cfg = config(props.state);
    return (
        <Topic id="universepolitics" title="Universe politics" lead="Universe-wide elections that change the rules for everyone.">
            <p>
                Elections come round regularly. Voting is open for {duration(cfg.BASE_ELECTION_LENGTH_MULTIPLIER, cfg)},
                and the winning policies then hold for {duration(cfg.BASE_ELECTION_RESULTS_DURATION_MULTIPLIER, cfg)}.
                The page says when the next vote opens.
            </p>
            <ul>
                <li>Buy votes with money, at {num(cfg.BASE_VOTES_COST)} each, while voting is open.</li>
                <li>Spend them on the policies you want, in either doctrine and in any amounts. Spent votes can not be taken back.</li>
                <li>When voting closes, the policy with the most votes in each doctrine wins. Votes you did not spend carry over to the next election.</li>
            </ul>
        </Topic>
    );
}

export default UniversePolitics;
