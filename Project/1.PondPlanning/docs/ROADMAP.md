# ROADMAP — AI-based Village Pond Planning System

**Operational tracker distilled from `docs/PLAN.md`.** The plan is the authority; this file is the day-to-day checklist and checkpoint gate. When they disagree, `docs/PLAN.md` wins — and fix this file.

### Authority chain

1. `docs/assignment/Assignment.pdf` — the specification and the rubric. Non-negotiable.
2. `docs/assignment/Phase{1,2,3}.txt` — what each submission must contain.
3. `docs/PLAN.md` — the 707-line marks-driven execution plan (P0–P7, evidence register, contingency ladder).
4. `docs/ROADMAP.md` (this file) — condensed phase gates and checkpoints.
5. `docs/PROGRESS.md` — where we actually are right now.

**Target: 100/100.** Final submission and live demonstration: **5 September** — the one fixed date.

Work is tracked by **phase and gate, not by calendar**. `docs/PLAN.md` carries a day-by-day allocation; treat it as the intended *ordering and relative effort*, not a schedule to feel behind on. What matters is that gates close in order and none closes without evidence.

---

## 1. Phase map

| Phase | Marks | Cumulative | Gate | Depends on |
|---|---|---|---|---|
| **P0** Foundations & Contract | 11 | 11 | G0 | — |
| **P1** Walking Skeleton | 10 | 21 | G1 | G0 (repo, compose, fixtures) |
| **P2** Terrain & Catchment ⭐ | 30 | 51 | G2 | G1 (real DEM in a real browser) |
| **P3** Rainfall · Runoff · Design ⭐ | 19 | 70 | G3 | **G2 — hard.** Runoff and sizing are computed *on* the catchment |
| **P4** Suitability & AI | 7 | 77 | G4 | G2 (slope, TWI, flow acc as features) |
| **P5** Frontend Integration | 7 | 84 | G5 | G3, G4 for real data; can be built against P0 fixtures in parallel |
| **P6** System Hardening ⭐ | 7 | 91 | G6 | G5 |
| **P7** Tests · Docs · Report | 8 | 99 | G7 | all |
| **P8** Landing page & UI/UX (added 27 Aug) | protects Frontend 5 · UX 1 | 99 | G8 | FR8 |

**P2 + P3 = 49 marks — half the project in two phases.** Best hours go there. Everything before is enablement; everything after is packaging.

**The one parallelism unlock:** P0 ships the full API contract as fixture endpoints, so P5 (frontend) can be built against realistic JSON without waiting for P3 or P4. Skipping that in P0 serialises the whole project.

## 2. Checkpoint gates

A gate is closed until **every** box has evidence a third party can see. Do not start the next phase on an open gate — `docs/PLAN.md` §7.3 is explicit that a broken catchment engine invalidates FR6 and FR7 downstream.

### G0 — Foundations ✅ **closed 2026-08-18**
- [x] Fresh clone → `make up` → Swagger at `/docs` lists **35 operations across 33 paths**, all returning fixtures
- [x] CI green on main (`ruff` + `mypy --strict app/domain` + `pytest`, plus an image build)
- [x] 12 ADR files committed
- [x] Fixture JSON ready to hand to the AI design tool — 17 payloads in `app/providers/fixture_data/`, mirrored in `docs/api/openapi.json`
- [x] *Added:* every fixture route is labelled `X-Fixture-Data: true`, and `GET /api/v1/meta/implementation-status` reports what is real
- **11 marks secured**

### G1 — Walking skeleton ✅ **closed 2026-08-26**
- [x] Browser shows real satellite imagery + hillshade from your own pipeline — **FR1 banked** (`docs/figures/p1-walking-skeleton.jpg`)
- [x] `assert_crs()` guard exists, with a unit test that fails on an EPSG:4326 array (`tests/test_geo.py::test_assert_crs_fails_on_a_geographic_grid`)
- [x] End-to-end path proven: browser → API → worker → MinIO → tile → browser (`make up && make seed`, then the app at :3000; `tests/test_contour_job_flow.py` runs the same path in-process)
- [x] *Revised scope (decision log 2026-08-26):* the DEM comes from the uploaded contour map, so `POST /analyzeContour` is real from P1 — parse → TIN → hillshade → COG → MinIO → TiTiler
- **10 marks secured · 21 cumulative**

