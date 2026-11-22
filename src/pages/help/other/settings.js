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
        </Topic>
    );
}

export default Settings;
