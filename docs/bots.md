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

### Also the players' quick starts

The same four archetypes are offered to new players on the Create Kingdom page (`Archetype.label` is the name they
see; `bots.preset_view` is what `/api/createkingdomdata` sends). Picking one starts the kingdom with the archetype's race,
units and structures and stores its plan exactly (no variation: `bots.player_settings`), but **nothing runs unless the
player says so**: the page asks whether to switch the auto builder on, and only then are auto spending, auto assigning
engineers, shields and auto attack or rob enabled. So an edit to an archetype changes what new players are offered as
well as what bots do; `problems()` still has to pass.

### Creating them

As an admin (log in at `/admin` or with the `admin` account):

```
POST /api/admin/bots     {"explorer": 25, "attacker": 25, "intel": 25, "thief": 25}
```

At most 200 per call. Names are `bot_<type>_<n>`. Each goes into the galaxy with the fewest members, like a new player.
Resetting the round (`/api/resetstate`) clears every account's kingdom, bots included; create them again afterwards.

## Bots that act: the brain

`api/untitledapp/botbrain.py` is the part that *decides*. It is built from what the in-game guide and help pages say a
good player does, as a few small rules per action (all numbers are `TUNE` guesses, in one `Personality` per archetype):

| Action | Rule |
|---|---|
| Attack | Never blind. Of the kingdoms it has fresh **military intel** on (the intel must outlast the wait), pick the one with the most stars that it can beat with a random 2-12% buffer (the same autofill the Attack page uses). Send 1-3 generals; the rest of the army stays home. No beatable target: send spies for military intel instead. Attackers only (to start with). |
| Intel | Spy for a reveal operation on a kingdom it has none, or little, on. Intel bots share what they learn with the galaxy (90% of the time), others sometimes. Thieves leave their auto-rob's spy attempts alone; nobody spends its last. |
| Aggressive spying | Thieves siphon funds from the richest kingdom they know the money of; if they know nobody's, they spy for it first. |
| Missiles | If it holds any, fire 30-60% at the biggest kingdom it has seen. (No archetype builds silos yet, so this is dormant.) |
| Politics | Votes for the galaxy policies that suit the playstyle (Expansionist for explorers, Warlike for attackers, Intelligence for the intel bot, ...). In an election, spends the votes it has on the universe policies. It never buys votes. |

**How it acts.** The brain never calls an action. It adds entries to the bot's own **schedule** (the Schedule page's
queue) at random times over the coming interval, and the refresh runs them when they fall due through the same code the
routes use. So the check "is this attack still winnable" happens when it is sent, and one bot's actions land at different
moments. **When it acts** is random too: every bot has its own `next_think` (in the kingdom document under `bot`), first
set at random when it is created and moved on by a random 1-5 epochs (depending on playstyle) after every think. A hundred
bots therefore think a few at a time, tick after tick. This is the answer to "bots should not all act in the same tick".

**What it can see.** Only what a player sees: names, galaxies and the intel revealed to the bot. Never hidden state.

**The log.** Each decision, and what became of it, goes to the bot's `bot.log` (the last 40), e.g.
`{"time": ..., "kind": "attack", "why": "attack Delta: 41,200 offense vs 38,900 defense with a 6% buffer", "outcome": "scheduled for ..."}`.
Read it in the kingdom document (`GET /kingdom/<id>` on the function app).

**Where it runs.** `refresh._refresh_kd` calls `botbrain.maybe_think` for every kingdom that has a `bot` field, after the
kingdom's own tick. Kingdoms made before the brain existed have no `bot` field and stay passive; create new bots (or add
`"bot": {"type": "attacker", "next_think": "<now>", "log": []}` to one by hand).

**Tests.** `tests/test_bot_brain.py`: every rule on a made-up world, the spreading of times, and one bot driven through
the real refresh until a spy it queued has run.

### Seeing them work

`python scripts/simulate_bots.py` runs a round of bots on the local stack at 60 times the normal speed; see
[development.md](development.md#simulating-a-round-with-bots). In a 14-minute run (24 bots, 28 epochs, 3 galaxies) no refresh failed, the bots cast 48 galaxy votes, ran 367 spy
operations, scheduled 6 attacks on real kingdoms, and the whole universe recorded 23 attacks (the rest are auto attacks on
primitives). Star totals moved both ways, as conquests landed.

**Generals.** An attacker's auto attack sends every free general at once (at primitives), which left the brain none for
an attack on a real kingdom. A bot's auto attack now keeps `botbrain.RESERVED_GENERALS` (2) back.

### Bugs found on the way (fixed)
- The refresh raised `KeyError` for any kingdom whose general carried a unit its unit targets do not list (attackers with
  big flex), so those kingdoms were skipped every tick. Found by running the bots.
- `api/run.py` replaced Flask's log handlers with gunicorn's even without gunicorn, so no refresh error ever reached the log.
- Scheduled **Intel Spy** and **Aggressive Spy** called `uag._get_kd`, which does not exist, so they could never run for
  anybody. Now `_get_kd_info`.
- A scheduled **attack with autofill** that was not winnable returned the kingdom document where the caller expected an
  action, which crashed the rest of that kingdom's due schedules. It now does nothing.

### Not yet
- Buying votes, joining or creating empires, declaring war, surrendering. The help says empire politics is not enabled, so
  nothing to do there yet.
- Sharing intel it already has (as opposed to intel it just spied for) with `_offer_shared`; and accepting intel offered to it.
- Primitives: the auto builder already handles them (auto attack / auto rob).
- Reacting to being attacked or spied on (revenge, more defense, shields up).
- Choosing targets by distance (return time) and by who has attacked the bot or its galaxy.

## Questions for Ben
Nothing is blocked on these; I picked a default and moved on.
1. **Should attackers ever hit their own empire or galaxy?** Currently never: a bot only acts against other galaxies.
2. **Aggression toward real players.** Bots treat players and bots alike. Should bots go easier on players (smaller
   `attack_chance`, or never attack a kingdom that has logged in recently)? With ~100 bots and a few humans, humans may get
   farmed.
3. **Vote preferences.** I chose galaxy and universe votes from the policy text (see `PERSONALITIES`). Check they are the
   ones you would want, in particular the explorer voting for "Treatied" (military units cost 20% more) in the universe.
4. **Existing bots** have no `bot` field. Want an admin route that adds it to the ones already created, or is
   re-creating them fine?
5. **Think rate.** One think costs ~6 function-app calls (more when it evaluates attacks: ~5 per candidate, up to 6
   candidates). At 100 bots thinking every 1-5 half-hours that is fine, but it adds to the refresh. Is the refresh time
   budget a concern?
6. **The 0-40% flex idea in the issue** (send a random share of flex units each cycle) is not used: the attack uses the
   autofill, which picks the units. If you want the random share, it would replace autofill for flex-heavy attackers.

## Known gaps

- Bots use the same `Locks`/SQLite accounts as players; 100 more users is nothing for SQLite, but they all appear in the
  accounts document that the function app keeps as a backup.
- The `TUNE` numbers have not been play-tested. Some, like `max_recruits` and the shield levels (which cost fuel), may
  starve a bot of fuel or money; watch the first few ticks of a real round.