### G2 — Terrain & catchment ⭐ ✅ **closed 2026-08-26**
- [x] Click any point → catchment polygon in < 5 s (cached < 2 s) — ~1 s via the worker, flow model cached per village (`docs/figures/p2-click-to-catchment.jpg`)
- [x] Catchment area within ±15 % of an independent implementation on the test village — pysheds: 2.0 % / 3.4 % / 22.5 % (floodplain flat; policy in ADR 0015), `tests/test_pysheds_crosscheck.py`. GRASS not installed (decision log)
- [x] Synthetic-DEM golden tests passing in CI — `tests/golden/test_hydrology.py`, `test_catchment.py`, `test_interpolation.py` (19 tests)
- [x] Contours, streams, slope, curvature, TWI all toggleable layers — plus aspect, flow accumulation, fill depth, conditioned DEM
- [x] Snap distance surfaced in the UI — catchment panel + `pour_point_snapped` warning
- [x] **`POST /analyzeContour` accepts the provided KML/KMZ and returns catchment JSON** — full `ContourAnalysisResult` with suggested location, rationale, candidates, method
- [x] **FR2 + FR4 complete · 51 marks secured**

### G3 — Water numbers ⭐ *ideal prototype demo point* ✅ **closed 2026-08-26**
- [x] `POST /analysis/pond-design` returns the full payload (catchment + rainfall + runoff + design + reliability + BoQ + warnings + confidence) — live run 6 s on the sample (`docs/figures/p3-design-panel.jpg`)
- [x] Three runoff methods produce a documented range, not one false-precision number — SCS-CN daily 99 k m³ / rational 244 k / Strange 18 k on the top site (spread 188 %, flagged)
- [x] Existing-pond comparison recorded honestly, including the error — `docs/figures/p3-existing-pond-comparison.md`
- [x] **FR5 + FR6 + FR7 complete · 70 marks secured**

### G4 — Suitability ✅ **closed 2026-08-26**
- [x] `POST /analysis/suitability` → ranked sites with per-criterion breakdown (raw value, membership, weight, contribution)
- [x] AHP consistency ratio computed and **CR < 0.10** asserted — CR 0.011 for the default matrix; `tests/golden/test_suitability.py` also checks an intransitive matrix is rejected
- [x] Sanity check recorded: do top-ranked sites land near existing tanks? — No, and correctly: the mapped tanks are canal-fed with 2–11 ha catchments (`docs/figures/p3-existing-pond-comparison.md`); the ranked sites are the rain-fed positions
- [x] **FR3 complete · 77 marks secured**

### G5 — Frontend ✅ **closed 2026-08-26**
- [x] All six PDF-listed overlays simultaneously toggleable — **FR8 done** (`docs/figures/p5-all-overlays.jpg`: results overlay + pond footprint + catchment + streams + contours + sites + boundary)
- [x] Every panel has designed loading, empty, error, and stale states — job progress with stage/percent, empty hints, RFC 9457 errors surfaced, offline badge from the service worker
- [x] Works at 390 px width (`docs/figures/p5-phone-390px.jpg`)
- [x] **All 8 FRs demonstrable · 84 marks secured**

### G6 — Hardening ✅ **closed 2026-08-27**
- [x] **Chaos test recorded** — API container stopped, page reloaded, the app serves the cached village, layers, rainfall and design with the offline badge (`docs/media/chaos-test.gif`)
- [x] Grafana dashboard screenshot captured (`docs/figures/p6-grafana.jpg`) — queue depth, job p50/p95, provider errors, cache hit rate, HTTP p95
- [x] Locust p95 numbers recorded (`docs/figures/p6-locust.txt`): 50 users / 60 s, 1 102 catchment submissions, POST p95 33 ms, end-to-end p95 560 ms, 0 HTTP failures
- [x] RBAC demo: viewer role gets `403` on the approval route — `tests/test_hardening.py::test_recommendation_lifecycle_is_role_gated_and_audited` (viewer 403, planner 403 on approve, officer 200) and the UI login panel
- [x] Audit log rows exist for every recommendation and status change — outbox → `audit_log` (append-only by DB rule), visible at `GET /recommendations/{id}/audit`
- [x] Bulkheads proven live: catchment finished in 0.6 s while a suitability job was at 10 % on the heavy queue
- [x] **91 marks secured**

