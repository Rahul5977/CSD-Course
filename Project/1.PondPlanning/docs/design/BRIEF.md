# Design brief — landing page and workspace (P8)

**Product:** AI-based Village Pond Planning System. A planner uploads a contour map of a village
and gets terrain, streams, ranked pond sites, the catchment of any point, 45 years of rainfall,
runoff by three methods, a costed pond design with fill reliability, eligible land, and a
recommendation workflow. Every number carries its unit and an uncertainty band.

**Audience:** block/district engineers and Gram Panchayat staff on laptops and mid-range Android
phones, often outdoors; evaluators at a live demo on a projector.

## Direction (unchanged from PLAN.md P5, now enforced by tokens)
Government utility tool, not a consumer app. Dense information, high contrast for sunlight,
earth/water palette with one accent for the primary action, Devanagari-capable type (Noto Sans /
Mukta), the map takes ≥ 65 % of the workspace viewport. Nothing decorative that does not carry
information. Numbers are the hero: **big value, small unit, uncertainty always beside it**.

## Tokens (`web/design/tokens.css` → `web/src/tokens.css`)
- Colour roles: `--paper` (bg), `--panel`, `--ink`, `--muted`, `--line`, `--water` (accent),
  `--earth`, `--ok`, `--warn`, `--error`, `--info`; each with an `-soft` tint for backgrounds.
- Type scale: 12 / 13 / 15 / 17 / 22 / 32 / 44 px; numerals tabular; headings 600.
- Spacing: 4-pt grid (`--s-1` … `--s-8`); radius 4 / 8; one shadow for floating cards only.
- Focus ring: 2 px `--water` offset 2 px — visible on every interactive element.

## Components
Button (primary / secondary / ghost / danger; sm / md), Panel (title, meta, body, footer),
Quantity (value · unit · ±band · method tooltip), Job progress (stage label · % · bar ·
cancel), Status badge (ok / warn / error / info / offline / stale / fixture), Data table
(dense, striped), Layer toggle row, Site row (rank · score bars · upstream area), Warning
callout (info / warning / critical), Empty state (icon · one line · one action), Skeleton.

## Named states — every panel must design all six
loading (skeleton) · empty (what to do next) · error (code + retry) · stale (served from
cache, timestamp) · offline (badge; read-only) · job-in-progress (stage + percentage + cancel).

## Real data to design against
`docs/api/samples/village_summary.json`, `siting.json`, `catchment_result.json`,
`rainfall_statistics.json`, `pond_design_result.json`, `available_land.json`, `recommendation.json`.

## Screens
1. **Landing `/`** — nav · hero (claim + sample screenshot with a floating quantity card) ·
   numbers strip · how it works (4 steps) · what you get (the 8 FRs as 6 cards) · methodology
   strip (named algorithms — "nothing is a black box") · validation table · honest limits
   callout · CTA · footer (repo, report, API docs, licences). Must be truthful: no feature
   named that the app does not have.
2. **Workspace `/app`** — top bar (brand, village selector, offline/stale badge, language,
   sign-in) · left rail of collapsible panels (Upload · Area · Layers · Sites · Catchment ·
   Rainfall · Design · Land · Recommendation) · map ≥ 65 % · results overlay bottom-right ·
   job progress pinned to the panel that started it.
3. **Phone 390 px** — map on top (45 vh), panels as a scrollable sheet below, sticky CTA.

## Out of scope
Marketing copy beyond the truth of the system; illustrations; dark mode (outdoor contrast first).
