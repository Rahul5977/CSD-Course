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
- **Next action:** P0 chunk 2 — the ~25 contract endpoints as fixture routes, ADRs 0005–0012, Swagger screenshot, CI badge in `README.md`
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

Gate checklists: `ROADMAP.md` §2. Evidence register: `ROADMAP.md` §8 — 3 of 38 ticked (rows 1, 2, 4), row 3 at 4/12 ADRs.

## What exists today

**Planning**
- `Docs/Assignment.pdf` — specification and rubric
- `Docs/PLAN.md` — the 707-line marks-driven execution plan (authoritative)
- `Plan/Phase{1,2,3}.txt` — phase briefs; Phase 1 (HLD) submitted and done
- `data/samples/contours_1m.kml` — the provided sample, 6.4 MB (analysed; see `ROADMAP.md` §4)
- `the working agreement`, `ROADMAP.md`, `PROGRESS.md`, `CONTRIBUTING.md`, `.gitignore`

**Code — P0 chunk 1, landed and verified 2026-08-18**
- `app/` — layered tree (`api schemas engines domain providers repositories jobs reports core`).
  Only `/health`, `/ready`, `/docs`, `/openapi.json` are live; `engines/`, `domain/` and
  `providers/` are declared but empty.
- `tests/` — 15 tests passing, including `test_layering.py`, which fails the build on a
  framework import in the pure core, an outward layer import, or a router over 25 statements
- `infra/docker-compose.yml` (postgres+postgis · redis · api) + `Dockerfile.api` (multi-stage, non-root)
- `migrations/` — revision `0001_initial`: postgis extension, `villages`, `jobs`, `audit_log`
- `pyproject.toml` + `uv.lock` (Python 3.12) · `Makefile` (15 targets) · `.env.example`
- `.github/workflows/ci.yml` — format · lint · types · tests · image build
- `Docs/adr/0001–0004` · `Docs/progress/DAY_01.md`

**Verified on a clean slate:** `make down ARGS=-v && make up` → 15 s → migration applied →
`/health` 200, `/ready` 200 (postgres reachable), `/docs` 200. `make check` → ruff clean,
mypy clean on 23 files, 15 passed.

**Still missing:** the ~25 contract endpoints and fixtures · ADRs 0005–0012 · `README.md`
(empty, and a graded deliverable) · everything from P1 onward.

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
| 2026-08-18 | `Docs/`, `Plan/`, `data/`, `the working agreement`, `PROGRESS.md` stay **tracked** in Git | An uncommitted `.gitignore` change would have excluded them. The already-tracked files would have survived, but every *new* `Docs/adr/*.md`, `Docs/progress/DAY_NN.md` and `Docs/figures/*` would be dropped silently — that is the graded evidence trail (Docs 10, evidence register §8) in the repo the report links | Keeping the planning docs private — the marks live in showing them |
| 2026-08-18 | Layering enforced by an executable test (`tests/test_layering.py`), not by convention | The 3 layering marks need evidence an evaluator can see; a rule nobody checks decays. AST parse: no framework import in `domain`/`engines`, no outward layer import, no handler over 25 statements | A written-down convention — drifts the first time someone is in a hurry. ADR 0001 |
| 2026-08-18 | Python **3.12**, not the 3.14 on the dev machine | numba/pysheds/rasterio wheels lag CPython by 1–2 releases; discovering that mid-P2 costs a day at the worst moment. uv + committed `uv.lock` so a fresh clone on another machine resolves identically (G7) | Newest CPython (guaranteed wheel problem later) · pip + requirements.txt (pins direct deps, lets transitive ones drift) · conda (defensible, but ~3× image size for no gain). ADR 0002 |
| 2026-08-18 | **Synchronous** SQLAlchemy 2.0 on psycopg3 | The expensive work is raster processing in a Celery worker, not database I/O. Async buys nothing measurable and adds a bug class — one blocking call stalls the event loop, presenting as "sometimes slow" rather than as an error. Also a much smaller viva surface | Async SQLAlchemy + asyncpg — the reflexive choice, wrong for this workload. ADR 0003 |
| 2026-08-18 | Compose starts at **3 services**, not PLAN.md's 9; each later service arrives in the phase that first calls it | Every library must be defensible live. Seven declared-but-uncalled services read as copied scaffolding and are seven things to defend for zero exercised behaviour. The phase→service table is the record, and goes in the report | Declaring the full topology on day one. ADR 0004 |
| 2026-08-18 | `audit_log` append-only **in the database** (`DO INSTEAD NOTHING` rules), not by convention | A trail the application can rewrite is not evidence, and G6 grades the audit log. Verified: UPDATE and DELETE affect 0 rows, original row survives | Application-level discipline · role grants (bypassed whenever the app connects as owner) |
| 2026-08-18 | Alembic autogenerate ignores any *reflected* table this metadata does not declare | The `postgis/postgis` image installs the tiger geocoder and topology and puts `tiger` on the search_path; without the filter every revision opens with ~40 `drop_table` calls against extension-owned tables | Naming the tables to exclude — a list that goes stale the moment an extension is added |
| 2026-08-18 | SCS-CN applied to the daily series then summed | Applying CN to annual totals overestimates runoff 2–3× | Annual-total CN — a common and visible error |

## Open questions

