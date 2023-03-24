import { createAuthProvider } from 'react-token-auth';

const { useAuth, authFetch, login, logout, getSession, getSessionState } = createAuthProvider({
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
export {useAuth, authFetch, login, logout, getSession, getSessionState, adminAuth}