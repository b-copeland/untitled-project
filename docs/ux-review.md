# UX / UI review

A page-by-page look at how information is shown, with concrete proposals. **This is for review, not for merging blindly:**
the proposals are opinions about a game I have only read the code of, and I could not look at the running app or try it
on a phone. Where a proposal is built in the accompanying PR it is marked **[built]**; everything else is a suggestion.

The game is a long-running strategy game where "one login every 12 hours with a good plan should stay competitive"
(`untitled_project.txt`). That shapes what matters on screen: when you log in after half a day you want to know **what
happened, what needs doing, and what is cheap to do next**, quickly, on a phone as often as on a desk.

## What I found across the whole app

1. **Every page starts from zero.** Each page is its own island of tabs, tables and forms, and the only thing that carries
   over is the strip at the top. There is no "what changed since I was last here" anywhere, and no "needs attention".
2. **Pages are organised by system, players think in tasks.** Money, funding, queues and the auto-spender are spread over
   Home > Status > Spending, Build > Queue, Build > Structures > Allocate and Home > Status again. A player who wants to
   know "is my economy healthy and what is the auto-spender doing" visits four pages.
3. **Numbers without context.** `Fuel: 5,000` does not say whether that is a lot, how fast it is falling, or when it runs
   out. Income is shown per N minutes (Status), as a lump (header) and nowhere as a rate against the stock.
4. **Tabs hold unrelated things.** Status has Kingdom / Shields / Spending / Military / Structures; Military has Recruits /
   Specialists / Levy / Allocate / Disband. The tab names are sensible but the first tab is a very long page and the rest
   are short; people will not find "Spending" (it is where you switch auto spending on) under Home > Status.
