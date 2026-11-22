import React from "react";
import { Topic, averageDuration, config, num, pct } from "../util";

function Settle(props) {
    const cfg = config(props.state);
    return (
        <Topic id="settle" title="Settle" lead="Buy new stars without a fight.">
            <ul>
                <li>You can have up to {pct(cfg.BASE_MAX_SETTLE_CAP)} of your current stars being settled at once.</li>
                <li>New stars take {averageDuration(cfg.BASE_SETTLE_TIME_MIN_MULTIPLIER, cfg.BASE_SETTLE_TIME_MAX_MUTLIPLIER, cfg)} on average to arrive. Each batch arrives over a spread of times.</li>
                <li>Each star costs more the more stars you have: stars<sup>{num(cfg.BASE_SETTLE_STARS_POWER)}</sup> × {num(cfg.BASE_SETTLE_COST_CONSTANT)}. The page shows today's price, after your race, policies and cluster benefits.</li>
            </ul>
            <p>A settled star arrives empty. Build on it to make it pay.</p>
        </Topic>
    );
}

export default Settle;
