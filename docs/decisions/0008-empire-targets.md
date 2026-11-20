# 0008: Empire targets: one document per empire, a hint on the empires document

Date: 2026-11-20. Status: accepted.

## Context
Issue #56 adds empire targets: kingdoms an empire's leadership marks for its members to take apart. Members earn
participation points for marked actions, scaled by the damage done; a share of attack spoils, every star missiles
destroy and a dead target's remains go into a spoils fund that leadership pays out in proportion to points. Intel on a
target is shared with the whole empire, and intel cuts do not apply to it. The maintainer chose (2026-11-20): the emperor
names delegates who manage targets with them; intel is copied to each member; the fund holds stars and money (funding
counts as money); ending a target pays out what is left at once. Then (2026-11-20): targets exist only in a war.

Every attack, spy operation and missile strike now has to know whether its target is one of the attacker's empire's
targets, and writes and function app calls cost request units on a free tier shared with production
([cost.md](../cost.md)).

## Decision
- **One document per empire**, `empire_targets_<empire>`, holds the delegates, each target (its marked actions and
  multipliers, fund share, points per participant, fund, what has been paid, the empire's intel on it) and the
  history. It is the decision point of every change (`occ.update`), created empty on first read like
  `galaxy_intel_<galaxy>`.
- **A hint on the `empires` document.** Each empire carries `targets`, a list of kingdom ids, which every attack, spy
  operation and strike already has in hand (the empires document is read once per request). Only when the hint lists
  the target is the targets document read. The hint is kept a superset: a target is added to it before the targets
  document, and removed after. `/api/empires` leaves it out.
- **Only in a war.** A target must be a kingdom of an empire at war with this one when it is added, and an action
  counts for it only while the two empires are still at war: a check on the `empires` document the action already
  has, so it costs nothing. War ends only with a surrender (`politics._surrender`), which then ends every target
  either side had in the other, with its final payout (`reason` `war_ended`). A target whose galaxy leaves the
  enemy empire stays listed but counts for nothing; the tab says so, and leadership can remove it.
- **Points and fund are written after the action lands,** as one conditional write to the targets document. If the
  target ended in between, an attack's fund share goes back to the attacker.
- **The emperor check reads other documents** (the empire's ruling galaxy, that galaxy's leader) before the decision;
  the delegate check is inside it, on the targets document.
- **A dead target's remains are claimed on the dead kingdom** (its stars, money and funding set to zero with a version
  check), so they are taken once however often the death is handled. They go to the killer's empire if it targets the
  kingdom, otherwise evenly to every empire that does. A death in the refresh is handled after the kingdom is written.
- **A dead target's land and money are earned, and payouts are capped** (the maintainer, 2026-11-20). An empire could
  otherwise spot a kingdom dying of starvation, declare war, mark it and land one blow with its largest kingdom, which,
  as the only participant, took the whole of its land. Now the empire's fund gets the dead target's land and money only
  in proportion to its points on it, all of it at `TARGET_REMAINS_POINTS_PER_STAR` points per star the target had when
  marked. And no payout, of any kind, gives a kingdom more stars than `TARGET_MAX_PAYOUT_STARS_SHARE` of its own land.
  What either holds back leaves the game, as a dead kingdom's land did before targets. Considered and not taken: a
  flat cut (it hits an empire that besieged a kingdom for days as hard as the opportunist), a minimum time a target
  must be held (it adds little once the share follows points), and land never going to the fund (it removes the
  reason to finish a starving kingdom).

## Rejected
- **Reading the targets document on every attack, spy operation and strike by an empire member:** one more read per
  action for almost every action, to find out almost always that the target is not one.
- **Keeping the targets themselves on the `empires` document:** it is written by every attack (aggression) and every
  tick, and points and funds would make it grow and be written on every action against a target.
- **Merging target intel into each member's reveals when they are read:** one write per operation instead of one per
  member, but an extra read on every route that filters by reveals (Attack, Spy, Galaxy, the kingdom view).
- **Leaving targets in place after a war** (dormant until the next one): a fund could then wait a long time for its
  payout, and the next war may be with someone else.
- **Points per payout period** (reset at each payout): a target's death would then pay only the last period's
  participants. Points last for the whole target.

## Consequences
- An intel operation on a target costs about three function calls per kingdom in the empire, like a free galaxy share.
- A crash between the hint and the targets document, or two adds racing for the last place, can leave a kingdom in the
  hint that is not a target: a wasted read on each action against it until the empire's targets next change it.
- A participant who is dead when a fund is paid out loses their share.
- Every number is a placeholder ([status.md](../status.md#empire-targets)).
