# src/: the React frontend

Create React App, react-bootstrap, TanStack Query. The root `CLAUDE.md` and `docs/` still apply. The UX principles and
the component catalog are in [docs/ux.md](../docs/ux.md); read it before changing a page.

## Conventions

- **Adding a page:** one entry in `routes.js`. The router and the sidebar both read it. Game pages get
  `{data, loading, updateData}`; add `props: (context) => ({...})` for anything else.
- **Data:** `data/gameData.js` fetches each key from its own `/api/<key>` route. After an action, call
  `updateData([keys it changed], [the request])`. Do not fetch game data with your own effects.
- **Constants:** `data.state.game_config` and `data.state.pretty_names`. Never copy a game number into the frontend.
- **Forecasts:** from the API (`useServerForecast` in `components/planner.js`), never computed in the browser.
- **Check before sending:** `validation.js` mirrors the server's limits so a form can say why it would fail, as a red
  message under the field and as `SubmitButton`'s `blocked` tooltip. The server still decides. Politics forms are not
  converted yet.
- **Tables:** `GameTable` from column definitions. **Forms:** `useFormValues`, `AmountInput`, `NumberField`,
  `SubmitButton` (`components/forms.js`). **Results:** `ResultToasts`. **Numbers:** `format.js`. **Icons:**
  `react-icons` through `IconButton`.
- **Amounts:** `AmountInput` is a slider with the chosen number on its left and the most possible on its right; give it
  `max` and `soloMax`. `box` adds a number box and Max for the planner pages.
- **Planner pages** (Attack, Spy, Primitives, Share Intel, Schedule, Launch Missiles): `Panel`, `FieldRow`, `Stats`,
  `VersusBar`, `Picker` from `components/planner.js`, a forecast that follows the inputs, and a confirmation only for
  the troublesome cases.
- **CSS:** shared classes and tokens in `styles/shared.css` (`col-center`, `box-tight`, `game-table`, `table-scroll`).
  A page stylesheet only for rules particular to that page. Check for an existing shared class first.
- **Help:** every page has a topic in `pages/help/` and a `HelpButton`. A rule change updates its help text.
- **Making a kingdom:** `/createkingdom` is a three-step wizard (`pages/createkingdom.js`), reachable only by a signed-in
  player without a kingdom (`NewKingdomRoute` in `App.js`). One request, `POST /api/createkingdom`, does everything.

## Tests

- Jest, next to the code: `$env:CI='true'; npm test -- --watchAll=false`. CI runs them before every deploy.
- `setupTests.js` stubs `matchMedia`. When testing a page, mock `components/header` and `components/helpbutton`, and
  set mock implementations in `beforeEach`, because Create React App resets mocks between tests.
- Look at UI changes in a browser at desktop and about 375 px wide.
