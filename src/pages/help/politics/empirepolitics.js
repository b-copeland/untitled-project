import { displayPercent } from "../../../format";
import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function EmpirePolitics(props) {
    const yourElementRef = useRef(null);
    const config = props.state.game_config || {};

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "empirepolitics") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="empirepolitics" ref={yourElementRef} className="help-section">
            <h2>Politics - Empire</h2>
            <p>
                An Empire is a group of galaxies. A galaxy leader can found an Empire, ask to join one, or accept an
                invitation from one. The leader of the Empire's ruling galaxy invites galaxies and accepts their
                requests. Empires can denounce, declare war on, make peace with and surrender to other Empires.
            </p>
            <h3>How large an Empire can be</h3>
            <p>
                A galaxy can not join an Empire if the Empire would then have more
                than {displayPercent(config.EMPIRE_MAX_KINGDOMS_SHARE)} of the universe's kingdoms or more
                than {displayPercent(config.EMPIRE_MAX_NETWORTH_SHARE)} of its networth (the galaxies' networth on the
                Scores page). An Empire of {config.EMPIRE_ALWAYS_ALLOWED_GALAXIES} galaxies is always allowed. The rule is
                checked when a galaxy joins: an Empire that grows past it afterwards keeps its galaxies, but takes in no
                more until it is back under.
            </p>
            <h3>Targets</h3>
            <p>
                In a war, the emperor (the leader of the Empire's ruling galaxy) marks kingdoms of the enemy Empire as
                targets, for every member to take apart together. Only kingdoms of an Empire yours is at war with can
                be targets. The emperor can name up to {config.TARGET_MAX_DELEGATES} delegates
                to manage targets with them. An Empire can have one target for each galaxy in it. Targets are on the
                Targets tab of the Empire page, which only the Empire's members see.
            </p>
            <p>
                Each target is marked for one or more actions: intel, kidnaps, bombing homes, sabotaging fuel plants,
                missiles, failed attacks and successful attacks. A member who takes a marked action on the target earns
                points for it, by the damage done: kidnapping twice the civilians earns twice the points. Successful
                attacks earn points by the stars taken, failed attacks by the defending units destroyed, and intel for
                each kind of intel the Empire did not already have on the target. Leadership can scale each action's
                points, and the tab shows what each earns.
            </p>
            <p>
                While a kingdom is a target, and only while the war lasts:
            </p>
            <ul>
                <li>intel any member takes on it is shared with the whole Empire straight away;</li>
                <li>intel cuts from your galaxy's intel market do not apply to attacks on it;</li>
                <li>
                    a share of every successful attack's stars and money (
                    {displayPercent(config.TARGET_DEFAULT_FUND_SHARE || 0)} unless leadership changes it, up
                    to {displayPercent(config.TARGET_MAX_FUND_SHARE || 0)}) goes into the target's spoils fund instead of
                    to the attacker; the attack forecast shows how much;
                </li>
                <li>every star missiles destroy goes into the spoils fund;</li>
                <li>
                    if it dies, its remaining stars and money go into the spoils fund, in the share the Empire has
                    earned, and the target ends. The share grows with the Empire's points on the target: all of it
                    once the Empire has {config.TARGET_REMAINS_POINTS_PER_STAR} points for every star the target had
                    when it was marked. Finishing off a kingdom you barely touched earns little of its land. The tab
                    shows the share so far.
                </li>
            </ul>
            <p>
                Leadership pays the spoils fund out to everyone who earned points on the target, in proportion to their
                points, at most once
                every {((config.TARGET_PAYOUT_COOLDOWN_EPOCHS || 0) * (config.BASE_EPOCH_SECONDS || 0)) / 3600} hours.
                No kingdom receives more stars from one payout
                than {displayPercent(config.TARGET_MAX_PAYOUT_STARS_SHARE || 0)} of its own land. Stars over that, and
                the part of a dead target's land and money the Empire had not earned, leave the game. Points last as
                long as the target. When a target ends, because leadership removes it, because it dies,
                or because the war ends (a surrender), whatever is left in its fund is paid out at once; with nobody to pay, it is lost. Ended targets
                stay in the History tab.
            </p>
        </div>
    )
}

export default EmpirePolitics;
