import { displayPercent } from "../../../format";
import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function EmpirePolitics(props) {
    const yourElementRef = useRef(null);
    const config = props.state.game_config || {};
    const epochSeconds = config.BASE_EPOCH_SECONDS || 0;
    const hours = (multiplier) => Math.round(((multiplier || 0) * epochSeconds) / 3600 * 10) / 10;
    const perHour = (perEpoch) => (epochSeconds > 0 ? Math.round(((perEpoch || 0) * 3600) / epochSeconds * 100) / 100 : 0);
    const starShares = (props.state.surrender_options?.stars || []).filter((share) => share > 0).map((share) => displayPercent(share));

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
                requests. Empires can denounce, declare war on, make peace with and surrender to other Empires. A galaxy
                leader can take their galaxy out of its Empire, but not while the Empire is at war: a war ends only
                when one side surrenders.
            </p>
            <h3>Aggression, war and peace</h3>
            <p>
                Only the leader of the Empire's ruling galaxy can denounce, declare war, and offer, ask for or accept a
                surrender. The Empire page shows your Empire's wars, peace, aggression and denouncement, and when each
                ends.
            </p>
            <ul>
                <li>
                    <b>Aggression.</b> Each attack by one of your kingdoms on a kingdom of another Empire adds
                    {" "}{config.AGGRO_PER_ATTACK} to your Empire's aggression towards that Empire, and each aggressive
                    spy operation adds {config.AGGRO_PER_AGGRO_SPY}. Aggression falls by
                    {" "}{perHour(config.AGGRO_METER_DECAY_PER_KD_PER_EPOCH)} per hour for each kingdom in your Empire.
                    When it passes {config.AGGRO_METER_PER_KD} for each kingdom in your Empire, the two Empires go to
                    war on their own (war by aggression).
                </li>
                <li>
                    <b>Denouncing.</b> Your Empire can denounce one Empire at a time, for
                    {" "}{hours(config.DENOUNCE_DURATION_MULTIPLIER)} hours. It raises your aggression towards them by
                    {" "}{displayPercent(config.DENOUNCE_AGGRO_METER_INCREASE || 0)} of the point where war starts, and
                    your kingdoms attack theirs with {displayPercent(config.DENOUNCE_OFFENSE_BONUS || 0)} more offense
                    (not added to the war bonus).
                </li>
                <li>
                    <b>War.</b> Between Empires at war, attacks have {displayPercent(config.WAR_OFFENSE_INCREASE || 0)} more
                    offense and take {displayPercent(config.WAR_GAINS_INCREASE || 0)} more, and both sides lose
                    {" "}{displayPercent(config.WAR_LOSSES_INCREASE || 0)} more units. Targets (below) exist only in a war.
                </li>
                <li>
                    <b>Surprise war.</b> Declaring war yourself, rather than reaching it by aggression, is a surprise
                    war. For {hours(config.SURPRISE_WAR_PENALTY_MULTIPLIER)} hours afterwards, every kingdom whose Empire is
                    not at war with yours (and every kingdom in no Empire) attacks your kingdoms with {displayPercent(config.SURPRISE_WAR_PENALTY_OFFENSE_INCREASE || 0)}
                    {" "}more offense.
                </li>
                <li>
                    <b>Surrender.</b> Either side can offer to surrender, or ask the other side to. The terms are a
                    share of stars{starShares.length > 0 ? ` (${starShares.join(" or ")}, or none)` : ""}: when the other
                    side accepts, every kingdom of the losing Empire gives up that share of its stars, split evenly
                    between the kingdoms of the winning Empire. The war ends, both aggressions go back to zero, and the
                    targets end with their payouts.
                </li>
                <li>
                    <b>Peace.</b> A surrender is followed by {hours(config.PEACE_DURATION_MULTIPLIER)} hours of peace,
                    during which neither Empire can declare war on the other. Kingdoms defend against attacks from the
                    other Empire with {displayPercent(config.PEACE_DEFENSE_BONUS || 0)} more defense, and its spy
                    operations succeed {displayPercent(config.PEACE_PROBE_DEFENSE_BONUS || 0)} less often.
                </li>
            </ul>
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
                The spoils fund is paid out only when the target ends: when leadership removes it, when it dies, or
                when the war ends (a surrender). Everyone who earned points on the target gets a part in proportion to
                their points, but no kingdom receives more stars from a target
                than {displayPercent(config.TARGET_MAX_PAYOUT_STARS_SHARE || 0)} of its own land. Stars over that, and
                the part of a dead target's land and money the Empire had not earned, leave the game; with nobody to
                pay, the whole fund does. A kingdom leadership removes can not be marked again
                for {((config.TARGET_REMARK_COOLDOWN_EPOCHS || 0) * (config.BASE_EPOCH_SECONDS || 0)) / 3600} hours.
                Points last as long as the target. Ended targets stay in the History tab.
            </p>
        </div>
    )
}

export default EmpirePolitics;
