# 0013: Galaxy policies change only at a timed tally

Date: 2026-11-22. Status: accepted.

## Context
Issue #168 grows the galaxy policies from two fixed doctrines to a pool of fourteen, four of them drawn per round. Many
options are discounts on things a kingdom can switch between easily (continuous or one-time projects, unit upgrades,
razing). With the old rule (the option with more votes is active the moment a vote lands, a changed vote locked for a
few hours), the galaxymates who log in most could flip a policy whenever it suited what they were about to buy,
leaving the others behind (tenet 1). A longer cooldown only delays the flip. The maintainer chose to lock policies
between tallies instead.

## Decision
- A round's policies are drawn once, in `admin.round_state`, and stored in the state (`galaxy_policies`); they hold for
  the whole round (the issue's rotation through the round was dropped by the maintainer).
- Votes can change at any time. A policy changes only at a **tally**, every `GALAXY_POLICY_TALLY_EPOCHS` from the
  round's start: the option with the most votes at that moment wins; a tie, or no votes, keeps the active option.
- Like cluster levels ([0007](0007-cluster-politics.md)), the tally is a pure function of the stored document and the
  clock (`galaxypolicies.advance`): the document keeps the votes, the active options and when it was brought up to
  date; the votes have not changed since, so every tally since counts the same votes. Every vote advances it to its own moment first; nothing is
  written on a tick.
- Everything a policy does is a named, signed **effect** (`EFFECTS`). The game sums a kingdom's effects once per
  request or tick (`getters._get_modifiers`, `_RefreshContext.modifiers`) and reads each where its rule lives, so the
  forecast on a page and the action use the same number. Cluster benefits feed the same sums.

## Rejected
- **A longer vote cooldown**: whoever is online when it ends can still flip the policy at once.
- **Weighing each vote by how long it was held** since the last tally, which this first did to blunt last-minute
  switches: the maintainer chose the plain count at the tally (2026-11-22) as simpler to explain.
- **Writing the tally on a tick**: a write per galaxy per tally, and a tick that runs late or twice would need a cursor;
  working it out on read gives the same answer for nothing.
- **A boolean per option at each call site** (`is_expansionist`), as before: with 28 options and cluster and universe
  sources of the same effects, one sum per kingdom is simpler and cannot drift between the page and the action.

## Consequences
- A new option is an entry in `GALAXY_POLICIES` with effects from `EFFECTS`; a new kind of effect is one entry there
  and one `uas.modifier(...)` where the rule lives (recipe 12).
- A vote no longer changes a policy at once, so no vote can move a price or a strength in an instant
  ([game-design.md](../game-design.md), tenet 1).
- Reading a galaxy's policies needs the state (the draw and the round's start) as well as the galaxy's document.
- Routes that charge for something now read the galaxy's politics and the cluster (once per request each, cached).
