import { useEffect } from "react";

/*
 * The colour theme (styles/themes.css): its name goes on <html> as data-theme, with data-bs-theme for Bootstrap.
 * The player's choice is saved in their preferences (api/untitledapp/preferences.py); this device also remembers it,
 * so the page opens in the right colours before the preferences have loaded, and the login page has them too.
 */

export const DEFAULT_THEME = "twilight"; // the same as DEFAULT_THEME in api/untitledapp/preferences.py
const STORAGE_KEY = "THEME";

/** Shows the page in `theme` and remembers it on this device. */
export function applyTheme(theme) {
    const name = theme || DEFAULT_THEME;
    const root = document.documentElement;
    root.setAttribute("data-theme", name);
    root.setAttribute("data-bs-theme", name === "light" ? "light" : "dark");
    try {
        window.localStorage.setItem(STORAGE_KEY, name);
    } catch (error) {
        // Storage can be blocked (a private window): the theme still applies, it is only not remembered.
    }
}

/** The theme this device last showed, or the default. */
export function rememberedTheme() {
    try {
        return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
    } catch (error) {
        return DEFAULT_THEME;
    }
}

/** Follows the player's saved theme once their preferences load, and whenever it changes. */
export function useTheme(preferences) {
    const theme = preferences?.theme;
    useEffect(() => {
        if (theme) {
            applyTheme(theme);
        }
    }, [theme]);
}
