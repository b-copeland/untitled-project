import React from "react";
import { Topic, config, duration } from "../util";

function Conquer(props) {
    const cfg = config(props.state);
    return (
        <Topic id="conquer" title="Conquer overview" lead="Every kingdom you know something about, and the ones you are watching.">
            <p>
                <b>Revealed</b> lists every kingdom with at least one kind of intel revealed to you. A reveal lasts
                {" "}{duration(cfg.BASE_REVEAL_DURATION_MULTIPLIER, cfg)}. You get one when:
            </p>
            <ul>
                <li>your spy operation on it succeeds;</li>
                <li>you buy intel on it, a galaxymate answers your bounty, or a galaxymate shares it free (see Intel);</li>
                <li>it attacks a kingdom in your galaxy;</li>
                <li>its spy operation on you fails, or your spy radar catches it.</li>
            </ul>
            <p>
                <b>Pinned</b> lists the kingdoms you pinned, from here or from the Galaxy page.
            </p>
            <p>
                The buttons on each row go to that kingdom's page, or to Attack, Spy or Launch Missiles with it already
                chosen. The Intel button opens what you can share, buy or ask for on it.
            </p>
        </Topic>
    );
}

export default Conquer;
