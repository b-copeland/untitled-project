# Status: what is in flux

The one place for things that are unfinished, known to be wrong, or about to change. The other docs describe the rules
and the target; this says how far the code is from them. Date every entry you add, and remove it when it is done.

## Concurrency migration

From [concurrency.md](concurrency.md). Updated 2026-11-14.

| Area | Status |
|---|---|
| Function app: the single-document `update_*` handlers | Conditional and retried |
| Function app: `create_kingdom`, `create_empire` | The new id, and joining the galaxy, are conditional writes on `kingdoms`, `empires` and `galaxies` (`change_document`); the documents they then create are new. |
| Function app: other multi-document admin handlers (`create_galaxy`, `reset_state`, `delete_all`, `init`) | Not changed. Admin and setup only. |
| Every action route (build, shields, spending, kingdom setup, votes, attacks, primitives, spying, robbing, missiles, schedules, the intel market, politics, empires, surrender, auto attack and rob settings) | Conditional (`occ.update`) or commutative (appends and merges). |
| The refresh: the kingdom write, schedules, siphons, revealed and shared expiry, scores, empires, queue trims | Conditional, with `queues_resolved_until` cursors. Schedules are taken off the kingdom with a version-checked write before they run. |
| The refresh: elections and the history mark | Decided on `/state` (`_claim_state`), so an overlapping tick does not open, close or record twice. |
| Kingdom reset (`/api/resetkingdom`) | Overwrites the kingdom's documents with the initial state on purpose (before the game starts). |
| Legacy locks | **Removed** (2026-11-14). `acquire_lock` and the `Locks` model are gone. |
| Outbox and sweep (exactly-once effects, recovery after a crash between the steps of an action) | Not built |
| A write applied but its response lost, then retried | Can duplicate an append. Not seen; the outbox ids would fix it. |

## Parallelism gaps

