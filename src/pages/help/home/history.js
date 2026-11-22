import React from "react";
import { Topic } from "../util";

function History() {
    return (
        <Topic id="history" title="History" lead="What you have done to other kingdoms, and how your kingdom has grown.">
            <ul>
                <li><b>Attack</b>, <b>Spy</b> and <b>Missiles</b>: every attack, spy operation and missile launch you have made, with the results. Click a header to sort, and type under it to filter.</li>
                <li><b>Stats</b>: a chart of your kingdom over the round. Choose what to plot, such as networth, stars, population or drones.</li>
            </ul>
        </Topic>
    );
}

export default History;
