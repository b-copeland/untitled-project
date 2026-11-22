import React, { useEffect, useRef } from "react";

function Settings(props) {
    const yourElementRef = useRef(null);

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "settings") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="settings" ref={yourElementRef} className="help-section">
            <h2>Settings</h2>
            <p>
                The Settings page, in the account menu at the top right (the button with your username), holds your own preferences. They belong to your
                account rather than your kingdom, so they follow you to every device and stay from one round to the next.
            </p>
            <p>
                <b>Colour theme</b> changes the colours of every page. Gray is the default; Dark is nearly black; Light is
                a light page with dark text; Eclipse, Nebula, Planet and Twilight are darker themes in the colours of
                space, with a faint glow behind the page. Each choice shows a small preview, and the page changes as soon
                as you pick one. This device remembers your theme too, so the login page shows it as well.
            </p>
        </div>
    )
}

export default Settings;
