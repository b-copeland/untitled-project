# 0011: Player preferences in their own document; colour themes from tokens

Date: 2026-11-21. Status: accepted.

## Context

The maintainer found the near-black page of [0010](0010-page-layout.md) too stark, preferred gray, and asked for a
theme selector as the first player preference, stored in a preference document of its own, with a page to change it.
Themes: Gray, Dark, Light, and a few colourful ones from four space palettes (Eclipse, Nebula, Planet, Twilight).

## Decision

- **One document per user, `preferences_<id>`**, read and written by `api/untitledapp/preferences.py` through
  `GET` / `PATCH /preferences/<id>` on the function app. No document means every default, so nothing needs a backfill.
  It outlives a round, like the user. The options and defaults live in `preferences.py`, and `GET /api/preferences`
  sends them, so the Settings page lists what the server accepts.
- **Themes are CSS tokens** on `[data-theme=...]` in `src/styles/themes.css`; `src/theme.js` sets the attribute on
  `<html>` (and `data-bs-theme`, light for Light). Every page colour comes from a token; Bootstrap's primary colour is
  pointed at the theme's `--accent`.
- **The device remembers the theme too** (`localStorage`), only so the page opens in the right colours before the
  preferences load and on the login page. The account's value wins once loaded.
- Gray was the default at first; the maintainer made Twilight the default on 2026-11-23. The Settings page keeps its
  order, so the default is named in `preferences.py` (`DEFAULT_THEME`) rather than being the first option.

## Rejected

- **A `theme` field on the user document.** Simpler, but the maintainer wanted preferences separate from identity, and
  the user document is read on many requests; preferences change rarely and are read once per page load.
- **The theme only in the browser.** It would not follow the player to another device.
- **Separate stylesheets per theme.** Tokens let any element show another theme (the Settings previews), and a new theme
  is one block of variables.

## Consequences

A new preference is a key in `OPTIONS` in `preferences.py` and a control on the Settings page. A stylesheet with a
hard-coded colour looks wrong in some theme (usually Light); ux.md says to use the tokens. The Settings page needs a
kingdom, like every game page; a player without one keeps the default or this device's last theme.
