/**
 * The server sends its lists as JSON objects, which Flask sorts by key. ``state.order`` holds the order the game means
 * them in (``units``, ``projects``, ``project_categories``); these put keys back in that order. Keys the order does not
 * know go last, in the order they came.
 */
export function inOrder(keys, order) {
    if (!order) {
        return [...keys];
    }
    const rank = (key) => {
        const index = order.indexOf(key);
        return index < 0 ? order.length : index;
    };
    return [...keys].sort((a, b) => rank(a) - rank(b));
}

/** ``Object.entries(object)`` in ``order``. */
export function entriesInOrder(object, order) {
    return inOrder(Object.keys(object || {}), order).map((key) => [key, object[key]]);
}
