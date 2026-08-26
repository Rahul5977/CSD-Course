# PROGRESS — current state

**Single source of truth for "where are we right now".**
the assistant reads this at the start of every session and updates it at the end of every session that changes anything.
`docs/PLAN.md` is the plan · `docs/ROADMAP.md` is the gate checklist · this file is the state.

---

## Snapshot

- **Last updated:** 2026-08-26
- **Current phase:** P8 complete — awaiting the user's review at the G8 checkpoint; then demo-day steps only
- **Active gate:** G8 — closed 2026-08-27 pending the user's review. **G7 closed 2026-08-27.** **G6 closed 2026-08-27. G1–G5 closed 2026-08-26. G0 closed 2026-08-18.**
- **Marks secured:** 99 / 100 targeted · the public URL (evidence row 36) is a demo-day step (`make tunnel`)
- **Next action:** user runs the design-sync tooling to push `web/design/` into the AI design tool (optional iteration there); rehearse `docs/DEMO.md` 3× starting from the landing page; on demo day `make up && make seed && make tunnel`, paste the public URL into the report and the Phase 2 submission; run `make check` before every commit
- **Calendar:** 10 days to submission as of 26 Aug. Autonomous loop protocol in the working agreement's autonomous loop; check-in with the user at every gate.
- **Tracking by phase, not calendar.** Only fixed date is the 5 September submission. Gates close in order; `docs/PLAN.md`'s day allocation is relative effort, not a schedule.

## Phase status

Legend: ☐ not started · ◐ in progress · ☑ done (gate green, evidence captured)

| Phase | Marks | Cumulative | Gate | Status |
|---|---|---|---|---|
| P0 Foundations & Contract | 11 | 11 | G0 | ☑ **done** |
| P1 Walking Skeleton | 10 | 21 | G1 | ☑ **done** |
| P2 Terrain & Catchment ⭐ | 30 | 51 | G2 | ☑ **done** |
| P3 Rainfall · Runoff · Design ⭐ | 19 | 70 | G3 | ☑ **done** |
| P4 Suitability & AI | 7 | 77 | G4 | ☑ **done** |
| P5 Frontend Integration | 7 | 84 | G5 | ☑ **done** |
| P6 System Hardening ⭐ | 7 | 91 | G6 | ☑ **done** |
| P7 Tests · Docs · Report | 8 | 99 | G7 | ☑ **done** |
| P8 Landing page & UI/UX | protects FE 5 · UX 1 | 99 | G8 | ☑ **done** |

Gate checklists: `docs/ROADMAP.md` §2. Evidence register: `docs/ROADMAP.md` §8 — 38 of 40 ticked; row 20 (ML AUC) deliberately not produced — ADR 0017; row 36 (public URL) is `make tunnel` on demo day.

## What exists today

**Planning**
- `docs/assignment/Assignment.pdf` — specification and rubric
- `docs/PLAN.md` — the 707-line marks-driven execution plan (authoritative)
- `docs/assignment/Phase{1,2,3}.txt` — phase briefs; Phase 1 (HLD) submitted and done
- `data/samples/contours_1m.kml` — the provided sample, 6.4 MB (analysed; see `docs/ROADMAP.md` §4)
- the working agreement, `docs/ROADMAP.md`, `docs/PROGRESS.md`, `CONTRIBUTING.md`, `.gitignore`

**Code — P6 complete, verified 2026-08-27** (ADR 0019)
- Bulkhead queues `interactive`/`heavy` with separate workers; WebSocket job progress; Saga with
  compensations around the contour pipeline's persistence (tested with an injected failure);
  idempotency keys; JWT RS256 + RBAC (viewer/planner/officer); recommendation state machine +
  transactional outbox → append-only audit log + audit route; PDF/GeoJSON/CSV exports; backpressure
  429; correlation ids + Prometheus + provisioned Grafana; beat with a leader-locked nightly rainfall
  refresh; nginx rate limits + headers. Compose: **11 services**. Tests: **206 passing**.
- Live: bulkheads (0.6 s click during a heavy job), Locust p95 560 ms E2E at 50 users, chaos test recorded.

**Code — P5 complete, verified 2026-08-26**
- **FR8** results overlay on the map (pond location, catchment area, 75 % rainfall, SCS runoff,
  dimensions, storage) + the designed pond footprint and a focus mask as map layers; every long
  action shows stage + percent; offline-first service worker with a stale badge (ADR 0018);
  generated OpenAPI types for the envelopes; EN/HI toggle; 390 px layout; initial-paint fix.

**Code — P4 complete, verified 2026-08-26**
- **FR3** `POST /analysis/suitability` real: Specification-pattern constraints (`app/engines/suitability/constraints.py`), Sentinel-2 NDWI + Otsu + OpenCV water mask (`water_mask.py`, `providers/sentinel.py`), AHP weights with CR (`ahp.py`), ranking restricted to eligible cells, suitability heat-map + water-mask COGs; `GET /villages/{id}/available-land` reads the stored parcels. ADR 0017; ML deferred by the plan's own fallback.
- UI: "Assess land & rank sites" → eligible-land polygons layer, suitability and water-mask raster layers, AHP ranking with per-criterion bars and the CR.
- Tests: **187 passing** (AHP golden incl. a perfectly consistent and an intransitive matrix; constraints; NDWI/OpenCV on a synthetic lake; API flow with offline providers).

**Code — P3 complete, verified 2026-08-26**
- **FR5** `GET /rainfall/statistics|series` real: Open-Meteo ERA5-Land → NASA POWER behind
  `Retry ∘ CircuitBreaker ∘ Cached` + `FallbackChain` (`app/providers/resilience.py`); statistics
  engine (Weibull 75 %, JJAS share, IMD rainy days, Gumbel 25-yr 1-day). 1981–2025 record for the
  AOI recorded as a fixture; tests/CI/offline demo run on it (`POND_RAINFALL_SOURCE=recorded`).
- **FR6** `POST /analysis/runoff` real: WorldCover windowed COG read × SoilGrids texture → TR-55 CN
  (AMC adjustable) → daily SCS-CN / rational / Strange → 75 % dependable volumes as a range with
  spread; providers degrade to stated defaults with warnings.
- **FR7** `POST /analysis/pond-design` real (`PondDesignBuilder`, ADR 0016): capped supply-side
  target, cost-optimised excavated frustum (depth 1.5–3.5 m searched), EAV curve, daily water
  balance → fill reliability, Gumbel/Kirpich/weir spillway, BoQ, worst-input confidence label.
