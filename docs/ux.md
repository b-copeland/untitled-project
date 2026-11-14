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
9. **One way to do each thing.** Use the shared components below rather than a hand-written table, input or toast.
10. **Every rule change updates its help page** (`src/pages/help/`), in the same pull request.

## Components

| Need | Use | Where |
|---|---|---|
| A table | `GameTable` with column definitions, not hand-written `<tr>`s | `src/components/gametable.js` |
| Form state | `useFormValues` | `src/components/forms.js` |
| Choosing an amount | `AmountInput`: a slider with the chosen number on the left and the most possible on the right; give it `max` (what is left now) and `soloMax` (most if nothing else were chosen) so the slider never changes length. Add `box` for a number box and Max button on planner pages. | `src/components/forms.js` |
| A plain number field | `NumberField` (shows `error` under the box) | `src/components/forms.js` |
| The send button | `SubmitButton` with `blocked` set to the reason, or null | `src/components/forms.js` |
| Results of an action | `ResultToasts` | `src/components/results.js` |
| A planning page (Attack, Spy, Primitives, Share Intel, Schedule, Launch Missiles) | `Panel`, `FieldRow`, `Stats`, `VersusBar`, `Picker`, status tags, `useServerForecast` (asks again 700 ms after the last change, drops answers that were overtaken) | `src/components/planner.js` |
| An icon action | `IconButton` (`react-icons`; the name is the tooltip and the accessible label) | `src/components/iconbutton.js` |
| Formatting numbers and percents | `src/format.js` | |
| Page header and help | `Header`, `HelpButton` with the page's help topic | `src/components/` |
| Layout classes and colour tokens | `col-center`, `box-tight`, `game-table`, `table-scroll`, ... Check here before writing a new rule. | `src/styles/shared.css` |

[src/pages/build/structures.js](../src/pages/build/structures.js) is the model for a form page; `src/pages/conquer/attack.js`
for a planner page.

## Visual language

- Stock Bootstrap in dark mode. Hierarchy comes from type size and muted labels, not borders.
- Colour means state: red is a problem, green is done, amber is a guess that matters or something needing a decision.
- One spacing scale and one table style, from `shared.css`.

## Building and checking a page

How data reaches a page (`data`, `loading`, `updateData`), the code conventions and the Jest setup are in
[src/CLAUDE.md](../src/CLAUDE.md); the steps for a new page or data key are recipes 2 and 7 in
[recipes.md](recipes.md). Look at every UI change in a browser at desktop and phone width before calling it done; if you
cannot, say so in the pull request.
