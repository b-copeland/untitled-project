import { useEffect, useState } from "react";

/** A wait in real time, rounded up to the minute: "2 h 5 min", "40 min". */
export function waitText(milliseconds) {
    const minutes = Math.max(1, Math.ceil(milliseconds / 60000));
    const hours = Math.floor(minutes / 60);
    return [hours ? `${hours} h` : "", minutes % 60 ? `${minutes % 60} min` : ""].filter(Boolean).join(" ");
}

/** The milliseconds until ``unlocksAt`` (an ISO time or null), re-read every 30 seconds; null once it has passed. */
export function useWait(unlocksAt) {
    const [now, setNow] = useState(Date.now());
    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 30000);
        return () => clearInterval(timer);
    }, []);
    const left = unlocksAt ? Date.parse(unlocksAt) - now : 0;
    return left > 0 ? left : null;
}

/** What a locked vote says: when it can change again, or null if it can change now. */
export function lockedVoteText(wait) {
    return wait === null ? null : `You changed this vote recently. You can change it again in ${waitText(wait)}.`;
}
