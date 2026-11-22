import React from "react";
import { Topic, HelpTable, config, duration, num } from "../util";

function UniversePolitics(props) {
    const cfg = config(props.state);
    const all = props.state?.universe_policies_desc || {};
    const order = props.state?.order?.universe_policies || Object.keys(all);
    const rows = order.filter((key) => all[key]).map((key) => {
        const options = Object.values(all[key].options || {});
        return [
            <>{all[key].name}{all[key].first_election_only ? <b> (first election only)</b> : null}</>,
            ...options.map((option) => <><b>{option.name}</b>: {option.desc}</>),
        ];
    });
    return (
        <Topic id="universepolitics" title="Universe politics" lead="Universe-wide elections that decide whose playstyle to rein in.">
            <p>
                The first election opens {duration(cfg.BASE_FIRST_ELECTION_START_MULTIPLIER, cfg)} after the round starts.
                Voting is open for {duration(cfg.BASE_ELECTION_LENGTH_MULTIPLIER, cfg)}, and the winners then hold until the
                next election closes; the next one opens {duration(cfg.BASE_ELECTION_RESULTS_DURATION_MULTIPLIER, cfg)} after
                the last one closed. While an election is open, the last result stays in force.
            </p>
            <ul>
                <li>Each election has {cfg.UNIVERSE_POLICIES_PER_ELECTION} policies on its ballot. The first always has Primitives, and no later one does. Each later ballot is drawn when the election before it closes, from the policies that were not on that one, so the page shows it days ahead.</li>
                <li>Every option punishes a playstyle: the vote decides whose. Wealth's options hit only the leaders: the {cfg.UNIVERSE_WEALTH_TOP_KINGDOMS} kingdoms, or the kingdoms of the {cfg.UNIVERSE_WEALTH_TOP_GALAXIES} galaxies, with the most networth.</li>
                <li>Buy votes with money, at {num(cfg.BASE_VOTES_COST)} each, and spend them on the ballot's options while voting is open, in any amounts. Spent votes can not be taken back; votes you did not spend carry over to the next election. Nobody sees how anyone else voted.</li>
                <li>When voting closes, the option with the most votes in each policy wins. A tie, no votes at all included, is decided at random.</li>
            </ul>
            <HelpTable columns={[["Policy"], ["One option"], ["The other"]]} rows={rows} />
        </Topic>
    );
}

export default UniversePolitics;
