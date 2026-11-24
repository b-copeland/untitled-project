import React from "react";
import { Topic } from "../util";
import { LastKnownHelp } from "../other/viewkingdom";

function Galaxy(props) {
    return (
        <Topic id="galaxy" title="Galaxy" lead="Browse the universe one galaxy at a time.">
            <p>
                Use the arrows or the two boxes to pick a cluster and galaxy, and switch between Table and Cards. Each
                kingdom has buttons to view it, attack, spy, launch missiles, message it, pin it to your Conquer page
                and, for kingdoms in other galaxies, trade intel on it.
            </p>
            <p>
                A kingdom in another galaxy shows its stars and networth only once they are revealed to you. You reveal
                them by spying, by buying or receiving intel, or when that kingdom attacks your galaxy or gets caught
                spying on you.
            </p>
            <LastKnownHelp state={props.state} />
            <h4>Sharing your kingdom</h4>
            <p>
                In your own galaxy, the share button on a galaxymate shows them almost everything about your kingdom
                for as long as you share. Only share with galaxymates you trust. Press it again to stop. Bots in your
                galaxy share their kingdoms with you on their own.
            </p>
        </Topic>
    );
}

export default Galaxy;
