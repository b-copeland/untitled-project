import React from "react";
import { Topic } from "../util";

function News() {
    return (
        <Topic id="news" title="News" lead="What has happened to you and the kingdoms around you.">
            <ul>
                <li><b>Kingdom</b>: attacks, spy operations and missiles against your kingdom.</li>
                <li><b>Galaxy</b>: the same for every kingdom in your galaxy, in both directions.</li>
                <li><b>Universe</b>: empires denouncing each other and going to war.</li>
                <li><b>Empire</b>: set aside for your empire's own news. Nothing is posted there yet.</li>
            </ul>
            <p>
                Click a column header to sort, and type in the box under it to filter. A number next to a tab is how
                many items you have not seen yet.
            </p>
        </Topic>
    );
}

export default News;
