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
                <li><b>Attack</b>: attack a kingdom. With Suggest the army on and military intel on the target, it picks units that should win, with your margin. If that intel shows it can not win, nothing is sent. Without the intel, it sends the shares of attackers and flexers you set.</li>
                <li><b>Attack primitives</b>: send shares of your attackers and flexers at the primitives.</li>
                <li><b>Gather intel</b>: an intel operation, retried up to Max tries times until it succeeds. It can share what it finds with your galaxy for free.</li>
                <li><b>Hostile operation</b>: an aggressive operation, repeated for the number of attempts you choose.</li>
                <li><b>Launch missiles</b>: launch missiles at a kingdom.</li>
            </ul>
            <p>
                <b>Shares count your whole army, including units already out.</b> If 30% of your attackers are out with
                a general and an action asks for 50%, it sends another 20%. Each action also needs the number of
                generals it asks for to be at home, or it does nothing.
            </p>
        </Topic>
    );
}

export default Schedule;
