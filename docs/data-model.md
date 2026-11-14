# Data model

Every piece of game state is a JSON document in one Cosmos DB container. This lists them, what they hold, who writes them
and how. `tests/test_docs.py` fails if a field of the initial kingdom is missing from this page, so keep it current when
you add one.

## Conventions

- **One document per item.** The document `id` is also its partition key (`/id`), so every document is its own partition
  and nothing is atomic across two documents.
- **Per-kingdom documents** are named `<type>_<kd_id>` (`kingdom_7`, `structures_7`, ...). `POST /kingdom` on the function
  app creates all of them empty; Flask then fills them from `INITIAL_KINGDOM_STATE` in `shared.py` through `/createitem`.
- **Ids are strings.** Kingdom ids are `"0"`, `"1"`, ... assigned in order. Galaxy ids look like `"1:3"`. Empire ids are
  `"0"`, `"1"`, ...
- **Times are ISO 8601 strings in UTC** (`2026-11-14T08:00:00+00:00`). Compare them as datetimes, not strings, unless both
  come from the same `isoformat()`. `DATE_SENTINEL` (`2099-01-01T00:00:00+00:00`) means "never".
- **Cosmos adds** `_etag`, `_ts`, `_rid`, `_self`, `_attachments`. `_etag` is the version used for conditional writes. The
  function app strips these from request bodies, so sending a document back is harmless.

## How the function app writes

Read the handler in `funcapp/function_app.py` before relying on one, but these are the patterns:

| Pattern | Routes | What the body does |
|---|---|---|
| **Shallow merge** | `PATCH /kingdom/<id>`, `/kingdoms`, `/scores`, `/empires`, `/galaxy/<id>/politics`, `/empire/<id>/politics`, `/universepolitics`; `POST /kingdom/<id>/shared`; `/updatestate` (merges into the inner `state` object) | `{**document, **body}`. Top-level keys in the body replace the stored ones **entirely**. Sending `{"next_resolve": {"structures": t}}` replaces the whole `next_resolve` object with one key. Send the full nested object. |
| **Append or replace** | queues (`/settles`, `/mobis`, `/structures`, `/missiles`, `/engineers`) | `new_<field>` (a list of entries) is appended and the queue folded, see below; `<field>` replaces the list. |
| | `/siphonsin`, `/siphonsout` | `new_siphons` (one item) is appended; `siphons` replaces the list. |
| | `/revealed` | `new_revealed` is merged per target kingdom and stat, the incoming expiry replacing the stored one; `new_galaxies` is merged; `new_revealed_galaxymates` and `new_revealed_to_galaxymates` are appended. The same names without `new_` replace. |
| **Prepend** | `/kingdom/<id>/news`, `/galaxy/<id>/news`, `/kingdom/<id>/messages` | The body is the item, or a list of items; newest first. Messages keep the newest 100. |
| | `/universenews` | The same, but the body is `{"news": item or list}`. |
| | `/spyhistory`, `/attackhistory`, `/missilehistory` | The body is one item. |
| **Special** | `/notifs` | `add_categories` adds one to each counter named; `clear_categories` zeroes them. |
| | `/pinned` | `pinned` adds kingdom ids, `unpinned` removes them. |
| | `/history` | `{"history": {series: value}}` appends one value to each series. |
| | `/accounts` | Replaces the whole list. |

Not retried, because they write several documents or create one: `/init`, `/deleteall`, `/resetstate`, `POST /kingdom`,
`POST /galaxy/<id>`, `POST /empire`, `/createitem` (creates the document, or shallow-merges into an existing one).

