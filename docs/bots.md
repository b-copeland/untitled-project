# Bots (issue #76)

Bots are kingdoms run by the computer, so a round feels populated and the game's systems get exercised. Target: about
100 of them.

## What exists: setup

`api/untitledapp/bots.py` defines four archetypes, one per playstyle in `untitled_project.txt` (the leader playstyle is
not ready, so there is no leader bot):

| Type | Race | Plays by |
|---|---|---|
| `explorer` | Gaian | cheap fast settling (50% of funding to settling), economy first, defends |
| `attacker` | Xo | 60% of funding to military, pure offense plus flex, **auto attack on** |
| `intel` | Lumina | drone-heavy support with spy shields; free reveal operations |
| `thief` | Vult | drone-heavy, **auto rob on** for primitives |

A bot is an ordinary kingdom in an ordinary account that nobody can log in to (random password). It starts with the
archetype's units and structures, and its auto builder is switched on: auto spending split, structure / unit / project
targets, auto assign engineers, shields, and auto attack or auto rob where the playstyle has one. The periodic refresh
then plays it like any other kingdom.

Each bot's numbers are the archetype's, varied by up to 20-25% (and re-normalised so shares still total what they did),
so a hundred bots are not a hundred copies.

**Every number is a first guess and marked `TUNE` in the file.** `bots.problems(archetype)` checks an archetype against
the same validators the routes use, and `tests/test_bots.py` fails if an edit makes one illegal, so a bad number can not
reach a bot.

### Creating them

As an admin (log in at `/admin` or with the `admin` account):

```
POST /api/admin/bots     {"explorer": 25, "attacker": 25, "intel": 25, "thief": 25}
```

At most 200 per call. Names are `bot_<type>_<n>`. Each goes into the galaxy with the fewest members, like a new player.
Resetting the round (`/api/resetstate`) clears every account's kingdom, bots included; create them again afterwards.

## Not yet: bots that act

The auto builder only does what it can: it builds, settles, trains, and (for attackers and thieves) attacks or robs
primitives on a timer. What it can not do is *decide*, and that is the harder half:

- pick a target and attack another kingdom (the issue suggests rolling, per cycle, a random 0-40% of flex units to send);
- spy and reveal, share the intel with the galaxy (intel bots), launch missiles;
- vote in galaxy, empire and universe politics, buy votes, join empires, declare war.

A sketch for when this is picked up: a bot "brain" run from the refresh (or a timer function) every N ticks, with one
small function per action that reads the state a player would see, rolls its randomness, and calls the same internal
action functions the routes use (`_attack`, `_spy`, `_offer_shared`, ...), never the HTTP routes. Each decision should be
logged to the bot's own history so a round can be replayed. `tests/test_bots.py` already runs a bot through several
refresh ticks without error, which is the harness to extend.

## Known gaps

- Bots use the same `Locks`/SQLite accounts as players; 100 more users is nothing for SQLite, but they all appear in the
  accounts document that the function app keeps as a backup.
- The `TUNE` numbers have not been play-tested. Some, like `max_recruits` and the shield levels (which cost fuel), may
  starve a bot of fuel or money; watch the first few ticks of a real round.
