# 0002: Concurrent attacks on one target resolve one after another

Date: 2026-11-13 (PR #87). Status: accepted; steps 1 to 3 built, outbox and sweep not built.

## Context

An attack is resolved against the target roughly as it was when the attacker decided. But if two players attack the same
kingdom at the same moment, each outcome depends on the other, so they must not both be computed against the same
snapshot. The maintainer's requirement: attacks on one target resolve **sequentially**.

An attack touches many documents: four kingdom documents, attack history, kingdom and galaxy news twice, reveals for every
member of the defender's galaxy, aggression in `/empires`, notifications. Only two of them hold what is at stake.

## Decision

The target's own document is the sequencer; no queue or lock is needed.

1. **Commit the attacker's side.** One conditional write to the attacker: units and generals leave, the cost is paid.
   An attacker cannot send the same units twice.
2. **Resolve against the target.** Read the target and its version, compute the outcome from the target as it is now,
   and write the losses with `If-Match`. If anything else wrote the target in between, read again and recompute. The
   outcome calculators are pure functions of (attacker forces, target state), so recomputing is safe.
3. **Report back.** Apply land, gains, casualties and return time to the attacker; write news and history.

Reveals are eventual (maintainer's decision): an attack across galaxies merges the reveal into each defender-galaxy
member's `revealed` document, and lowers that member's `next_resolve.revealed` timer to the sooner of the stored and the
new time, which is idempotent and order-independent. The aggression counter is an increment on the newest `/empires`.

## Rejected

- **A per-target queue** so attacks resolve in the order players clicked. The order that exists across several servers
  is the order attacks reach the target document. A queue is only worth building if click order turns out to matter in
  play.
- **Resolving against a snapshot taken at click time.** Two simultaneous attacks would both win against the same
  defense.

## Consequences

- If the target spent or built something in the milliseconds between steps 1 and 2, the attack sees it, which is closer
  to real-time play than a snapshot.
- Scheduled attacks and auto attacks use the same path.
- Not built: an `attack_id` outbox and sweep. If the process dies between steps, the attacker's units are out with no
  result applied (if step 2 fails normally, step 1 is compensated).
