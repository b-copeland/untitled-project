import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

const percent = (fraction, digits = 1) => (fraction != null ? `${(fraction * 100).toFixed(digits)}%` : "");

// The game works in epochs; players read hours.
const perHour = (perEpoch, epochSeconds) => (perEpoch != null && epochSeconds ? (perEpoch * 3600) / epochSeconds : null);

function ClusterPolitics(props) {
    const yourElementRef = useRef(null);

    useEffect(() => {
        if (Object.keys(props.state).length > 0 && props.scrollTarget === "clusterpolitics") {
            yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [props.state, props.scrollTarget]);

    const config = props.state.game_config || {};
    const benefits = props.state.cluster_benefits || {};
    const order = props.state.order?.cluster_benefits || Object.keys(benefits);
    return (
        <div id="clusterpolitics" ref={yourElementRef} className="help-section">
            <h2>Politics - Cluster</h2>
            <p>
                Galaxies are grouped into clusters of {config.CLUSTER_SIZE || "a few"} when the round begins, and a galaxy
                never leaves its cluster. Galaxy 2:3 is galaxy 3 of cluster 2. The galaxies of a cluster can belong to
                different empires.
            </p>
            <p>
                Each galaxy's leader casts the galaxy's one vote for a benefit, which every kingdom in the cluster gets.
                The leader can change or withdraw the vote, but once it has changed (cast, switched or withdrawn)
                it stays for {config.CLUSTER_VOTE_COOLDOWN_EPOCHS * config.BASE_EPOCH_SECONDS / 3600} hours, so it can not be
                flipped to chase whatever is ahead; the page says when it can change again. Voting for what the galaxy already
                votes for changes nothing and starts no wait. Every hour, each vote builds its benefit up by
                {" "}{percent(perHour(config.CLUSTER_VOTE_RATE, config.BASE_EPOCH_SECONDS))} of the benefit's maximum (shared out so that a whole cluster
                voting together builds as fast whatever its size), and every benefit fades by
                {" "}{percent(perHour(config.CLUSTER_DECAY_RATE, config.BASE_EPOCH_SECONDS))} of its maximum, whether anyone votes for it or not. A benefit
                nobody keeps up fades away, and one that only some galaxies vote for may only hold steady.
            </p>
            <p>
                The higher a benefit is, the less each vote adds: past each threshold below, votes are less effective.
            </p>
            <ul>
                {order.filter((key) => benefits[key]).map((key) => {
                    const benefit = benefits[key];
                    const thresholds = (benefit.thresholds || [])
                        .map(([level, efficiency]) => `past ${percent(level * benefit.max)}, votes add ${percent(efficiency, 0)} as much`)
                        .join("; ");
                    return (
                        <li key={key}>
                            <strong>{benefit.name}</strong>: {benefit.desc}, by up to {percent(benefit.max, 0)}.
                            {thresholds ? ` (${thresholds}.)` : ""}
                        </li>
                    );
                })}
            </ul>
            <p>
                The Cluster Politics page shows each benefit now, how fast it is changing, and how the galaxies of the
                cluster are voting. Prices on the Settle and Military pages, and drone production, already include the
                cluster's benefits.
            </p>
            <p>
                The Universe page shows every galaxy as a bubble inside a bigger one: its cluster (coloured by empire)
                or its empire (coloured by cluster). Galaxies are sized by their kingdoms still alive or their
                networth. Your galaxy has a white ring. Point at or tap a galaxy to see it, or switch to the table.
            </p>
        </div>
    );
}

export default ClusterPolitics;
