import React from "react";
import { Topic, config, duration, pct, perHour } from "../util";

const percent = (fraction, digits = 1) => (fraction != null ? `${(fraction * 100).toFixed(digits)}%` : "?");

function ClusterPolitics(props) {
    const cfg = config(props.state);
    const benefits = props.state.cluster_benefits || {};
    const order = props.state.order?.cluster_benefits || Object.keys(benefits);
    const playing = new Set(props.state.state?.cluster_benefits || []);
    return (
        <Topic id="clusterpolitics" title="Cluster politics"
            lead="Neighbouring galaxies vote to build up benefits that every kingdom among them shares.">
            <p>
                At the start of the round, galaxies are grouped into clusters of {cfg.CLUSTER_SIZE || "a few"}, for good.
                Galaxy 2:3 is galaxy 3 of cluster 2. The galaxies of a cluster can belong to different empires.
            </p>
            <h4>Voting</h4>
            <ul>
                <li>Each galaxy's leader casts one vote for a benefit, which every kingdom in the cluster gets.</li>
                <li>Each vote builds its benefit up by {percent(perHour(cfg.CLUSTER_VOTE_RATE, cfg))} of its maximum per hour. The rate is scaled so a whole cluster voting together builds as fast whatever its size.</li>
                <li>Every benefit fades by {percent(perHour(cfg.CLUSTER_DECAY_RATE, cfg))} of its maximum per hour, voted for or not. One nobody votes for fades away. One that only a few galaxies vote for may only hold steady.</li>
                <li>Once a galaxy's vote changes (cast, switched or withdrawn), it stays for {duration(cfg.CLUSTER_VOTE_COOLDOWN_EPOCHS, cfg)}. Voting again for the same benefit changes nothing and starts no wait.</li>
            </ul>
            <h4>Benefits</h4>
            <p>
                Each round plays {cfg.CLUSTER_BENEFITS_PER_ROUND} of the benefits below, drawn when the round is made,
                for the whole round; a galaxy can only vote for those. The higher a benefit gets, the less each vote
                adds: past each threshold, votes count for less.
            </p>
            <p>
                Benefits that raise a capacity (homes, hangars, workshops, silos, fuel storage, recruits in training)
                fade slowly when nobody keeps them up. A kingdom left over a capacity keeps what it has: it can not
                train or build more engineers, missiles or recruits until it is under again, units over the hangar
                space take room from homes, and fuel over the storage is lost.
            </p>
            <ul>
                {order.filter((key) => benefits[key]).map((key) => {
                    const benefit = benefits[key];
                    const thresholds = (benefit.thresholds || [])
                        .map(([level, efficiency]) => `past ${percent(level * benefit.max)}, votes add ${percent(efficiency, 0)} as much`)
                        .join("; ");
                    return (
                        <li key={key}>
                            <strong>{benefit.name}</strong>{playing.has(key) ? <b> (this round)</b> : null}: {benefit.desc}, by up to {pct(benefit.max)}.
                            {thresholds ? ` (${thresholds}.)` : ""}
                        </li>
                    );
                })}
            </ul>
            <p>
                The Benefits tab shows each benefit's level, how fast it is changing, and your galaxy's vote. The
                Galaxies tab shows how each galaxy is voting. Prices, times and capacities elsewhere already include
                the cluster's benefits.
            </p>
        </Topic>
    );
}

export default ClusterPolitics;