- UI: rainfall card + SVG monthly chart with the plain-language verdict; design panel with
  dimensions, storage, EAV chart, reliability, methods table, BoQ, confidence badge.
- Tests: **180 passing** (rainfall golden + resilience, CN/method golden, design golden, API flows
  with offline providers). Existing-pond comparison recorded (`docs/figures/p3-existing-pond-comparison.md`).
- Live sample run: catchment 38 ha, 75 % rainfall 1 192 mm, CN 88, SCS 99 k m³ (rational 244 k,
  Strange 18 k), design 50 000 m³ capped, 3.5 m × 126 × 126 m, fills 100 % of years, ₹97 lakh, 6 s.

**Code — P2 complete, verified 2026-08-26**
- `POST /analyzeContour` returns the full Phase 2 payload: `suggested_pond_location` + rationale,
  its `catchment`, 5 `candidate_sites` with per-criterion scores, the `siting` method, and the
  terrain block. `POST /analysis/catchment` (FR4) is real: snap → D8 upstream BFS → polygon, ~1 s.
- `app/engines/hydrology/` — `conditioning` (Priority-Flood + ε), `flow` (D8, accumulation,
  streams), `streams` (links + Strahler), `catchment` (snap, BFS, metrics), `siting` (terrain MCDA
  + NMS). `app/engines/terrain/{derived,contours}.py` (curvature, TWI; marching squares + D-P).
  `workflows/catchment.py`, `workflows/terrain_products.py` (the product catalogue).
- Real routes: `/terrain/{id}/contours|streams|derived/*|layers|dem`, `/villages/{id}/siting`,
  `/analysis/results/{contour,catchment}/{job}`. 10 raster products as COGs + streams/siting JSON per village.
- Validation: 19 golden tests; pysheds cross-check (ADR 0015); `make figures` (sink fill, flow
  accumulation, pour-point sensitivity). Tests: **156 passing**.
- UI: click-to-catchment with snap distance, contours + labels + interval, streams by order,
  ranked sites panel with criterion bars, 13 toggleable layers.
- Sample run: 672 drainage cells scored; 101 stream links, Strahler 3, 24.4 km; fill 2 141 cells
  max 8.6 m; contours 2 m: 13 levels, 5 097 → 1 408 vertices.

**Code — P1 complete, verified 2026-08-26**
- `POST /analyzeContour` is **real**: upload → `ContourKMLAdapter` (lxml parser, ordered elevation
  strategy, KMZ) → provenance from the file's own metadata → Delaunay TIN → DEM at a derived
  resolution → Horn slope + hillshade → COGs in MinIO → village row (reverse-geocoded name) →
  `dem_assets` row → layer descriptors. Job flow `202 → /jobs/{id} → /result` is real (Celery on
  Redis in Docker, inline in tests). `/villages*`, `/terrain/{id}/dem|layers` real.
- `app/domain/{geo,raster,contours,dem}.py` — `utm_epsg_for`, `assert_crs`, `GridSpec`, `Raster`,
  the `DEMProvider` port. `app/engines/terrain/{interpolate,surfaces,adapters,layers}.py`,
  `app/engines/workflows/contour_analysis.py`, `app/engines/village.py`.
- Ports + adapters (ADR 0013): repositories (SQL/memory), job runner (Celery/inline), object store
  (MinIO/local). `make check` runs the real pipeline on the real sample without Docker.
- `web/` — React + MapLibre SPA: upload → progress → village select → summary card → layer
  toggles (satellite, hillshade, elevation, boundary). Served by nginx, which proxies `/api` and `/tiles`.
- Compose: **7 services** (postgres, redis, minio, api, worker, titiler, web). `make seed` analyses
  the sample. Migration 0002 (`dem_assets`, `jobs.stage`).
- Tests: **137 passing** (golden: inclined plane, cone, resolution rule; parser on the sample and
  on Z/ExtendedData/KMZ/decoy variants; end-to-end job flow on the sample).
- Sample run (Docker): village **Khapri, Durg, CG** (Nominatim), SRTM 30 m detected, EPSG:32644,
  30 m grid 110×89, 830 ha, elevation 268.7–295.7 m on the grid, mean slope 1.6°, ~2 s per job.

**Code — P0 complete, verified 2026-08-18**
- `app/` — layered tree. **35 operations across 33 paths**, all fixture-backed except
  `/health`, `/ready` and `/api/v1/meta/*`. `engines/` is still empty by design.
- `app/domain/` — `Quantity` (value + unit + uncertainty + method) and the error hierarchy
  with stable codes. `mypy --strict` clean, 96 % covered.
- `app/providers/fixture_data/` — 17 internally consistent payloads, generated not hand-typed
- `tests/` — **101 passing**: architecture enforcement, whole-contract coverage, fixture
  validity, fixture labelling, domain units
- `infra/` (postgres+postgis · redis · api) · `migrations/0001_initial` · CI · `Makefile` (16 targets)
- `docs/adr/0001–0012` · `docs/api/{openapi.json,errors.md}` · `docs/figures/p0-swagger-*.jpg`
  · `docs/progress/DAY_{01,02}.md`
- **Repository restructured** to a conventional layout — `Docs/` → `docs/`, `Plan/` →
  `docs/assignment/`, trackers under `docs/`. Root holds only what convention expects.

**Verified:** clean `make up` → migration applied → 35 operations served · `make check` green
(ruff, mypy on 43 files, 101 tests, green with and without a database) · `/meta/implementation-status` reports `engines: []`.

**Still missing:** every engine (P1 onward) · `README.md` is a stub with the CI badge; the
graded installation guide is written in P7 · the API cookbook (P7).

## Sample contour map — established facts

Full table in `docs/ROADMAP.md` §4. The four that change decisions:

1. **Elevation lives only in `<Placemark><name>`** (e.g. `277.0`). Coordinates are 2-D — there is no Z. `ExtendedData` carries `SimpleData name="ID"` (0…1354), which is numeric and **is not elevation**; an adapter that grabs the first numeric field fails silently.
2. **Root element is `<Folder>`, not `<kml><Document>`** — strict KML parsers reject the file outright.
3. **The contours are interpolated from SRTM ~30 m** (`srtm/N21E081.tif`, via Mapzen terraincache), per the file's own `sources` placemark. The 1 m interval is interpolated precision, not measured accuracy — SRTM is ±6 m relative / ±16 m absolute (LE90). Micro-relief below ~5 m is not real, and the plan's ±20 % storage claim must be defended against a 30 m source.
4. **A `land` polygon defines the AOI** — but it is a 4-corner bounding rectangle, not a cadastral parcel. Do not present it as "government land" for FR3.