Code must assume many web processes and instances ([architecture.md](architecture.md#1-design-for-many-processes-on-many-machines)).
These pieces do not yet:

| Piece | Problem | Direction |
|---|---|---|
| The `accounts` document (2026-11-14) | The last copy of the SQLite users. Nothing writes it since users moved to `user_` documents; `adhoc/migrate_users_to_cosmos.py` reads it. `/resetstate` still clears kingdom fields in it, and `GET`/`PATCH /accounts` still exist. | Kept as a backup until the migration has run in production and been checked, then remove the document, the routes, and its place in `/init` and `/resetstate` |
| `SOCK_HANDLERS` (websocket registry) | A push only reaches sockets on the process that raised it. Each open socket also holds a server thread for its lifetime. | A pub/sub service, or polling notifications |
| Rate limiter (`memory://`) | Limits are per process | Shared storage for the limiter |
| The refresh | One request loops over every kingdom in turn. Two overlapping refreshes are safe (every step is version-checked), but one long tick is still one request | Split the tick per kingdom |

## Deployment and operations

- The function app is published by CI (2026-11-14) but the workflow is untested until the maintainer adds the
  `AZUREFUNCTIONS_PUBLISHPROFILE` secret and a merge to `main` runs it ([deployment.md](deployment.md)).
- CI runs on pushes to `main` only, not on pull requests, so nothing checks a pull request before it merges. A pull
  request workflow running the same three suites would fix that.
- `scripts/check.ps1` is PowerShell and expects conda; there is no equivalent script for Linux or macOS, only the plain
  commands in [testing.md](testing.md#the-suites).
- The refresh is triggered by a WebJob configured in the portal; its script is not in the repo.
- The web app moved to Basic B1 (about $13 a month) on 2026-11-21 for the custom domain, as a stopgap: issue #173 plans a
  move of the web app to a cheaper host.
- `iac/` is the Azure quickstart sample, not a description of production.
- No staging environment.

## Admin page (issue #172)

Starting a round, its dates and bots were reworked on 2026-11-21 ([admin.md](admin.md)). Still open:

- Not built yet from the issue: resetting a player's password, banning an account (`/api/disable_user` exists, with no
  page, and a ban waits for the player's token to expire, decision 0005), rolling back to a backup, and spotting players
  with several accounts.
- A refresh already running when a new round pauses the game can finish its tick on the documents being reset. It
  starts no new work, and the new round's last write replaces the state, but such a tick can leave old kingdoms' entries
  in `scores`. Harmless to the pages, which list kingdoms from `kingdoms`; starting the round again clears them.
- After a new round, a player's open page polls with an old token until the app reloads; `/api/kingdom` answers 500 for
  it rather than nothing, because the kingdom is gone.
- Bot accounts from earlier rounds stay, without kingdoms; new bots are numbered on from them.

## Code health

- The function app's handlers catch everything with a bare `except` and answer `500`, which hides throttling (`429`) and
  real errors alike. Several `GET` handlers answer `201`.
- A function app write route that cannot work (2026-11-14), uncalled: `PATCH /empire/<id>/news` reads `empire_<id>`
  where the document is `empire_news_<id>`, so empire news is never written. Kingdoms made before the intel market
  (2026-11-18) still have an unused `shared_<id>` document; a round reset removes it.
- `getters.py` and `conquer.py` are large and mix routes, formulas and storage calls.
- Over a hundred raw `REQUESTS_SESSION` calls across the blueprints; the target is one storage module
  ([architecture.md](architecture.md#target-one-storage-module)).
- Some pages keep their own copies of lists the server has (`STRUCTURES` in `src/pages/build/structures.js`).
- Python 3.10 reached end of life in October 2026. The Create React App toolchain is old. GitHub reports many
  Dependabot alerts on `main`.
- Unused leftovers: `adhoc/service_bus_testing.py`.

## Cost and efficiency

Measured with `scripts/profile_calls.py` on 2026-11-14 (24 bots, in-process backend). Not done, each for the reason given.

- **Lists that grow all round:** kingdom, galaxy and universe news, attack, spy and missile history, and the kingdom
  `history` are appended to and never trimmed (messages are capped at 100). Every append rewrites the whole document,
  so writes cost more as a round goes on. Capping them changes what players can see, so it needs a decision.
- **One read per kingdom shown:** the Galaxy page (`/api/galaxy/<id>`) and `/api/kingdomsinfo` read each kingdom with
  its own function app call. A batch read would make it one call, but the function app's rule is one document per
  route; this is what the storage module ([architecture.md](architecture.md#target-one-storage-module)) would allow.
- **Siphons are read on every tick for every kingdom** (`siphons_in` and `siphons_out`, two calls), almost always to
  find them empty. Skipping them needs a marker on the kingdom document, which is a document shape change.

## Frontend

- Not converted to check-before-sending: the politics forms.
- UX proposals not built: see [decisions/0003-ux-review.md](decisions/0003-ux-review.md#proposed-not-built).
- Spy attempts come back every epoch again (2026-11-17), so a player away for more than 10 epochs loses attempts.
  Recurring scheduled siphons and intel are issue #137.
- 2026-11-21, on production: right after making a kingdom, Status showed 0% of stars built and Structures had no
  rows, until a reload or an action that refetched `structures`. The server's data was right. Not reproduced
  locally. The likely cause is that the refetch of every key right after creation failed (a throttled or busy
  backend). Failed fetches are now retried for about half a minute (`src/data/gameData.js`). If it happens again,
  look in the browser's network tab for a failing or empty `/api/structures`.

## Galaxy policies

Added 2026-11-22 (issue #168, [decisions/0013](decisions/0013-galaxy-policy-tally.md)):

- Every number is a placeholder for the maintainer to balance: each option's `effects` in `GALAXY_POLICIES`,
  `GALAXY_POLICIES_PER_ROUND` (4) and `GALAXY_POLICY_TALLY_EPOCHS` (12).
- Discounts from different sources add up with no floor (only below zero is cut off): settling can be cheaper by
  Expansionist, the cluster, Gaian, Cheaper Exploring and Xo Evolution together.
- Galaxies of a round made before this keep the options they had by name (Expansionist, Warlike, Intelligence,
  Conscription, where their policy is in the draw) until a tally decides otherwise. Their old votes are read as new ones,
  and the `168_galaxy_policies` migration writes them in the new shape on the first tick after the deploy. Once no
  environment has a round from before #168, `galaxypolicies.LEGACY_VOTES` and the reading of `active_policies` can go.
- A kingdom that dies keeps its policy votes, as it keeps its vote for leader.
- Bots vote by a fixed list per playstyle; they do not weigh what the galaxy is short of.
- The Galaxy page has not been checked in a browser.

## Vote cooldown

Added 2026-11-20: a changed galaxy vote for leader holds for `BASE_GALAXY_VOTE_COOLDOWN_EPOCHS` (6, proposed
by the maintainer; policy votes had one too until 2026-11-22, when the tally replaced it). Galaxy `GET /api/galaxypolitics` carries `vote_unlocks_at` per vote. Cluster votes have the same rule
(`CLUSTER_VOTE_COOLDOWN_EPOCHS`) in the cluster politics PRs; once both are merged, the cluster code's own copies of the
wait text (`clusters._wait_text`, and `waitText`/`useWait` on the cluster page) should be replaced by `shared.wait_text`
and `src/components/wait.js`.

## Intel market

Built 2026-11-18 ([game-design.md](game-design.md#glossary), `intel.py`).

- `BASE_MAX_TOTAL_SHARE_CUT` (0.30) and `BASE_INTEL_BOUNTY_MAX_EPOCHS` (48) are proposals awaiting the maintainer's
  review.
- Bots buy listings and list or share what they spy, but never post or answer bounties.

## Empire war and peace

Found while writing the Empire help (issue #59, 2026-11-20). Not changed: each is a rule question for the maintainer.

- `DENOUNCE_COOLDOWN_MULTIPLIER` is defined but nothing reads it: an empire can denounce again as soon as its
  denouncement ends.
- Every war an empire declares sets the surprise-war penalty on it; only a war reached by aggression has none.
- Peace stops a declared war but not a war by aggression: the refresh starts one whenever the meter passes the limit,
  peace or not (a surrender resets the meter to zero, so it takes fresh attacks).

## Empire targets

Built 2026-11-20 (issue #56, [decisions/0008](decisions/0008-empire-targets.md), `targets.py`). The framework is in; the
balance is not.

- Every number is a placeholder: `TARGET_MAX_DELEGATES` (3), `TARGET_DEFAULT_FUND_SHARE` (10%, from the issue),
  `TARGET_MAX_FUND_SHARE` (50%), `TARGET_MAX_POINTS_MULTIPLIER` (5), `TARGET_REMARK_COOLDOWN_EPOCHS` (24, from the maintainer),
  `TARGET_HISTORY_LENGTH` (20), `TARGET_REMAINS_POINTS_PER_STAR` (0.5), `TARGET_MAX_PAYOUT_STARS_SHARE` (10%, from the
  maintainer), and the points each measure earns in `TARGET_ACTIONS`.
- A dead target's land and money count only in the share its empire earned, and no payout gives a kingdom more than its
  star cap (the maintainer, 2026-11-20, against an empire marking a kingdom dying of starvation and taking its land with
  one blow). What either holds back leaves the game.
- Targets exist only in a war (the maintainer, 2026-11-20): a surrender ends them. A target whose galaxy leaves the
  enemy empire mid-war is not ended automatically; it counts for nothing until leadership removes it.
- Funds are paid out only when a target ends (the maintainer, 2026-11-20: the issue's payouts at any time, once an
  epoch, would let small payouts pass the star cap). Removing and re-marking a kingdom every
  `TARGET_REMARK_COOLDOWN_EPOCHS` is still a slow way to pay out more often.
- Points last for the whole target. A participant who is dead when it ends loses their share.
- Intel copied to the empire from a target can be listed or shared on a member's galaxy intel market like intel they
  took themselves.
- Bots act on their empire's targets (about half their strikes, sabotage, intel and missiles, `TARGET_SHARE`) but never
  mark targets, name delegates or pay funds out.
- The Targets tab has not been checked in a browser yet.

## Last-known intel

Built 2026-11-20 (issue #27, `lastknown.py`, [decisions/0009](decisions/0009-last-known-intel.md)).

- The function app's `/kingdom/<id>/lastknown` routes must be published before the web app; until then the display
  routes still work (a failed read counts as no snapshots) but nothing is recorded.
- Kingdoms that leave a galaxy, and reveals that end with the round, leave no snapshot. Only expiry and Unshare do.
- The Conquer page's Revealed table lists kingdoms with intel now; one known only from a snapshot shows in Pinned and
  on the Galaxy page, not there.
- Bots do not use snapshots; they decide from what is revealed now.
- `LAST_KNOWN_FRESH_EPOCHS` (12) and `LAST_KNOWN_AGING_EPOCHS` (24) are the maintainer's numbers from the issue.

## Cluster politics

Started 2026-11-19 (issue #157, [decisions/0007](decisions/0007-cluster-politics.md), `clusters.py`). The framework is
built; the content is not.

- Every number is a placeholder: `CLUSTER_SIZE`, `CLUSTER_REF_SIZE`, `CLUSTER_VOTE_COOLDOWN_EPOCHS` (6, proposed by the maintainer 2026-11-20), `CLUSTER_VOTE_RATE`, `CLUSTER_DECAY_RATE`, `CLUSTER_BENEFITS_PER_ROUND` (7), and each
  benefit's `max` and `thresholds` in `CLUSTER_BENEFITS`. The fourteen benefits are the list the maintainer chose for
  issue #168 (2026-11-22); the ideas cut from it are in the maintainer's politics backlog.
- A running round plays the first `CLUSTER_BENEFITS_PER_ROUND` benefits; the `168_cluster_benefits` migration writes
  that list into its state on the first tick after the deploy (2026-11-22).
- A capacity that fades below what a kingdom has (2026-11-22): nothing is taken away. Over the workshop, silo or
  recruit cap it can train or build no more of that kind; units over the hangar space take room from homes, as they
  already do; over the homes cap population shrinks as it already does; fuel over the storage is cut to it, as when
  fuel plants are lost. Bots still plan with the capacities before
  benefits (`botbrain._silo_capacity`, the recruit cap).
- `CLUSTER_VOTE_RATE` and `CLUSTER_DECAY_RATE` are fractions of each benefit's max, so every benefit fills at the same
  relative speed. The issue's example could also be read as absolute percentage points; the maintainer to confirm.
- The empire coordination bonus is a hook only: the alignment is computed, stored and shown, but
  `clusters.alignment_multiplier` returns 1.0.
- Bots do not cast cluster votes.
- The Map page (under Politics) colours the first eight empires (or, grouped by empire, clusters) by id and shows the rest in one
  "other" grey. Its eight colours pass the palette checks for neighbouring colours, not for every pair, so the legend,
  the names on hover and the table view carry identity too. Selecting a galaxy does not yet open it on the Galaxy page.
- Neither the Cluster page nor the Map page under Politics has been checked in a browser yet.

## Unit upgrades and playstyle units

Added 2026-11-21 (issue #145). Upgrading units at home to the next tier, and the six playstyle units that replaced the
playstyle projects' effects on whole kingdoms.

- Upgrading is by hand only: the auto spender trains towards unit targets from recruits but never upgrades, and an
  upgrade can not be scheduled. Tenet 1 wants both; not built yet.
- Bots neither train nor upgrade to the heavy, elite or playstyle units.
- The playstyle units' costs, `NETWORTH_VALUES` and `SELF_DESTRUCT_LOSSES_INCREASE` are the maintainer's first
  numbers, not yet tested in play.

## Bots

See [bots.md](bots.md) for what bots do not do yet and the open questions.

Found by simulating rounds (2026-11-15), not changed because they are rules or balance:

- An attack always takes at least `BASE_ATTACK_MIN_STARS_GAIN` stars, so a small kingdom can be ground down to nothing.
- Details, and what else the simulations show, in
  [bots.md](bots.md#what-the-simulations-say-about-the-game-for-the-maintainer).