### G7 — Submission
- [x] Fresh clone → `make down ARGS=-v` → `make up` → `make seed` → working system (verified 2026-08-26 from a clean clone in a scratch directory; a second machine is the demo-day check)
- [x] Coverage: engines 94.3 %, domain 97.6 %, overall 86.2 % — `docs/figures/p7-coverage.jpg`
- [x] `docs/report/REPORT.md` — §7 validation table with the measured numbers, 20 references
- [x] `docs/DEMO.md` script, timed at 7 min; backup recording `docs/media/chaos-test.gif` + the figure set; rehearsals are the user's (demo-day)
- [x] Evidence register: every row ticked except 20 (deliberately not produced, ADR 0017) and 36 (public URL — `make tunnel` on demo day)

### G8 — Landing page & UI/UX
- [x] Landing page at `/` on the Docker stack (nginx 200; `p8-landing.jpg`); every claim maps to a shipped feature; links to `/app`, `/docs`, the report, ADRs, licences, the repo
- [x] Workspace on the token system; six named states designed (`p8-proto-states.jpg`) and coded in `ui.tsx` + every panel (`p8-app-workspace.jpg`, `p8-app-design.jpg`)
- [x] Design system as a real package (`web/ds`, `pond-planner-ui`, 19 components) synced to the AI design tool (the design-sync tooling: render check 19/19, all cells graded good); `web/design/` prototypes; parity pair `p8-proto-landing.jpg` / `p8-landing.jpg`
- [x] Lighthouse accessibility 100 on `/` and `/app`, best practices 100 / 96, SEO 100 · 390 px (`p8-phone-390.jpg`) · `make check` and `npm run build` green

## 3. Stop-and-fix rules

Triggered by state, not by date. When one fires, stop feature work and deal with it.

| Trigger | Rule |
|---|---|
| G1 not closing — the wire doesn't run end-to-end | Stop adding features. Fix integration. Nothing else matters until a browser shows a real hillshade. |
| G2 open | **Do not start P3.** A broken catchment engine silently invalidates FR6 and FR7, and you will not find out until the viva. |
| G3 open after a full P3 pass | Begin the cut ladder at item 1 (§5). |
| Prototype demo called with G2 green | Demo FR1, FR2, FR4 + the validation evidence. Lead with "catchment engine validated against GRASS". Acceptable posture. |
| Prototype demo called with G3 green | Demo the full hydrology chain — 6 of 8 FRs. Strong posture. |
| G5 open and P6/P7 not started | Cut ladder items 2–4. Protect P6 (7 marks) and P7 (8 marks) — they outweigh frontend polish (5). |
| Submission near with G6 open | Compress P7 to docs-only; drop MkDocs polish. Never drop the installation guide or the report's validation section. |

## 4. The sample contour map — and the Phase 2 gap

`data/samples/contours_1m.kml` · 6.4 MB · generated by "ContourMapGenerator".

### What is actually in the file

| Property | Value | Consequence for the parser |
|---|---|---|
| Root element | `<Folder>`, **not** `<kml><Document>` | Non-standard. Strict parsers (fastkml, some GDAL paths) reject it. Parse with `lxml` + namespace-agnostic local-name matching. |
| Placemarks | 2712 = 1355 `LineString` + 1355 `Point` + 1 `Polygon` + 1 metadata | Filter to `LineString`; the Points are duplicate labels and would double-weight the interpolation. |
| **Elevation source** | `<Placemark><name>` only, e.g. `277.0` | Coordinates are **2-D** — there is no Z to read. |
| `ExtendedData` | `SimpleData name="ID"` (0…1354) | ⚠️ **Trap.** Numeric, sequential, and *not* elevation. An adapter that grabs the first numeric `SimpleData` produces garbage silently. Match field names against `elev\|elevation\|contour\|level\|height` and reject `ID`. |
| Elevation range | 267.0 – 298.0 m · 32 levels · **1.0 m interval** | 31 m of relief. |
| Extent | lon 81.2814–81.3126, lat 21.2398–21.2636 | ≈ 3.24 km × 2.63 km ≈ **8.5 km²** |
| Centroid | 81.2970 E, 21.2517 N (Chhattisgarh) | → **UTM 44N, EPSG:32644**, computed at runtime, never written down |
| `land` placemark | 4-corner Polygon at altitude 30 | The AOI boundary. Useful to clip against — but it is a **bounding rectangle, not a cadastral parcel**. Do not present it as "government land" for FR3. |
| `sources` placemark | Attribution text | See below — this is the important one. |

