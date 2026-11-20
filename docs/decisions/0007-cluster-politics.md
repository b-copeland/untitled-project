# 0007: Cluster politics: levels computed on read, one document per cluster

Date: 2026-11-19. Status: accepted.

## Context
Issue #157 adds clusters: fixed groups of galaxies whose leaders vote for benefits that every kingdom in the cluster
gets. A benefit's level rises with its votes (less so the higher it is) and falls on its own, "every refresh, scaled by
the epoch duration". The galaxies of a cluster can be in different empires, and a cluster aligned in one empire may
later get a coordination bonus. Writes and function app calls cost request units on a free tier shared with production
([cost.md](../cost.md)).

## Decision
- **Membership is the galaxy id.** `/api/createstate` deals galaxies in order into clusters of `CLUSTER_SIZE`, and
  galaxy `2:3` is in cluster 2. The `galaxies` document already lists every galaxy, so no membership list is stored.
- **One document per cluster**, `cluster_<cluster>`, holds the votes (galaxy to benefit), the levels, the alignment
  and `last_update`. It is the decision point of every change (`occ.update`), created empty on first read like
  `galaxy_intel_<galaxy>`.
- **Levels are a pure function of the document and the clock.** Between writes the votes and the alignment are
  constant, so `clusters.advance` computes the levels at any moment exactly, segment by segment between the
  diminishing-return thresholds. Every write advances to its own moment first. A tick writes only when a cluster's
  empire alignment has changed.
- **The galaxy leader casts the galaxy's vote.** The leader is checked against `galaxy_votes_<galaxy>` before the
  decision, not in it, because it is another document.

## Rejected
- **Advancing and writing every cluster on every tick**, as the issue phrases it: the same result for one write per
  cluster per tick, and a tick that runs late or twice would need a cursor anyway.
- **Storing the vote on the galaxy's politics document**, where the leader check would be in the same document: then
  the levels depend on every galaxy's document, so reading a cluster, and every tick, would read all of them.
- **A stored list of each cluster's galaxies**: the id already says it, and galaxies never move.
- **Recomputing the alignment when it is read**: a change in empires would then apply to the time before it as well,
  once the alignment multiplier is more than 1.0.

## Consequences
- Adding a benefit is an entry in `CLUSTER_BENEFITS` and, for a new kind of effect, one hook where the game reads it.
- A leader replaced at the moment of a vote can land that one vote; the next leader can change it.
- The levels' history between writes is not stored; only the current level and rate are shown.
