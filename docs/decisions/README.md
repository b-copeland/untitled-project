# Decision records

Short records of decisions that shaped the code: what was decided, why, and what was rejected. They explain the rules in
the other docs; they are not instructions themselves. Read one before arguing to reverse it.

| # | Decision |
|---|---|
| [0001](0001-versions-not-locks.md) | Optimistic concurrency with document versions instead of locks or queues |
| [0002](0002-attack-sequencing.md) | Concurrent attacks on one target resolve one after another, sequenced by the target's version |
| [0003](0003-ux-review.md) | Outcomes of the UX review: what the maintainer chose and why |
| [0004](0004-users-in-cosmos.md) | Users move from SQLite to Cosmos documents behind the function app |
| [0005](0005-kingdom-in-the-token.md) | The kingdom id travels in the login token, so game requests stop reading the user document |
| [0006](0006-bots-plan-by-rules.md) | Bots plan by rules a player could follow, computed from the game's own formulas |
| [0007](0007-cluster-politics.md) | Cluster politics: one document per cluster, levels computed on read, membership from the galaxy id |
| [0008](0008-empire-targets.md) | Empire targets: one document per empire, and a hint on the empires document so actions know a target without a read |
| [0009](0009-last-known-intel.md) | Last-known intel: one document per kingdom, snapshotted after the tick from the kingdoms it already read |
| [0010](0010-page-layout.md) | Page layout: one content column, sections as cards, borderless tables, segmented left-aligned tabs, pages not dialogs |
| [0011](0011-preferences-and-themes.md) | Player preferences in their own document; colour themes from tokens |
| [0012](0012-one-request-new-round.md) | A new round is one request that pauses the game first and writes the state whole last |
| [0013](0013-galaxy-policy-tally.md) | Galaxy policies change only at a timed tally of the votes; every policy is a sum of named effects |
| [0014](0014-universe-ballots.md) | Universe elections have ballots, keep the last result while voting, and break ties at random |
| [0015](0015-migrations-on-the-tick.md) | Data migrations run on the refresh tick, behind code that reads both shapes |
| [0016](0016-login-signals.md) | Login signals are keyed hashes on the user document, kept for 90 days |
| [0017](0017-unread-cursors.md) | Unread counts are a running total and a read cursor, marked read up to what the page showed |

To add one: copy the shape below into the next number, and link it from this table.

```markdown
# NNNN: <the decision in a few words>

Date: YYYY-MM-DD. Status: accepted | superseded by NNNN.

## Context
What problem, and what constraint made it a decision.

## Decision
What was chosen, in a few sentences.

## Rejected
Each alternative and why not.

## Consequences
What this makes easy, what it makes hard, and what is still open.
```
