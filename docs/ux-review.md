# UX / UI review

A page-by-page look at how information is shown, with concrete proposals. **This is for review, not for merging blindly:**
the proposals are opinions about a game I have only read the code of, and I could not look at the running app or try it
on a phone. Where a proposal is built in the accompanying PR it is marked **[built]**; everything else is a suggestion.
The first version of this document was written before most of the work below; it has been updated to say what has since been
built (and reviewed against your feedback) and what is still only a proposal.

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
5. **Forms say "no" late.** **[mostly built]** Settle, Structures, Missiles, Military, Projects, Attack, Spy, Primitives,
   Share Intel and Schedule now say what is wrong (or disable the button with the reason) before sending. Launch Missiles and
   the politics forms still send first and report in a toast.
6. **Results are toasts in the corner and disappear.** Fine for "built", poor for an attack report, which is the most
   important thing the game ever tells you. They are kept in News/History, but nothing says so. A failed request used to
   show nothing at all; it now shows a message **[built]**. Attack and Spy now ask "are you sure?" with the forecast
   before they send **[built]**, but the result is still a toast.
7. **Loading is the text "Loading..."** in many places, so the page jumps when data arrives.
8. **The table code is the UI.** Most pages are hand-written tables, so every change is a copy-paste, which is why they
   drift from each other (alignment, fonts, which numbers are formatted). The shared components (`GameTable`, `NumberField`,
   `ResultToasts`, and now `AmountInput` and the planner kit in `components/planner.js`) are the way out; they are used on
   the Scores, Build and Conquer pages **[built]**.
9. **Phone width is an afterthought.** **[partly built]** Wide tables now scroll sideways inside a wrapper instead of pushing
   the page wider (`table-scroll`), modals can no longer be wider than the screen, and the planner pages stack on a narrow
   screen. Wide tables (Galaxy, Military, Projects, Empire Politics) would still be better as cards.
10. **Information that is not known looked the same as information that is.** **[built on Attack and Spy]** Every number about
    the target now carries a tag saying where it comes from: *Revealed* (exact), *Estimate needed* (not revealed, and it
    matters), *Your estimate* (you changed it) or *Optional* (only sharpens the forecast).
11. **Projections must come from the game, not be re-derived in the browser.** **[built]** Offense, defense, success chance,
    losses and "what is left at home" all come from the API; the browser holds only what was typed and asks again after a
    pause (see "Forecasts" below).

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

