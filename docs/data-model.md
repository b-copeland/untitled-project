# Data model

Every piece of game state is a JSON document in one Cosmos DB container. This lists them, what they hold, who writes them
and how. `tests/test_docs.py` fails if a field of the initial kingdom is missing from this page, so keep it current when
you add one.

## Conventions

- **One document per item.** The document `id` is also its partition key (`/id`), so every document is its own partition
  and nothing is atomic across two documents.
- **Per-kingdom documents** are named `<type>_<kd_id>` (`kingdom_7`, `structures_7`, ...). `POST /kingdom` on the function
  app creates all of them empty; Flask then fills them from `INITIAL_KINGDOM_STATE` in `shared.py` through `/createitem`.
- **Ids are strings.** Kingdom ids are `"0"`, `"1"`, ... assigned in order. Galaxy ids are `"<cluster>:<galaxy>"`
  (`"2:3"` is galaxy 3 of cluster 2), so a galaxy's cluster is the first part of its id. Empire ids are `"0"`, `"1"`, ...
- **Times are ISO 8601 strings in UTC** (`2026-11-14T08:00:00+00:00`). Compare them as datetimes, not strings, unless both
  come from the same `isoformat()`. `DATE_SENTINEL` (`2099-01-01T00:00:00+00:00`) means "never".
- **Cosmos adds** `_etag`, `_ts`, `_rid`, `_self`, `_attachments`. `_etag` is the version used for conditional writes. The
  function app strips these from request bodies, so sending a document back is harmless.

## How the function app writes

Read the handler in `funcapp/function_app.py` before relying on one, but these are the patterns:

| Pattern | Routes | What the body does |
|---|---|---|
| **Shallow merge** | `PATCH /kingdom/<id>`, `/kingdoms`, `/scores`, `/empires`, `/galaxy/<id>/politics`, `/empire/<id>/politics`, `/universepolitics`, `/galaxy/<id>/intel`, `/cluster/<id>`, `/empire/<id>/targets`; `/updatestate` (merges into the inner `state` object) | `{**document, **body}`. Top-level keys in the body replace the stored ones **entirely**. Sending `{"next_resolve": {"structures": t}}` replaces the whole `next_resolve` object with one key. Send the full nested object. |
| **Append or replace** | queues (`/settles`, `/mobis`, `/structures`, `/missiles`, `/engineers`) | `new_<field>` (a list of entries) is appended and the queue folded, see below; `<field>` replaces the list. |
| | `/siphonsin`, `/siphonsout` | `new_siphons` (one item) is appended; `siphons` replaces the list. |
| | `/revealed` | `new_revealed` is merged per target kingdom and stat, each stat keeping the later of the stored and the incoming expiry (so shared intel never shortens a reveal); `new_galaxies` is merged; `new_revealed_galaxymates` and `new_revealed_to_galaxymates` are appended. The same names without `new_` replace. |
| | `/kingdom/<id>/lastknown` | `new_known` (target to category to `{ended, values}`) is merged per target and category, each keeping the entry that ended later, so writes land in any order and a repeat changes nothing. The first write creates the document; a read of a kingdom with none answers `known: {}` without writing. |
| **Prepend** | `/kingdom/<id>/news`, `/galaxy/<id>/news`, `/kingdom/<id>/messages` | The body is the item, or a list of items; newest first. Messages keep the newest 100. |
| | `/universenews` | The same, but the body is `{"news": item or list}`. |
| | `/spyhistory`, `/attackhistory`, `/missilehistory` | The body is one item. |
| **Special** | `/notifs` | `add_categories` adds one to each counter named; `clear_categories` zeroes them. |
| | `/pinned` | `pinned` adds kingdom ids, `unpinned` removes them. |
| | `/history` | `{"history": {series: value}}` appends one value to each series. |
| | `/accounts` | Replaces the whole list. Nothing calls it any more (see `accounts` below). |

