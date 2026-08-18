# PROGRESS — current state

**Single source of truth for "where are we right now".**
the assistant reads this at the start of every session and updates it at the end of every session that changes anything.
`Docs/PLAN.md` is the plan · `ROADMAP.md` is the gate checklist · this file is the state.

---

## Snapshot

- **Last updated:** 2026-08-18
- **Current phase:** P0 — Foundations & Contract
- **Active gate:** G0 — open, nothing started
- **Marks secured:** 0 / 100 · next 11 are in P0
- **Next action:** P0 task group 1 — repo tree, `docker-compose.yml`, `Makefile`, Pydantic `Settings`, Alembic init, `.gitignore` (done) and conventional-commit convention
- **Tracking by phase, not calendar.** Only fixed date is the 5 September submission. Gates close in order; `Docs/PLAN.md`'s day allocation is relative effort, not a schedule.

## Phase status

Legend: ☐ not started · ◐ in progress · ☑ done (gate green, evidence captured)

| Phase | Marks | Cumulative | Gate | Status |
|---|---|---|---|---|
| P0 Foundations & Contract | 11 | 11 | G0 | ◐ active |
| P1 Walking Skeleton | 10 | 21 | G1 | ☐ |
| P2 Terrain & Catchment ⭐ | 30 | 51 | G2 | ☐ |
| P3 Rainfall · Runoff · Design ⭐ | 19 | 70 | G3 | ☐ |
| P4 Suitability & AI | 7 | 77 | G4 | ☐ |
| P5 Frontend Integration | 7 | 84 | G5 | ☐ |
| P6 System Hardening ⭐ | 7 | 91 | G6 | ☐ |
| P7 Tests · Docs · Report | 8 | 99 | G7 | ☐ |

Gate checklists: `ROADMAP.md` §2. Evidence register: `ROADMAP.md` §8 (0 of 38 ticked).

## What exists today

- `Docs/Assignment.pdf` — specification and rubric
- `Docs/PLAN.md` — the 707-line marks-driven execution plan (authoritative)
- `Plan/Phase{1,2,3}.txt` — phase briefs; Phase 1 (HLD) submitted and done
- `data/samples/contours_1m.kml` — the provided sample, 6.4 MB (analysed; see `ROADMAP.md` §4)
- `the working agreement`, `ROADMAP.md`, `PROGRESS.md`, `.gitignore`
- `README.md` — **empty**, and it is a graded deliverable
- **No source code, no `docker-compose.yml`, no `Makefile`, no ADRs, no CI.**

## Sample contour map — established facts

Full table in `ROADMAP.md` §4. The four that change decisions:

1. **Elevation lives only in `<Placemark><name>`** (e.g. `277.0`). Coordinates are 2-D — there is no Z. `ExtendedData` carries `SimpleData name="ID"` (0…1354), which is numeric and **is not elevation**; an adapter that grabs the first numeric field fails silently.
2. **Root element is `<Folder>`, not `<kml><Document>`** — strict KML parsers reject the file outright.
3. **The contours are interpolated from SRTM ~30 m** (`srtm/N21E081.tif`, via Mapzen terraincache), per the file's own `sources` placemark. The 1 m interval is interpolated precision, not measured accuracy — SRTM is ±6 m relative / ±16 m absolute (LE90). Micro-relief below ~5 m is not real, and the plan's ±20 % storage claim must be defended against a 30 m source.
4. **A `land` polygon defines the AOI** — but it is a 4-corner bounding rectangle, not a cadastral parcel. Do not present it as "government land" for FR3.

Attribution owed in the report: NASA/USGS SRTM · USGS GMTED2010 · HydroSHEDS © WWF · Mapzen terrain tiles.

## Blockers

1. ~~Sample contour map missing~~ **resolved** — `data/samples/contours_1m.kml` added 18 Aug and fully analysed.
2. **Village not formally chosen.** The sample fixes an AOI — *area of interest*, the ~8.5 km² rectangle the analysis is clipped to, in Chhattisgarh around 81.297 E, 21.2517 N. P1 still needs the named village and boundary, and for FR7 validation an existing pond nearby to compare computed storage against. Confirm the sample AOI *is* the demo village, or name a different one.

## Decision log

Non-obvious choices go here **when made** — decision, reasoning, rejected alternative. Feeds the report and the viva.