### ⚠️ The contours are SRTM-derived

The `sources` placemark attributes the terrain to **Mapzen terrain tiles / terraincache → NASA/USGS SRTM**, raw raster `srtm/N21E081.tif`, native resolution **~30 m**, mission 2000 (with GMTED2010 ~250 m as a coarser fallback, and HydroSHEDS © WWF).

So the 1 m contour interval is **interpolated precision, not measured accuracy**. SRTM's vertical error is roughly ±6 m relative / ±16 m absolute (LE90). Three consequences you must carry into the code and the report:

1. **Micro-relief below about 5 m is not real.** Do not let the EAV curve or the depth optimiser claim decimetre fidelity off this input.
2. **Uncertainty statements must widen.** The plan's ±20 % storage figure has to be defended against a 30 m source, not a 1 m contour interval.
3. **ALOS 12.5 m (PLAN.md P1) is a genuine upgrade for the demo village** — but the Phase 2 route must still work entirely from the uploaded KML, because that is what is graded.

Attribution owed in the report's licence register: NASA/USGS SRTM · USGS GMTED2010 · HydroSHEDS © WWF · Mapzen terrain tiles.

### The gap

`docs/assignment/Phase2.txt` requires a route that **accepts an uploaded KML/KMZ contour map** (`POST /analyzeContour` or `/findCatchment`) and returns catchment JSON, demonstrated on this sample. It is graded on "Working API endpoint" and "Catchment identification/estimation".

`docs/PLAN.md` builds terrain from **provider DEM tiles** (Copernicus/ALOS) and treats contours as an FR2 *output*. Its only upload path is parcel import in P4. **As written, the plan does not produce the Phase 2 submission artifact.**

Reconciliation — cheap, because the hydrology engine is shared:

1. `ContourKMLAdapter` behind the same `DEMProvider` Protocol as the Copernicus/ALOS adapters.
2. Parse per the table above: `LineString` only, elevation from `<name>`, with an ordered fallback (Z → whitelisted `ExtendedData` field → name) so other people's contour maps still work. Fail loudly when no strategy yields elevations — never guess.
3. Derive the UTM zone from the uploaded centroid. This is the anti-hard-coding mechanism the assignment grades.
4. Interpolate contours → DEM raster at a resolution derived from mean contour spacing (**not** finer than the ~30 m source justifies), then hand off to the **existing** sink-fill → D8 → accumulation → snap → BFS chain, unchanged.
5. Expose `POST /analyzeContour` (multipart) → standard `202` + poll → catchment JSON.

Roughly one day of work, and it belongs **early in P2** — right after the DEM interpolation lands, before the layer work. It reuses everything downstream and it is the difference between having a Phase 2 submission and not.

## 5. Non-negotiables

**Never cut** (`docs/PLAN.md` §6.1): any of FR1–FR8 · the async job architecture · the GRASS validation · the installation guide · hydrology golden tests · the chaos test.

**Cut in this order if behind:** cascade correction → water-balance simulation → ML scoring (ship AHP α=1.0) → site comparison → Hindi depth → D-∞ routing.

**Floors:** P0–P2 only ≈ 58 · P0–P3 + P7 ≈ 74 · all phases ≈ 95+.

## 6. Standing rules

