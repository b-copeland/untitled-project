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

/** authFetch, but a 401 (a token from an earlier round, or one the server no longer accepts) signs the player out. */
const authFetch = async (...args) => {
    const response = await tokenAuthFetch(...args);
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