1. ~~Where is the provided sample contour map?~~ **resolved** — `data/samples/contours_1m.kml`, analysed in `ROADMAP.md` §4.
2. ~~What is the Phase 2 submission deadline?~~ **resolved 2026-08-18** — the Phase 2 window has passed and it is not scored as a separate submission. Consequence: it no longer drives sequencing, so P0 → P1 → P2 runs in `Docs/PLAN.md` order. **The KML route stays in scope** — G2 still requires it (`ROADMAP.md` §4), Phase 3 is end-to-end over arbitrary contour maps, and the final report must carry a working API route URL.
3. **When are the lab hours for the prototype demo?** Posture depends on which gate is green when it lands — see the stop-and-fix table (`ROADMAP.md` §3).
4. **Which village?** See blocker 2 — and is the sample AOI the demo village, or just a test fixture?
5. **Given the source is SRTM 30 m, is the ALOS 12.5 m download (PLAN P1) still worth the day?** It genuinely improves the demo village, but the graded Phase 2 route must run off the uploaded KML regardless.
6. **Is the full P6 stack (JWT/RBAC, Grafana, Locust, Celery bulkheads, Saga, outbox audit log) within your explain-it-live budget?** The LLM policy requires justifying every library on demand. Breadth earns SysDes marks; it also multiplies viva surface. Worth an explicit call before P0 locks the compose file.
7. Minor: the marks matrix in `Docs/PLAN.md` §2.1 sums to **99**, not 100 — the System Design column totals 14 against a stated 15. One mark is unallocated.

## Session log

Newest first. One entry per working session: what changed, what is next.

### 2026-08-18 (session 6)
**P0 chunk 1 built and verified.** Layered `app/` tree · uv/ruff/mypy-strict/pytest · `Makefile` · 3-service compose + multi-stage non-root `Dockerfile.api` · Alembic revision 0001 (postgis, `villages`, `jobs`, `audit_log`) · GitHub Actions CI · `CONTRIBUTING.md` · ADRs 0001–0004 · `Docs/progress/DAY_01.md`. Clean-slate `make up` brings the stack up in 15 s and applies the migration; `make check` is green (ruff, mypy on 23 files, 15 tests). Four defects found by running it rather than reading it — image build missing `README.md`, ruff isort misconfiguration, autogenerate trying to drop 40 PostGIS extension tables, and ORM/migration drift on the `jobs` CHECK constraints; all fixed, and autogenerate now produces an empty diff. Six decisions logged above. **Next:** P0 chunk 2 — the ~25 contract endpoints as fixture routes (the parallelism unlock), ADRs 0005–0012, Swagger screenshot.

### 2026-08-18 (session 5)
Status review, no code written. Confirmed toolchain on the dev machine: Python 3.14.6 · Docker 29.1.3 · Compose v5.0.1 · uv 0.9.5 · remote `github.com/Rahul5977/AI-BasedPondAnalysis`. **Caught and reverted an uncommitted `.gitignore` change** that would have excluded `Docs/`, `Plan/`, `data/`, `the working agreement` and `PROGRESS.md` — see the decision log. **Closed open questions 1 and 2:** the Phase 2 window has passed and is not separately scored, so sequencing follows `Docs/PLAN.md` P0 → P1 → P2 unmodified; the KML route remains a G2 exit criterion. **Next:** P0 chunk 1 — repo tree, `pyproject`, ruff/mypy/pytest config, `Makefile`, `Settings`, CI.

### 2026-08-18 (session 4)
Reframed both trackers around **phases and gates rather than calendar days** at the user's direction — dropped date columns, replaced the weekly-checkpoint table with state-triggered stop-and-fix rules, and added a phase dependency column so the ordering constraints are explicit rather than implied by dates. `Docs/PLAN.md` keeps its day allocation untouched; it now reads as relative effort. Defined AOI in place. **Next:** P0 in full.

### 2026-08-18 (session 3)
Sample contour map added and analysed: 2712 placemarks (1355 contour `LineString`s + 1355 label `Point`s + AOI polygon + attribution), 267–298 m at 1 m interval over ~8.5 km², centroid → EPSG:32644. **Found three parser traps and one accuracy finding** — elevation only in `<name>`, a numeric `ID` decoy in `ExtendedData`, a non-standard `<Folder>` root, and SRTM-30 m provenance that caps real vertical fidelity. All recorded in `ROADMAP.md` §4. Trimmed the docs: `Docs/evidence.md` folded into `ROADMAP.md` §8 (now 38 rows), `Docs/progress/TEMPLATE.md` inlined into `the working agreement`, `Readme.md` → `README.md`, KML moved to `data/samples/`, `.gitignore` added, and a **repository map** added to `the working agreement` giving every file one stated job. **Next:** P0 in full.

### 2026-08-18 (session 2)
`Docs/PLAN.md` arrived with full content (707 lines) — it had been 0 bytes in every prior commit. Rebuilt `ROADMAP.md` as the operational distillation of it: 8 phases P0–P7, gates G0–G7 with verifiable exit criteria, weekly hard checkpoints, cut ladder, standing rules. Created `Docs/evidence.md` (34 plan artifacts + 3 added for the Phase 2 submission) and `Docs/progress/TEMPLATE.md` for the daily ritual. Superseded four of the previous session's stack decisions that conflicted with the plan. **Flagged one substantive gap:** PLAN.md derives terrain from provider DEM tiles and never ingests an uploaded KML/KMZ, but that endpoint is exactly what `Plan/Phase2.txt` is graded on — reconciliation in `ROADMAP.md` §4, roughly one day inside P2. **Next:** P0 in full — repo tree, compose, Makefile, ~25 fixture endpoints, CI, 12 ADRs.

### 2026-08-18 (session 1)
Set up initial working documents from `Docs/Assignment.pdf` and `Plan/*.txt` while `Docs/PLAN.md` was still empty. Extracted the 8 functional requirements and the rubric. Superseded by session 2.
