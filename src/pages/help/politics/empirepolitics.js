import React from "react";
import { Topic, config, duration, num, pct, perHour } from "../util";

function EmpirePolitics(props) {
    const cfg = config(props.state);
    const starShares = (props.state.surrender_options?.stars || []).filter((share) => share > 0).map((share) => pct(share));
    return (
        <Topic id="empirepolitics" title="Empire politics" lead="Galaxies band together into empires, which fight wars as one.">
            <h4>Joining</h4>
            <p>
                A galaxy leader can found an Empire, ask to join one, or accept an invitation. The leader of the
                Empire's ruling galaxy (the emperor) invites galaxies, accepts requests, and makes every decision of war
                and peace below. A galaxy can leave its Empire, but not during a war. A galaxy can make
                {" "}{num(cfg.GALAXY_DIPLOMACY_ACTIONS_PER_HOUR)} requests, invitations, cancellations of either, or
                foundings an hour in all.
            </p>
            <p>
                A galaxy can not join if the Empire would then hold more than {pct(cfg.EMPIRE_MAX_KINGDOMS_SHARE)} of
                the universe's kingdoms or {pct(cfg.EMPIRE_MAX_NETWORTH_SHARE)} of its networth. An Empire
                of {num(cfg.EMPIRE_ALWAYS_ALLOWED_GALAXIES)} galaxies is always allowed. This is checked only when a
                galaxy joins: an Empire that outgrows it keeps its galaxies but takes no more.
            </p>

            <h4>Aggression, war and peace</h4>
            <ul>
                <li><b>Aggression.</b> Each attack by one of your kingdoms on another Empire adds {num(cfg.AGGRO_PER_ATTACK)} to your Empire's aggression towards that Empire, and each aggressive spy operation adds {num(cfg.AGGRO_PER_AGGRO_SPY)}. It falls by {num(perHour(cfg.AGGRO_METER_DECAY_PER_KD_PER_EPOCH, cfg))} per hour for each kingdom in your Empire. Past {num(cfg.AGGRO_METER_PER_KD)} per kingdom in your Empire, the two go to war on their own.</li>
                <li><b>Denouncing.</b> Denounce one Empire at a time, for {duration(cfg.DENOUNCE_DURATION_MULTIPLIER, cfg)}. It raises your aggression towards them by {pct(cfg.DENOUNCE_AGGRO_METER_INCREASE)} of the war point, and your attacks on them get {pct(cfg.DENOUNCE_OFFENSE_BONUS)} more offense (not added to the war bonus).</li>
                <li><b>War.</b> Between Empires at war, attacks have {pct(cfg.WAR_OFFENSE_INCREASE)} more offense and take {pct(cfg.WAR_GAINS_INCREASE)} more, and both sides lose {pct(cfg.WAR_LOSSES_INCREASE)} more units. A war ends only when one side surrenders.</li>
                <li><b>Surprise war.</b> Declaring war yourself, instead of reaching it by aggression, is a surprise war. For {duration(cfg.SURPRISE_WAR_PENALTY_MULTIPLIER, cfg)} afterwards, every kingdom not at war with you (including those in no Empire) attacks your kingdoms with {pct(cfg.SURPRISE_WAR_PENALTY_OFFENSE_INCREASE)} more offense.</li>
                <li><b>Surrender.</b> Either side can offer to surrender, or ask the other to. The terms are a share of stars{starShares.length > 0 ? ` (${starShares.join(" or ")}, or none)` : ""}. When accepted, every kingdom of the losing Empire gives up that share, split evenly among the winners. The war ends, both aggressions reset to zero, and targets pay out.</li>
                <li><b>Peace.</b> A surrender is followed by {duration(cfg.PEACE_DURATION_MULTIPLIER, cfg)} of peace. Neither side can declare war, attacks from the other side face {pct(cfg.PEACE_DEFENSE_BONUS)} more defense, and its spy operations succeed {pct(cfg.PEACE_PROBE_DEFENSE_BONUS)} less often.</li>
            </ul>

            <h4>Targets</h4>
            <p>
                During a war, the emperor and up to {num(cfg.TARGET_MAX_DELEGATES)} delegates mark enemy kingdoms as
                targets, at most one per galaxy in the Empire. Only the Empire's members see the Targets tab. Each target
                is marked for actions: intel, kidnaps, bombing homes, sabotaging fuel plants, missiles, failed attacks
                and successful attacks. Taking a marked action earns points by the damage done. Successful attacks
                count stars taken, failed attacks the defenders destroyed, and intel each kind the Empire did not
                already have. Leadership can scale each action's points, and the tab shows what each earns.
            </p>
            <p>While a kingdom is a target:</p>
            <ul>
                <li>intel any member takes on it goes to the whole Empire at once, and no intel cuts are paid on it;</li>
                <li>{pct(cfg.TARGET_DEFAULT_FUND_SHARE)} of every win's stars and money (leadership can set up to {pct(cfg.TARGET_MAX_FUND_SHARE)}) goes into its spoils fund instead of to the attacker, as the attack forecast shows;</li>
                <li>every star missiles destroy goes into the fund;</li>
                <li>if it dies, the share of its stars and money the Empire has earned goes into the fund. The Empire earns all of it at {num(cfg.TARGET_REMAINS_POINTS_PER_STAR)} points per star the target had when marked, so finishing off a kingdom you barely touched gets little.</li>
            </ul>
            <p>
                The fund pays out when the target ends: removed, dead, or the war over. Everyone with points on it gets
                a part in proportion to their points, but no kingdom gets more stars than {pct(cfg.TARGET_MAX_PAYOUT_STARS_SHARE)} of
                its own land. The rest, and anything with nobody to pay, leaves the game. A removed kingdom can not be
                marked again for {duration(cfg.TARGET_REMARK_COOLDOWN_EPOCHS, cfg)}. Ended targets stay on the History tab.
            </p>
        </Topic>
    );
}

export default EmpirePolitics;
