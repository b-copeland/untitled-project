# Game design

What the game is for, how it works, and how to judge whether a change belongs. The original notes are in
[untitled_project.txt](../untitled_project.txt). That file says "sector" where the code says **galaxy**; they are the
same thing.

## The tenets, in order of priority

When two tenets pull in different directions, the one higher in this list wins. Each tenet comes with the rule that
turns it into something a reviewer can check.

| # | Tenet | What it means for a change |
|---|---|---|
| 1 | **Strategy beats activity.** One login every 12 hours with a good plan stays competitive. Rounds last a day, a week or a month. | Anything a player can do, they can also schedule or automate (Schedule page, auto spending, auto attack, auto rob). Nothing rewards being online at an exact moment or clicking fast. Timers are measured in epochs (30 minutes of game time), not seconds. |
| 2 | **Moderate obscurity.** Fog of war and reveal timers, so outside tools cannot beat human judgment. Information only reachable through an external program is made available to everyone or no one. | The server filters every response by what the caller has revealed ([architecture.md](architecture.md#2-the-server-decides-what-a-player-can-see)). Do not add an endpoint that lets a script learn more, or faster, than the UI shows. If a script could compute something useful from visible data, show it in the UI. |
| 3 | **Clear information at every decision point.** | Every action shows a forecast before it is sent and says why it would fail. Numbers shown are from the server. See [ux.md](ux.md). |
| 4 | **Teams outperform individuals.** Three tiers of politics: galaxy, empire, universe. | Prefer features that reward cooperation (sharing intel, galaxy policies, empire war targets) over ones a lone player maximizes alone. |
| 5 | **Several playstyles:** attacker, explorer (defender and expander), thief, support (intel), leader. | A change that helps one playstyle should not make another pointless. Say which playstyles a change affects. |
| 6 | **Real time.** Ticks of at most one second, or continuous formulas. | State is computed from timestamps (`time_update - last_income`), not by counting ticks. A late or missed refresh must give the same result once it runs. |
| 7 | **Minor comeback mechanics, and an early end if someone runs away with it.** Leaderboards reward contribution during the round over the snapshot at the end. | Scores accrue over time (`points` from the top 10 by networth, per epoch), not only at the end. |
| 8 | **Simplicity over complexity.** Only add a feature if it is a net positive for the other tenets. | A proposal names the tenet it serves. Prefer changing a number over adding a system. |

Not for version 1.0: a graphical map, and built-in chat beyond kingdom-to-kingdom messages.

## Does this feature belong? A checklist

Answer these before designing a new mechanic. If any answer is "no" or "not sure", raise it with the maintainer before
building.

1. Which tenet does it serve, and does it work against any of tenets 1 to 3?
2. Can a player who logs in twice a day use it fully (schedule it, automate it, or it does not need attention)?
3. What does it reveal, to whom, and for how long? Is that enforced on the server?
4. Which playstyles does it help or hurt?
5. Which documents does it write, and which one is the decision point? ([concurrency.md](concurrency.md))
6. What does it cost per player per day in requests and database writes? ([cost.md](cost.md))
7. Can it be explained in a few sentences on its help page?

## Glossary

| Term | Meaning |
|---|---|
| Universe | Everyone in the round. Universe politics: policies voted on by all players; votes are bought with money. |
| Empire | A group of galaxies. Empire politics: invitations, join requests, war, peace, denouncing, surrender. |
| Galaxy | A team of kingdoms (the design notes call it a sector). Has a leader and galaxy policies chosen by vote. Ids look like `1:3`. |
| Kingdom | One player's state. Ids are strings of integers (`"7"`). |
| Epoch | The unit of game time, `BASE_EPOCH_SECONDS` (30 minutes). Durations are written as multiples of it. |
| Stars | Land. Most costs and capacities scale with stars. |
| Settling | Buying new stars; they arrive over time through the `settles` queue. |
| Structures | Built on stars: homes, mines, fuel plants, hangars, drone factories, missile silos, workshops. |
| Recruits | Population drafted for the army; trained into units. |
| Units | `attack`, `defense`, `flex`, `big_flex` (unlocked by a project), plus `recruits` and `engineers`. Stats in `UNITS`. |
| Mobis | Units being trained (mobilizations); the `mobis` queue. |
| Engineers | Work on projects, earning project points. |
| Projects | Continuous bonuses (pop, fuel, military, money, generals, spy) that scale with points, and one-time unlocks. |
| Generals | Lead attacks. An attack sends some, and they return after a delay that grows with distance (`coordinate`). |
| Drones | Used for spying and robbing primitives. |
| Spy attempts | A limited, regenerating allowance of spy operations. |
| Reveal | Spying that shows part of another kingdom for a time (`REVEAL_OPERATIONS`). What is revealed decides what the API shows you. |
| Aggressive spying | Siphon funds, bomb homes, sabotage fuel plants, kidnap population, suicide drones (`AGGRO_OPERATIONS`). |
| Siphon | Taking a share of another kingdom's income for a time. |
| Shared intel | Passing a reveal to a galaxymate, optionally for a cut of the gains. |
| Primitives | Unclaimed land held by nobody. Attacking them gains stars; robbing them gains money. Both have automatic versions. |
| Shields | Paid, per-epoch protection: military, spy, spy radar, missiles. |
| Missiles | Planet, star and galaxy busters; built in silos, launched at a kingdom. |
| Funding and auto spending | The share of income the auto builder puts into settling, structures, military and engineers. Targets say what to build. |
| Schedule | Actions queued to run at a future time by the refresh (attacks, spying, missiles). |
| Networth | A weighted sum of a kingdom's assets (`NETWORTH_VALUES`). |
| Points | Score earned over time by the top 10 kingdoms by networth (`NETWORTH_POINTS`). |
| Aggression | An empire's counter of attacks and aggressive spying; feeds denouncing and war. |
| Bots | Computer-run kingdoms using the same rules as players. See [bots.md](bots.md). |

## How time works

- Each kingdom document has `last_income` and a `next_resolve` time per category (`settles`, `mobis`, `structures`,
  `generals`, `spy_attempt`, `auto_spending`, ...). `DATE_SENTINEL` (2099) means "nothing pending".
- Starting something (a build, a training, an attack) appends entries with a finish `time` to a queue document and lowers
  the matching `next_resolve`.
- The refresh, for each kingdom, resolves every category whose `next_resolve` has passed: credits finished queue entries,
  returns generals, regenerates spy attempts, runs auto spending. Then it adds income for the time elapsed since
  `last_income`, writes the kingdom once, and runs due scheduled actions and auto attack or rob.
- Finish times are spread: a build of 100 structures arrives in several parts between a minimum and maximum number of
  epochs (`*_TIME_MIN_MULTIPLIER`, `*_TIME_MAX_MUTLIPLIER`, `*_TIME_SPLITS`; the misspelling is in the real key names).

## Where each system lives

| System | Rules | Constants | Help page |
|---|---|---|---|
| Income, population, fuel | `refresh._kingdom_with_income`, `_calc_pop_change_per_epoch` | `BASE_POP_*`, `BASE_*_INCOME_PER_EPOCH` | `src/pages/help/home/home.js` |
| Settling, structures, military, projects, missiles (building) | `build.py`, calculations in `getters.py` | `BASE_SETTLE_*`, `BASE_STRUCTURE_*`, `UNITS`, `PROJECTS`, `MISSILES` | `src/pages/help/build/*.js` |
| Attacks and primitives | `conquer.py` (`_attack`, `/api/attack/<target>`, `/api/calculate/<target>`, `/api/attackprimitives`) | `BASE_GENERALS_*`, `BASE_*_LOSS_RATE`, `BASE_PRIMITIVES_*` | `src/pages/help/conquer/attack.js`, `primitives.js` |
| Spying and robbing | `conquer.py` (`/api/spy/<target>`, `/api/calculatespy/<target>`, `/api/robprimitives`) | `BASE_SPY_*`, `BASE_DRONES_*`, `BASE_REVEAL_DURATION_MULTIPLIER` | `src/pages/help/conquer/spy.js` |
| Shared intel | `conquer.py` (`/api/offershared`, `/api/shared`), `misc.py` (`/api/share/<kingdom>`) | `BASE_MAX_SHARE_CUT` | `src/pages/help/conquer/shareintel.js` |
| Schedule | `conquer.py` (`/api/schedule`), `refresh._resolve_schedules` | | `src/pages/help/conquer/schedule.js` |
| Politics | `politics.py`, `refresh._begin_election`, `_resolve_election` | `GALAXY_POLICIES`, `UNIVERSE_POLICIES`, `BASE_VOTES_COST`, `AGGRO_*`, `DENOUNCE_*`, `PEACE_*`, `WAR_*` | `src/pages/help/politics/*.js` |
| Scores and history | `refresh._resolve_scores`, `_update_history` | `NETWORTH_VALUES`, `NETWORTH_POINTS` | `src/pages/help/home/scores.js` |
| Races | spread through the formulas (search the race name) | `GAIAN_*`, `VULT_*`, `LUMINA_*`, `XO_*`, `FUZI_*` | `src/pages/help/other/createkingdom.js` |
| Bots and quick starts | `bots.py` | `TUNE` values in `bots.py` | [bots.md](bots.md) |

The help pages are what players read, so they are the player-facing statement of the rules. **A change to a rule updates
its help page in the same pull request.**

## Changing numbers

Balance numbers (`GAME_CONFIG`, `UNITS`, `PROJECTS`, race modifiers, bot `TUNE` values) are the maintainer's call. Do not
change one as a side effect of other work. If a change needs a new number, add it to `GAME_CONFIG` with a name that says
what it is, propose a value, and say so in the pull request.
