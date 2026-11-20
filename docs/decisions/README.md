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
