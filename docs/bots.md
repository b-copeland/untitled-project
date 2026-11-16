# Bots (issue #76)

Bots are kingdoms run by the computer, so a round feels populated and the game's systems get exercised. Target: about
100 of them, each playing about as well as an average player, in different ways.

A bot is an ordinary kingdom in an ordinary account that nobody can log in to (random password). It plays by the same
rules as a player, through the same code as the routes, and sees only what a player sees.

| File | Holds |
|---|---|
| `api/untitledapp/bots.py` | The four **archetypes**: race, starting units and structures, and the plan a new kingdom starts with. Also the players' quick starts. Creating bots. |
| `api/untitledapp/botstrategy.py` | The **sums**: plain functions of what a bot can see. No Flask, no storage. |
| `api/untitledapp/botbrain.py` | The **brain**: what a bot decides each time it thinks, the `Personality` of each playstyle (every `TUNE` number), and carrying the decisions out. |
| `scripts/simulate_round.py` | A whole round of bots in one process on a simulated clock, in minutes. The tool for tuning. |

## Archetypes and styles

| Type | Race | Grows by |
|---|---|---|
| `explorer` | Gaian | settling all round (it stays ahead of the army in the queue for money), primitives, the strongest defense |
| `attacker` | Xo | primitives, then kingdoms when they pay better; most of its army is offense |
| `intel` | Lumina | primitives and settling; spies widely and offers what it learns to its galaxy for a cut of the spoils |
| `thief` | Vult | primitives and settling; robs primitives, siphons kingdoms when that pays more, sabotages leaders |

(The leader playstyle is not ready, so there is no leader bot.)

Each bot also draws a **style** when it is created (`botbrain.roll_style`, stored in `bot.style`), so a hundred bots of a
type are not a hundred copies, and between them they use every action:

| Style | Values | Meaning |
|---|---|---|
| `army` | `none`, `primitives`, `players`, `both` | What its army hits. Most attackers hit both; a quarter hit only kingdoms and a quarter only primitives. A tenth of the others hit nothing. |
| `drones` | `primitives`, `players`, `both` | Whether its drones rob primitives, work on kingdoms (siphons), or whichever pays more. |
| `bomber` | true or false | Builds missile silos from the mid game, researches Star Busters, and fires at whoever hit it, or at the leader. |
| `temper` | 0.85 to 1.15 | Bold bots keep less defense and buy more offense; cautious ones the other way. |

### Also the players' quick starts

The same four archetypes are offered to new players on the Create Kingdom page (`Archetype.label` is the name they
see; `bots.preset_view` is what `/api/createkingdomdata` sends). Picking one starts the kingdom with the archetype's race,
units and structures and stores its plan exactly (`bots.player_settings`), but **nothing runs unless the player says
so**: the page asks whether to switch the auto builder on, and only then are auto spending, auto assigning engineers,
shields, auto attack and auto rob enabled. So an edit to an archetype changes what new players are offered as well as
what bots start with; `bots.problems(archetype)` still has to pass (`tests/test_bots.py`). A player gets the starting
plan only: the brain does not run for players.

### Creating them

As an admin (log in at `/admin` or with the `admin` account):

```
POST /api/admin/bots     {"explorer": 30, "attacker": 40, "intel": 10, "thief": 20}
```

That is `bots.DEFAULT_MIX` for 100 bots (`bots.mix_for(100)`), the mix the simulator uses unless told otherwise: few
intel bots, because they compete to sell the same galaxymates intel, and thieves a minority, so their siphons do not
crowd each other.

At most 200 per call. Names are `bot_<type>_<n>`. Each goes into the galaxy with the fewest members, like a new player.
Resetting the round (`/api/resetstate`) clears every account's kingdom, bots included; create them again afterwards.

## How a bot plays

`refresh._refresh_kd` calls `botbrain.maybe_think` for every kingdom with a `bot` field, after the kingdom's own tick. A
bot thinks on its own timer (`bot.next_think`, a random 1 to 5 epochs apart depending on playstyle), so a hundred bots
think a few at a time. Each think:

| Step | Rule (function) |
|---|---|
| Read the news | An attack makes its sender a grudge and raises the defense the bot wants (it wears off); missiles raise the missile shields, caught spies the spy shields (`react`). |
| Learn | A strike that failed widens the buffer it asks for, one that worked narrows it. A kingdom whose spies it keeps failing against is left alone for two days. A kingdom that has stopped growing settles harder and sends its army at primitives whatever its style (`learn`). |
| Plan the economy | The auto builder's settings for the coming hours (`plan_economy`, below). |
| Survive | An army the hangars and fuel plants can no longer keep (after losing stars) is disbanded, defenders last, before it empties the homes (`plan_survival`). |
| Spend loose money | Settle, build and train engineers with money that is not in a funding category, as on the Build pages (`spend_money`). |
| Politics | Below (`plan_politics`). |
| Intel | Reveal a galaxy when it knows nobody; spy where it pays; accept the intel galaxymates offer if it can use it (`plan_intel`, `accept_intel`). |
| Strike | A kingdom, when one pays better than primitives (`plan_attack`). |
| Drones | A siphon when it beats robbing; sabotage on a leader late in the round (`plan_drones`). |
| Missiles | Fill the silos; fire at whoever hit it, or the leader (`plan_missiles`). |

**How it acts.** Attacks, spying and missiles go on the bot's own **schedule** (the Schedule page's queue), at times
spread over the coming interval, and the refresh runs them through the code the routes use. So "is this attack still
winnable" is checked when it is sent. Everything else (votes, purchases, empire actions, settings) is done on the spot
through the same functions as the routes: the routes for these are thin wrappers around a function that takes the
kingdom id (`build._settle`, `politics.found_empire`, `conquer._reveal_random_galaxy` and so on). The settings, the new
schedule entries and the bot's memory are one conditional write.

**What it can see.** Its own kingdom, names, galaxies, empires, the scores as the Scores page shows them
(`_get_scores_redacted`), its news, and other kingdoms through `_get_max_kd_info` with what is revealed to it. Never
hidden state.

**The round in three phases** (`botstrategy.phase`: the first 30% is early, to 70% mid, then late):

| Phase | What changes |
|---|---|
| Early | Money goes to structures, settling, then the army; the army is nearly all attackers for primitives; engineers work on the key unlock; no shields (the fuel is for growth). |
| Mid | The army moves ahead of settling for money (except for explorers); military shields go up; bombers start building silos; an empire leader denounces the strongest rival. |
| Late | The army comes first; strikes may gather the whole army; leaders (the top three by networth it can name) are worth double as targets, get its intel first, are sabotaged, have their fuel burnt, and are worn down with losing attacks; war is declared if it has not come by itself. |

### The economy (`plan_economy`, sums in `botstrategy.py`)

- **Nothing sits idle** (`spending_plan`). Income is split by what each category can use in the coming hours: settling is
  capped at a tenth of the kingdom in the queue, structures at the empty stars, engineers by workshops and population,
  the army by how fast recruits can be drafted. Funding already waiting in a category counts against what it asks for.
  What nothing can use stays as money (and is spent by hand, or on votes and missiles).
- **Enough defense to not be worth it** (`deterrence_per_star`). An attacker gains a tenth of your stars, or what the
  same army takes from primitives. Primitives get harder all round, so the defense per star that makes a kingdom the
  worse deal rises with the square root of time. Each playstyle keeps a margin on that line (`defense_margin`), more
  when it has been hit, 30% more while its empire is at war.
- **And enough to keep out the strongest army it knows of** (`note_threat`): the largest offense among the outsiders
  whose military is revealed to it (its own spying, and intel it accepted from galaxymates), a little over
  (`THREAT_MARGIN`), remembered for a day after the intel runs out, and never more than twice the line
  (`THREAT_CAP`): a kingdom can not out-defend everybody.
- **A floor for every playstyle, off for now** (`MIN_DEFENSE`): at 1.1 every bot keeps at least 1.1 times the
  peacetime break-even with primitives (`break_even_per_star`), so a hit on it pays less than primitives. Measured at
  1.1 it cost attackers 10% of their stars and intel bots 16%, without saving the attackers any stars, so it is 0.
- **The rest of the army money is offense** (`army_plan`, `offense_share`), sent at primitives by the auto attack with
  every pure attacker (`pure` is 100%: they are no use at home). Recruits are drafted only as fast as the money turns
  them into units (`max_recruits`, units before recruits).
- **Strength per recruit when people run short.** With money to spare, defense is bought as flexers, and big flexers
  once unlocked: twice and four times the strength for each recruit and hangar place. Otherwise defenders, the cheapest
  defense for the money.
- **Land for the army on order** (`structures_plan`): hangars and fuel plants for the units the budget will buy, before
  they arrive.