- **Derive everything from the input.** No coordinates, extents, CRS, or results specific to the sample map. The UTM-zone-from-centroid rule is the test.
- **Graded from the browser.** A feature that passes pytest but has no visible control scores near zero on functionality.
- **Units and uncertainty on every number.** "18,950 m³ (±20 %)" beats "18950".
- **SCS-CN runs on the daily series, then sums.** Applying it to annual totals overestimates 2–3×.
- **Log the decision when you make it.** `docs/PROGRESS.md` decision log feeds the report and the viva.
- **Daily ritual (15 min, non-negotiable):** commit and push · write `docs/progress/DAY_NN.md` · list tomorrow's three tasks.

## 7. Trackers

See the working agreement § Repository map for what every file in the repo is for.

## 8. Evidence register

Every mark needs an artifact an evaluator can see (`docs/PLAN.md` Part 5). Figures → `docs/figures/`, videos → `docs/media/`. Tick as produced.

| # | Artifact | Defends | Phase | ✓ |
|---|---|---|---|---|
| 1 | Repo tree + routers with zero business logic (enforced by `tests/test_layering.py`) | Code layering 3 | P0 | ☑ |
| 2 | `docker-compose.yml` + `Makefile` (clean `make up` → 15 s → migration applied) | DevOps 2 + install 2 | P0 | ☑ |
| 3 | 12 ADR files | SysDes 1 + Docs 1 | P0 | ☑ 12/12 |
| 4 | CI badge (ruff + mypy + pytest + image build) — green on main | Code 3 | P0 | ☑ |
| 5 | `docs/api/openapi.json` + Swagger screenshots + error catalogue | Docs API 2 | P0 | ☑ |
| 6 | Sink fill before/after raster figure | Terrain 3 | P2 | ☑ `docs/figures/p2-sink-fill-before-after.png` |
| 7 | Flow-accumulation raster image | Terrain 4 | P2 | ☑ `docs/figures/p2-flow-accumulation.png` |
| 8 | Streams overlaid on satellite (visual match) | Terrain 4 | P2 | ☑ `docs/figures/p2-streams-on-satellite.jpg` |
| 9 | Contours at 2 intervals + vertex-reduction figure | Terrain 2 + FR2 3 | P2 | ☑ `p2-contours-5m.jpg` + 2 m in the UI; 5 097 → 1 408 vertices at 2 m (API reports both counts) |
| 10 | Slope/aspect/curvature/TWI screenshots | Terrain 2 | P2 | ☑ `p2-layers-slope.jpg`, `p2-layers-twi.jpg` |
| 11 | **GRASS `r.watershed` comparison table** | Terrain validation 2 | P2 | ☑ pysheds table, `tests/test_pysheds_crosscheck.py` (ADR 0015) |
| 12 | **Synthetic-DEM golden tests in CI** | Terrain validation 2 + Code 3 | P2 | ☑ 19 golden tests in CI |
| 13 | Pour-point sensitivity plot | Terrain validation 2 | P2 | ☑ `docs/figures/p2-pour-point-sensitivity.png` |
| 14 | Rainfall statistics table (75 % dependable) | FR5 4 | P3 | ☑ `GET /rainfall/statistics` + `p3-rainfall-panel.jpg` (45-yr ERA5-Land, Weibull 75 %) |
| 15 | Runoff three-method comparison range | FR6 5 | P3 | ☑ `p3-design-panel.jpg` methods table; `tests/test_runoff_flow.py` |
| 16 | EAV curve figure | FR7 6 | P3 | ☑ `p3-design-panel.jpg` EAV chart (SVG) |
| 17 | **Existing-pond comparison note** | FR7 6 + credibility | P3 | ☑ `docs/figures/p3-existing-pond-comparison.md` |
| 18 | AHP matrix + CR value | Code patterns 4 | P4 | ☑ default Saaty matrix + CR 0.011 in every suitability response (`ahp_matrix` warning); `app/engines/suitability/ahp.py` |
| 19 | NDWI water-mask before/after OpenCV cleanup | FR3 4 | P4 | ☑ `docs/figures/p4-ndwi-opencv.png` |
| 20 | ML AUC under spatial block CV | Validation 2 | P4 | ☐ not produced by design — ML deferred, ADR 0017 |
| 21 | SHAP explanation panel screenshot | FR3 | P4 | ◐ per-criterion contribution bars in the UI (screenshot at G5; browser throttled at capture time) — SHAP deferred with the ML path |
| 22 | All-overlays-on screenshot (six layers) | FR8 5 + FE 1 | P5 | ☑ `docs/figures/p5-all-overlays.jpg` |
| 23 | Phone-viewport screenshot | FE 1 | P5 | ☑ `docs/figures/p5-phone-390px.jpg` |
| 24 | Loading/error/stale state screenshots | FE 1 | P5 | ☑ progress bars with stage/percent on every job, offline badge (`p5-*`) |
| 25 | **Chaos test video** | Resilience 3 | P6 | ☑ `docs/media/chaos-test.gif` |
| 26 | Grafana dashboard screenshot | Observability 2 | P6 | ☑ `docs/figures/p6-grafana.jpg` |
| 27 | Locust load-test p95 numbers | Scalability 1 | P6 | ☑ `docs/figures/p6-locust.txt` — POST p95 33 ms, E2E p95 560 ms at 50 users |
| 28 | RBAC `403` demo + audit log rows | Security 2 | P6 | ☑ `tests/test_hardening.py`; `GET /recommendations/{id}/audit` |
| 29 | Coverage report screenshot (≥70 %) | Code testing 3 | P7 | ☑ `docs/figures/p7-coverage.jpg` — engines 94 %, domain 98 % |
| 30 | Installation guide with troubleshooting table | Docs install 2 | P7 | ☑ `README.md` — 14-row troubleshooting table |
| 31 | API cookbook + error catalogue | Docs API 2 | P7 | ☑ `docs/api/cookbook.md`, `errors.md`, `samples/` |
| 32 | Technical report with citations | Docs report 3 | P7 | ☑ `docs/report/REPORT.md` |
| 33 | Clean `git log` + conventional commits + v1.0 tag | Code Git 2 | P7 | ☑ tag `v1.0` |
| 34 | `docs/progress/DAY_NN.md` series | Feeds report | Daily | ☑ DAY_01–08 |
| 34a | P1 walking-skeleton screenshot — satellite + hillshade + summary card (`docs/figures/p1-walking-skeleton.jpg`) | FR1 3 · FE 1 | P1 | ☑ |
| 34b | ADR 0013 ports-and-adapters wiring; `tests/test_contour_job_flow.py` runs the real pipeline on the sample with no Docker | Code 2 · SysDes 1 | P1 | ☑ |

