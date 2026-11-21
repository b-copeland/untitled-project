import { createAuthProvider } from 'react-token-auth';

const { useAuth, authFetch: tokenAuthFetch, login, logout, getSession, getSessionState } = createAuthProvider({
    getAccessToken: session => session.accessToken,
    storage: localStorage,
    onUpdateToken: token =>
        fetch('/api/refresh', {
            method: 'POST',
            body: token.refreshToken,
        }).then(r => r.json()),
    storageKey: "DOMNUS_GAME_TOKEN",
    onHydratation: session => session,
    expirationThresholdMillisec: 1000 * 3600
});

/**
 * "api/x" from the site's root, wherever the page is: pages written "api/..." would otherwise ask for
 * /kingdom/api/x on a page like /kingdom/12. A full URL or a path from the root is left alone.
 */
export const fromRoot = (url) => (typeof url === "string" && !/^([a-z][a-z0-9+.-]*:|\/)/i.test(url) ? "/" + url : url);

/**
 * authFetch, asking from the site's root, and a 401 (a token from an earlier round, or one the server no longer
 * accepts) signs the player out.
 */
const authFetch = async (url, ...rest) => {
    const response = await tokenAuthFetch(fromRoot(url), ...rest);
    if (response.status === 401) logout();
    return response;
};

/**
 * The server returns new tokens when it changes the player's kingdom (created, reset): the old ones still name the
 * old state. Store them before anything is read again. A response without tokens changes nothing.
 */
const storeNewTokens = async (response) => {
    try {
        const body = await response.clone().json();
        if (body && body.accessToken && body.refreshToken) {
            login({ accessToken: body.accessToken, refreshToken: body.refreshToken });
        }
    } catch (e) {
        // not JSON: nothing to store
    }
    return response;
};

const adminAuth = createAuthProvider({
    getAccessToken: session => session.accessToken,
    storage: localStorage,
    onUpdateToken: token =>
        fetch('/api/adminrefresh', {
            method: 'POST',
            body: token.refreshToken,
        }).then(r => r.json()),
    storageKey: "DOMNUS_ADMIN_TOKEN",
    onHydratation: session => session,
    expirationThresholdMillisec: 1000 * 3600
});
export {useAuth, authFetch, storeNewTokens, login, logout, getSession, getSessionState, adminAuth}