- **Homes and mines by what the kingdom is short of** (`HOMES_RULE = "surplus"`). Homes earn less than mines but
  hold the people recruits and engineers are drafted from. The homes share moves up while money is left over (people
  are short) and down while the army is short of money, so both run out together.
  The other rule, `"people"` (`homes_for_people`), sizes homes directly: at most 12% of the people can be recruits in
  training, for about 12 epochs, so `n` units an epoch need `100 n` people. It did worse. Sized from the army's share of
  the spending plan, which is itself capped by how fast recruits can be drafted, homes and army shrank each other
  (armies a quarter the size); sized from all the money the other categories leave, it overbuilt homes for intel bots
  and thieves (about half their homes-and-mines land) and the universe ended 6% smaller.
- **Engineers where a bonus is slipping** (`projects_plan`): a continuous bonus gets what keeps it full as the kingdom
  grows; a share works on the playstyle's unlock (Drone Gadgets, Big Flexers, Star Busters for bombers), which also
  takes whoever the bonuses do not need.
- **Settle while it pays** (`settle_worth`): the networth of a star and what its income buys before the round ends,
  against simply buying units. Land gets dearer as a kingdom grows and the round runs out, so settling fades by itself.
- **Shields** as the guide has it: military at maximum from the mid game whenever the fuel is there, the others with a
  reason.

### Fighting

- **Never blind.** A strike needs military intel that outlasts the wait. Without it, the bot spies for it, on the kingdom
  with the most stars for the army its networth could hide, or takes it from a galaxymate.
- **Hit what pays** (`player_edge`). A target is worth its stars per point of offense, compared with primitives. A bot
  that hits both strikes only when the kingdom is the better deal; one that hits only kingdoms takes the best there is.
  Enemies at war, grudges and (late) leaders count for more.
- **One strike at a time, with the army at home.** Auto attack is switched off from the think that plans a strike until
  it has run; the strike is timed for when enough generals are back (`_army_timeline`).
- **Thieves compare too**: a siphon is scheduled when its expected take beats what the same spy attempt robs from
  primitives, which it does more and more as primitives are robbed bare.
- **Siphons spread out.** Siphons on one kingdom share its 15%, so thieves that all pick the richest target take from
  each other. Each target is drawn in proportion to what it is worth (`SIPHON_PICK`), its income worked out from its
  structures when they are revealed (`income_from_intel`), so a kingdom of mines is worth more than one of homes.
- **And learn who catches them** (`note_siphons`): every siphon's outcome, from the spy history, is counted per
  target with the older ones counting less (`SIPHON_MEMORY`), and blended with the forecast (`SIPHON_PRIOR`). A
  kingdom with more drones than its stars suggest, a thief for example, is tried less and less, without anybody being
  named as a thief.

### Politics

