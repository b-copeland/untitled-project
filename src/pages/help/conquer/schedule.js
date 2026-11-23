import React from "react";
import { Topic } from "../util";

function Schedule() {
    return (
        <Topic id="schedule" title="Schedule" lead="Set an action to happen on its own at a time you choose.">
            <p>
                On <b>Add</b>, choose what to do, when, and the details, then press Schedule it. <b>Queue</b> lists what
                is scheduled, where you can cancel it. An action uses what you have when it runs, not what you have now.
            </p>
            <ul>
                <li><b>Attack</b>: attack a kingdom with the shares of attackers and flexers you set. With Suggest the army on and military intel on the target, it sends only the units that should win, with your margin, and never more than your shares. If even your shares would not win against what the intel shows, nothing is sent. Without the intel, it sends your shares, unless you turned off Without military intel, send the share anyway.</li>
                <li><b>Attack primitives</b>: send shares of your attackers and flexers at the primitives.</li>
                <li><b>Gather intel</b>: an intel operation, retried up to Max tries times until it succeeds. It can share what it finds with your galaxy for free.</li>
                <li><b>Hostile operation</b>: an aggressive operation, repeated for the number of attempts you choose.</li>
                <li><b>Launch missiles</b>: launch missiles at a kingdom.</li>
            </ul>
            <p>
                <b>How much to send.</b> Both attacks let you choose how a share is counted. Shares are always of your
                whole army: the units at home plus the units out with generals.
            </p>
            <ul>
                <li><b>Send X% of total units</b> (the default for attacks): each attack sends that share, as far as
                    the units at home allow. Four attacks at 25% send four waves of a quarter each.</li>
                <li><b>Send up to X% of total units, including units already out on generals</b> (the default for
                    primitives): it sends only what brings the units away up to the share. If 30% of your attackers are
                    out and it asks for 50%, it sends another 20%; with 50% or more out, it sends nothing. Repeated
                    attacks this way never leave more than the share away.</li>
            </ul>
            <p>
                Each action also needs the number of generals it asks for to be at home. When a scheduled action does
                nothing (no units to send, not enough generals, or the intel says it would fail), your news says why.
            </p>
            <p>
                <b>Repeating</b> holds spy operations that run again by themselves, so you use your spy attempts while
                you are away. Each one has a target and a share of your drones to send.
            </p>
            <ul>
                <li><b>Siphon funds</b> runs again once its last siphon on that kingdom has run its course, and at the
                    next free spy attempt if it failed.</li>
                <li><b>Gather intel</b> runs again once the intel it revealed runs out. It can share what it finds with
                    your galaxy, free or for a cut.</li>
                <li>Repeating operations take your spy attempts before the automatic rob, which only uses the attempts
                    left over. When several are due and attempts are short, the ones added first go first.</li>
                <li>One stops by itself when it fails the number of times in a row you set (0 never stops), when it is
                    refused three times in a row, when its target dies, or at the end time you set. Your news says
                    which. The Repeating tab shows what each one did last.</li>
            </ul>
        </Topic>
    );
}

export default Schedule;
