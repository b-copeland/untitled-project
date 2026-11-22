# UX guide

How pages should look and behave, and the components that already do it. Follow these for any new or changed page. The
maintainer's specific choices from the last review are in [decisions/0003-ux-review.md](decisions/0003-ux-review.md);
do not re-propose what it rejects.

## Who the player is

Someone who logs in once or twice a day, as often on a phone as at a desk, and wants to know quickly: **what happened,
what needs doing, and what is worth doing next.** Every page should answer its part of that without a manual.

## Principles

1. **Say no before sending.** A form shows why a request would fail as a red message under the field and as the
   disabled button's tooltip, before anything is sent. Use `src/validation.js` for the checks; it mirrors the server's
   limits, and the server still decides.
2. **Forecast before acting.** Anything that spends or risks something shows what will happen first (cost, offense
   against defense, chance, losses). Forecasts come from the API, never from game math re-derived in the browser.
3. **Mark what is known.** A number about another kingdom carries a tag for where it comes from: *Revealed* (exact),
   *Estimate needed* (unknown and it matters), *Your estimate* (typed by the player), *Optional* (only sharpens the
   forecast). Never show a guess as if it were known, and do not show a misleading figure (say "not meaningful yet").
4. **Confirm only the troublesome cases.** Send straight away when the outcome is known and good; ask first when the
   forecast is missing, uncertain or bad. A confirmation states the consequence ("declares war on X for 24 hours").
5. **Give numbers context.** A stock alone does not say whether to act: show the rate, the limit, or when it runs out,
   where the player would otherwise have to work it out.
6. **Do not grow the header strip.** Put extra detail in tooltips or on the page.
7. **Fewer, plainer words.** No explanatory subtitles on planner pages; labels, tags and forecasts should explain
   themselves. Use the game's terms from the glossary in [game-design.md](game-design.md#glossary), the same everywhere.
8. **Works at phone width.** No page wider than the screen: wide tables scroll inside `table-scroll`, panels stack.
   Check at about 375 px wide.
9. **Real time, not epochs.** Players never see the word "epoch": rates are per hour and durations are in hours or
   minutes, converted from `BASE_EPOCH_SECONDS`. This holds for pages, help topics and server-sent descriptions.
10. **One way to do each thing.** Use the shared components below rather than a hand-written table, input or toast.
11. **Every rule change updates its help page** (`src/pages/help/`), in the same pull request.

## Components

