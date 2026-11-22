import React from "react";
import { Topic } from "../util";

function News() {
    return (
        <Topic id="news" title="News" lead="What has happened to you and the kingdoms around you.">
            <ul>
                <li><b>Kingdom</b>: attacks, spy operations and missiles against your kingdom.</li>
                <li><b>Galaxy</b>: attacks and missiles involving any kingdom in your galaxy, in both directions (not spy operations); your galaxymates' attacks on primitives, with when their generals are home; kingdoms joining the galaxy or dying; and changes of galaxy leader or policy.</li>
                <li><b>Empire</b>: your empire's own news, seen only by its members: galaxies asking to join, invited, joining and leaving; denouncements, wars and surrenders it is part of; and the targets it marks and ends, with what each spoils fund paid out.</li>
                <li><b>Universe</b>: empires denouncing each other, going to war and surrendering, and universe elections opening and their results.</li>
            </ul>
            <p>
                Click a column header to sort, and type in the box under it to filter. A number next to a tab is how
                many items you have not seen yet.
            </p>
        </Topic>
    );
}

export default News;
