import React from "react";
import { Topic } from "../util";

function Settings() {
    return (
        <Topic id="settings" title="Settings" lead="Your own preferences, from the account menu at the top right.">
            <p>
                Settings belong to your account, not your kingdom, so they follow you to every device and from one
                round to the next.
            </p>
            <p>
                <b>Colour theme</b> changes the look of every page as soon as you pick one. Gray is the default, Dark is
                nearly black, and Light has dark text on a light page. Eclipse, Nebula, Planet and Twilight are dark
                themes in the colours of space. This device also remembers your theme, so the login page uses it too.
            </p>
            <p>
                <b>Notifications</b> has a switch for each kind of notification: finished settles, structures, military
                and the rest of your own kingdom, messages and news from other players, and attacks, spy operations and
                missile strikes against you. Turn one off and it no longer appears in the Notifications panel, on any
                device. Nothing else changes: the pages still update, and your news still records what happened. You
                are always told when your kingdom dies.
            </p>
            <p>
                <b>Advisors</b> turns the advice on the Status page on or off. It is on to start with.
            </p>
            <p>
                <b>Effects</b> turns on or off the short animations that play when your attack lands, a spy operation
                succeeds or fails, your missiles strike (some shot down if the target's shields stopped part of the
                damage), and when you first see a new universe election result. They are on to start with, never play
                on a device set to reduce motion, and a tap skips one.
            </p>
            <p>
                <b>Guided tour</b> starts the tour of the main pages again. It is offered on your first visit: Not now
                keeps a reminder on the Status page, and No thanks or finishing the tour leaves it here only.
            </p>
            <p>
                On a phone or tablet, swipe a notification or a result sideways, either way, to dismiss it.
            </p>
        </Topic>
    );
}

export default Settings;