- **Galaxy policies** by playstyle (`Personality.galaxy_votes`), and a **leader**: whoever the others back, and with no
  votes to go by, the strongest. (Everybody voting for today's strongest split the vote and elected nobody.)
- **Empires.** A galaxy leader joins the strongest empire that has room, or founds one; an empire leader admits who asks
  and invites galaxies without an empire. The game refuses a join that would give an empire more than 30% of the
  universe's kingdoms or 35% of its networth (`politics.empire_size_problem`; two galaxies may always ally), and the
  bots ask the same question first (`fits_in_empire`), so there is somebody left to fight. Bots never act against their
  own empire, and attack an under-defended human as readily as an under-defended bot.
- **War.** From the mid game the empire leader denounces the strongest other empire (the aggression that follows can
  bring a war without the penalty for a surprise), and late in the round declares war if it has not come.
- **Universe votes.** In an election a bot buys votes once, with a quarter of its loose money, and casts most on the arms
  doctrine (where playstyles disagree) and the rest on trade.

### The bot's own record

In the kingdom document, under `bot` (read it with `GET /kingdom/<id>` on the function app):

| Field | Holds |
|---|---|
| `type`, `style` | Archetype and style. |
| `next_think`, `phase` | When it thinks next; the phase it last planned for. |
| `log` | The last 40 decisions: `{time, kind, why, outcome}`. `plan` entries say what it is spending on and how its defense stands. |
| `counts` | How many times it has done each kind of thing all round (`attack`, `intelspy`, `buy_settle`, `empire_found`, `... refused`). |
| `memory` | What it has learned: `grudges`, `defense_boost`, `buffer_extra`, `spy_fails`, `strike` (the one pending), `siphons` running, `siphon_record` (per target, siphons that worked and tried, decayed) and `siphons_seen`, `threat` (the strongest offense known, whose, when), `stars_log`, `stalled`, `surplus` (money to spare, -0.5 to 1). |
| `reserved_generals` | Generals its auto attack leaves at home (0 once the brain has planned; bots from before keep 2). |

Bots made before styles and memory existed get a default style and an empty memory on their next think.

## Tuning: `scripts/simulate_round.py`

```
python scripts/simulate_round.py --days 7 --bots 40 --galaxies 4 --seed 1 --detail
python scripts/simulate_round.py --days 5 --set WAR_MARGIN=1.5 --set thief.defense_margin=1.3 --set "*.rob_share=1.0"
```

It runs the real function app handlers on the in-memory backend the tests use and moves a simulated clock, so the epoch
keeps its real length. A simulated day of 40 bots takes about 25 seconds, a week of 100 bots about 12 minutes; most
of it is the refresh's own function app calls, each a JSON round trip. It prints, per playstyle, stars and networth
(median and best), points, growth by day, metrics by day, where stars and money came from (including intel sold for a
cut), every action taken, the empires and wars, anything the game logged as an error, and the function app calls the
bots cost. `--set` tries a number without editing the code. **A seed always plays the same round**: the script fixes
Python's hash seed (it restarts itself with `PYTHONHASHSEED=0`) and draws every random number from the seed, so two
versions run with the same seed differ only by the change. One seed is still one round: compare the mean of several
before believing a change. `tests/test_bot_simulation.py` plays one day of it in the suite. (`scripts/simulate_bots.py` is the other one:
it drives the real local stack in real time.)

**All `Personality` and archetype numbers are `TUNE` values.** `botbrain.problems(personality)` and
`bots.problems(archetype)` check them, with the validators the routes use.

### Where it stands (2026-11-15)

**100 bots in 10 galaxies, the default mix, seven days, mean of three seeds** (median stars): attackers 9,700,
explorers 11,200, thieves 8,500, intel bots 7,400. Against the bots before siphon spreading and learning and the
threat-aware defense, that is the same overall (9,520 median stars both ways); attackers lose a third fewer stars to
strikes (960 against 1,380) and fewer die; siphon losses are spread (explorers lose 1.1 million each over the week
instead of 0.3 million, intel bots 1.4 instead of 2.9); thieves take about a fifth less by siphons (6.5 million
against 8.3), since spreading means less likely targets, which costs them nothing in stars (siphons are a few percent
of their income).

Before that, at 40 bots in 4 galaxies:

Seven days, 40 bots, 4 galaxies, mean of four seeds, against the bots as they were (auto builder only, plus a brain
that spied, voted and attacked kingdoms):

| | Stars (median) before | after | Networth (median) before | after |
|---|---|---|---|---|
| attacker | 3,100 | 11,000 to 12,000 | 420,000 | 1,800,000 |
| explorer | 4,500 | 10,800 | 400,000 | 1,800,000 |
| intel | 2,400 | 7,000 | 270,000 | 1,400,000 |
| thief | 2,600 | 8,700 | 265,000 | 1,650,000 |

What the old bots got wrong, in the order it mattered: recruits took all the army's money (millions of recruits, no
units); funding piled up in capped categories (up to 18 million idle); half the attackers and all the flex units stayed
home; defenders never grew (see the builder bug below), so explorers ended the week with their starting 1,400; nobody
but attackers hit primitives; starting points went to recruits and drones instead of an army.

In a typical run every playstyle uses its actions: primitives attacked and robbed, kingdoms attacked (won and lost),
all six reveal operations, siphons, kidnaps, bombed homes, sabotaged fuel plants, suicide drones, missiles built and
launched, intel offered, accepted and paid for, galaxy and universe votes, votes bought, leaders elected, empires
founded and joined, denouncements, wars (by aggression and declared), units disbanded.

A think costs about 10 function app calls, 4 per bot per epoch, next to the roughly 150 per kingdom per epoch the
refresh itself makes at one tick a minute.

**Not known:** how this compares with a real average player. There are no human rounds to measure against; "average
skill" here means every rule is one the Help pages give a player, applied consistently, with no hidden information.

### What the simulations say about the game (for the maintainer)

Not changed: these are balance and rules, which are the maintainer's call.

1. **Settling is where most stars come from**, not primitives: over a week, 55-75% of a bot's stars are settled,
   20-30% come from primitives, and attackers take another 25% from kingdoms (but lose most of it to each other).
