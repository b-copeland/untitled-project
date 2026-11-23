# Advisors (issue #185)

The advisors are the first card on the Status page: short advice, in plain English, on what in a player's kingdom may
need fixing, each with links to the page where it is fixed. They are for newer players, who do not yet know what a
healthy kingdom looks like, and they stay quiet for a kingdom that is doing fine.

| File | Holds |
|---|---|
| `api/untitledapp/advisors.py` | The **checks** (one function per advice), the context they read, the ranking, and the routes |
| `api/untitledapp/preferences.py` | The on/off switch and the advice a player has hidden |
| `src/pages/home/advisors.js` | The card's list: text, links, Hide, and the toggle for hidden advice |

## How it works

`GET /api/advisors` reads the player's preferences, the state, their kingdom, its mobis queue and the empires and galaxies
(about six reads), builds a `Context`, runs every check in `CHECKS` and answers the advice that applies, most serious kind first:

```json
{"enabled": true, "advice": [{"id": "fuel_running_out", "kind": "danger", "text": "Your fuel runs out in about 5 hours: ...",
  "links": [{"label": "Build fuel plants", "to": "/structures"}], "hideable": false, "hidden": false}]}
```

The card fetches it each time the Status page opens, not with the rest of the game data, so a player who never opens
the Status page costs nothing. Bots never call it.

**Decided on the server**, for the same reasons as everything else: the thresholds are the game's own formulas (hard
rule 7, one home per rule), and anything the advice is built from that the player could not see stays on the server
(tenet 2).

**A check is a plain function** of the `Context`: no Flask, no storage, no reads. It returns an `Advice` or `None`.
That keeps them testable with plain inputs (`tests/test_advisors.py`) and lets the bot simulator run them on every
bot.

## Kinds

| Kind | What | Can be hidden |
|---|---|---|
| `danger` | Something is hurting the kingdom now: out of fuel, fuel running out, hangars over capacity, defense so low that attacking it pays better than primitives | No |
| `waste` | Money, land or people doing nothing | Yes |
| `team` | Something the galaxy, cluster, empire or universe is waiting on. Advice only a galaxy leader can act on goes only to the leader | Yes |

## Where a threshold may come from

Every advice says, in a comment on its check, where its line is drawn. One of:

1. **A game formula** from `shared.py` (fuel per epoch, hangar capacity, the fuelless penalties).
2. **A bot sum** from `botstrategy.py`, with the finding in [bots.md](bots.md) that backs it. The bots see only what a
   player sees ([decisions/0006](decisions/0006-bots-plan-by-rules.md)), so their rules can be given to a player.
   Example: `defense_under_break_even` uses `break_even_per_star`: below it, a hit on the kingdom pays an attacker more
   than primitives, and in the simulations bots that dropped to it were hunted at once.
3. **A plain reason**, named in the comment. `FUEL_WARNING_HOURS` is 12 because a player who logs in twice a day
   (tenet 1) would otherwise find the fuel gone before they are back.

Never a number guessed in `advisors.py` without one of these.

## Writing the text

- Plain English, at most three short sentences: what is wrong, why it matters, what to do.
- Real time: hours, never epochs ([src/CLAUDE.md](../src/CLAUDE.md)).
- Numbers only about the player's own kingdom. Comparisons with other kingdoms are qualitative ("almost all
  kingdoms...") and never give a figure.
- Every advice has at least one link, to the page (and tab, `?tab=`) where the fix is made.
- The `id` is stable and particular (`hangars_full`, not `structures`): hiding one must not hide another, and hidden
  ids are kept for good.

## Hiding and the switch

- **Hide** on an advice that is not `danger` hides it for good, for the account: it stays hidden in later rounds. It
  is stored as its own key, `hide_advice_<id>: true`, in `preferences_<user id>`, so two hides at once can not undo
  each other through the shallow merge. `POST /api/advisors/hide` with `{"id", "hidden"}`; `false` shows it again.
- Hidden advice still comes back from the route, flagged `hidden`, and the card shows it only behind a small "Show
  hidden advice" toggle.
- **Settings** has a switch (`advisors`: `on` or `off`, on by default). Off, the route answers
  `{"enabled": false, "advice": []}` after one read and the card says where to turn them on.

## Adding an advice

Recipe 14 in [recipes.md](recipes.md#14-an-advisor).
