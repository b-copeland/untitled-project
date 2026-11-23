import { authFetch } from "../auth";

/**
 * Mark ``categories`` read once the player has seen them. It notes how many items each category has had
 * (``<category>_total``, from the notifs as last fetched), refetches ``listKeys`` so every one of those items is on
 * the page, and only then marks read up to that total. Anything that comes in after stays unread, so a message that
 * lands while the page loads is not lost. A server without the totals clears the categories outright.
 */
export function markRead(updateData, notifs, categories, listKeys = []) {
    const seen = {};
    categories.forEach((category) => {
        const total = notifs?.[`${category}_total`];
        if (Number.isInteger(total)) seen[category] = total;
    });
    const clear = () => authFetch("api/clearnotifs", { method: "POST", body: JSON.stringify({ categories, seen }) });
    return Promise.resolve(listKeys.length ? updateData(listKeys, []) : undefined)
        .then(() => updateData(["notifs"], [clear]));
}
