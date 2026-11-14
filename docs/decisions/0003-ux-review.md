# 0003: Outcomes of the UX review

Date: 2026-11-13 (PR #116, three review rounds). Status: accepted. The principles that came out of it are in
[ux.md](../ux.md); this records the maintainer's specific choices so they are not re-proposed.

## Context

A page-by-page review found that pages each started from zero, forms said "no" only after sending, numbers had no
context (a stock with no rate), most tables were hand-written and drifted apart, phone width was an afterthought, and
estimated numbers looked the same as known ones.

## Decisions

| Topic | Chosen | Not chosen |
|---|---|---|
| Header strip | Stays the same size. Fuel and money get a tooltip with the net rate per hour and when fuel runs out; fuel turns red at 0, money flags debt. | Adding rates or more boxes to the strip ("be careful not to overbloat the header") |
| Status page | Opens on an Overview of four cards (Economy, Military, Growth, Threats) with per-hour rates; each card links to where you act. Other tabs unchanged. | Replacing the tabs |
| Galaxy page | A Table / Cards switch, remembered per browser, so the whole galaxy can still be seen at a glance | Cards only |
| News | Keep sortable, filterable tables. News items carry a `kind` (attack, spy, missiles, intel) shown as a Type column. | A single feed with "Show more" (built, then reverted) |
| Build pages | `AmountInput` is a slider only: the chosen number on its left, the most you can choose on its right (press it to fill in). The auto builder does most building, so speed matters more than precision. | Number box and Max button on every row |
| Planner pages (Attack, Spy, Primitives, Schedule, Launch Missiles) | Keep the number box and Max (`<AmountInput box>`), because the exact number matters | |
| Planner page text | No explanatory subtitles under section titles; tags, labels and the forecast should explain themselves. Text only to report something (an alert, a warning). | |
| Confirmations | Attack sends straight away when the target's army is revealed and the forecast wins; it asks first when the army is not revealed, there is no forecast, or the forecast loses. Spy asks only when the chance is known and below 40%. | Confirming every send |
| Scores | "You are ranked 12 of 98." | Also showing the gap to the next kingdom |
| Military page | One units table with a Train / Allocate / Disband switch, a hangar-space bar, and the Levy placeholder removed | Five tabs |
| Missile forecast | `/api/calculatemissiles` returns structured `damage` and `shields_assumed`, shown as stats | A sentence only |
| Order of work | Status dashboard and unified military before politics | |
| Create Kingdom | Needed a bigger rework (state updates lagged); since rebuilt as a three-step wizard with quick starts (PR #123) | |

## Proposed, not built

Kept here so a later change can pick them up: a "since you were last here" line; a queue timeline with live countdowns
and funding as one stacked bar; current vs target bars on Structures > Allocate; project cards with progress to the cap
and the marginal bonus of more engineers; a politics inbox ("3 things need your decision") with dangerous actions behind
a confirmation that states the consequence; a timeline of wars, peace and denouncements; universe vote tallies as bars
with the price of the next vote; View Kingdom as greyed cards labelled with the age of the intel; attack result report
cards instead of toasts; unread counts per conversation; a jump-to-me button on Scores; cards for every wide table on a
phone. None of the review's UI was checked in a browser at the time.