Not retried, because they write several documents or create one: `/init`, `/deleteall`, `/resetstate`, `POST /kingdom`,
`POST /galaxy/<id>`, `POST /empire`, `/createitem` (creates the document, or shallow-merges into an existing one),
`POST /user` and `POST /username/<key>` (create only, `409` if the document exists). `POST /kingdom` and
`POST /empire` take the new id with a conditional write on `kingdoms` / `empires` (and `POST /kingdom` joins the
galaxy with one on `galaxies`), so creations at the same moment get different ids. `POST /kingdom` answers `400` for a
name already taken (exactly the same name); `POST /empire` answers `409` if the galaxy is already in an empire, and
both answer `503` if the document stayed too busy to write.

A route that exists but does not work with the current documents, so do not call it: `PATCH /empire/<id>/news`
([status.md](status.md#code-health)).

Every `update_*` handler is wrapped in `@retry_on_conflict`, so merges and appends land on the newest version and never
lose each other. A caller that sends `If-Match: <_etag>` gets `412` if the document changed since it read it; `occ.update`
uses that.

**Queue entries** are `{"time": <finish time>, "<unit or structure name>": <count>, ...}` and must carry no other keys:
the refresh treats every key except `time` as something to credit. Appended entries are folded (`funcapp/queues.py`):
finish times are rounded up to a grid of 0.1% of an epoch and entries on the same time are summed.

## Global documents

| id | Holds | Written by | Tier |
|---|---|---|---|
| `state` | `round` (an id that changes at every round reset; login tokens carry it, and tokens from another round are refused); `state`: `game_start`, `game_end`, `election_start`, `election_end`, `next_history`, `active_policies`, `game_over` (when the round ended, `""` while it runs), `rounds_archived`, galaxy sizing, and whatever the admin page sets | admin routes, the refresh (elections, history time, the end of the round), `/resetstate` (`round`) | strict |
| `archive_<n>` | One finished round: `number`, `ended_at`, `reason`, `game_start`, `game_end`, `scores`, `galaxies`, `kingdoms` (kd id to `{name, galaxy, race, status, stars, networth, bot}`), `ranking`. Kept by `/resetstate` | `roundend.end_round`, once per round | strict (written once) |
| `kingdoms` | `kingdoms`: kd id to name; `next_id`, the next id to hand out, which survives a round reset so ids are never reused (read with a default of 0) | kingdom creation, `/resetstate` | strict |
| `galaxies` | `galaxies`: galaxy id to a list of kd ids | the function app only: `POST /galaxy/<id>` (admin) and `POST /kingdom` (kingdom creation) | strict |
| `empires` | `empires`: empire id to `{name, galaxies, aggression, num_kingdoms, aggression_max, war, peace, denounced, denounced_expires, surprise_war_penalty, surprise_war_penalty_expires, targets}`; `last_update`. `targets` (missing on empires that never had one) is the hint of [empire targets](#empire-targets): a superset of the empire's target kingdoms, left out of `/api/empires` | politics routes, the refresh (`_resolve_empires`), attacks (aggression), `targets.py` (the hint) | strict for membership and war, derived for aggregates |
| `scores` | `points`, `stars`, `networth`, `galaxy_networth` (each keyed by id), `galaxy_kingdoms_alive` (galaxy to the number of its kingdoms the refresh scored, so neither dead nor never set up; missing until the first tick that wrote it), `last_update` | the refresh only | derived |
| `universe_votes` | `votes`: policy, option, kd id to votes | `/api/votes`, `/api/universepolitics/policies`, elections | strict |
| `universe_news` | `news`: list | elections, politics | eventual |
| `accounts` | `accounts`: the last copy of the SQLite users, from before they moved to `user_` documents; the migration reads it | nothing any more | a frozen backup, to be removed ([status.md](status.md#parallelism-gaps)) |
| `galaxy_news_<galaxy>` | `news`: list | actions affecting the galaxy | eventual |
| `galaxy_votes_<galaxy>` | `votes` (`policy_1`, `policy_2`, `leader`), `vote_changed` (vote kind to kingdom to when that kingdom last changed that vote; read with a default, since kingdoms that never changed one have no entry; a change holds for `BASE_GALAXY_VOTE_COOLDOWN_EPOCHS`), `active_policies`, `leader`, `policy_1_winner`, `policy_2_winner`, `empire_invitations`, `empire_join_requests` | galaxy politics routes, empire routes | strict |
| `empire_politics_<empire>` | `empire_invitations`, `empire_join_requests`, `surrender_offers_sent`, `surrender_offers_received`, `surrender_requests_sent`, `surrender_requests_received`, `leader` | empire politics routes | strict |
| `galaxy_intel_<galaxy>` | The galaxy's intel market, see [below](#the-intel-market). `GET /galaxy/<id>/intel` creates the document as `{"id": ...}` the first time it is read, so every field is read with a default | `intel.py` (every intel action) | strict: every change is decided on it with `occ.update` |
| `cluster_<cluster>` | The cluster's politics, see [below](#cluster-politics). `GET /cluster/<id>` creates the document as `{"id": ...}` the first time it is read, so every field is read with a default | `clusters.py`: a galaxy leader's vote, and the refresh when the cluster's empire alignment changes | strict: every change is decided on it with `occ.update` |
| `empire_targets_<empire>` | The empire's targets, see [below](#empire-targets). `GET /empire/<id>/targets` creates the document as `{"id": ...}` the first time it is read, so every field is read with a default | `targets.py`: leadership's routes, and every attack, spy operation and missile strike on a target | strict: every change is decided on it with `occ.update` |
| `empire_news_<empire>` | `news`: list | nothing yet: it is created empty and read, but never written | eventual |

## Per-kingdom documents

| id | Holds | Tier |
|---|---|---|
| `kingdom_<id>` | The kingdom itself; fields below | strict: the decision point for almost every action |
| `settles_<id>`, `mobis_<id>`, `structures_<id>`, `missiles_<id>`, `engineers_<id>` | Build queues: a list of queue entries under the same name | strict-ish: appended by actions, trimmed by the refresh |
| `siphons_out_<id>` | `siphons_out`: the siphons running on this kingdom, see [below](#siphons) | eventual: appended by Siphon Funds, settled by the refresh |
| `siphons_in_<id>` | `siphons_in`: payments to this kingdom from its siphons, waiting for its next refresh | eventual: appended by the target's refresh, cleared by this kingdom's |
| `news_<id>` | `news`: list of `{time, from, to, news, kind}` (`kind` is `attack`, `spy`, `missiles`, `intel`, `targets` or missing on old items) | eventual |
| `revealed_<id>` | `revealed`: kd id to stat to expiry time; `galaxies`: galaxy id to expiry; `revealed_galaxymates`, `revealed_to_galaxymates` | eventual. The kingdom's `next_resolve.revealed` timer is lowered to the soonest expiry (`_lower_timer` in `conquer.py`) so the refresh expires them on time. |
| `lastknown_<id>` | `known`: kd id to reveal category to `{ended, values}`: what that intel showed when it ended (the category's fields from `REVEAL_FIELDS`, projects without their zero entries and without the bonuses, which are worked out when read). Only kingdoms that have had intel end have one. See `lastknown.py` and [decisions/0009](decisions/0009-last-known-intel.md) | eventual: merged by the refresh when reveals expire, and by Unshare |
| `pinned_<id>` | `pinned`: list of kd ids | eventual |
| `spy_history_<id>`, `attack_history_<id>`, `missile_history_<id>` | Lists of past operations | eventual |
| `messages_<id>` | `messages`: list | eventual |
| `notifs_<id>` | Counters: `news_kingdom`, `news_galaxy`, `messages`, `shared` (intel market events for this kingdom: a sale, a bounty answered, free intel received) | eventual |
| `history_<id>` | `history`: series of `networth`, `stars`, `population`, `drones`, `engineers`, `max_offense`, `max_defense` | eventual, written by the refresh once an epoch |

The tiers are explained in [concurrency.md](concurrency.md#which-documents-need-strict-handling). In short: **strict**
documents are read to decide whether something is allowed, so writes to them are conditional; **eventual** ones are only
displayed, so appends are enough; **derived** ones are recomputed by the refresh and never written by actions.

### Siphons

A successful Siphon Funds appends one entry to the target's `siphons_out`:

| Key | Meaning |
|---|---|
| `from` | The siphoning kingdom. Stripped from `/api/siphonsout`, so the target does not learn who it is. |
| `time` | When the siphon ends |
| `siphon` | Money it still has to take |
| `rate` | Money it takes per epoch. Set to `siphon / BASE_DRONES_SIPHON_TIME_MULTIPLIER` when it is made. The refresh can lower it when the cap cuts this siphon, and never raises it. Entries made before this key existed do not have it: read it with `.get`. The refresh then uses what is left divided by the epochs left, and stores that rate. |

Each tick, `_settle_siphons` in `refresh.py` pays each siphon its `rate` for the part of the tick it was running, never
more than its `siphon`. If the rates together exceed `BASE_MAX_SIPHON` of the target's gross income, it cuts the
soonest to end first. It then writes each siphon's lowered `siphon` and `rate` back, and drops siphons that have ended
or have nothing left. Each payment is appended to the siphoner's `siphons_in` as `{from, siphon, time,
remaining_siphon}`: `from` is the target, `siphon` the money paid, and `time` and `remaining_siphon` say when the
siphon ends and what it still has to take. The siphoner's next refresh credits the payments and clears them. A siphon
whose siphoner is dead (or no longer exists) ends at the target's next tick: it pays nothing, does not count towards
the cap, and is dropped. The refresh knows the siphoner's status from the kingdoms it has already refreshed that tick,
or reads it once.

### The intel market

`galaxy_intel_<galaxy>` is the one decision point of every intel action (`intel.py`): listing, buying, sharing free,
posting, withdrawing or answering a bounty, and exclusions. Nothing in it is on a timer: expired entries are ignored when
it is read and dropped whenever it is next written. Cuts are fractions.

| Key | Holds |
|---|---|
| `listings` | Listing id (`<seller>.<target>.<category>`) to `{id, seller, target, category, cut, time, listed_at}`. One per seller, target and category; listing again replaces it. `time` is when the seller's reveal, and so the listing, ends. Buying does not remove it. |
| `bounties` | Bounty id (`<requester>.<target>.<category>`) to `{id, requester, target, category, cut, time, posted_at}`. `time` is when it expires. Answering it removes it. |
| `accepted` | Buyer to target to category to `{sharer, cut, time, source, accepted_at}`: intel the buyer received and owes a cut for until `time`. `source` is `market`, `bounty` or `free` (cut 0). An attack pays each sharer the cuts of its records on that target. |
| `received` | Receiver to target to category to the time until which it has that intel from galaxymates: the latest of everything bought, given for a bounty, or shared free. Intel received can not be passed on (listed, shared, or used for a bounty) until then. Kept apart from `accepted` because free intel that outlasts paid intel leaves the paid record in place. |
| `exclusions` | Kingdom to the galaxymates it keeps its intel from: they do not see its listings or bounties, can not buy or answer them, and get nothing from its free shares |
| `history` | The newest 50 of `{kind, time, from, to, target, category, cut}`; `kind` is `purchase`, `bounty` or `free` (`to` is null: the whole galaxy) |

Ids are never parsed: every entry carries its own fields. An action that gives intel then appends it to the receiver's
`revealed` (keeping the later expiry) and lowers their `next_resolve.revealed`, so the refresh expires it on time.

### Cluster politics

`cluster_<cluster>` is the one decision point of a cluster's politics (`clusters.py`). Its members are the galaxies
whose ids start with `<cluster>:`, from the `galaxies` document, so it does not list them. Levels are not advanced on a
tick: anyone reading the document advances them from `last_update` to now (`clusters.advance`), and every write stores
the advanced levels with its own time.

| Key | Holds |
|---|---|
| `votes` | Galaxy id to the key of the benefit (in `CLUSTER_BENEFITS`) its leader voted for. A galaxy with no vote is absent |
| `vote_changed` | Galaxy id to when its vote last changed (cast, switched or withdrawn). The vote can not change again for `CLUSTER_VOTE_COOLDOWN_EPOCHS` |
| `levels` | Benefit key to its level from 0 to 1 (a fraction of the benefit's `max`), as of `last_update` |
| `alignment` | The share of the cluster's galaxies in its largest empire, as of `last_update`. The refresh stores it when it changes |
| `last_update` | When `levels` were last advanced |

### Empire targets

`empire_targets_<empire>` is the one decision point of an empire's targets (`targets.py`). Each empire in the `empires`
document also carries `targets`, a list of kingdom ids, so an action knows whether its target may be one without
reading this document: a kingdom is added to that list before it is added here, and taken out after it is removed
here, so the list is never short of a real target ([decisions/0008](decisions/0008-empire-targets.md)). A target is
only added while the two empires are at war, an action counts for it only while they still are (checked against
the `empires` document the action has in hand), and a surrender ends every target either side had in the other.

| Key | Holds |
|---|---|
| `delegates` | The kingdoms the emperor named to manage targets with them, at most `TARGET_MAX_DELEGATES` |
| `targets` | Target kingdom to `{target, stars_at_start, actions, fund_share, created_at, created_by, points, fund, paid, intel, lost}`. `stars_at_start`: its land when it was marked, which the points that earn its land and money at its death are measured against. `lost` (missing until something is): `{stars, money}` that left the game instead of being paid, over the star caps. `actions`: each marked action (a key of `TARGET_ACTIONS`) to its points multiplier. `points` and `paid` (`{stars, money}`) per participant. `fund`: `{stars, money}`, paid out only when the target ends. `paid` is filled in then. `intel`: category to when the empire's shared intel on the target ends |
| `removed` | Kingdom to when leadership removed it as a target. It can not be marked again until `TARGET_REMARK_COOLDOWN_EPOCHS` later; entries past that are dropped when a target is next added |
| `history` | The newest `TARGET_HISTORY_LENGTH` ended targets, newest first: `{target, actions, fund_share, created_at, ended_at, reason, ended_by, points, paid, lost}`; `reason` is `removed`, `killed` or `war_ended`, `lost` everything that left the game instead of being paid (over the star caps, the unearned part of a dead target's land and money, rounding, or the whole fund with nobody to pay) |

## The kingdom document

Created from `INITIAL_KINGDOM_STATE["kingdom"]` in `shared.py`, which has the starting values.

| Field | Meaning |
|---|---|
| `kdId`, `name`, `race`, `coordinate` | Identity, and position (distance affects general return times) |
| `status` | `Active` or `Dead` |
| `stars`, `fuel`, `population`, `money`, `drones`, `networth`, `votes` | Resources and totals |
| `last_income` | When income was last credited |
| `income` | The last income breakdown, for display |
| `next_resolve` | Per category, when the refresh next has work: `generals`, `spy_attempt`, `settles`, `mobis`, `missiles`, `engineers`, `structures`, `revealed`, `auto_spending`, and `galaxies_revealed` (only on kingdoms with Lumina Evolution: when to renew its reveal of every galaxy). Kingdoms made before the intel market also have `shared`, which their next refresh sets to never |
| `spy_attempts` | Spy operations available now |
| `generals_available`, `generals_out` | Generals home, and those on an attack with their return time and units |
| `units` | Units at home, one count per key of `UNITS` (including `recruits` and `engineers`) |
| `units_target`, `structures_target`, `projects_target` | What the auto builder aims for, as shares |
| `max_recruits`, `recruits_before_units` | Auto builder settings for recruits |
| `structures` | Structures built |
| `missiles` | Missiles held |
| `shields` | `military`, `spy`, `spy_radar`, `missiles` levels |
| `revealed_to` | Who currently sees this kingdom, for display |
| `auto_spending_enabled`, `auto_spending`, `funding` | Auto builder switch, the income split, and the money set aside per category |
| `auto_attack_enabled`, `auto_attack_settings` | Automatic attacks on primitives |
| `auto_rob_enabled`, `auto_rob_settings` | Automatic robbing of primitives |
| `projects_points`, `projects_max_points`, `projects_assigned`, `completed_projects`, `auto_assign_projects` | Projects: progress, caps, engineers assigned, unlocks done. One key per project in `PROJECTS`; a kingdom made before a unit or project existed lacks its keys until its next tick fills them (`with_new_fields` in `shared.py`), so read them with the helpers there. |
| `schedule` | Scheduled actions waiting for their time |
| `siphons` | Siphons this kingdom is running |

Fields added after creation:

| Field | Meaning |
|---|---|
| `queues_resolved_until` | Per queue, the time up to which finished entries have been credited, so a repeated refresh never credits twice |
| `bot` | Only on bots run by the bot brain: `type`, `style`, `next_think`, `phase`, `log`, `counts`, `memory`, `reserved_generals` (see [bots.md](bots.md#the-bots-own-record)). Read each with `.get`: bots made earlier have only the first, third and fifth. |

## Users

Users are Cosmos documents too ([decisions/0004](decisions/0004-users-in-cosmos.md)), read and written through
`api/untitledapp/users.py` (`User`). Nothing is stored in SQL any more
([architecture.md](architecture.md#target-no-sqlite)).

| id | Holds | Written by |
|---|---|---|
| `user_<id>` | `id_number` (the numeric user id, an int: it is the `id` claim in JWTs and in email tokens), `username`, hashed `password`, `roles` (comma-separated: `operator`, `admin`, `verified`), `kd_id` (a string, or null), `kd_created`, `kd_death_date`, `email`, `email_verified`, `is_active`, `is_verified`; `kd_pending` while a kingdom is being made for it | `POST /user` (create only, `409` if it exists); `PATCH /user/<id>` (shallow merge, honours `If-Match`; never changes `id_number`). Flask writes through `user.save` / `user.update`, which are `occ.update` |
| `username_<key>` | `user_id`: the int id of the user with that name. `key` is the lowercase hex of the UTF-8 username, so any name is a valid id and lookups stay case-sensitive | `POST /username/<key>` at sign-up: creating it is the uniqueness check, `409` if the name is taken |
| `user_counter` | `next_id`: the next free user id | `PATCH /usercounter` with `If-Match` (`occ.update`), at sign-up. `GET /usercounter` creates it with `next_id: 1` if it is missing |

- **Sign-up** takes an id from the counter, claims the name for it, then writes the user. A crash after the claim leaves
  the name taken by nobody; `User.lookup` also checks that the user it finds has the name, so a stale claim finds
  nobody.
- **Kingdom creation** claims the user first: `kd_pending` (`{request, time}`) is set with `occ.update` only while the
  user has no `kd_id` and no other request's claim younger than `KINGDOM_CLAIM_SECONDS` (`misc.py`). It is cleared when
  the kingdom is recorded, or when making it fails.
- **Read per request:** `current_user()` answers `id`, roles, `kd_id` and `kd_created` from the login token (claims `id`,
  `rls`, `kd`, `kc`, `rnd`) and reads `user_<id>` once per request (`request_cache.py`) only for any other field. The
  token is up to a day old: a disabled player or a changed role takes effect when the token is renewed
  ([decisions/0005](decisions/0005-kingdom-in-the-token.md)).
- **Queries:** `GET /users` is one cross-partition query over the user documents, in id order, filtered by any of
  `email`, `kd_id` and `prefix` (of the username). For admin and rare lookups only (round reset, kingdom death, email
  recovery, bot names), never per request or per tick.
- **Users outlive a round:** `/resetstate` keeps every `user_` and `username_` document (the admin reset then clears
  their kingdom fields). `/deleteall` (tests) removes them rather than blanking them, so names become free again.
- **Old documents:** a user document written before a field existed lacks it; `users.FIELDS` holds the defaults.
