import React from "react";
import { Topic, config, duration, pct } from "../util";

function Intel(props) {
    const cfg = config(props.state);
    return (
        <Topic id="intel" title="Intel" lead="Your galaxy's market for intel on kingdoms in other galaxies.">
            <p>
                Intel you revealed yourself (kingdom, military, shields, projects, structures or drones) can be sold to
                galaxymates for a cut of their spoils, or given away free.
            </p>
            <h4>The three tabs</h4>
            <ul>
                <li><b>Market</b>: intel for sale. A listing asks a cut of up to {pct(cfg.BASE_MAX_SHARE_CUT)}. Buying reveals it to you at once. A listing stays up until the seller's reveal ends, so several galaxymates can buy it. Intel you already have is marked "taken".</li>
                <li><b>Bounties</b>: ask the galaxy for intel, offering a cut, for up to {duration(cfg.BASE_INTEL_BOUNTY_MAX_EPOCHS, cfg)} (leave the length blank for the longest). The first galaxymate to answer with their own intel earns the cut. If you lack the intel a bounty wants, Attempt opens the Spy page with the right operation chosen. Fulfil it once your drones bring the intel back.</li>
                <li><b>Your intel</b>: what you can list or share, and the galaxymates you keep it from. They do not see your listings or bounties and get nothing from your free shares. They are not told.</li>
            </ul>
            <h4>How cuts work</h4>
            <ul>
                <li>A cut is paid from every successful attack the buyer makes on that kingdom while the intel lasts.</li>
                <li>Each kind of intel pays whoever provided it. The cuts add up, to at most {pct(cfg.BASE_MAX_TOTAL_SHARE_CUT)} on one kingdom.</li>
                <li>Once you have taken a kind of intel on a kingdom, you can not take it again at a lower cut. Nobody can undercut the first seller. Free intel never replaces intel you paid for.</li>
                <li>Free intel reaches every galaxymate at once and answers their bounties for it.</li>
                <li>Intel a galaxymate gave you can not be passed on.</li>
                <li>No cuts are paid on your empire's targets. Intel on a target goes to the whole empire instead (see Empire politics).</li>
            </ul>
            <p>
                On each row, the eye button opens that kingdom's page and the clipboard opens its intel market. On a
                kingdom's page, each kind of intel you lack offers to spy for it, buy it, or ask the galaxy. Each kind
                you have offers to share it.
            </p>
        </Topic>
    );
}

export default Intel;