Routes that exist but do not work with the current documents, so do not call them: `PATCH /empire/<id>/news`,
`PATCH /kingdom/<id>/shared`, `/sharedrequests` ([status.md](status.md#code-health)).

Every `update_*` handler is wrapped in `@retry_on_conflict`, so merges and appends land on the newest version and never
lose each other. A caller that sends `If-Match: <_etag>` gets `412` if the document changed since it read it; `occ.update`
uses that.

**Queue entries** are `{"time": <finish time>, "<unit or structure name>": <count>, ...}` and must carry no other keys:
the refresh treats every key except `time` as something to credit. Appended entries are folded (`funcapp/queues.py`):
finish times are rounded up to a grid of 0.1% of an epoch and entries on the same time are summed.

## Global documents

| id | Holds | Written by | Tier |
|---|---|---|---|
| `state` | `state`: `game_start`, `game_end`, `election_start`, `election_end`, `next_history`, `active_policies`, galaxy sizing, and whatever the admin page sets | admin routes, the refresh (elections, history time) | strict |
| `kingdoms` | `kingdoms`: kd id to name | kingdom creation | strict |
| `galaxies` | `galaxies`: galaxy id to a list of kd ids | the function app only: `POST /galaxy/<id>` (admin) and `POST /kingdom` (kingdom creation) | strict |
| `empires` | `empires`: empire id to `{name, galaxies, aggression, num_kingdoms, aggression_max, war, peace, denounced, denounced_expires, surprise_war_penalty, surprise_war_penalty_expires}`; `last_update` | politics routes, the refresh (`_resolve_empires`), attacks (aggression) | strict for membership and war, derived for aggregates |
| `scores` | `points`, `stars`, `networth`, `galaxy_networth` (each keyed by id), `last_update` | the refresh only | derived |
| `universe_votes` | `votes`: policy, option, kd id to votes | `/api/votes`, `/api/universepolitics/policies`, elections | strict |
| `universe_news` | `news`: list | elections, politics | eventual |
| `accounts` | `accounts`: a backup copy of the SQLite users | account routes | backup only; SQLite is the source |
| `galaxy_news_<galaxy>` | `news`: list | actions affecting the galaxy | eventual |
| `galaxy_votes_<galaxy>` | `votes` (`policy_1`, `policy_2`, `leader`), `active_policies`, `leader`, `policy_1_winner`, `policy_2_winner`, `empire_invitations`, `empire_join_requests` | galaxy politics routes, empire routes | strict |
| `empire_politics_<empire>` | `empire_invitations`, `empire_join_requests`, `surrender_offers_sent`, `surrender_offers_received`, `surrender_requests_sent`, `surrender_requests_received`, `leader` | empire politics routes | strict |
| `empire_news_<empire>` | `news`: list | nothing yet: it is created empty and read, but never written | eventual |

## Per-kingdom documents

| id | Holds | Tier |
|---|---|---|
| `kingdom_<id>` | The kingdom itself; fields below | strict: the decision point for almost every action |
| `settles_<id>`, `mobis_<id>`, `structures_<id>`, `missiles_<id>`, `engineers_<id>` | Build queues: a list of queue entries under the same name | strict-ish: appended by actions, trimmed by the refresh |
| `siphons_in_<id>`, `siphons_out_<id>` | Active siphons on and by this kingdom | eventual |
| `news_<id>` | `news`: list of `{time, from, to, news, kind}` (`kind` is `attack`, `spy`, `missiles`, `intel` or missing on old items) | eventual |
| `revealed_<id>` | `revealed`: kd id to stat to expiry time; `galaxies`: galaxy id to expiry; `revealed_galaxymates`, `revealed_to_galaxymates` | eventual. The kingdom's `next_resolve.revealed` timer is lowered to the soonest expiry (`_lower_timer` in `conquer.py`) so the refresh expires them on time. |
| `shared_<id>` | `shared`, `shared_requests`, `shared_offers`: intel shared with, requested from and offered by this kingdom | strict for accepting offers |
| `pinned_<id>` | `pinned`: list of kd ids | eventual |
| `spy_history_<id>`, `attack_history_<id>`, `missile_history_<id>` | Lists of past operations | eventual |
| `messages_<id>` | `messages`: list | eventual |
| `notifs_<id>` | Counters: `news_kingdom`, `news_galaxy`, `messages`, `shared` | eventual |
| `history_<id>` | `history`: series of `networth`, `stars`, `population`, `drones`, `engineers`, `max_offense`, `max_defense` | eventual, written by the refresh once an epoch |

The tiers are explained in [concurrency.md](concurrency.md#which-documents-need-strict-handling). In short: **strict**
documents are read to decide whether something is allowed, so writes to them are conditional; **eventual** ones are only
displayed, so appends are enough; **derived** ones are recomputed by the refresh and never written by actions.

## The kingdom document

Created from `INITIAL_KINGDOM_STATE["kingdom"]` in `shared.py`, which has the starting values.

| Field | Meaning |
|---|---|
| `kdId`, `name`, `race`, `coordinate` | Identity, and position (distance affects general return times) |
| `status` | `Active` or `Dead` |
| `stars`, `fuel`, `population`, `money`, `drones`, `networth`, `votes` | Resources and totals |
| `last_income` | When income was last credited |
| `income` | The last income breakdown, for display |
| `next_resolve` | Per category, when the refresh next has work: `generals`, `spy_attempt`, `settles`, `mobis`, `missiles`, `engineers`, `structures`, `revealed`, `shared`, `auto_spending` |
| `spy_attempts` | Spy operations available now |
| `generals_available`, `generals_out` | Generals home, and those on an attack with their return time and units |
| `units` | Units at home: `attack`, `defense`, `flex`, `big_flex`, `recruits`, `engineers` |
| `units_target`, `structures_target`, `projects_target` | What the auto builder aims for, as shares |
| `max_recruits`, `recruits_before_units` | Auto builder settings for recruits |
| `structures` | Structures built |
| `missiles` | Missiles held |
| `shields` | `military`, `spy`, `spy_radar`, `missiles` levels |
| `revealed_to` | Who currently sees this kingdom, for display |
| `auto_spending_enabled`, `auto_spending`, `funding` | Auto builder switch, the income split, and the money set aside per category |
| `auto_attack_enabled`, `auto_attack_settings` | Automatic attacks on primitives |
| `auto_rob_enabled`, `auto_rob_settings` | Automatic robbing of primitives |
| `projects_points`, `projects_max_points`, `projects_assigned`, `completed_projects`, `auto_assign_projects` | Projects: progress, caps, engineers assigned, unlocks done |
| `schedule` | Scheduled actions waiting for their time |
| `siphons` | Siphons this kingdom is running |

Fields added after creation:

| Field | Meaning |
|---|---|
| `queues_resolved_until` | Per queue, the time up to which finished entries have been credited, so a repeated refresh never credits twice |
| `bot` | Only on bots run by the bot brain: `type`, `next_think`, `log` (see [bots.md](bots.md)) |

## Users (SQLite)

`User` in `api/untitledapp/__init__.py`: `username`, hashed `password`, `roles` (`operator`, `admin`), `kd_id`,
`kd_created`, `kd_death_date`, `email`, `email_verified`, `is_active`, `is_verified`. The `Locks` table holds the legacy locks.
Both live in a file on one machine and are being phased out
([architecture.md](architecture.md#target-no-sqlite)): add nothing to them.