### Home > Galaxy (408 lines) **[partly built]**
A table of the galaxy's kingdoms with actions in modals.
- Built: the seven text buttons per row are a row of link-coloured icons with tooltips (#39), centred and without a button box;
  the table scrolls sideways on a phone; the action modals can no longer be wider than the screen, and the Attack modal is
  wider on large screens.
- Problem: still a wide table.
- Proposed: on a phone show each kingdom as a **card** (name, race, stars, distance, status, icon row). Sort and filter
  (e.g. only attackable, only revealed). Show **what you know** (revealed stats age) on the row, so you can see which targets
  have fresh intel.

### Home > Message **[built]**
Was a flat list of messages with a select box.
- Built: a chat. Conversations on the left, newest first, with a preview and time; the open conversation as bubbles (yours on
  the right) with a compose box (Enter sends, Shift+Enter for a new line); a New button to write to someone; on a phone one
  pane at a time with a back arrow.
- Proposed next: an unread count per conversation (the sidebar badge is still the only indicator).

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

### Build > Settle **[built]**
- Built: validation, plus the shared amount input (box, slider and a **Max** button that fills in the most you can afford and
  have room for).

### Build > Structures (211 lines now) **[built: validation, data-driven, sliders]**
- Built: the "to build", "new allocation" and "to raze" boxes are amount inputs with sliders and Max; the allocation boxes no
  longer spill out of their table cells.
- Proposed: in the Allocate tab, show the **current vs target as a bar per structure**, so the gap the auto-spender will
  close is visible. The Build and Allocate tabs share the same first four columns; they could be one table with a toggle.

### Build > Military (684 lines, 5 tabs, 13 inputs)
Recruits / Specialists / Levy / Allocate / Disband, each with its own table.
- Problem: five tabs of the same units table with different input columns. "Levy" says "Coming soon".
- Built: every input here (recruits, train, allocate, disband) is an amount input with a slider and Max.
- Proposed: **one units table** (cost, offense, defense, hangar, fuel, have, training, [to train]) with a mode switch
  (Train / Allocate / Disband) that changes only the last columns; remove the placeholder tab. Show **hangar capacity and
  fuel use as a bar** so the constraint you will hit is visible before you hit it.

### Build > Projects (1467 lines, 46 inputs)
The largest page. Train engineers; assign them to continuous and one-time projects; allocate for the auto-assigner.
- Problem: three tabs, 46 input boxes, two tables with different columns; hard to see which project is worth the next engineer.
- Built: the engineer, assign, add and allocate inputs are amount inputs with sliders (capped by the free engineers or 100%).
- Proposed: a card per project with a **progress bar to its cap, current bonus and the marginal bonus of +100 engineers**,
  plus an "auto-assign" toggle on the page. One-time projects as a checklist with a progress bar and an "unlocks missiles /
  big flex units / spy bonus" line.

### Build > Missiles (108 lines) **[built: validation, sliders]**
Sliders are capped by silo room, money and fuel together.

### Build pages: the amount input **[built]**
Used on Settle, Structures, Military, Projects and Missiles. A number box, a slider and a Max button, designed so that
several boxes can draw on one pool (money, recruits, 100%) without the sliders jumping about:
- each slider's **length is the most that box could take if nothing else were ordered**, so it never changes length as you
  fill in the others;
- it has **three tones**: dark blue up to what you have chosen, light blue up to what is still free, grey for what the other
  boxes have used up; the thumb stops at the grey line and Max fills in up to it;
- the reason a request would fail shows under the box in red, and the button's tooltip says why it is disabled.
Not checked in a browser: how the track draws in Firefox (it needs separate selectors from Chrome).
Proposed: a "reset" per row, and showing the cost next to each slider as it moves.


### Conquer home (1069 lines) **[icons built]**
The Revealed / Shared / Pinned lists. The text action buttons are now the same icon row as the Galaxy page.
- Proposed: the lists and the Attack page each re-show the target's stats in different shapes; one target-centred panel
  would remove that (see below).

### Conquer > Attack **[rebuilt]**
Principle for these planner pages: no explanatory subtitles under the section titles. The tags, labels and the forecast should be self-evident; text is kept only where it reports something (an alert, a warning).
Was two tables of text boxes, three buttons in a row (Autofill, Calculate, Attack) and a text blob for the result.
Now five steps on one page, in a column on a phone and two columns on a wide screen or a wide modal:
1. **Choose a target.** Picking one loads, from the API (`/api/attackcontext`), what is revealed about them, a starting
   estimate for what is not, and how well defended you are.
2. **The matchup** (a strip of five numbers): their defense, your offense, your defense now, your defense after this attack,
   and your defense if you sent everything.
3. **Their defense.** Units, military efficiency and shields, each tagged *Revealed*, *Estimate needed*, *Your estimate*.
   The starting estimate is an army as big as yours with the **highest possible bonus and shields** (so a guess errs on the
   side of caution). The "all exact" note appears only when units, efficiency and shields are all revealed.
4. **Your attack.** A suggested attack is filled in for you when you pick the target ("Suggest again" does it again). It
   fills in the form and sends **nothing**. Units are sliders with Max.
5. **Forecast** and **Send**. The verdict, offense against defense on a bar, margin, losses for both sides and spoils, all
   from the API. Sending always shows a confirmation with the forecast and what your home defense falls to.
- Note on "Autofill launches an attack": the old Autofill route does not send anything (checked in the code); the label and the
  separation from Send are what changed.
- Proposed: a **report card** that stays on the page after an attack instead of a toast, and "send the same again".

### Conquer > Spy **[rebuilt]**
Target and operation, your drones (slider, shield switch, share and cut for operations that reveal), what you know about
them, forecast, send with confirmation.
- Their drones, stars and spy shields are tagged and are all **Optional**: nothing is needed to send spies, they only improve
  the success estimate. If none of it is known or entered, the page says the chance is not meaningful yet rather than
  showing a misleading 100%.
- The success chance and drone losses come from the API.

### Conquer > Primitives **[rebuilt]**
Attack and Rob tabs with the same layout as Attack and Spy, a live forecast, a confirmation, and the automatic-action
settings in their own panel with an on/off switch. The old "expected haul" on Rob was a multiplication in the browser; it
is gone and only the money-per-drone rate is shown.

### Conquer > Share Intel **[rebuilt]**
Three steps (what, who and your cut, check) and a plain-language sentence of exactly what you are offering and what you get
if they accept. The cut is validated.

### Conquer > Schedule **[rebuilt]**
Pick what to schedule from five cards (not a dropdown), choose the time with quick buttons and a check that it is in the
future (this also fixes a time-zone bug in the old default), the details for that kind of action with limits that mirror
the server's, and a summary before you schedule. The queue is a list of cards with Cancel.
- Proposed: a week calendar of what will run.

### Conquer > Launch Missiles
Not reworked. Same pattern as Attack would apply (target, missiles with sliders, forecast, confirm).

### Forecasts: how they are fetched **[built]**
All projections on Attack, Spy and Primitives come from the API. To keep the number of requests small:
- whatever can be known when a target is chosen is **loaded once up front** (what is revealed, the starting estimates, your
  own defense, a suggested attack);
- after that only the forecast is re-asked, **700 ms after the last change** (dragging a slider is one request, not
  hundreds), never twice for the same plan, and an answer that has been overtaken by a newer question is dropped;
- the "(updating...)" note is derived from "waiting out the pause or waiting for an answer", so it cannot stay on.

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

## Navigation **[built]**

- The sidebar is a plain scrollable list: a small non-clickable label for each section and every page as a link at one
  indent, with the current page highlighted. (The first version expanded the current section only, which hid the shape of
  the game; the double-click-to-close and the sticky-positioning CSS are gone.)
- On a phone a top bar with a menu button opens it as a drawer, which closes on any navigation (including to the page you
  are already on). From the `lg` breakpoint up it is a fixed column.
- Section labels carry the count of anything new (messages, news, shared intel); pages carry their own.
- Still proposed: the kingdom name and galaxy at the top of the sidebar, and a badge for things that need a decision
  (an unanswered surrender offer, a finished project). `Forums` has a route and no link; remove it or finish it.

## Help **[built]**

- The help button is a round floating button at the bottom-right ("Help" with an icon, icon only on a phone).
- The help itself shows one topic at a time: a grouped topic list beside it on a wide screen, a drop-down on a narrow one,
  and Previous / Next at the bottom. It opens on the topic for the page you pressed it on. It used to be one long page.

## Landing and sign-in **[built]**

- Landing: a hero with sign-up / sign-in buttons (or "Go to your kingdom" when signed in), a card for each playstyle, and the
  round's start and end.
- Login: a centred card with labelled fields, a disabled button until both are filled, an error alert, and links to
  recover an account and to sign up.

## Visual design

- The app uses stock Bootstrap in dark mode; the grid of boxes with identical borders gives everything the same weight.
  A small amount of hierarchy would do more than any restyle: larger type for the three numbers that matter on a page, muted
  type for labels, colour reserved for state (red = problem, green = done, amber = needs a decision).
- One spacing scale and one table style (now in `styles/shared.css` and `GameTable`) rather than per-page font sizes.
- Icons for repeated actions (done on the galaxy and conquer pages, as link-coloured icons rather than buttons) and for
  resource types in the header (stars, fuel, money; not done).
- Tags for where a number comes from (revealed / estimate / optional) are the first use of colour for meaning beyond
  red / green; amber is "this is a guess that matters".

## Suggested order

What is left, in the order I would do it (the target-centred conquer flow, the build inputs, the nav, help, landing and
messages from the first version of this list are built):
1. Header rates and the dashboard Status page: they are seen on every visit.
2. Launch Missiles on the same planner pattern as Attack; result report cards instead of toasts.
3. The politics inbox and the unified military table: they remove the most tabs.
4. Cards on narrow screens for every wide table, once the remaining tables are on `GameTable` (it makes that one change).

## What is in this PR

Built (see the sections above for the detail):
- Navigation: scrollable grouped list, top bar and drawer on phones, fixed column on desktop.
- Shared components: `AmountInput` (slider with three tones and Max), the planner kit (`Panel`, `FieldRow`, status tags,
  `Stats`, `VersusBar`, `Picker`, `useServerForecast`), `IconButton` as link-coloured icons.
- Pages rebuilt: Attack, Spy, Primitives, Share Intel, Schedule, Message (chat), Landing, Login, Help (paged), plus the
  help button.
- Pages changed: Settle, Structures, Military, Projects, Missiles (amount inputs, scrolling tables), Galaxy (icons, scrolling
  table, modal widths), Conquer home (icons), Scores and the header (from the first version).
- API additions to avoid duplicating logic in the browser: `GET /api/attackcontext/<target>`; `attacker_home_defense_before`
  and `_after` on the attack forecast and the suggested attack; `success_chance` and `drone_losses` on the spy forecast.
  Also fixed: a blank "cut" on a spy operation crashed the route.
- This document.

Not built: the Status dashboard, News feed, Queue timeline, Launch Missiles rework, politics inbox, Create Kingdom presets,
View Kingdom cards, result report cards. None of the UI has been seen in a browser by me.