| Date | Decision | Reasoning | Alternative rejected |
|---|---|---|---|
| 2026-08-18 | `Docs/PLAN.md` is the authoritative plan | It decomposes the rubric to sub-item level and allocates all 100 marks across dated phases | The earlier roadmap inferred from the PDF alone — superseded, see below |
| 2026-08-18 | ~~Avoid GDAL/rasterio~~ **superseded** | PLAN.md builds on pysheds/richdem, `gdal_contour`, rasterio, TiTiler and COGs; the raster path is required for FR2 contour generation and the tile layers | The lightweight numpy-only pipeline — insufficient for the planned layer set |
| 2026-08-18 | DEM from Copernicus/ALOS provider tiles, contours as *output* | PLAN.md P1; enables slope/aspect/curvature/TWI and satellite-matched stream calibration | Contour-interpolated DEM as the only source — kept as an *additional* adapter, see next row |
| 2026-08-18 | Add `ContourKMLAdapter` behind the same `DEMProvider` Protocol | `Plan/Phase2.txt` grades an endpoint that ingests an uploaded KML/KMZ; PLAN.md has no such path. Same Protocol means the hydrology chain is reused unchanged | A separate parallel pipeline — duplicate code, double the viva surface |
| 2026-08-18 | UTM zone derived from input centroid, enforced by `assert_crs()` | The assignment's explicit anti-hard-coding constraint; also prevents the classic degrees-treated-as-metres area bug | A fixed project CRS |
| 2026-08-18 | D8 flow routing, D-∞ left as a documented stub | Textbook, deterministic, defensible in a viva; the stub is evidence of extensibility and is cut-ladder item 6 | D-∞ as primary — harder to justify under cross-examination |
| 2026-08-18 | Parse elevation with an ordered fallback: Z → whitelisted `ExtendedData` name → placemark `<name>`; reject `ID` | The sample carries elevation only in `<name>` and has a numeric `ID` decoy; a whitelist keeps other contour maps working without hard-coding this file's quirk | Reading the first numeric `ExtendedData` field — silently wrong on this exact sample |
| 2026-08-18 | DEM grid resolution derived from mean contour spacing, floored at the source resolution | Contours are SRTM-30 m derived; interpolating to 1–2 m would manufacture detail the source does not contain | A fixed fine grid — false precision, and slow |
| 2026-08-18 | Repo trimmed to four working `.md` files + `README.md` | `evidence.md` folded into `ROADMAP.md` §8, daily template inlined into `the working agreement`; every remaining file has one job, listed in the the working agreement repository map | Keeping a separate file per concern — drift between overlapping trackers |
| 2026-08-18 | SCS-CN applied to the daily series then summed | Applying CN to annual totals overestimates runoff 2–3× | Annual-total CN — a common and visible error |

## Open questions

1. **Where is the provided sample contour map?** Blocks the Phase 2 deliverable.
2. **What is the Phase 2 submission deadline?** `Plan/Phase2.txt` says it will not be extended for mid-sems but states no date. The KML route (`ROADMAP.md` §4) is the artifact it grades — the tighter the deadline, the earlier that work moves inside P2.
3. **When are the lab hours for the prototype demo?** Posture depends on which gate is green when it lands — see the stop-and-fix table (`ROADMAP.md` §3).
4. **Which village?** See blocker 2 — and is the sample AOI the demo village, or just a test fixture?
5. **Given the source is SRTM 30 m, is the ALOS 12.5 m download (PLAN P1) still worth the day?** It genuinely improves the demo village, but the graded Phase 2 route must run off the uploaded KML regardless.
6. **Is the full P6 stack (JWT/RBAC, Grafana, Locust, Celery bulkheads, Saga, outbox audit log) within your explain-it-live budget?** The LLM policy requires justifying every library on demand. Breadth earns SysDes marks; it also multiplies viva surface. Worth an explicit call before P0 locks the compose file.
7. Minor: the marks matrix in `Docs/PLAN.md` §2.1 sums to **99**, not 100 — the System Design column totals 14 against a stated 15. One mark is unallocated.

## Session log

Newest first. One entry per working session: what changed, what is next.

### 2026-08-18 (session 4)
Reframed both trackers around **phases and gates rather than calendar days** at the user's direction — dropped date columns, replaced the weekly-checkpoint table with state-triggered stop-and-fix rules, and added a phase dependency column so the ordering constraints are explicit rather than implied by dates. `Docs/PLAN.md` keeps its day allocation untouched; it now reads as relative effort. Defined AOI in place. **Next:** P0 in full.

### 2026-08-18 (session 3)
Sample contour map added and analysed: 2712 placemarks (1355 contour `LineString`s + 1355 label `Point`s + AOI polygon + attribution), 267–298 m at 1 m interval over ~8.5 km², centroid → EPSG:32644. **Found three parser traps and one accuracy finding** — elevation only in `<name>`, a numeric `ID` decoy in `ExtendedData`, a non-standard `<Folder>` root, and SRTM-30 m provenance that caps real vertical fidelity. All recorded in `ROADMAP.md` §4. Trimmed the docs: `Docs/evidence.md` folded into `ROADMAP.md` §8 (now 38 rows), `Docs/progress/TEMPLATE.md` inlined into `the working agreement`, `Readme.md` → `README.md`, KML moved to `data/samples/`, `.gitignore` added, and a **repository map** added to `the working agreement` giving every file one stated job. **Next:** P0 in full.

### 2026-08-18 (session 2)
`Docs/PLAN.md` arrived with full content (707 lines) — it had been 0 bytes in every prior commit. Rebuilt `ROADMAP.md` as the operational distillation of it: 8 phases P0–P7, gates G0–G7 with verifiable exit criteria, weekly hard checkpoints, cut ladder, standing rules. Created `Docs/evidence.md` (34 plan artifacts + 3 added for the Phase 2 submission) and `Docs/progress/TEMPLATE.md` for the daily ritual. Superseded four of the previous session's stack decisions that conflicted with the plan. **Flagged one substantive gap:** PLAN.md derives terrain from provider DEM tiles and never ingests an uploaded KML/KMZ, but that endpoint is exactly what `Plan/Phase2.txt` is graded on — reconciliation in `ROADMAP.md` §4, roughly one day inside P2. **Next:** P0 in full — repo tree, compose, Makefile, ~25 fixture endpoints, CI, 12 ADRs.

### 2026-08-18 (session 1)
Set up initial working documents from `Docs/Assignment.pdf` and `Plan/*.txt` while `Docs/PLAN.md` was still empty. Extracted the 8 functional requirements and the rubric. Superseded by session 2.
