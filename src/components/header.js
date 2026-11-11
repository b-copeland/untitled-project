import React, { useEffect, useRef, useState } from "react";
import { authFetch } from "../auth";
import { useInterval } from "../hooks";
import { displayNumber } from "../format";

/**
 * The server's clock, ticking. It asks the server for the time once, then counts from there with the local clock, so a
 * wrong clock on the player's device does not matter (the game's timers run on the server's time).
 */
function Clock({ interval }) {
    const [date, setDate] = useState(new Date());
    const origin = useRef(null);

    useEffect(() => {
        let cancelled = false;
        authFetch('/api/time').then(r => r.json()).then((serverTime) => {
            if (!cancelled) {
                origin.current = { server: new Date(serverTime).getTime(), local: Date.now() };
            }
        });
        return () => { cancelled = true; };
    }, []);

    useInterval(() => {
        if (origin.current) {
            setDate(new Date(origin.current.server + (Date.now() - origin.current.local)));
        }
    }, interval);

    return <span>Time: {date.toLocaleTimeString()}</span>;
}

/**
 * The things a player glances at on every page. Fuel and money turn red when they run out: with no fuel the military is
 * at a penalty, which is easy to miss if the number is the same colour as the others.
 */
const STATS = [
    { label: "Stars", value: (kd) => kd.stars?.toLocaleString() },
    { label: "Fuel", value: (kd) => displayNumber(kd.fuel), alert: (kd) => kd.fuel <= 0, why: "Out of fuel: your military fights at a penalty" },
    { label: "Pop", value: (kd) => displayNumber(kd.population) },
    { label: "Money", value: (kd) => displayNumber(kd.money), alert: (kd) => kd.money < 0, why: "In debt" },
    { label: "Networth", value: (kd) => displayNumber(kd.networth) },
    { label: "Spy Attempts", value: (kd) => kd.spy_attempts },
    { label: "Generals", value: (kd) => kd.generals_available },
];

function Header(props) {
    if (Object.keys(props.data?.kingdom).length === 0) {
        return null;
    }
    const kingdom = props.data.kingdom;
    return (
        <div className="header-container">
            <div className="header-contents">
                <div className="header-item">
                    <Clock interval={1000}/>
                </div>
                {STATS.map(({ label, value, alert, why }) => {
                    const warn = alert ? alert(kingdom) : false;
                    return (
                        <div key={label} className={"header-item" + (warn ? " header-alert" : "")} title={warn ? why : undefined}>
                            <span>{label}: {value(kingdom)}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default Header;