2. **A sensibly defended kingdom is exactly as good a target as primitives, and no better.** An attack takes a tenth of
   the target's stars, so a kingdom with a tenth of the primitives' defense per star pays the same per point of offense
   (the deterrence line, `botstrategy.deterrence_per_star`). Bots hold that line (about 55-65 per star on day 7 against
   a line of 46 and primitives at 387). It moves with primitives, as the square root of time, so longer rounds do not
   change it. What makes kingdoms the better target is whatever pulls their defense under the line: war (+20% gains),
   losing attacks that wear it down, burning their fuel.
3. **Money is what limits a bot, at the margin.** Idle money (money and funding not yet spent, in epochs of income,
   when the kingdom is looked at) is about two epochs, and recruits are none of the army: the bots move land between
   homes and mines until neither people nor money is left over. Sizing homes by formula instead did worse (above).
4. **Siphons can not make a thief.** A siphon is worth 8 money per drone sent (`BASE_DRONES_SIPHON_PER_DRONE`); the 15%
   is only a cap on the target, shared pro rata by the siphons on it (see [status.md](status.md#siphons-2026-11-15) for
   the rule intended instead). With 6 drones per star and one spy attempt every two epochs, even a siphon with every
   attempt brings about 15 per star per epoch, against about 95 a thief earns at home. Over a week siphons were 3-4% of a
   thief's income. Robbing primitives falls to about 1 per drone by day 7. A siphon that scaled with the target's
   income, or a higher per-drone amount, would be the lever.
5. **Selling intel earns intel bots nothing.** Over a week of 100 bots no intel bot earned a star from a cut: about
   30% of the attackers' winning strikes used intel a galaxymate shared, but all of it was shared free (by attackers
   and thieves, who ask no cut), and attackers accept what is offered first. Lumina's offense penalty also keeps it off
   the primitives. Why no paid offer is ever used is not yet known.
6. **The mix of playstyles matters less than expected** (100 bots, 10 galaxies, one seed each, so a lead not a
   result; before the default mix). With only 10 attackers, those attackers took two and a half times the stars from kingdoms (3,200 against
   1,300 each). With only 10 thieves, each thief siphoned 30% more, but did not end ahead. At this size empires of three
   galaxies formed, and several wars ran at once.
7. **`pop_bonus` does nothing.** The project says it increases homes capacity; no formula reads it. The bots put no
   engineers on it.
8. **Engineers can be disbanded.** `_validate_disband` builds the message "You can't disband engineers" but does not
   return it.
9. **A small kingdom can be ground down to nothing.** An attack takes at least 25 stars however small the target, and
   nothing protects a kingdom a tenth of the attacker's size. Bots that only hit kingdoms do this to each other.
10. **Treatied won the election in the runs looked at**, because three of the four playstyles vote for it. It makes
   every unit 20% dearer for all of them too.

### Bugs found on the way (fixed)

- **The auto builder built no units once the army had the mix asked for**, which is always the case for a single-unit
  target such as "all defense". It now keeps building in the target's proportions. This affects players too (the Help
  page says so now).
- The auto builder divided by zero for a kingdom with none of the units it aims for, which skipped that kingdom on
  every tick.
- An attack on a kingdom with no defense at all divided by zero.
- A scheduled attack asking for more generals than were home raised `KeyError` in the refresh. It now does nothing.
- Universe votes cast by bots never counted: the tally is kept under `option_1` and `option_2`, and the bots sent `1`
  and `2`.
- Earlier: `KeyError` in the refresh for a general carrying a unit the unit targets do not list; scheduled Intel Spy
  and Aggressive Spy calling a function that does not exist; a scheduled attack with autofill that was not winnable
  crashing the rest of that kingdom's due schedules; `api/run.py` hiding refresh errors.

### Not yet

- Surrender, peace and leaving an empire.
- Messages, pinning, razing structures (a shrunken kingdom would raze mines for hangars before disbanding).
- A fifth archetype for the Fuzi (the missile race).
- Reacting to what the galaxy's news says about galaxymates being attacked.

## Questions for Ben

Nothing is blocked on these; I picked a default and moved on.

1. **Quick starts.** The archetypes now start with far more attackers and fewer drones (it is worth about 20% in the
   simulations). New players are offered the same starts. Is that what you want them offered?
2. **Vote preferences** are from the policy text (`Personality.galaxy_votes`, `universe_votes`). Three playstyles
   vote Treatied, which they also pay for.
3. **Existing bots** (without `style`) keep working with a default style. Re-create them to get the mix.
