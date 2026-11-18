# 0006: Bots plan by rules a player could follow, computed from the game's own formulas

Date: 2026-11-15. Status: accepted.

(0005 is taken by the record on the kingdom id in the login token, which is in its own pull request.)

## Context

The first bots were a starting kingdom with the auto builder switched on, plus a brain that spied, voted and attacked
kingdoms with fixed chances. Simulated, they wasted most of what they earned (funding piled up in capped categories,
recruits were never turned into units) and used a fraction of the game. The goal is bots that play about as well as an
average player, in several styles, change with the round, and work as a team; on a free tier, inside the refresh.

## Decision

- **Rules, not search.** Each decision is a rule from the guide or a help page, with its threshold worked out from the
  formulas in `shared.py` instead of guessed: defend to the point where primitives are the better target for an
  attacker; strike a kingdom when its stars per point of offense beat primitives; siphon when the expected take beats a
  rob; settle while a star still pays back before the round ends; fund each category by what it can use.
- **The auto builder stays the engine.** The brain does not build anything itself tick by tick: every think it rewrites
  the auto builder's settings (spending split, targets, engineers, shields, auto attack and rob) and the refresh does the
  rest. Scheduled actions go through the schedule. So a bot costs a few calls an epoch, and plays the way tenet 1 asks
  of a player: a plan every few hours.
- **Same code as the routes, same view as a player.** On-the-spot actions call the function behind the route; the
  routes became thin wrappers around functions of the kingdom id. Other kingdoms are read only through
  `_get_max_kd_info` and the redacted scores.
- **Coordination without a channel.** Bots in a galaxy or an empire do not talk. They converge because each applies the
  same public rule to the same public facts: back the leader the others back, join the strongest empire with room,
  treat the strongest other empire as the rival, the top kingdoms by networth as the leaders.
- **Sums apart from decisions.** `botstrategy.py` is plain functions (tested with plain inputs); `botbrain.py` decides
  and acts; `Personality` holds every tunable number per playstyle; a per-bot style gives variety and coverage.
- **Tuned by simulation.** `scripts/simulate_round.py` plays a round in minutes on a simulated clock; a number changes
  when the mean of several seeds says so.

## Rejected

- **Search or learning over simulated rounds** (a bot that optimises its own numbers, or looks ahead). It would outplay
  an average player, cost far more per think, and could not explain itself in a log line.
- **The brain performing every build itself each tick.** More control, but many more calls per bot per epoch, and it
  would stop exercising the auto builder that players rely on (which is how two of its bugs were found).
- **Reading other kingdoms directly** (`max=True`) for better targets. Against tenet 2: a bot would know what no player
  can.
- **A shared plan document per galaxy or empire** for coordination. A new document shape and more writes, for what
  public rules already achieve.
- **Fixed phase scripts** (build X on day 2). They break when the round length or the rules change; rules computed from
  the formulas follow them.

## Consequences

- A balance change moves the bots with it (they read `GAME_CONFIG`), but can also make a rule's assumption wrong: rerun
  the simulation after one.
- The archetypes are the players' quick starts too, so tuning a start changes what new players are offered.
- Bots treat players and bots alike; whether they should is an open question in [bots.md](../bots.md#questions-for-ben).
- Runs are close but not identical for one seed, so small differences need several seeds.
