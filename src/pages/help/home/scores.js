import React from "react";
import { HelpTable, Topic, config, num, perHour } from "../util";

function Scores(props) {
    const cfg = config(props.state);
    const points = cfg.NETWORTH_POINTS || [];
    return (
        <Topic id="scores" title="Scores" lead="The leaderboards. Points decide the round.">
            <p>
                <b>Points</b> build up all round. While your kingdom is in the top {points.length || "few"} by networth,
                it earns points every hour, at the rate for its rank below. Rising early and staying there counts for
                more than a high networth at the very end.
            </p>
            <p>
                The boards show Points, Networth, Stars and Galaxy networth. Names on the Points board are always
                hidden. On the Networth and Stars boards, you see the name of a kingdom from another galaxy only if its
                stats are revealed to you.
            </p>
            <HelpTable columns={[["Networth rank", "right"], ["Points per hour", "right"]]}
                rows={points.map((value, index) => [index + 1, num(perHour(value, cfg))])} />
        </Topic>
    );
}

export default Scores;
