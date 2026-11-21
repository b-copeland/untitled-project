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
- **Tabs are underlined and left-aligned**, not stretched across the page. On a phone they scroll sideways rather than
  wrap.
- **Summaries are stat tiles** (`text-box text-box-stats`, or `Stats` inside a Panel): label above value, two or more
  per row.
- **The action under a form is on the right** (`form-actions`), with the running total (cost, what is left) as muted
  text beside it rather than a large heading.

## Rejected

- **Keep hierarchy from type alone, no borders** (0003's wording). Without any surface or edge the sections ran
  together; that was the complaint.
- **Centered narrow columns per page.** Each page picked its own width, and tabs never lined up with what was under them.
- **Cards for every table, even inside a Panel.** Cards inside cards add lines back; a table inside a Panel uses the
  Panel's card.

## Consequences

Most of the change is in `shared.css`, so a new page gets it by using `Panel`, `GameTable`, `Stats` and `form-actions`.
Some older pages are still laid out by hand inside the column (Empire > Status, the Attack page before a target is
chosen); they are aligned but not yet converted to Panels.