Added for the **Phase 2 submission**, which is graded separately (§4):

| # | Artifact | Defends | Phase | ✓ |
|---|---|---|---|---|
| 35 | `POST /analyzeContour` working on `data/samples/contours_1m.kml` | Working endpoint + catchment estimation | P2 | ☑ `make seed`; browser + API |
| 36 | Public URL for that route, reachable from another machine | Phase 2 report requirement | P2 | ◐ `make tunnel` (ngrok) — started on demo day, URL pasted into the report |
| 37 | A second contour KML (elevation in Z or `ExtendedData`, not `<name>`) parsing through the same code path | "Extensibility to generalized contour maps" | P2 | ☑ `tests/test_contour_kml.py` (Z, `ExtendedData`, KMZ, `<Folder>` root, ID decoy rejected) |
| 39 | Design brief + design-system bundle pushed to the AI design tool | Frontend 2 · UX 1 | P8 | ☑ `pond-planner-ui` (19 components, authored previews) synced to the AI design tool via the design-sync tooling |
| 40 | Landing-page prototype and coded page, screenshot pair | Frontend 2 | P8 | ☑ `p8-proto-landing.jpg` / `p8-landing.jpg` |
| 41 | Workspace redesign — six panel states, screenshot sheet | UX 1 | P8 | ☑ `p8-proto-states.jpg`, `p8-app-workspace.jpg`, `p8-app-design.jpg` |
| 42 | Lighthouse accessibility report ≥ 90 on `/` and `/app` | Frontend 1 | P8 | ☑ 100 / 100 — `docs/figures/p8-lighthouse-*.html` |
| 38 | Data-source licence register (SRTM · GMTED2010 · HydroSHEDS · Mapzen) | Docs report 3 | P7 | ☑ `docs/LICENSES.md` |
