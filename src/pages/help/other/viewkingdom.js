import React from "react";
import { Topic, config } from "../util";
import { StrengthHelp } from "../home/home";

function ViewKingdom(props) {
    return (
        <Topic id="viewkingdom" title="Kingdom page" lead="Everything you know about one kingdom.">
            <p>
                Every kingdom name in the game links to its page. Its tabs (Kingdom, Military, Structures, Production,
                Projects and Shields) show only what you have revealed by spying, received from galaxymates, or been shown by a
                galaxymate who shares their kingdom with you. Unknown values show as "?". The buttons at the top open
                Attack, Spy or Launch Missiles with this kingdom chosen.
            </p>
            <p>
                For a kingdom in another galaxy, an Intel market tab sits beside Kingdom info. Each kind of intel you
                lack offers to spy for it, buy it, or ask the galaxy for it. Each kind you have offers to share it (see
                Intel).
            </p>
            <p>
                The Production tab, filled by Spy on Production, shows what the kingdom has in production: units in
                training, structures being built, engineers in training, stars being settled and missiles being built,
                with how many arrive within each time shown and how many are queued in all. Last-known intel does not
                keep it, since it changes as things arrive.
            </p>
            <p>
                With their military revealed, the Military tab forecasts their strength over time. With their
                production revealed too, it adds their training as it arrives. Military shields and military
                efficiency you have not revealed start at the most there can be.
            </p>
            <StrengthHelp />
            <LastKnownHelp state={props.state} />
        </Topic>
    );
}

/** How last-known intel is shown, with the ages in hours from the game's thresholds. Also used by the Galaxy topic. */
export function LastKnownHelp({ state }) {
    const cfg = config(state);
    const hours = (epochs) => Math.round((epochs || 0) * (cfg.BASE_EPOCH_SECONDS || 0) / 3600);
    return (
        <p>
            When intel ends, you keep what it last showed. Those last-known values fill in wherever the kingdom
            appears, coloured by age: <span className="last-known last-known-fresh">yellow</span> under
            {" "}{hours(cfg.LAST_KNOWN_FRESH_EPOCHS)} hours, <span className="last-known last-known-aging">orange</span> under
            {" "}{hours(cfg.LAST_KNOWN_AGING_EPOCHS)} hours, and <span className="last-known last-known-stale">red</span> after
            that. Hover over a value to see its age. Fresh intel always replaces them. A galaxymate who stops sharing
            leaves you their whole kingdom as it was then.
        </p>
    );
}

export default ViewKingdom;
