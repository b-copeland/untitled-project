# 0014: Universe elections have ballots, keep the last result while voting, and break ties at random

Date: 2026-11-22. Status: accepted.

## Context
Issue #168 turns the two fixed universe doctrines into nine policies whose options each punish a playstyle. A round
must not meet them all at once, the Primitives policy only matters early, and with punishments in play the old rules
had two problems: while voting was open nothing applied (a free window every election), and a tie went to the first
option, so a policy nobody voted on punished one playstyle by default.

## Decision
- **A ballot per election**, `UNIVERSE_POLICIES_PER_ELECTION` policies, stored in the state. The first is drawn with the
  round (`admin.round_state`) and always has every `first_election_only` policy (Primitives); each later one is drawn
  when the election before it closes, from the policies that were not on that one and never a first-election policy.
  Drawing at the close lets players see the next ballot for the days before it opens (tenet 3).
- **The last result holds while voting**: opening an election no longer clears `active_policies`; closing it replaces
  them with the ballot's winners.
- **Ties at random**, seeded by the election so a close decided twice (a conflict) gives the same answer.
- **The first election opens `BASE_FIRST_ELECTION_START_MULTIPLIER` epochs after the start** unless the admin sets a
  time (or none), replacing the admin page's required field.
- **Effects**: universe options are named effects like galaxy options and cluster benefits ([0013](0013-galaxy-policy-tally.md)),
  summed into each kingdom's modifiers. Wealth's options hit only the leaders by networth, read from the scores.
- **Votes only while an election is open**: before, votes cast between elections were silently wiped.

## Rejected
- **Rotating every policy through the round**, as the issue first asked: the maintainer chose ballots of two.
- **A tie keeping the old option**: with a new ballot each time there usually is no old option.
- **Drawing each ballot as its election opens**: players could not plan for it.

## Consequences
- The state holds the ballot as well as the result; old rounds without one draw it when their next election opens.
- The universe page shows the ballot (the open election's, or the next one's), the kingdom's own votes and what is in
  force, never the tally.
- Universe policies that hit only some kingdoms make the refresh read the scores once a tick, only while one is in force.
