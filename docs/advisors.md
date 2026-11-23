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

`GET /api/advisors` reads the player's preferences, the state, their kingdom, its mobis and structures queues,
the empires, the galaxies and the galaxy's politics (eight reads), plus the cluster for a galaxy leader, the universe
votes while an election is open, and the empire's targets while it is at war. It builds a `Context`, runs every check
in `CHECKS` and answers the advice that applies, most serious kind first:

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
| `peer` | The kingdom is far below almost every other kingdom on a measure ([below](#peer-comparisons)) | Yes |

## The advice

| Id | Kind | When | Line from |
|---|---|---|---|
| `out_of_fuel` | danger | fuel at or below zero | game rule (the fuelless penalties) |
| `fuel_running_out` | danger | fuel falling, gone within `FUEL_WARNING_HOURS` | twice-a-day logins (tenet 1) |
| `hangars_full` | danger | units at home, out and in training need more than `HANGAR_WARNING_SHARE` of the hangar space there is | game rule (overflow takes room in homes) |
| `defense_under_break_even` | danger | defense at home now under `DEFENSE_WARNING_SHARE` of `break_even_per_star` (at war, the war line) | bot sum; bots.md finding 2; measured on the bots |
| `empty_stars` | waste | `EMPTY_STARS_SHARE` of the stars empty with nothing on order, and auto spending not set to build on them | the guide: empty stars earn nothing |
| `idle_money` | waste | money and funding over `IDLE_MONEY_EPOCHS` of income | bots.md finding 3 (bots keep about two epochs idle) |
| `auto_spending_without_targets` | waste | auto spending funds structures or units with no targets for them | game rule (nothing to build) |
| `engineers_idle` | waste | auto assign off and any engineer unassigned | game rule |
| `generals_idle` | waste | all generals home, at least `ATTACKERS_SHARE` of the army pure attackers, no auto attack and no attack scheduled | bots.md finding 1 (primitives) |
| `spy_attempts_full` | waste | spy attempts at `BASE_SPY_ATTEMPTS_MAX`, auto rob off | game rule (attempts over the cap are lost) |
| `empire_war_targets` | team | the empire is at war and has targets | |
| `universe_election_open` | team | an election is open and the kingdom has no votes in it | |
| `cluster_vote_missing` | team | the galaxy has no cluster vote; the leader only | |
| `galaxy_without_empire` | team | the galaxy is in no empire, from the mid round; the leader only | |
| `galaxy_votes_missing` | team | the kingdom has not voted for leader or policies | |
| `galaxy_without_policies` | team | the galaxy has no policy in force | |
| `peer_income_low`, `peer_defense_low`, `peer_offense_low`, `peer_drones_low`, `peer_bonuses_low` | peer | income, home defense, offense or drones per star, or how full the project bonuses are, under the universe's `PEER_LOW` percentile and under `PEER_GAP` of its median | the universe, live |

## Peer comparisons

Besides the formulas and the bots, advice can come from how everyone else in this round plays. The decisions behind it
(issue #185):

- **Compared with everyone**, bots included: one range per measure over every live, set-up kingdom. No groups by size
  or playstyle. Each measure is per star or a share, so size matters less. With bots most of the universe, the ranges
  are in effect what the bots do this round, under this round's rules: the bot evidence, kept up to date by itself.
- **Qualitative only.** The advice says "almost every kingdom...", never a figure, a percentile or a range, so it tells
  nobody how defended anybody else is (tenet 2). Only the low side warns: having more of these than most is a choice.
- **Only the extreme**: under the `PEER_LOW` percentile (nine in ten have more) and under `PEER_GAP` of the median, so
  a spread that is tight (the start of a round) says nothing. Fewer than `PEER_MIN_KINGDOMS` kingdoms, nothing.

How: the refresh already holds every kingdom it refreshed (`_RefreshContext.kingdoms`). After the loop it calls
`advisors.peer_ranges` on them and stores the result as `peer_ranges` in the scores document, in the write it makes
every tick anyway: no new reads, writes or documents. `/api/scores` names the keys it sends and leaves it out; the
advisors route reads it with the scores. A new measure is a line in `peer_measures` and an entry in `PEER_ADVICE`.

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

## Measured on the bots

`scripts/simulate_round.py` runs every check on every kingdom at every sample and reports how often each fired, by
playstyle and phase ([bots.md](bots.md#tuning-scriptssimulate_roundpy)). The bots play every rule the Help gives
consistently, so an advice that fires on most of them all round is either drawn in the wrong place or points at
something the bots also get wrong. Rerun it after changing a threshold or a bot rule.

What it showed (seven days, 40 bots, three seeds), and what was done:

- **Defense.** Fired on any shortfall, it caught 50-85% of attackers and explorers: they aim at about the break-even
  on purpose and sit a little under it without being hunted. It now warns from `DEFENSE_WARNING_SHARE` of the line.
- **Hangars.** Any overflow caught 93% of bots: they ran 5-20% over capacity all round, counting units in training,
  which the game's overflow rule counts and the bots' hangar sizing did not: a bot gap ([status.md](status.md#advisors)). In
  the players' advice the warning starts a hair over capacity (`HANGAR_WARNING_SHARE`), since every unit over costs a person.
- **Cluster vote.** Fired on every galaxy-leader bot all round: the bots never cast a cluster vote. A bot gap.
- **Settling slowly** was dropped: whether a star still pays depends on prices that climb fast as a kingdom grows, and
  a nudge to settle more late in the round is more often wrong than right.
- The rest fire on a minority, at the times one would expect: empty stars early (primitives bring land faster than it
  is built on), idle generals on bots whose style keeps the army home, full spy attempts on thieves holding theirs for
  siphons.

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