5. **Forms say "no" late.** Fixed for Settle, Structures and Missiles (#50); the other
   forms still send first and report in a toast.
6. **Results are toasts in the corner and disappear.** Fine for "built", poor for an attack report, which is the most
   important thing the game ever tells you. They are kept in News/History, but nothing says so.
7. **Loading is the text "Loading..."** in many places, so the page jumps when data arrives.
8. **The table code is the UI.** Most pages are hand-written tables, so every change is a copy-paste, which is why they
   drift from each other (alignment, fonts, which numbers are formatted). The shared components added in the previous PRs
   (`GameTable`, `NumberField`, `ResultToasts`) are the way out; this PR uses them on the Scores page.
9. **Phone width is an afterthought.** Tables use fixed font sizes (9-12 px) to fit instead of changing shape.
   Wide tables (Galaxy, Military, Projects, Empire Politics) become unreadable; they should become cards on a narrow screen.

## Page by page

Sizes are lines of code, as a rough guide to how much is on the page.

### Header strip (all game pages) **[built]**
Clock, stars, fuel, population, money, networth, spy attempts, generals. Eight equal boxes.
- Problem: all equal weight; nothing tells you something is wrong; the class-component clock re-fetches the time on every page.
- Built: fuel turns red with the reason when it reaches 0 (military is at a penalty, easy to miss); money flags debt; clock is
  a hook-based component.
- Proposed: show **net rate** under fuel and money (`+1,200/h`, or `runs out in 3h` when negative), because the stock alone
  does not say whether to act. Pin the strip to the top on scroll. Group as "Economy: stars, pop, money, fuel" and
  "Actions: spy attempts, generals" with the actions highlighted when non-zero (they are a use-it-or-lose-it resource).

### Home > Status (1057 lines, 5 tabs)
Kingdom summary, income breakdown, statuses (shields, siphons), who it is revealed to, and auto spending controls.
- Problem: the Kingdom tab is a long vertical list of text boxes; the interesting question ("how am I doing relative to
  last time / to others?") is not answered; auto spending, the main way to play, is on its own tab with percent boxes that
  must add up to 100.
- Proposed: make Status a **dashboard of cards**: *Economy* (money, income/h, fuel with net rate, population),
  *Military* (offense, defense, units home vs out, generals returning in HH:MM), *Growth* (stars, settling queue, structures
  by %), *Threats* (revealed to N kingdoms, active siphons, last attack on you). Each card links to its page. Put **auto
  spending as sliders** that cap at the remainder, with a stacked bar of the split.
- Proposed: a **"since you were last here"** line at the top (news items, attacks, queues finished), using the existing news
  and history data and the time of the last login.

### Home > News (291 lines)
Tabs Kingdom / Galaxy / Empire / Universe with Time, Time Since, To, News columns.
- Problem: long text in a table; attacks on you look the same as spam; read/unread state is a counter in the sidebar only.
- Proposed: a **feed**, newest first, with a coloured icon per type (attack, spy, missile, shared intel), the first line
  bold and the detail collapsed; unread items marked until viewed; filter chips. Time as "3h ago" with the exact time on hover.

### Home > Galaxy (408 lines) **[partly built: icon buttons were done earlier (#39)]**
A table of the galaxy's kingdoms with actions in modals.
- Problem: wide table; seven actions per row (fixed by the icon buttons).
- Proposed: on a phone show each kingdom as a **card** (name, race, stars, distance, status, icon row). Sort and filter
  (e.g. only attackable, only revealed). Show **what you know** (revealed stats age) on the row, so you can see which targets
  have fresh intel.

### Home > Message (172 lines)
Latest messages and a send box.
- Proposed: conversations grouped by kingdom (a thread view) instead of a flat list, with the unread count per thread.

### Home > History (422 lines) and Scores **[Scores built]**
History: Attack / Spy / Missiles / Stats tabs with line charts.
- Proposed: charts share an x axis and can be overlaid (networth vs stars); a "compare to galaxy average" line is the one
  thing the charts lack.
- Scores **[built]**: four near-identical tables became one leaderboard component; your row and your galaxymates' rows are
  highlighted and the page says "You are ranked 12 of 98" (on a list of 100 kingdoms, finding yourself was the main job).
  Proposed next: jump-to-me button, and the gap to the kingdom above ("2,300 networth to pass Delta").

### Build > Queue (218 lines)
Funding boxes plus an accordion of five queues (settle, structures, units, engineers, missiles).
- Problem: times are `HH:MM:SS` countdowns computed once (they do not tick); the queue holds many near-identical rows (now
  folded server-side, #47).
- Proposed: a **single timeline** of everything in progress ("2h 10m: 40 homes, 12 attackers"), with a progress bar per item
  and live countdowns; funding as one stacked bar (settle / structures / military / engineers) instead of four boxes.

### Build > Settle (88 lines) **[validation built]**
- Proposed: a slider alongside the box, with the cost, time and "this uses X% of your settle capacity" as you drag.

### Build > Structures (211 lines now) **[built earlier: validation, data-driven]**
- Proposed: in the Allocate tab, show the **current vs target as a bar per structure**, so the gap the auto-spender will
  close is visible. The Build and Allocate tabs share the same first four columns; they could be one table with a toggle.

### Build > Military (684 lines, 5 tabs, 13 inputs)
Recruits / Specialists / Levy / Allocate / Disband, each with its own table.
- Problem: five tabs of the same units table with different input columns. "Levy" says "Coming soon".
- Proposed: **one units table** (cost, offense, defense, hangar, fuel, have, training, [to train]) with a mode switch
  (Train / Allocate / Disband) that changes only the last columns; remove the placeholder tab. Show **hangar capacity and
  fuel use as a bar** so the constraint you will hit is visible before you hit it.

### Build > Projects (1467 lines, 46 inputs)
The largest page. Train engineers; assign them to continuous and one-time projects; allocate for the auto-assigner.
- Problem: three tabs, 46 input boxes, two tables with different columns; hard to see which project is worth the next engineer.
- Proposed: a card per project with a **progress bar to its cap, current bonus and the marginal bonus of +100 engineers**,
  plus an "auto-assign" toggle on the page. One-time projects as a checklist with a progress bar and an "unlocks missiles /
  big flex units / spy bonus" line.

### Build > Missiles (108 lines) **[validation built earlier]**

### Conquer (1069 lines) and Conquer > Attack (714), Spy (459), Launch Missiles (270), Share Intel (263), Primitives (549), Schedule (971)
The core of the game, and the pages with the most inputs and the least guidance.
- Problem: you choose a target on one page and act on another; the Revealed/Pinned lists and the Attack page each re-show
  the target's stats in different shapes; calculation requires pressing Calculate; results go to a toast.
- Proposed: a **target-centred flow**. Picking a kingdom opens one panel with (1) what you know and how fresh it is,
  (2) a unit selector with a live **forecast** (your offense vs their defense, the loss ranges, the stars you would take) that
  updates as you type, and (3) the action buttons (attack / spy / missile / message). The Calculate button and the
  separate pages become the same panel at different depth.
- Proposed: show the **result as a report card** that stays on the page (units lost, land gained, and an "again" button) instead
  of a toast, and a one-click **"send the same again"** for repeating attacks on primitives.
- Proposed: Schedule is a form of ~15 inputs for five action types; show it as a **week calendar** of what will run, with the
  form as a side panel for the selected slot.

### Politics > Galaxy (336), Empire (1132, 4 tabs, 9 tables), Universe (393)
- Problem: Empire politics has nine tables across four tabs, many of them lists of pending offers; "Danger Zone" actions
  (declare war, denounce, leave) sit beside routine ones.
- Proposed: an **inbox** ("3 things need your decision": invitations, join requests, surrender offers) at the top; routine
  and dangerous actions separated and the dangerous ones behind a confirmation that states the consequence ("declares war on
  X for ..."). A **timeline of active wars/peace/denouncements** with expiry times in place of the status tables.
- Universe: show the vote tally for each policy as a bar with your votes marked, and the **price of the next vote**.

### Create Kingdom (505 lines)
Point-buy for starting units and structures with live stats.
- Proposed: **presets** ("Explorer", "Attacker", "Support", "Thief", the same four playstyles as the bots in `docs/bots.md`) that
  fill the point-buy, which the player can then adjust. A new player faces 14 inputs and a points budget with no hint
  of what a good start is.

### View Kingdom (538 lines)
- Problem: five tabs mirroring the Status tabs, with "Not Revealed!" when you lack intel.
- Proposed: the **same card layout as the Status dashboard**, with each card greyed and labelled with how old the intel
  is, or with the button to get it.

### Login / Sign up / Recover
- Done earlier: recovery pages, email field. Proposed: show the password rules before submit, and do not discard the form on
  a failed login (it keeps the username today; keep it on sign-up too).

## Navigation

- The sidebar shows only the current section's pages. That is tidy on a phone but hides the shape of the game on a desk; at
  wide widths show all sections expanded.
- Put the **kingdom name and galaxy** at the top of the sidebar, and a **badge on the section** whenever something needs
  action (new shared intel, an unanswered surrender offer, a finished project).
- `Forums` has a route and no link; remove the route or finish it.

## Visual design

- The app uses stock Bootstrap in dark mode; the grid of boxes with identical borders gives everything the same weight.
  A small amount of hierarchy would do more than any restyle: larger type for the three numbers that matter on a page, muted
  type for labels, colour reserved for state (red = problem, green = done, amber = needs a decision).
- One spacing scale and one table style (now in `styles/shared.css` and `GameTable`) rather than per-page font sizes.
- Icons for repeated actions (done on the galaxy page) and for resource types in the header (stars, fuel, money).

## Suggested order

1. Header rates and warnings, Scores (built) and the dashboard Status page: they are seen on every visit.
2. The target-centred conquer panel with live forecast: it removes the most clicks from the most common action.
3. The politics inbox and the unified military table: they remove the most tabs.
4. Cards on narrow screens for every wide table, once the remaining tables are on `GameTable` (it makes that one change).

## What is in this PR

- `components/header.js`: hook-based clock, red warning on empty fuel / debt with the reason as tooltip.
- `pages/home/scores.js`: one leaderboard component for the four tabs, your row and galaxymates highlighted, "You are
  ranked N of M".
- This document. Everything else above is a proposal and is not implemented.