| Need | Use | Where |
|---|---|---|
| A table | `GameTable` with column definitions, not hand-written `<tr>`s | `src/components/gametable.js` |
| Form state | `useFormValues` | `src/components/forms.js` |
| Choosing an amount | `AmountInput`: a slider with the chosen number on the left and the most possible on the right; give it `max` (what is left now) and `soloMax` (most if nothing else were chosen) so the slider never changes length. Your own amounts are sliders only; `box` (a number box and Max) is for figures with no known maximum. | `src/components/forms.js` |
| Sliders that start at what the kingdom has now (shares, shields, engineers) | `useSliders(current)`: `value(key)` is the moved value or the current one, and a slider moved to 0 stays at 0; `body(keys)` sends only the moved ones (`""` keeps the server's value) | `src/components/forms.js` |
| A plain number field | `NumberField` (shows `error` under the box). Any other number box is a `NumberControl`, never a bare `Form.Control`: it takes the commas out of "1,000,000" before `onChange`, as `NumberField` and `AmountInput` do. | `src/components/forms.js` |
| The send button | `SubmitButton` with `blocked` set to the reason, or null | `src/components/forms.js` |
| Results of an action | `ResultToasts`: cards in the bottom corner, above the help button. Green ones close themselves after a few seconds, amber ones stay until closed, a swipe sideways closes one, and with several there is a Close all | `src/components/results.js` |
| Notifications the server pushes | Nothing to add: App.js shows them in one panel in the top corner, under the account button, needing-attention first. A notification with `status: "warning"` keeps the panel open until the player closes it. Kinds the player muted in Settings are not shown | `src/components/notifications.js` |
| Dismissing a card by swiping | `useSwipeToDismiss(onClose)` and the `swipeable` class: touch and pen only, either direction. The result toasts and each notification already have it | `src/components/swipe.js` |
| The player's own account (Settings, Logout) | Nothing to add: App.js puts `UserMenu` at the top right, the username on its button; on a phone it is in the top bar. Account pages go in its menu, not the side navigation | `src/components/usermenu.js` |
| A planning page (Attack, Spy, Primitives, Schedule, Launch Missiles) | `Panel`, `FieldRow`, `Stats`, `VersusBar`, `Picker`, status tags, `useServerForecast` (asks again 700 ms after the last change, drops answers that were overtaken) | `src/components/planner.js` |
| An icon action | `IconButton` (`react-icons`; the name is the tooltip and the accessible label) | `src/components/iconbutton.js` |
| Another kingdom's values, with last-known intel where nothing is revealed now | `withLastKnown(info)` gives the kingdom and `endedOf(path)`; show each value in `Known`, and `LastKnownNote` at the top of a section whose intel has ended | `src/components/lastknown.js` |
| Formatting numbers and percents | `src/format.js` | |
| Page header and help | Nothing to add: App.js puts the header strip, the section name and the title (`PageHead`, from the route's `label` or `title`) over every game page, with a link back when another page sent the player there. The header strip carries the round-wide banners: round over (above it) and not started yet (below it). Each page adds its `HelpButton`. | `src/components/pagehead.js`, `src/components/header.js` |
| The game's name and the player's kingdom | Nothing to add: the side navigation opens with the star and "Farsteel", then the kingdom's name and its galaxy (`1:3`). On a phone the drawer's title is the name | `src/components/navbar.js` |
| A kingdom's name | `KingdomLink`: links to the kingdom's page (`/kingdom/:id`), which says where the player came from. Links that leave a page pass `useFromHere()` as their `state`. Attack, Spy and Launch Missiles open on `?target=`. | `src/components/kingdomlink.js` |
| A section of any page | `Panel` (a titled card); `panel-grid` for several side by side | `src/components/planner.js`, `src/styles/shared.css` |
| A summary of numbers | `Stats` inside a Panel, or `text-box text-box-stats` with `text-box-item`s (a slider and button under them go in `summary-form`) | `src/components/planner.js`, `src/styles/shared.css` |
| The button under a form or table | `form-actions` (right-aligned, with any running total as muted text before the button) | `src/styles/shared.css` |
| Layout classes and colour tokens | `--surface`, `--border-subtle`, `--radius`, `page-note`, `game-table`, `table-scroll`, ... Check here before writing a new rule. | `src/styles/shared.css` |

[src/pages/build/structures.js](../src/pages/build/structures.js) is the model for a form page; `src/pages/conquer/attack.js`
for a planner page.

## Visual language

- Colour themes, chosen on the Settings page (in the account menu): Gray (the default), Dark, Light, and four from space palettes
  (`src/styles/themes.css`). **Never write a hex colour in a page's stylesheet**: use the theme tokens (`--surface`,
  `--surface-raised`, `--border-subtle`, `--row-divider`, `--hover-tint`, `--accent`, `--accent-contrast`, Bootstrap's
  `--bs-*` colours), or the page will be wrong in some theme, most often Light. Check a new page in Light and one dark
  theme.
- A darker page with raised sections ([decisions/0010](decisions/0010-page-layout.md)).
  Hierarchy comes from type size, muted labels and section cards: a card is a step lighter than the page with a faint
  edge, never a heavy line.
- One content column: everything on a page, tabs included, shares the header strip's edges. A page does not set its
  own max-width and center it.
- Tabs are a segmented control, left-aligned (no `justify` or `fill`); a tab that destroys something (Raze, Disband) is
  `tabClassName="tab-warning"` and its content `warning-zone`. Tables are borderless rows (no `bordered` or
  `striped`) inside a card. The action under a form sits on the right, in `form-actions`.
- Colour means state: red is a problem, green is done, amber is a guess that matters or something needing a decision.
  One scale is different: last-known intel is written in yellow, orange, then red as it ages (`Known` in
  `src/components/lastknown.js`), with its age in the tooltip.
- One spacing scale and one table style, from `shared.css`.

## Building and checking a page

How data reaches a page (`data`, `loading`, `updateData`), the code conventions and the Jest setup are in
[src/CLAUDE.md](../src/CLAUDE.md); the steps for a new page or data key are recipes 2 and 7 in
[recipes.md](recipes.md). Look at every UI change in a browser at desktop and phone width before calling it done; if you
cannot, say so in the pull request.
