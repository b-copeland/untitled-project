import { displayPercent } from "../../../format";
import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Intel(props) {
    const yourElementRef = useRef(null);

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "intel") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const config = props.state.game_config || {};
    const maxHours = (config.BASE_INTEL_BOUNTY_MAX_EPOCHS || 0) * (config.BASE_EPOCH_SECONDS || 0) / 3600;
    return (
        <div id="intel" ref={yourElementRef} className="help-section">
            <h2>Conquer - Intel</h2>
            <p>
                Your galaxy trades intel on its own market. Intel you have revealed yourself on a kingdom in another
                galaxy (its kingdom, military, shields, projects, structures or drones) can be listed for a cut of the
                spoils, or shared free. The Intel button wherever a kingdom is shown does the same for that kingdom.
            </p>
            <ul>
                <li>
                    <strong>Market.</strong> A listing asks a cut of up to {displayPercent(config.BASE_MAX_SHARE_CUT)}.
                    Any galaxymate can buy it, and it stays listed, so several can buy the same intel. It lasts until
                    your reveal ends. Buying gives the buyer the reveal at once. A listing of intel you have already
                    taken is greyed out and tagged "taken".
                </li>
                <li>
                    <strong>Free.</strong> Intel shared free needs no accepting: every galaxymate gets it at once, and
                    it answers their bounties for it.
                </li>
                <li>
                    <strong>Bounties.</strong> Ask the galaxy for intel you want, offering a cut, for up
                    to {maxHours} hours (leave the length blank for the longest). The first
                    galaxymate to answer it with their own intel earns the cut, and the bounty leaves the board. If you
                    do not have the intel a bounty asks for, Attempt opens the Spy page with that kingdom and operation
                    chosen; once the spies bring it back, Fulfil the bounty.
                </li>
            </ul>
            <p>
                A cut is paid from every successful attack the buyer makes on that kingdom while the intel lasts. Each
                kind of intel is paid to whoever provided it, and the cuts add up, to at most
                {" "}{displayPercent(config.BASE_MAX_TOTAL_SHARE_CUT)} for one kingdom. Once you have taken a kind of intel
                on a kingdom, you can not take the same kind on it at a lower cut, so nobody can cut the first sharer
                out by offering it cheaper. Free intel never replaces intel you paid a cut for.
            </p>
            <p>
                Intel a galaxymate gave you can not be passed on. On Your intel you can keep your intel from chosen
                galaxymates: they do not see your listings or bounties, can not buy or answer them, and get nothing from your
                free shares.
                They are not told.
            </p>
            <p>
                On each row, the eye button opens the kingdom the intel is on, as far as you have revealed it, and the
                clipboard button opens the intel market for that kingdom alone. The two are tabs of one dialog, so you
                can move between them.
            </p>
            <p>
                Viewing a kingdom in another galaxy, each kind of intel says what you can do about it. Without it: Spy on
                it (the Spy page, with that operation chosen), buy the cheapest listing you can take, or Ask the galaxy,
                which opens the bounty form with that intel filled in. With intel of your own: share it, for a cut or
                free. Military, structures, projects and shields are at the top of their tab; kingdom intel at the top
                of the Kingdom tab, and drones next to the drones value.
            </p>
            <p>
                The history keeps the most recent purchases, answered bounties and free shares.
            </p>
        </div>
    )
}

export default Intel;
