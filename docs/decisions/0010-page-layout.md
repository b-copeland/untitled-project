# 0010: Page layout: one content column, sections as cards, borderless tables

Date: 2026-11-21. Status: accepted. Refines the visual language of [0003](0003-ux-review.md).

## Context

A visual review of every page, at desktop and phone width, found the full-screen pages looking unfinished. Tabs stretched
across the whole page while the tables under them sat in a narrow centered column (half the width, or pinned to the
left with the button centered under them). Every table had a full grid of lines. Summary boxes had 2 px borders, some
black. The page, the boxes and the tables were all the same colour, so nothing marked where one section ended and the
next began. Each page had grown its own widths and centering, so no two lined up.

## Decision

- **One content column.** Every page shares the header strip's left and right edges (`.router-body`, at most 1200 px).
  Pages do not set their own max-width and center it.
- **Sections are cards.** The page is a step darker than the cards on it (`--surface` in `shared.css`), and a card has
  a faint edge (`--border-subtle`). A titled section is a `Panel`; several side by side are a `panel-grid`.
- **Tables are borderless rows inside a card.** No vertical lines and no stripes: a muted uppercase header, a faint
  line between rows, a tint on hover. A `GameTable` on its own is its own card (`table-scroll`); inside a Panel it is
  just the rows.
- **Tabs are left-aligned**, not stretched across the page. On a phone they scroll sideways rather than wrap.
- **Summaries are stat tiles** (`text-box text-box-stats`, or `Stats` inside a Panel): label above value, two or more
  per row.
- **The action under a form is on the right** (`form-actions`), with the running total (cost, what is left) as muted
  text beside it rather than a large heading. A long form repeats it after each table (Projects).
- **The frame is App.js's.** Every game page gets the header strip, its section name and title, and a link back to the
  page that sent the player there. Pages do not render their own header or title.
- **Pages, not dialogs.** Kingdom Info became the Kingdom page (`/kingdom/:id`), and Attack, Spy and Launch Missiles
  open as their own pages with the target chosen (`?target=`). Every kingdom name links to its page. Dialogs stay for
  short confirmations (send this attack?) and small forms (share your kingdom). A full planner in a dialog hid the
  page it came from, could not be linked to or reloaded, and was cramped on a phone.
- **Tabs are a segmented control**, a filled button for the chosen tab, because underlined tabs did not look
  clickable. A tab that destroys something is orange.
- **Your own amounts are sliders only** on the planners; the number box stays for the target's figures, which have no
  known maximum. This replaces 0003's "keep the number box and Max on planner pages".

## Rejected

- **Keep hierarchy from type alone, no borders** (0003's wording). Without any surface or edge the sections ran
  together; that was the complaint.
- **Centered narrow columns per page.** Each page picked its own width, and tabs never lined up with what was under them.
- **Planners in dialogs** (as before): see above.
- **Cards for every table, even inside a Panel.** Cards inside cards add lines back; a table inside a Panel uses the
  Panel's card.

## Consequences

Most of the change is in `shared.css`, so a new page gets it by using `Panel`, `GameTable`, `Stats` and `form-actions`.
A few older pages are still laid out by hand inside the column (Empire > Join, Galaxy > Policies); they are aligned and
carded but not yet converted to Panels. Colours are still the dark theme only; a theme setting is to follow.