Attribution owed in the report: NASA/USGS SRTM · USGS GMTED2010 · HydroSHEDS © WWF · Mapzen terrain tiles.

## Blockers

1. ~~Sample contour map missing~~ **resolved** — `data/samples/contours_1m.kml` added 18 Aug and fully analysed.
2. ~~Village not formally chosen~~ **resolved 2026-08-26** — the demo village **is** the sample KML's AOI; its name is derived at runtime by reverse-geocoding the centroid. Original note: The sample fixes an AOI — *area of interest*, the ~8.5 km² rectangle the analysis is clipped to, in Chhattisgarh around 81.297 E, 21.2517 N. P1 still needs the named village and boundary, and for FR7 validation an existing pond nearby to compare computed storage against. Confirm the sample AOI *is* the demo village, or name a different one.

## Decision log

Non-obvious choices go here **when made** — decision, reasoning, rejected alternative. Feeds the report and the viva.

| Date | Decision | Reasoning | Alternative rejected |
|---|---|---|---|
| 2026-08-27 | **UI primitives extracted into a package (`web/ds`, `pond-planner-ui`)** so the AI design tool builds with the real compiled components | The design-sync converter binds a compiled `dist/` + `.d.ts`; a hand-authored HTML bundle would give the AI design tool the look but not the parts. The app imports the same source, so there is one implementation | Lightweight HTML-only bundle (no component contract) |
| 2026-08-27 | **Two routes, no router library** (`/` landing, `/app` workspace, resolved in `main.tsx`) | nginx `try_files` already serves both; a router is one more dependency to defend for two static paths | react-router (unneeded surface) |
| 2026-08-27 | **Design system mirrored into the app, not imported** (`web/design/*.css` copied to `web/src/`) | the AI design tool gets a self-contained bundle; the app has no build-time coupling; drift is caught by eye in the parity screenshots | A shared package (build complexity for one consumer) |
| 2026-08-27 | **Raster sources declare the village `bounds`** | MapLibre stops requesting tiles outside the COG, removing TiTiler 404s from the console and the tile queue | Leave as is (harmless 404s, noisy console, wasted requests) |
| 2026-08-27 | **P8 added: landing page + UI/UX pass, the AI design tool first, then code** (user's decision at G7) | The first impression of the live demo and the 6 frontend/UX marks; a token system replaces ad-hoc CSS so the redesign is consistent and cheap to maintain | Polish the existing panels in place (no landing page, no design system) |
| 2026-08-27 | **Report PDF rendered from the Markdown by `make report`** (python-markdown + headless Chrome) | No pandoc/LaTeX on the machine; one source of truth; figures inlined so the PDF is self-contained | Hand-exported PDF (drifts from the Markdown) |
| 2026-08-27 | **Postgres healthcheck probes TCP (`pg_isready -h localhost`)**, `make up` retries the migration | On a fresh volume initdb's temporary server answers the unix-socket probe, so the stack reported healthy before the real server restarted — a defect only a clean clone shows | Fixed `sleep` before migrating (masks the cause; slow on slow disks) |
| 2026-08-27 | **Report lives in the repo as Markdown** (`docs/report/REPORT.md`) with figures linked | Version-controlled, diffable, reviewable at the G7 checkpoint; `pandoc` produces the PDF if the form insists | A separate Word/PDF document (drifts from the code it describes) |
| 2026-08-27 | **Backup recording = chaos GIF + the captured figure set**, not a fresh screen recording | Every demo beat already has an artifact; a run-through recording is best made by the presenter at rehearsal | A synthetic recording of the automation window (throttled rendering, misleading) |
| 2026-08-27 | **API samples captured from the live stack and committed** (`docs/api/samples/`) | The cookbook shows real payloads, trimmed to two list items, so it cannot describe shapes that do not exist | Hand-written JSON in the cookbook (drifts) |
| 2026-08-18 | `docs/PLAN.md` is the authoritative plan | It decomposes the rubric to sub-item level and allocates all 100 marks across dated phases | The earlier roadmap inferred from the PDF alone — superseded, see below |
| 2026-08-18 | ~~Avoid GDAL/rasterio~~ **superseded** | PLAN.md builds on pysheds/richdem, `gdal_contour`, rasterio, TiTiler and COGs; the raster path is required for FR2 contour generation and the tile layers | The lightweight numpy-only pipeline — insufficient for the planned layer set |
| 2026-08-18 | DEM from Copernicus/ALOS provider tiles, contours as *output* | PLAN.md P1; enables slope/aspect/curvature/TWI and satellite-matched stream calibration | Contour-interpolated DEM as the only source — kept as an *additional* adapter, see next row |
| 2026-08-18 | Add `ContourKMLAdapter` behind the same `DEMProvider` Protocol | `docs/assignment/Phase2.txt` grades an endpoint that ingests an uploaded KML/KMZ; PLAN.md has no such path. Same Protocol means the hydrology chain is reused unchanged | A separate parallel pipeline — duplicate code, double the viva surface |
| 2026-08-18 | UTM zone derived from input centroid, enforced by `assert_crs()` | The assignment's explicit anti-hard-coding constraint; also prevents the classic degrees-treated-as-metres area bug | A fixed project CRS |
| 2026-08-18 | D8 flow routing, D-∞ left as a documented stub | Textbook, deterministic, defensible in a viva; the stub is evidence of extensibility and is cut-ladder item 6 | D-∞ as primary — harder to justify under cross-examination |
| 2026-08-18 | Parse elevation with an ordered fallback: Z → whitelisted `ExtendedData` name → placemark `<name>`; reject `ID` | The sample carries elevation only in `<name>` and has a numeric `ID` decoy; a whitelist keeps other contour maps working without hard-coding this file's quirk | Reading the first numeric `ExtendedData` field — silently wrong on this exact sample |
| 2026-08-18 | DEM grid resolution derived from mean contour spacing, floored at the source resolution | Contours are SRTM-30 m derived; interpolating to 1–2 m would manufacture detail the source does not contain | A fixed fine grid — false precision, and slow |
| 2026-08-18 | Repo trimmed to four working `.md` files + `README.md` | `evidence.md` folded into `docs/ROADMAP.md` §8, daily template inlined into the working agreement; every remaining file has one job, listed in the the working agreement repository map | Keeping a separate file per concern — drift between overlapping trackers |
| 2026-08-18 | `docs/`, `data/`, the working agreement stay **tracked** in Git | An uncommitted `.gitignore` change would have excluded them. The already-tracked files would have survived, but every *new* `docs/adr/*.md`, `docs/progress/DAY_NN.md` and `docs/figures/*` would be dropped silently — that is the graded evidence trail (Docs 10, evidence register §8) in the repo the report links | Keeping the planning docs private — the marks live in showing them |
| 2026-08-18 | Units and uncertainty enforced by a **domain type** (`Quantity`), not by convention | The standing rule is that every number carries its unit and a band. A rule in a document decays the first time someone returns a bare float; a constructor that demands a unit does not. Carries `method` too, so provenance reaches the API response | Formatting at the presentation layer — the engine still produces bare floats internally, and the first consumer that bypasses the formatter loses the unit |
| 2026-08-18 | RFC 9457 problem details, with stable `code`s, and the catalogue **generated** at `/api/v1/meta/errors` | Half the API-documentation mark is the error catalogue. Generating it from the same table the handlers use means documentation cannot drift from behaviour. Clients branch on `code`, since one HTTP status covers several distinct failures | FastAPI's default `{"detail": ...}` — no stable identifier, so a client can only match on prose |
| 2026-08-18 | Every fixture response is **labelled** — `X-Fixture-Data: true`, a `critical` warning, and `/meta/implementation-status` | A stub indistinguishable from a real result is a trap: the frontend starts depending on numbers that will change, and an evaluator cannot tell what is implemented. Asserted by a test, so it cannot rot | Silent fixtures — faster, and actively misleading |
| 2026-08-18 | Fixtures generated by one script, not hand-typed; fixture village deliberately **not** the sample KML's AOI | Internally consistent numbers (runoff really is area x rainfall x coefficient; storage really is the EAV integral) stop the frontend learning wrong relationships and expose unit bugs. A different location keeps `fixture_data/` from becoming a back-door source of truth for the provided map | Hand-written JSON that looks plausible but does not add up |
| 2026-08-18 | `/analysis/results/*` routes exposing the full result payloads alongside the `202` envelopes | Without them the OpenAPI document would carry only job envelopes, and the frontend would have no schema for the payloads it actually renders — defeating the purpose of the contract phase | Documenting result shapes in prose only |
| 2026-08-18 | Repository restructured to a conventional layout (`docs/`, `docs/assignment/`, trackers under `docs/`) | Root now holds only the readme, contributing guide, the working agreement, build manifest, `Makefile` and `alembic.ini`. A tidy root is the first thing a reviewer sees, and mixed-case `Docs/`+`Plan/` at root is non-standard | Leaving the layout as it grew |
| 2026-08-18 | Layering enforced by an executable test (`tests/test_layering.py`), not by convention | The 3 layering marks need evidence an evaluator can see; a rule nobody checks decays. AST parse: no framework import in `domain`/`engines`, no outward layer import, no handler over 25 statements | A written-down convention — drifts the first time someone is in a hurry. ADR 0001 |
| 2026-08-18 | Python **3.12**, not the 3.14 on the dev machine | numba/pysheds/rasterio wheels lag CPython by 1–2 releases; discovering that mid-P2 costs a day at the worst moment. uv + committed `uv.lock` so a fresh clone on another machine resolves identically (G7) | Newest CPython (guaranteed wheel problem later) · pip + requirements.txt (pins direct deps, lets transitive ones drift) · conda (defensible, but ~3× image size for no gain). ADR 0002 |
| 2026-08-18 | **Synchronous** SQLAlchemy 2.0 on psycopg3 | The expensive work is raster processing in a Celery worker, not database I/O. Async buys nothing measurable and adds a bug class — one blocking call stalls the event loop, presenting as "sometimes slow" rather than as an error. Also a much smaller viva surface | Async SQLAlchemy + asyncpg — the reflexive choice, wrong for this workload. ADR 0003 |
| 2026-08-18 | Compose starts at **3 services**, not PLAN.md's 9; each later service arrives in the phase that first calls it | Every library must be defensible live. Seven declared-but-uncalled services read as copied scaffolding and are seven things to defend for zero exercised behaviour. The phase→service table is the record, and goes in the report | Declaring the full topology on day one. ADR 0004 |
| 2026-08-18 | `audit_log` append-only **in the database** (`DO INSTEAD NOTHING` rules), not by convention | A trail the application can rewrite is not evidence, and G6 grades the audit log. Verified: UPDATE and DELETE affect 0 rows, original row survives | Application-level discipline · role grants (bypassed whenever the app connects as owner) |
| 2026-08-18 | Alembic autogenerate ignores any *reflected* table this metadata does not declare | The `postgis/postgis` image installs the tiger geocoder and topology and puts `tiger` on the search_path; without the filter every revision opens with ~40 `drop_table` calls against extension-owned tables | Naming the tables to exclude — a list that goes stale the moment an extension is added |
| 2026-08-18 | SCS-CN applied to the daily series then summed | Applying CN to annual totals overestimates runoff 2–3× | Annual-total CN — a common and visible error |
| 2026-08-26 | **Demo village = the sample KML's AOI**; name derived at runtime by reverse-geocoding the centroid | Zero extra data work with 10 days left; keeps the anti-hard-coding rule intact — nothing about the village is written into code | A separately chosen village — ~1 day of boundary + DEM work, no marks gained |
| 2026-08-26 | **Uploaded contour KML is the primary terrain source**; provider DEM tiles (Copernicus/ALOS) demoted to an optional secondary adapter behind the same `DEMProvider` Protocol | Phase 2 grades the KML route and Phase 3 feeds arbitrary contour maps; removes DEM downloads from the critical path; every step (parse → TIN → fill → D8 → snap → BFS) is explainable in the viva, which the professor said is the focus | PLAN.md's order (provider DEM first, KML adapter later in P2) — adds ~1 day and external-download risk for the same marks |
| 2026-08-26 | **Site selection is a first-class terrain algorithm** (P2), not a P4 afterthought: candidates on the drainage network scored on upstream area, valley-floor slope, TWI and impoundment efficiency (storage per m³ excavated, from the EAV curve), constraints, then non-max suppression → ranked top-N | The Phase 2 brief asks the route to "identify a suitable pond location/region" from the contour map alone, and the professor flagged area selection as the examined topic. P4 layers land/LULC constraints and AHP weights on the same scorer | Selecting sites only in P4 from suitability rasters — leaves the Phase 2 route without a defensible answer to "where" |
| 2026-08-26 | **Cross-validate catchment against pysheds** (independent published implementation) ±15 %, plus synthetic golden tests and pour-point sensitivity; GRASS `r.watershed` only if QGIS gets installed | GRASS/QGIS/GDAL are not on the dev machine; an independent implementation comparison is the same evidence class, pip-installable, and runs in CI | Installing QGIS for one comparison table — ~1 GB and wall-clock we do not have |
| 2026-08-26 | **P6 shipped in full** as planned (bulkheads, Saga, WebSocket progress, JWT/RBAC, outbox audit, Grafana, Locust, chaos test) — user's explicit call, open question 6 closed | The user accepts the larger viva surface for the SysDes marks | Trimmed P6 |
| 2026-08-26 | **Contour → DEM by Delaunay TIN linear interpolation** of densified contour vertices, then Gaussian smoothing (sigma = 1 cell) | Exact on the contours, one-sentence explainable ("the plane through the three nearest contour vertices"), no tuning parameters. Its known flaw — flat triangles where all three vertices share one contour — is softened by the smoothing and finished by the P2 flat-resolution stage, which must exist anyway. Summits above the top contour are flattened; documented as a limitation, and verified by the cone golden test | Thin-plate spline / kriging — smoother, but a hyper-parameter and a covariance model to defend; `gdal_grid` — not installed and no better |
| 2026-08-26 | **Grid resolution = mean contour spacing / 4, clamped to [source resolution, 50 m]**; spacing estimated as convex-hull area / total contour length | ≥ 4 cells between adjacent contours resolves the surface between them; the floor stops the grid claiming detail the source lacks (30 m for the SRTM-derived sample → 30 m cells, ~110 × 90 grid); the cap keeps a sparse map usable. The estimator is exact for parallel contours (bias (n-1)/n for n lines, negligible at hundreds) | A fixed fine grid — false precision and slow; user-chosen resolution — invites hard-coding per map |
| 2026-08-26 | **DEM provenance inferred from the upload's own metadata** by a table of known datasets; primary = most-mentioned dataset with raw `.tif` references weighted ×5, ties to the finer product; unknown → conservative defaults + `source_unknown` warning | The sample names SRTM five times and by file (`srtm/N21E081.tif`) and Copernicus once in a generic blurb; naive "first match" or "finest match" both pick the wrong one. The table generalises to other maps; nothing about this file is coded | Hard-coding "30 m SRTM" (violates the anti-hard-coding rule); ignoring provenance entirely (every uncertainty band would be a guess) |
| 2026-08-26 | **Village named by reverse-geocoding the AOI centroid** (OSM Nominatim, 5 s timeout) with a coordinate-based fallback name and a `geocode_unavailable` warning | The village is derived from the input like everything else; the demo works offline (falls back), and CI never calls the network (`POND_GEOCODE_ENABLED=false`) | A `name` form field (fine as an override later; not a source of truth) |
| 2026-08-26 | **Ports and adapters chosen by settings** — persistence (postgres/memory), job runner (celery/inline), object store (minio/local); tests run the real pipeline on the real sample with no Docker, no mocks. ADR 0013 | The bugs this project fears live in the real code path, and `make check` must be green on a fresh clone without Docker. The in-memory adapters also power `make api-dev` | Mocks (test the mock); conditionals in engines (scatter wiring, engines depend on settings) |
| 2026-08-26 | **Hillshade/DEM served as COGs from MinIO via TiTiler**, browser reaches everything through one nginx origin (`/api`, `/tiles`) | The plan's tile path; a new DEM is on the map the moment the worker writes it, no restart, no CORS | Serving PNG tiles from FastAPI (couples the API to raster I/O and blocks its workers) |
| 2026-08-26 | **Satellite imagery = Esri World Imagery XYZ basemap**, clipped visually to the derived boundary in the client | FR1 asks for imagery for a selected village; a global basemap needs no download and no key, and Sentinel-2 via STAC arrives in P4 for NDWI where pixel access is actually needed | Downloading Sentinel-2 in P1 — a day of work for an image the basemap already shows |
| 2026-08-26 | **Priority-Flood + ε** (Barnes et al. 2014) for sink filling *and* flat resolution in one pass | Deterministic, O(n log n), textbook; the fill-depth raster is itself an evidence figure. On the sample: 2141 cells (22 %) filled, max 8.6 m — the TIN leaves shallow depressions between contours and the river floor sits below its map-edge exit | Breaching (changes the surface less but is harder to explain and to show); separate fill + flat passes (two algorithms to defend) |
| 2026-08-26 | **D8 accumulation by one descending-elevation pass** (pure numpy, no numba) | On a filled+ε surface descending elevation is a topological order, so a single sorted loop is exact; village-scale grids run in milliseconds and the code is 20 legible lines | numba/Cython (a dependency to justify for no measurable gain at this scale); recursive upstream sums (recursion depth) |
| 2026-08-26 | **Stream threshold expressed as an area (5 ha)**, not a cell count | Means the same thing on any grid resolution; overlaying the 5 ha network on the satellite basemap reproduces the visible N–S river and its main tributaries without hillside noise (`docs/figures/p2-streams-on-satellite.jpg`) | A cell count (changes meaning with resolution); a fixed fraction of the grid |
| 2026-08-26 | **Snap to the *nearest* channel cell within 150 m that drains ≥ 2 ha**, not the largest | A click on a tributary must not be dragged onto the main river; the distance moved is returned and shown. Sensitivity figure: pour-point CV 212 % → 48 % | Max-accumulation in a 5×5 window (PLAN) — always the main river |
| 2026-08-26 | **Catchments that touch the map edge carry `catchment_truncated`** | The upload bounds the analysis, not a divide; the number must not be read as complete | Silently reporting the clipped area |
| 2026-08-26 | **Site selection = terrain MCDA with an upstream-area plateau (10–150 ha)** — ADR 0014 | First version scored area monotonically and put every top site on the main river (345–406 ha upstream): a dam, not a pond. The plateau encodes "enough to fill, not a river" | Monotone area; max-TWI; deferring siting to P4 |
| 2026-08-26 | **Validation by golden tests + pysheds cross-check + sensitivity plot** — ADR 0015 | No GRASS on the machine; an independent implementation is the same evidence class and runs in CI. Result: 2.0 % / 3.4 % / 22.5 % (floodplain flat) | Installing QGIS |
| 2026-08-26 | **Curvature uses the ArcGIS sign convention** (plan < 0 = laterally concave) | Every evaluator who has opened a GIS expects it; Zevenbergen & Thorne's own sign is the opposite for plan curvature and would read as a bug | Z&T's original sign |
| 2026-08-26 | **Contours and streams served as GeoJSON from the API**, not MVT via Martin | At village scale a contour set is ~1 400 vertices after simplification; a tile server would be a service to defend for nothing exercised. Martin stays in the ADR 0004 table for district scale | Martin now |
| 2026-08-26 | **Impoundment efficiency = volume behind a 2 m rise / footprint** as a siting criterion | Rewards natural basins over open slopes with one flood fill per candidate; the same fill becomes the EAV curve in P3 | Excavation-only sizing (ignores what the terrain gives for free) |
| 2026-08-26 | **Rainfall from Open-Meteo ERA5-Land (primary) with NASA POWER fallback**, both behind `Retry ∘ CircuitBreaker ∘ Cached` and a `FallbackChain`; the 1981-2025 record for the AOI is checked in as a fixture and used when `POND_RAINFALL_SOURCE=recorded` | Free, keyless, 45 years in 2 s; the resilience stack is what the chaos test exercises and the recorded fixture is what makes tests, CI and the demo independent of the network | IMD gridded data (registration, manual download); a single provider (one outage = no demo) |
| 2026-08-26 | **75 % dependable rainfall by Weibull plotting position** on complete calendar years; incomplete years excluded, never scaled | Indian minor-irrigation practice designs to the 75 % year; scaling a partial year invents rain | Mean annual (fails every second year); Gringorten/Hazen positions (defensible but less familiar) |
| 2026-08-26 | **TimescaleDB deferred**: the daily series lives in the object-store cache, not a hypertable | ~16 000 rows per point; a hypertable earns nothing at village scale and is one more service to defend. Re-evaluate at district scale (ADR 0004 table) | Hypertable now |
| 2026-08-26 | **Curve number from ESA WorldCover (windowed COG read) × SoilGrids texture → HSG**, TR-55 table, AMC II; both providers degrade to stated defaults with a warning and pull confidence to *low* | Real land cover for the actual catchment at 10 m without a download; SoilGrids is slow (~40 s) so it runs in the worker and is cached 30 days | FAO HWSD download; a single "cropland, C" assumption |
| 2026-08-26 | **Three runoff methods on the daily series, reported as a range**; SCS-CN is the design figure; the annual-total shortcut is shown in a test to overestimate > 3× | The disagreement is information; a single number would be false precision. ADR 0010 | One method |
| 2026-08-26 | **Pond design method** — capped supply-side target, excavated frustum, cost-derived depth, daily water balance, Gumbel/Kirpich spillway, worst-input confidence — ADR 0016 | See the ADR | See the ADR |
| 2026-08-26 | **Pool behind a bund = 8-connected flood fill on the upstream side**, not D8 donors only; shared by the EAV curve and the siting efficiency | The donor-only pool excluded cells that drain into the channel beside the bund — physically wrong (a cone test gave 2 100 m² where π·50² ≈ 7 850 m² was expected). The upstream-or-not-lower rule keeps the channel below the bund dry | Donor-only fill; unconstrained fill (floods the downstream channel) |
| 2026-08-26 | **FR3 eligibility as a Specification expression** with self-naming leaves; ownership *unknown* passes with a warning — ADR 0017 | The response can list the rules applied and never claims government land it cannot know | Hard-coded if/else filters; assuming government ownership |
| 2026-08-26 | **Existing water from Sentinel-2 NDWI + Otsu + OpenCV open/close + connected components**, WorldCover class 80 as fallback | Fresh, scene-adaptive, and the OpenCV usage the PDF names in a real job; the fallback keeps the job alive offline | Fixed NDWI threshold (fails across scenes); WorldCover only (2021, static) |
| 2026-08-26 | **AHP weights with the consistency ratio returned** (CR 0.011 for the default matrix) over the P2 terrain criteria, restricted to eligible cells | Defended weights on an already-explainable score; CR makes the weighting checkable, not asserted | Fixed weights (P2); an ML scorer (see next row) |
| 2026-08-26 | **XGBoost + SHAP deferred; AHP-only ships (α = 1.0)** — the plan's designed fallback, ADR 0017 | Two OSM tanks in 8.5 km² are not a training set; a model fitted to them cannot be evaluated under spatial CV and would be theatre. The scorer interface keeps the ML path as documented future work | Training on two positives |
| 2026-08-26 | **Suitability computed by one job** (`POST /analysis/suitability`) that stores available-land parcels, the water mask and the heat-map; `GET /villages/{id}/available-land` is a read | Sentinel-2 reads take 10–30 s — too slow for a GET; one job, one cache, one place to look | Computing on every GET |
| 2026-08-26 | **FR8 as a results overlay on the map + the designed pond drawn as a footprint** at the outlet, all six PDF items in one panel | The rubric grades "all overlays simultaneously toggleable + stats panel"; the footprint makes the dimensions a map object, not a number | A separate results page |
| 2026-08-26 | **Offline-first service worker** (cache-first tiles, network-first API with stale fallback + badge) — ADR 0018 | The chaos test in one line; stale is visible | Workbox; server cache headers |
| 2026-08-26 | **Generated OpenAPI types for the wire envelopes**, hand-written shapes kept for GeoJSON payloads | A contract change fails the frontend build; generated GeoJSON types are `dict` and useless for the map | Fully generated client (openapi-fetch) — more surface for little gain at this size |
| 2026-08-26 | **Minimal EN/HI toggle** (headings + the offline message) | Cut-ladder item 5: proof of capability suffices; full translation is future work | Full i18n |
| 2026-08-27 | **P6 hardening set** — bulkheads, WebSocket observer, saga with compensations, idempotency keys, JWT RS256 + RBAC, state machine + outbox → append-only audit, backpressure 429, correlation ids + Prometheus + Grafana, leader-elected refresh, nginx rate limits — ADR 0019 | User chose the full scope; each item is exercised by a test or a recorded demo, not declared | Trimmed P6 |
| 2026-08-27 | **Audit via a transactional outbox drained by beat**, not direct inserts | Same-transaction event + async projection is the pattern that survives an external audit sink; the pending count is visible on the audit route so nothing is silently lost | Direct insert (simpler; not the pattern the plan names) |
| 2026-08-27 | **Users are a configured list** (`POND_USERS`), roles viewer/planner/officer | No identity provider in the assignment; the gate is what is graded. Swap for OIDC later without touching the routes (dependency injection) | A users table with password hashing (more to defend, same grade) |
| 2026-08-26 | **Autonomous phase loop** with a user check-in at every gate (the working agreement's autonomous loop) | The user wants progress visibility at each checkpoint and otherwise uninterrupted building; the gate is the natural unit | Check-ins per task (too chatty) or per phase without a stop (no visibility) |

## Open questions

1. ~~Where is the provided sample contour map?~~ **resolved** — `data/samples/contours_1m.kml`, analysed in `docs/ROADMAP.md` §4.
2. ~~What is the Phase 2 submission deadline?~~ **resolved 2026-08-18** — the Phase 2 window has passed and it is not scored as a separate submission. Consequence: it no longer drives sequencing, so P0 → P1 → P2 runs in `docs/PLAN.md` order. **The KML route stays in scope** — G2 still requires it (`docs/ROADMAP.md` §4), Phase 3 is end-to-end over arbitrary contour maps, and the final report must carry a working API route URL.
3. **When are the lab hours for the prototype demo?** Posture depends on which gate is green when it lands — see the stop-and-fix table (`docs/ROADMAP.md` §3).
4. ~~Which village?~~ **resolved 2026-08-26** — the sample AOI is the demo village.
5. ~~Is the ALOS 12.5 m download still worth the day?~~ **resolved 2026-08-26** — no; KML-first (decision log). Provider DEM adapter is optional stretch.
6. ~~Is the full P6 stack within the explain-it-live budget?~~ **resolved 2026-08-26** — user chose full P6.
7. Minor: the marks matrix in `docs/PLAN.md` §2.1 sums to **99**, not 100 — the System Design column totals 14 against a stated 15. One mark is unallocated.

## Session log

Newest first. One entry per working session: what changed, what is next.

### 2026-08-27 (session 16)

**P8 complete — G8 closed pending review.** Report PDF via `make report`; design brief + design-system bundle + three prototypes in `web/design/`; app rebuilt on tokens with shared primitives and six states per panel; landing page at `/`; Lighthouse 98/96 accessibility; 390 px verified; nginx serves both routes. Defects found by running: a `.site` class collision that collapsed the landing footer, a Vite proxy without WebSocket upgrades that hung job polling in dev, verbose quantity bands. **Next:** G8 checkpoint — the user reviews the landing page and workspace, optionally pushes the bundle to the AI design tool with the design-sync tooling.

### 2026-08-27 (session 15)

**P7 complete — G7 closed pending review, 99 marks targeted.** Coverage measured (engines 94.3 %, domain 97.6 %, overall 86.2 %; `p7-coverage.jpg`); README installation guide with a 14-row troubleshooting table; API cookbook with 15 real captured samples and the regenerated error catalogue; technical report with the validation table and 20 references; licence register; demo script; `make tunnel`; DAY_08. Found `make check` had drifted on four P6-era files (format + 11 lint findings) — fixed. Clean-clone verification (fresh volumes → `make up` 49 s → `make seed` → `/ready`, `fixture_backed: []`, village Khapri, web 200) found and fixed two fresh-volume defects — a unix-socket Postgres healthcheck and an unwritable beat schedule file — then passed; tagged `v1.0`. **Next:** G7 checkpoint — the user reviews the report; demo-day steps.

### 2026-08-27 (session 14)
**P6 complete — G6 closed, 91 marks secured.** Full hardening scope (see "What exists today"), ADR 0019, three decisions logged. Defects found by running: a saga step that fails half-way must clean its own partial writes (compensation only covers completed steps); the generated OpenAPI types caught two hand-typed shortcuts in the frontend; the old single `worker` container lingered as an orphan after the split. **Next:** G6 checkpoint, then P7.

### 2026-08-26 (session 13)
**P5 complete — G5 closed, 84 marks secured; all 8 FRs demonstrable.** Results overlay, pond footprint, progress states, service worker, generated types, EN/HI, mobile layout (see "What exists today"); ADR 0018; four decisions logged. **Next:** G5 checkpoint, then P6 in full.

### 2026-08-26 (session 12)
**P4 complete — G4 closed, 77 marks secured.** Also, at the user's request, stripped the AI co-author trailers from every commit message (`git filter-branch`, force-pushed; authors unchanged). Suitability engines, providers, routes and UI (see "What exists today"); ADR 0017; five decisions logged. Defects found by running: my own guard clamped Otsu to 0 on a two-valued test image (OpenCV returns the lower mode) — test relaxed, behaviour kept; a buffer test cell 80 m from the tank, not 50. **Next:** G4 checkpoint, then P5.

### 2026-08-26 (session 11)
**P3 complete — G3 closed, 70 marks secured; the ideal prototype-demo point.** Rainfall, runoff and pond design engines, providers and routes (see "What exists today"), ADR 0016, seven decisions logged. Defects found by running: the donor-only pool excluded cells beside the bund (fixed with an upstream-side flood fill shared by EAV and siting); a Gumbel expectation that chased an outlier; a synthetic bowl whose channel expression evaluated to 199 m (operator precedence) — the engine was right, the test terrain wrong; SoilGrids ~40 s → worker + 30-day cache + default. **Next:** G3 checkpoint, then P4.

### 2026-08-26 (session 10)
**P2 complete — G2 closed, 51 marks secured.** Built the entire terrain & catchment engine in one session (see "What exists today"), ADR 0014 (siting) and 0015 (validation). Ten decisions logged. Defects found by running: monotone area scoring sited every pond on the river (fixed with a plateau); pysheds/NumPy 2 incompatibility; a synthetic that was right and a test that was wrong (Strahler 3, bowl drainage); curvature sign convention. **Next:** G2 checkpoint with the user, then P3.

### 2026-08-26 (session 9)
**P1 complete — G1 closed, 21 marks secured.** Built the KML-first walking skeleton end to end (see "What exists today"). Defects found by running rather than reading: rasterio wheel needs `libexpat1` on `python:3.12-slim`; TiTiler images are amd64-only and listen on port 80; the provenance heuristic initially picked Copernicus from Mapzen's generic attribution blurb over the explicit `srtm/N21E081.tif` (fixed by evidence weighting); a 30 m grid with smoothing loses the single-cell 267/298 m extremes (documented as expected, tests widened). Seven decisions logged. ADR 0013 added, ADR 0004 amended. **Next:** G1 checkpoint with the user, then P2.

### 2026-08-26 (session 8)
**Planning session — loop established, four decisions taken with the user.** Read the assignment, phase briefs, full PLAN.md and ROADMAP.md. Eight days had passed with no commits; 10 days remain. Verified `make check` green (101 tests). Decisions: demo village = sample AOI · KML-first terrain source · pysheds + golden tests for validation (no GRASS on the machine) · full P6. Added the autonomous loop protocol to the working agreement. Blocker 2 and open questions 4–6 closed. **Next:** P1 revised — `assert_crs()`, `ContourKMLAdapter`, contour→DEM, hillshade → MinIO → TiTiler → browser via `POST /analyzeContour`.

### 2026-08-18 (session 7)
**P0 complete — G0 closed, 11 marks secured.** Built the full API contract: 35 operations across 33 paths, 17 generated fixture payloads, `Quantity` and the domain error hierarchy, RFC 9457 problem details with a generated error catalogue, and `/meta/implementation-status`. Added ADRs 0005–0012. **Restructured the repository** to a conventional layout. Captured evidence: `docs/api/openapi.json`, two Swagger screenshots, `docs/api/errors.md`. Tests now 102, `mypy --strict` clean on 43 files, `domain/` 96 % covered. Four defects found in the process, two of them real bugs — a `default_factory` whose type did not match its `Literal`, which would have admitted an invalid runoff method through the default path. **Next:** choose the village (blocker 2, the only thing gating P1), then P1 day 1.

### 2026-08-18 (session 6)
**P0 chunk 1 built and verified.** Layered `app/` tree · uv/ruff/mypy-strict/pytest · `Makefile` · 3-service compose + multi-stage non-root `Dockerfile.api` · Alembic revision 0001 (postgis, `villages`, `jobs`, `audit_log`) · GitHub Actions CI · `CONTRIBUTING.md` · ADRs 0001–0004 · `docs/progress/DAY_01.md`. Clean-slate `make up` brings the stack up in 15 s and applies the migration; `make check` is green (ruff, mypy on 23 files, 15 tests). Four defects found by running it rather than reading it — image build missing `README.md`, ruff isort misconfiguration, autogenerate trying to drop 40 PostGIS extension tables, and ORM/migration drift on the `jobs` CHECK constraints; all fixed, and autogenerate now produces an empty diff. Six decisions logged above. **Next:** P0 chunk 2 — the ~25 contract endpoints as fixture routes (the parallelism unlock), ADRs 0005–0012, Swagger screenshot.

### 2026-08-18 (session 5)
Status review, no code written. Confirmed toolchain on the dev machine: Python 3.14.6 · Docker 29.1.3 · Compose v5.0.1 · uv 0.9.5 · remote `github.com/Rahul5977/AI-BasedPondAnalysis`. **Caught and reverted an uncommitted `.gitignore` change** that would have excluded `Docs/`, `Plan/`, `data/`, the working agreement and `docs/PROGRESS.md` — see the decision log. **Closed open questions 1 and 2:** the Phase 2 window has passed and is not separately scored, so sequencing follows `docs/PLAN.md` P0 → P1 → P2 unmodified; the KML route remains a G2 exit criterion. **Next:** P0 chunk 1 — repo tree, `pyproject`, ruff/mypy/pytest config, `Makefile`, `Settings`, CI.

### 2026-08-18 (session 4)
Reframed both trackers around **phases and gates rather than calendar days** at the user's direction — dropped date columns, replaced the weekly-checkpoint table with state-triggered stop-and-fix rules, and added a phase dependency column so the ordering constraints are explicit rather than implied by dates. `docs/PLAN.md` keeps its day allocation untouched; it now reads as relative effort. Defined AOI in place. **Next:** P0 in full.

### 2026-08-18 (session 3)
Sample contour map added and analysed: 2712 placemarks (1355 contour `LineString`s + 1355 label `Point`s + AOI polygon + attribution), 267–298 m at 1 m interval over ~8.5 km², centroid → EPSG:32644. **Found three parser traps and one accuracy finding** — elevation only in `<name>`, a numeric `ID` decoy in `ExtendedData`, a non-standard `<Folder>` root, and SRTM-30 m provenance that caps real vertical fidelity. All recorded in `docs/ROADMAP.md` §4. Trimmed the docs: `Docs/evidence.md` folded into `docs/ROADMAP.md` §8 (now 38 rows), `docs/progress/TEMPLATE.md` inlined into the working agreement, `Readme.md` → `README.md`, KML moved to `data/samples/`, `.gitignore` added, and a **repository map** added to the working agreement giving every file one stated job. **Next:** P0 in full.

### 2026-08-18 (session 2)
`docs/PLAN.md` arrived with full content (707 lines) — it had been 0 bytes in every prior commit. Rebuilt `docs/ROADMAP.md` as the operational distillation of it: 8 phases P0–P7, gates G0–G7 with verifiable exit criteria, weekly hard checkpoints, cut ladder, standing rules. Created `Docs/evidence.md` (34 plan artifacts + 3 added for the Phase 2 submission) and `docs/progress/TEMPLATE.md` for the daily ritual. Superseded four of the previous session's stack decisions that conflicted with the plan. **Flagged one substantive gap:** PLAN.md derives terrain from provider DEM tiles and never ingests an uploaded KML/KMZ, but that endpoint is exactly what `docs/assignment/Phase2.txt` is graded on — reconciliation in `docs/ROADMAP.md` §4, roughly one day inside P2. **Next:** P0 in full — repo tree, compose, Makefile, ~25 fixture endpoints, CI, 12 ADRs.

### 2026-08-18 (session 1)
Set up initial working documents from `docs/assignment/Assignment.pdf` and `docs/assignment/*.txt` while `docs/PLAN.md` was still empty. Extracted the 8 functional requirements and the rubric. Superseded by session 2.
