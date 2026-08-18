# AI-BASED VILLAGE POND PLANNING SYSTEM
# MARKS-DRIVEN EXECUTION ROADMAP
### Detailed Phase-Wise Plan · Every Mark Accounted For

**Planning window:** 17 August → 5 September = **19 calendar days**
**Prototype demonstration:** lab hours (earliest credible: 24 Aug · ideal: 27 Aug)
**Final submission & demonstration:** 5 September

---

# PART 1 — RUBRIC DECOMPOSITION

The PDF gives six criteria totalling 100. Those are the *headline* buckets. Below is the decomposition I would use if I were grading this — build to this, and you cannot be surprised on submission day.

## 1.1 System Functionality — 35 marks

Marks here measure **breadth and whether each feature actually works end-to-end from the browser**. This is the largest bucket and the one where partial credit is easiest to lose (a feature that works in pytest but not in the UI scores near zero).

| Sub-item | Marks | What must be demonstrably true |
|---|---|---|
| FR1 Satellite imagery for selected village | 3 | Village selectable; imagery clipped to real boundary; not a static screenshot |
| FR2 Contour map visualization | 3 | Contours generated from *your* DEM pipeline; interval selectable; labelled |
| FR3 Identify available land for excavation | 4 | Ownership + slope + LULC + buffer + min-area filters applied; result rendered as polygons |
| FR4 Catchment area estimation | 5 | Click any point → correct upstream catchment polygon + area in hectares |
| FR5 Historical rainfall via public API | 4 | Live API call; ≥20 years; statistics computed (not just raw dump) |
| FR6 Runoff volume estimation | 5 | Rainfall × catchment × CN → volume in m³; method stated |
| FR7 Pond depth + storage capacity recommendation | 6 | Depth *derived*, not assumed; storage from EAV curve; dimensions given |
| FR8 Overlay all results on one map | 5 | All six PDF-listed overlays simultaneously toggleable + stats panel |

**Highest-value single item:** FR7 (6 marks). **Do not leave any FR at zero** — a crude working version of all eight beats four excellent ones.

## 1.2 Terrain and Catchment Analysis — 20 marks

Marks here measure **technical soundness of the geoprocessing**, separately from whether the button works. FR4/FR6/FR7 therefore earn twice — once for functioning, once for being correct.

| Sub-item | Marks | Evidence required |
|---|---|---|
| DEM acquisition & pre-processing (mosaic, clip, **UTM reprojection**, COG) | 3 | Pipeline code + CRS assertion tests |
| Hydrological conditioning (sink fill, flat resolution) | 3 | Before/after sink raster figure |
| Flow direction (D8) + flow accumulation + stream extraction | 4 | Flow-accumulation raster + streams overlaid on satellite (visual match) |
| Contour generation quality (smoothing, simplification) | 2 | Contour layer at 2 intervals; vertex-count reduction stated |
| Derived surfaces (slope, aspect, curvature, TWI) | 2 | All four rendered as layers |
| Catchment delineation correctness (snap-to-drainage + upstream traversal) | 4 | Algorithm code + snap distance surfaced in UI |
| **Accuracy validation** | 2 | GRASS `r.watershed` comparison + synthetic-DEM golden tests + sensitivity plot |

**Cheapest 2 marks in the entire rubric:** the validation row. One afternoon in QGIS produces a comparison table that almost no student submits.

## 1.3 Frontend and Visualization — 5 marks

| Sub-item | Marks |
|---|---|
| Interactive map with working layer control | 2 |
| Analysis panel + charts (rainfall, EAV curve) | 1 |
| UX quality: loading/empty/error states, mobile viewport | 1 |
| Overlay integration & readability (FR8 done *well*) | 1 |

⚠️ **Only 5 marks.** Cap frontend effort at 2 days via the AI design tool. It is, however, the surface your demo runs on — so it punches above its weight in the *functionality* demonstration.

## 1.4 Software Design and Code Quality — 15 marks

| Sub-item | Marks | Evidence |
|---|---|---|
| Layered architecture & separation of concerns | 3 | Repo tree; routers contain zero business logic |
| Design patterns applied meaningfully (not decoratively) | 4 | Patterns table in report + pattern named in each class docstring |
| Code quality: typing, lint, naming, function/module size | 3 | `ruff` clean, `mypy --strict` on `domain/`, CI badge |
| Testing: coverage + golden/property tests | 3 | ≥70 % on `engines/`; coverage report screenshot |
| Repo & Git hygiene | 2 | Conventional commits, feature branches, no secrets/binaries, README |

## 1.5 System Design and Management — 15 marks

| Sub-item | Marks | Evidence |
|---|---|---|
| Async job architecture (queues, `202`, progress, bulkhead) | 3 | Job flow demo with real percentages |
| Resilience (circuit breaker, retry, fallback chain, graceful degradation) | 3 | **Chaos test video** |
| Data layer design (schema, spatial indexes, caching strategy) | 2 | DDL + cache-hit metric |
| Security (JWT, RBAC, audit log, upload hardening) | 2 | Role-gated route demo + audit log rows |
| Observability (structured logs, metrics, health checks) | 2 | Grafana dashboard screenshot |
| DevOps (Docker Compose, CI, one-command install) | 2 | `make up` from clean clone |
| Scalability reasoning & documented decisions (ADRs) | 1 | 12 ADRs + scaling arithmetic table |

## 1.6 Documentation and Report — 10 marks

| Sub-item | Marks |
|---|---|
| Installation guide (reproducible, with troubleshooting) | 2 |
| API documentation (OpenAPI + curl cookbook + error catalogue) | 2 |
| Technical report: structure, methodology, **citations** | 3 |
| Validation & results section with real numbers | 2 |
| Architecture docs + ADRs | 1 |

---

# PART 2 — MARKS-TO-PHASE MATRIX

## 2.1 Where each phase earns

| Phase | Dates | Days | Func /35 | Terrain /20 | FE /5 | Code /15 | SysDes /15 | Docs /10 | **Phase total** |
|---|---|---|---|---|---|---|---|---|---|
| **P0** Foundations & Contract | 17–18 Aug | 2 | — | — | — | 5 | 4 | 2 | **11** |
| **P1** Walking Skeleton | 19–20 Aug | 2 | 3 | 3 | 1 | 2 | 1 | — | **10** |
| **P2** Terrain & Catchment ⭐ | 21–24 Aug | 4 | 8 | 17 | 1 | 3 | 1 | — | **30** |
| **P3** Rainfall · Runoff · Design ⭐ | 25–27 Aug | 3 | 15 | — | 1 | 2 | 1 | — | **19** |
| **P4** Suitability & AI | 28–29 Aug | 2 | 4 | — | — | 2 | 1 | — | **7** |
| **P5** Frontend Integration | 30–31 Aug | 2 | 5 | — | 2 | — | — | — | **7** |
| **P6** System Hardening ⭐ | 1–2 Sept | 2 | — | — | — | 1 | 6 | — | **7** |
| **P7** Tests · Docs · Report | 3–4 Sept | 2 | — | — | — | — | — | 8 | **8** |
| **5 Sept** | Submit | — | | | | | | | **100** |

## 2.2 Cumulative burn-up (use this as your tracker)

| By end of | Marks secured | % of total | Status if you're here |
|---|---|---|---|
| 18 Aug (P0) | 11 | 11 % | On track |
| 20 Aug (P1) | 21 | 21 % | On track — **integration risk eliminated** |
| 24 Aug (P2) | 51 | 51 % | ✅ Halfway. Minimum viable prototype demo possible |
| 27 Aug (P3) | 70 | 70 % | ✅ **Ideal prototype demo point** — all core hydrology working |
| 29 Aug (P4) | 77 | 77 % | Comfortable |
| 31 Aug (P5) | 84 | 84 % | All 8 FRs demonstrable |
| 2 Sept (P6) | 91 | 91 % | Architecture marks banked |
| 4 Sept (P7) | 100 | 100 % | Submit-ready |

**The critical observation:** P2 + P3 together are worth **49 marks in 7 days**. That is where your best hours must go. Everything before them is enablement; everything after is packaging.

## 2.3 Mark efficiency — work that earns in two buckets at once

Prioritise these; they are the highest return per hour in the project.

| Single piece of work | Earns in | Total |
|---|---|---|
| Catchment engine (snap + BFS + validation) | Func FR4 (5) + Terrain delineation (4) + Terrain validation (2) | **11** |
| Pond design engine (EAV + optimiser) | Func FR7 (6) + Code patterns/Builder (1) | **7** |
| Docker Compose + Makefile | SysDes DevOps (2) + Docs install guide (2) | **4** |
| FastAPI auto-OpenAPI (free by choosing FastAPI) | Docs API (2) + Code contract-first (1) | **3** |
| Runoff engine with 3 Strategy methods | Func FR6 (5) + Code patterns (1) | **6** |
| Chaos test (kill network, cached fallback) | SysDes resilience (3) + demo impact | **3** |
| Progress log `docs/progress/DAY_NN.md` | Docs report (≈3 of the 5 report marks written for free) | **~3** |

---

# PART 3 — PHASE-BY-PHASE DETAILED PLAN

---

## ⬛ PHASE 0 — Foundations & Contract
**17–18 August · 2 days · 11 marks at stake**
`Code quality 5 · System design 4 · Documentation 2`

### Objective
Make the skeleton compile, CI green, and **the entire API contract exist as mock endpoints** — so the frontend can be built in the AI design tool from Day 1 and never blocks on the backend.

### Day 1 (17 Aug)

| # | Task | Earns |
|---|---|---|
| 1 | Create monorepo tree exactly as in the LLD (`api/ core/ domain/ schemas/ engines/ providers/ repositories/ jobs/ reports/`) | Code: layering 3 |
| 2 | `infra/docker-compose.yml`: postgres+postgis+timescale, redis, minio, api, worker, titiler, martin, nginx | SysDes DevOps 2 |
| 3 | `Makefile`: `up down seed test lint migrate` | SysDes DevOps (same 2) |
| 4 | `.env.example`, Pydantic `Settings` (12-factor config), structured logging skeleton | Code 1 |
| 5 | Alembic initialised; first migration with `villages`, `jobs`, `audit_log` | SysDes data 1 |
| 6 | `git init`, `.gitignore`, conventional-commit convention documented in CONTRIBUTING.md | Code: Git 2 |

### Day 2 (18 Aug)

| # | Task | Earns |
|---|---|---|
| 7 | **Define all ~25 endpoints** from the HLD as FastAPI routes returning realistic hardcoded fixtures | Docs API 2 |
| 8 | Write the fixture pack: one village's worth of realistic JSON (esp. the full `pond-design` payload) | Enables P5 |
| 9 | GitHub Actions CI: `ruff` + `mypy --strict app/domain` + `pytest` | Code 3 |
| 10 | Write **12 ADRs** (one page each, from the HLD decision table) | SysDes 1 |
| 11 | `docs/progress/DAY_01.md` — start the log habit today | Docs (compounds) |
| 12 | Push. Confirm CI badge green. | Code |

### Exit gate — do not proceed until all true
- [ ] Fresh `git clone` → `make up` → Swagger UI at `/docs` shows every endpoint returning fixtures
- [ ] CI green on main
- [ ] 12 ADR files committed
- [ ] You can hand the fixture JSON to the AI design tool and start the frontend **in parallel from tomorrow**

### Artifacts produced
`repo tree` · `docker-compose.yml` · `Makefile` · `openapi.json` · `docs/adr/0001–0012` · CI badge

### Mark leakage warning
Skipping the contract step feels efficient and costs you 3–4 days later, because the frontend then cannot start until P4. **This phase is not overhead; it is the parallelism unlock.**

---

## ⬛ PHASE 1 — Walking Skeleton
**19–20 August · 2 days · 10 marks at stake**
`Functionality 3 (FR1) · Terrain 3 · Frontend 1 · Code 2 · SysDes 1`

### Objective
Real DEM → real terrain → real browser. Thin, ugly, but **end-to-end**. This is the phase that eliminates integration risk.

### Day 1 (19 Aug)

| # | Task | Earns |
|---|---|---|
| 1 | **Choose your village.** Criteria: visible drainage lines in satellite view, an existing pond nearby for later validation, ideally somewhere you know the ground. Save boundary as `fixtures/village.geojson`. | FR1 |
| 2 | `DEMProvider` Protocol + `CopernicusAdapter` / `ALOSAdapter` → download tiles for bbox | Terrain 3 |
| 3 | Pipeline stages 1–4: **mosaic → clip (boundary + 500 m buffer) → reproject to UTM 44N/45N → write COG → MinIO** | Terrain 3 |
| 4 | **Write the `assert_crs()` guard utility now.** Every array entering a computation must be UTM. | Terrain / prevents C8 |
| 5 | Persist `dem_assets` row (source, resolution, vertical RMSE, bbox) | SysDes data |

### Day 2 (20 Aug)

| # | Task | Earns |
|---|---|---|
| 6 | Hillshade derivation → COG → **TiTiler** raster tile endpoint | Terrain |
| 7 | `GET /villages/{id}/summary` real (area, elev min/max/mean, mean slope) | FR1 |
| 8 | Frontend v0: MapLibre + Esri satellite basemap + village boundary + hillshade overlay + layer toggle | FR1 3 · FE 1 |
| 9 | First screenshot into `docs/progress/` | Docs |

### Exit gate
- [ ] Browser shows **real satellite imagery + real hillshade** derived by your own pipeline
- [ ] **FR1 complete (3 marks banked)**
- [ ] CRS guard has a unit test that fails on an EPSG:4326 array
- [ ] End-to-end path proven: browser → API → worker → MinIO → tile → browser

### Artifacts
Village COG in MinIO · hillshade tiles · first UI screenshot · `dem_assets` row

### Mark leakage warning
Do **not** polish the frontend here. Do **not** add a second village. The only goal is that the wire runs end to end.

---

## ⬛ PHASE 2 — Terrain & Catchment Engine ⭐ HIGHEST VALUE
**21–24 August · 4 days · 30 marks at stake**
`Functionality 8 (FR2 3 + FR4 5) · Terrain 17 · Frontend 1 · Code 3 · SysDes 1`

### Objective
The technical heart. 30 marks in 4 days — the densest phase in the project. Budget your best hours here.

### Day 1 (21 Aug) — Hydrological conditioning · Terrain 3

| # | Task |
|---|---|
| 1 | Priority-flood sink filling (`pysheds.fill_depressions` or `richdem`) |
| 2 | Flat resolution (`resolve_flats`) — impose micro-gradient |
| 3 | Save **before/after difference raster** and render it → report figure |
| 4 | Unit test: a synthetic DEM with a known artificial pit is correctly filled |

### Day 2 (22 Aug) — Flow modelling · Terrain 4

| # | Task |
|---|---|
| 5 | `FlowRoutingStrategy` Protocol; `D8Strategy` implementation (numba `@njit`) |
| 6 | Flow accumulation via topological in-degree queue |
| 7 | Stream extraction by accumulation threshold — **calibrate the threshold by overlaying computed streams on satellite imagery and tuning until they match visible nallahs. Document the calibration.** |
| 8 | Vectorize streams → PostGIS → Strahler order → serve as MVT via Martin |
| 9 | Leave `DInfStrategy` as a documented stub (evidence of extensibility) |

### Day 3 (23 Aug) — Derived surfaces & contours · Terrain 4 · FR2 3

| # | Task |
|---|---|
| 10 | Slope (Horn 3×3), aspect, plan + profile curvature, **TWI = ln(a/tanβ)** |
| 11 | Each as COG → TiTiler layers |
| 12 | **Contours:** Gaussian-smooth DEM → `gdal_contour` → Douglas–Peucker simplify → GeoJSON → PostGIS → MVT. Selectable interval 1/2/5/10 m. Record vertex-count reduction (e.g. 48,000 → 900). |
| 13 | Frontend: contour layer with elevation labels + interval selector → **FR2 done** |

### Day 4 (24 Aug) — Catchment delineation · Terrain 4+2 · FR4 5

| # | Task |
|---|---|
| 14 | **Snapper:** 5×5 window max-accumulation search; return `snap_distance_m`; reject if max acc < 30 cells ("no drainage at this point") |
| 15 | **Delineator:** BFS over inverse D8 → boolean mask |
| 16 | Polygonize (`rasterio.features.shapes`) → dissolve → simplify → area_ha, mean slope, elevation range, LULC histogram |
| 17 | Cache-aside keyed on `(village_id, snapped_cell)` — unique index in DB |
| 18 | Async job wired: `POST /analysis/catchment` → `202` → poll → render polygon in UI → **FR4 done** |

### ⭐ Validation block — 2 marks, ~3 hours, almost nobody does it

| # | Task | Deliverable |
|---|---|---|
| V1 | **Synthetic DEM golden tests:** generate an inclined plane and a cone where the true catchment area is analytically computable. Assert your algorithm matches. Add to CI. | `tests/golden/test_synthetic_dems.py` |
| V2 | **Cross-validate against GRASS:** run the same DEM through QGIS → GRASS `r.watershed`. Compare catchment area and stream network. Report the % delta. | Comparison table + side-by-side map figure |
| V3 | **Sensitivity analysis:** move the pour point ±3 cells in each direction; plot resulting catchment area. Documents Challenge C3 with real data. | Sensitivity plot |

### Exit gate
- [ ] Click any point → catchment polygon in **< 5 s** (cached < 2 s)
- [ ] Catchment area within **±15 %** of GRASS on the test village
- [ ] Synthetic golden tests passing in CI
- [ ] Contours, streams, slope, curvature, TWI all rendering as toggleable layers
- [ ] Snap distance visible in the UI
- [ ] **FR2 + FR4 complete · 51 cumulative marks secured**

### Artifacts
Sink before/after figure · flow-accumulation raster image · streams-vs-satellite overlay · contour layer at 2 intervals · GRASS comparison table · sensitivity plot · golden tests in CI

### Mark leakage warnings
- **Skipping threshold calibration** costs Terrain marks — an uncalibrated stream network is visibly wrong and an evaluator will see it.
- **Skipping the snap step** produces catchments that vary 100× on adjacent clicks. This is the single most visible correctness failure in the whole project.
- **Skipping validation** leaves 2 easy marks and, worse, means you cannot defend any number in your viva.

### 🚦 Checkpoint (end 24 Aug): if P2 is not complete, you have a **minimum viable prototype demo** (FR1, FR2, FR4) — enough for lab hours. Do not proceed to P3 until the P2 exit gate is fully green; a broken catchment engine invalidates everything downstream.

---

## ⬛ PHASE 3 — Rainfall · Runoff · Pond Design ⭐
**25–27 August · 3 days · 19 marks at stake**
`Functionality 15 (FR5 4 + FR6 5 + FR7 6) · Frontend 1 · Code 2 · SysDes 1`

### Objective
Turn terrain into water numbers. Highest functionality density in the project: 15 of the 35 functionality marks in 3 days.

### Day 1 (25 Aug) — Rainfall · FR5 4

| # | Task |
|---|---|
| 1 | `RainfallProvider` Protocol + `OpenMeteoAdapter` (ERA5-Land, free, no key, daily from 1950) |
| 2 | `NASAPowerAdapter` as fallback |
| 3 | Stack decorators: `Cached(ttl=1d) ∘ CircuitBreaker(5,300s) ∘ Retry(3, jitter)` |
| 4 | `FallbackChain([open_meteo, nasa_power, cache_only])` recording provenance |
| 5 | Persist to TimescaleDB hypertable + continuous aggregate for monthly |
| 6 | **Statistics engine:** mean annual · **75 % dependable (Weibull `m/(n+1)`)** · CV · JJAS monsoon share · rainy days (≥2.5 mm) · max 1-day · 25-yr IDF intensity |
| 7 | `GET /rainfall/statistics` + frontend bar chart + stats card → **FR5 done** |

### Day 2 (26 Aug) — Runoff · FR6 5

| # | Task |
|---|---|
| 8 | Fetch ESA WorldCover LULC (10 m) + FAO HWSD soil → derive **Hydrologic Soil Group A/B/C/D** |
| 9 | **CN grid** = frozen lookup `{(lulc, hsg): CN}` (Flyweight); area-weighted CN over catchment |
| 10 | AMC I/II/III adjustment |
| 11 | **`SCSCNMethod`: apply on the DAILY series then sum.** `Q = (P−Iₐ)²/(P−Iₐ+S)` where `S = 25400/CN − 254`, `Iₐ = 0.2S`. **Never on annual totals** — that overestimates 2–3×. |
| 12 | `RationalMethod` + `StrangeMethod` as Strategy implementations |
| 13 | Report a **range across the three methods** × harvest efficiency 0.5–0.7, not a single false-precision number |
| 14 | `POST /analysis/runoff` + frontend method-comparison panel → **FR6 done** |

### Day 3 (27 Aug) — Pond design · FR7 6

| # | Task |
|---|---|
| 15 | **EAV curve:** flood-fill (8-connected `scipy.ndimage.label`) from pond point over cells ≤ level, levels 0.25 m steps → Area(h), Volume(h) |
| 16 | **Frustum solver** (prismoidal) for excavated ponds on flat ground |
| 17 | **Depth optimiser:** grid search D∈[1.5,3.5] step 0.25 × aspect ratio ∈[1,2]; minimise `c_exc·V_exc + c_emb·V_emb` subject to `V_storage ≥ V_target`, `z ≥ 1.5`, minimise surface area (evaporation) |
| 18 | **Losses:** evaporation (0.7 × pan) + seepage (1–3 mm/day) + dead storage (10–20 % silt) → **net usable** |
| 19 | **25-year daily water balance → fill reliability %**, months-with-water, average spill |
| 20 | Spillway sizing (weir equation, 25-yr peak) + **BoQ** (excavation m³, embankment m³, cost) |
| 21 | `PondDesignBuilder` assembles it all; `POST /analysis/pond-design` returns the full payload |
| 22 | Frontend: EAV curve chart + design card + reliability gauge + warnings array → **FR7 done** |

### ⭐ Reality check (30 minutes, high value)
Take a **real existing pond** near your village. Feed its location into your system. Compare computed storage against its actual approximate size. **Document the comparison honestly, including the error.** This is the single most persuasive paragraph you can put in your report.

### Exit gate
- [ ] `POST /analysis/pond-design` returns the complete payload (catchment + rainfall + runoff + design + reliability + BoQ + warnings + confidence label)
- [ ] Three runoff methods produce a documented range
- [ ] Existing-pond comparison recorded
- [ ] **FR5 + FR6 + FR7 complete · 70 cumulative marks secured**

### Artifacts
Rainfall statistics table · EAV curve figure · runoff method comparison · existing-pond validation note · full JSON payload sample for the API cookbook

### 🚦 **IDEAL PROTOTYPE DEMO POINT (27 Aug).** Five of eight FRs working with real hydrology. If lab hours fall here, you demo from a position of strength.

---

## ⬛ PHASE 4 — Suitability & AI Layer
**28–29 August · 2 days · 7 marks at stake**
`Functionality 4 (FR3) · Code 2 · SysDes 1`

### Objective
The "AI-based" in the project title, plus FR3. Compressed to 2 days — this phase has a designed fallback if time runs short.

### Day 1 (28 Aug) — Constraints + MCDA · FR3 4

| # | Task |
|---|---|
| 1 | **Specification-pattern constraints:** `SlopeUnder(15) & IsGovernmentLand() & MinContiguousArea(2500) & ~WithinBuffer("water",150) & MinFlowAcc(100) & HabitationDistance(100,2000)` with `__and__ __or__ __invert__` |
| 2 | Parcel upload endpoint (`POST /villages/{id}/parcels:import`, multipart SHP/GeoJSON) with driver whitelist + zip-entry validation + size cap |
| 3 | `GET /villages/{id}/available-land` → eligible polygons → frontend layer → **FR3 done** |
| 4 | Fuzzy trapezoidal membership functions (slope optimum is a **plateau at 1–3 %**, not a max at 0) |
| 5 | **AHP:** Saaty pairwise matrix → principal eigenvector → **Consistency Ratio check, assert CR < 0.10**. Put the matrix and CR value in the report. |
| 6 | Weighted linear combination → suitability raster → COG → TiTiler heat-map layer |

### Day 2 (29 Aug) — CV + ML + site extraction

| # | Task |
|---|---|
| 7 | Sentinel-2 via STAC → **NDWI/MNDWI** → Otsu threshold (`cv2.threshold(...OTSU)`) → **OpenCV** `morphologyEx` open/close → `connectedComponentsWithStats`, reject <200 m² → pre/post-monsoon composites → seasonal vs perennial |
| 8 | Weak-supervision labels: detected tanks + OSM water = positives; sampled eligible mask = background |
| 9 | XGBoost on feature stack (slope, curvature, TWI, flow acc, dist-to-stream, CN, HSG, LULC one-hot, relative elevation); **spatial block CV (1 km GroupKFold)** — never random k-fold; report AUC honestly |
| 10 | SHAP explainer → per-site contributions |
| 11 | Hybrid blend `S = α·AHP + (1−α)·ML`, α configurable |
| 12 | **Non-max suppression** (200 m radius, KD-tree) → Top-N ranked sites |
| 13 | Frontend: ranked site list + "why this site?" SHAP panel |

### Exit gate
- [ ] `POST /analysis/suitability` → ranked sites with per-criterion breakdown
- [ ] Suitability heat-map renders
- [ ] **FR3 complete · 77 cumulative marks secured**
- [ ] Sanity test recorded: **do your top-ranked sites land near existing tanks?** Either answer is a good report paragraph.

### Designed fallback (use without guilt)
If the ML underperforms or time runs out: **ship AHP-only with α = 1.0.** Because scoring is behind a Strategy interface, this is a documented engineering decision, not a failure. State it in the report: *"ML path implemented and evaluated; AUC under spatial CV was X, below the threshold for production use, so the AHP path ships by default with the ML path available behind a feature flag."* That sentence earns code-quality marks rather than losing functionality marks.

---

## ⬛ PHASE 5 — Frontend Integration
**30–31 August · 2 days · 7 marks at stake**
`Functionality 5 (FR8) · Frontend 2`

### Objective
FR8 (all overlays on one map) + the 5 frontend marks. Built in **the AI design tool**, wired to the real API.

### What to give the AI design tool
1. **The actual fixture JSON** from P0 (the full `pond-design` payload). Designing against real data shapes prevents rework.
2. **Specific visual direction**, not "make it nice": *"Government utility tool, not a consumer app. Dense information. High contrast for outdoor phone screens in sunlight. Earth/water palette, one accent colour for the primary action. Devanagari-capable typeface (Noto Sans / Mukta). Map occupies 65 % of viewport."*
3. **Named states for every panel:** loading, empty, error, stale-data, offline, job-in-progress-with-percentage. Ask for these explicitly — they are the 1 UX mark, and they're what separates a mockup from a product.

### Build order (one screen at a time, iterate before moving on)

| Step | Screen | Why this order |
|---|---|---|
| 1 | Map workspace shell + layer control | Everything hangs off it |
| 2 | Analysis panel (rainfall · runoff · EAV · design · reliability · warnings) | Densest information design |
| 3 | Village selector + readiness/progress | Entry point, simple |
| 4 | Site comparison (up to 3) | Reuses analysis components |
| 5 | Report/export + Hindi toggle | Polish |

### Day 2 (31 Aug) — wire-up

| # | Task |
|---|---|
| 1 | Generate typed client: `openapi-typescript` + `openapi-fetch` from your OpenAPI spec |
| 2 | Flip mock base URL → real API |
| 3 | TanStack Query for the `202 → poll /jobs/{id}` pattern + WebSocket progress |
| 4 | MVT layers (contours, streams, parcels, sites) + raster layers (hillshade, slope, TWI, suitability) |
| 5 | Show **snapped point + snap distance** — makes Challenge C3 visible rather than mysterious |
| 6 | Plain-language verdict strings: not "75 % dependable rainfall: 968 mm" but "*In 3 of every 4 years, expect at least 968 mm*" |
| 7 | Service-worker tile caching (PWA) |
| 8 | Test on a phone-sized viewport |

### Exit gate
- [ ] **All six PDF-listed overlays simultaneously toggleable** (pond location, catchment, rainfall stats, runoff volume, pond dimensions, maps) → **FR8 done**
- [ ] Every panel has a designed loading and error state
- [ ] Works at 390 px width
- [ ] **All 8 FRs demonstrable · 84 cumulative marks secured**

### Mark leakage warning
Do not exceed 2 days here. Frontend is 5 marks; P6 (system hardening) is 7 and P7 (docs) is 8. Overrunning here is the most common way strong developers lose marks on this assignment.

---

## ⬛ PHASE 6 — System Design Hardening ⭐
**1–2 September · 2 days · 7 marks at stake**
`SysDes 6 · Code 1`

### Objective
Two focused days that bank the "System Design and Management" marks. Highest return per hour after P2.

### Day 1 (1 Sept)

| # | Task | Earns |
|---|---|---|
| 1 | **Bulkhead queues live:** separate `interactive` (catchment, <5 s) and `heavy` (village prep, minutes) Celery queues. Prove one cannot starve the other. | Async 3 |
| 2 | WebSocket job progress (Observer pattern) with **real percentages** from a stage-weight table | Async 3 |
| 3 | **Saga** for village onboarding: 9 steps, each idempotent (skip-if-exists), each with a compensating rollback | Async / Code |
| 4 | Idempotency keys on all POST analyses (double-tap on a phone must not queue two 60 s jobs) | Async |
| 5 | JWT (RS256, 15 min access + 7 d refresh) + RBAC dependency `require_role("officer")` | Security 2 |
| 6 | Site **State machine** with illegal-transition tests (cannot sanction an unverified site) | Security / Code |
| 7 | **Outbox → immutable audit log** (append-only, no UPDATE/DELETE grants) | Security 2 |

### Day 2 (2 Sept)

| # | Task | Earns |
|---|---|---|
| 8 | structlog JSON logging with request/job correlation IDs | Observability 2 |
| 9 | Prometheus `/metrics` + **one Grafana dashboard**: queue depth, job duration p50/p95, provider error rate, cache hit rate → **screenshot for report** | Observability 2 |
| 10 | `/health` (liveness) + `/ready` (dependency check) | Observability |
| 11 | Leader-elected nightly rainfall refresh (Redis lock) — the correct answer to "what if you run 10 workers?" | Scalability 1 |
| 12 | Backpressure: queue depth > threshold → `429 + Retry-After` | Resilience 3 |
| 13 | **Locust load test:** 50 concurrent catchment requests → record p95 → into the report | Scalability 1 |
| 14 | ⭐ **CHAOS TEST:** `docker network disconnect` the API from the internet. Reload the app. It must still serve cached results with a staleness badge. **Record this as a video.** | Resilience 3 |
| 15 | Verify `make up` from a clean clone still works after all changes | DevOps 2 |

### Exit gate
- [ ] Chaos test passes and is recorded
- [ ] Grafana screenshot captured
- [ ] Load-test numbers recorded
- [ ] RBAC demo: viewer role gets `403` on the approval route
- [ ] Audit log shows rows for every recommendation and status change
- [ ] **91 cumulative marks secured**

### Why the chaos test matters disproportionately
It is 30 seconds of your demo that proves the architecture is real rather than described. It converts an abstract claim ("resilient design") into an observed fact. Nothing else in the project has that ratio of impact to effort.

---

## ⬛ PHASE 7 — Tests · Documentation · Report · Demo Prep
**3–4 September · 2 days · 8 marks at stake**
`Documentation 8`

### Day 1 (3 Sept) — Tests + docs

| # | Task | Earns |
|---|---|---|
| 1 | Push coverage to **≥70 % on `engines/` and `domain/`**; capture coverage report screenshot | Code testing 3 (banked earlier, confirmed here) |
| 2 | Confirm test taxonomy complete: golden (synthetic DEM, frustum vs hand calc, known-area polygon, CN snapshot) · property (Hypothesis: runoff monotonic in P, EAV monotonic in level) · contract (recorded adapter fixtures) · integration · E2E (Playwright happy path) | Code |
| 3 | `mypy --strict` clean on `domain/`; `ruff` clean everywhere | Code |
| 4 | **Installation guide:** prerequisites → `make up` → `make seed` → verification checklist → troubleshooting table (min 6 common failures) | Docs 2 |
| 5 | **API cookbook:** curl request/response for every major endpoint + full error catalogue (RFC 7807 `type` codes) | Docs 2 |
| 6 | MkDocs site: architecture, 12 ADRs, algorithms with equations, data-source licence register, patterns table | Docs 1 |

### Day 2 (4 Sept) — Report + demo prep

**Technical report structure (Docs 3 + 2):**

| § | Content | Marks |
|---|---|---|
| 1 | Problem statement & objectives | Report 3 |
| 2 | Methodology basis with **real citations**: SCS-CN (USDA NRCS TR-55), D8 (O'Callaghan & Mark 1984), AHP (Saaty 1980), Weibull plotting position, priority-flood (Wang & Liu 2006) | Report 3 |
| 3 | Architecture + **design patterns table** + ADR summary | Report 3 |
| 4 | Algorithms with equations (§B.7 of the HLD) | Report 3 |
| 5 | ⭐ **Validation & Results** — GRASS delta table, synthetic golden tests, pour-point sensitivity plot, existing-pond comparison, load-test p95, ML AUC under spatial CV | **Validation 2** |
| 6 | Limitations & honest uncertainty (planning-grade, ±15 % catchment, ±20 % storage, cadastral data caveat) | Report |
| 7 | Future work: the distributed roadmap (Part 4 below) | Report |

**Demo preparation:**

| # | Task |
|---|---|
| 7 | `make seed` **pre-computes 2–3 demo villages fully offline** — nothing depends on live internet |
| 8 | Rehearse the demo end-to-end, timed, **three times** |
| 9 | Record a **backup video** of the full flow; have it open in another browser tab |
| 10 | `git tag v1.0`; clean `git log`; README with screenshots and a GIF |
| 11 | Final `docs/progress/` review — your daily log is now most of the report's narrative |

### Exit gate
- [ ] Fresh clone on a different machine → `make up` → `make seed` → working system
- [ ] Report complete with a Validation section containing **real numbers**
- [ ] Demo rehearsed 3× and backup video recorded
- [ ] **100 marks accounted for**

---

# PART 4 — PROTOTYPE DEMONSTRATION PLAN

The PDF schedules the prototype demo in lab hours (date unspecified). Prepare for two scenarios.

## 4.1 Readiness by date

| If lab hours fall on | You can demo | Grade posture |
|---|---|---|
| ≤ 20 Aug | FR1 only + architecture walkthrough + Swagger | Weak — lead with the architecture and the plan |
| 24 Aug | FR1, FR2, FR4 + validation evidence | **Acceptable** — "core terrain engine validated against GRASS" |
| 27 Aug | FR1, FR2, FR4, FR5, FR6, FR7 | ✅ **Strong** — full hydrology chain working |
| ≥ 31 Aug | All 8 FRs | ✅ **Excellent** |

## 4.2 Demo script (7 minutes)

| # | Time | Show | Say |
|---|---|---|---|
| 1 | 0:30 | Satellite image of a **real failed pond** that never fills | "Built in the wrong place. That's public money in a dry hole." |
| 2 | 0:45 | Select village → satellite + contours + streams appear | "All derived from a free 12.5 m DEM. Nothing drawn by hand." |
| 3 | 1:30 | Suitability heat-map → click top-ranked site | "Red zones are excluded — private land, too steep, too near an existing tank." |
| 4 | 1:30 | Catchment → runoff → depth → **"fills in 22 of 25 years"** | "That's the number an administrator actually cares about." |
| 5 | 0:45 | SHAP "why this site" panel | "Not a black box. Every recommendation explained and auditable." |
| 6 | 0:45 | **Kill the network. Reload. Still works, staleness badge.** | "Circuit breaker with cached fallback. Village internet is 2G and intermittent." |
| 7 | 0:45 | Grafana dashboard + Swagger UI | "Async worker pool, bulkhead queues, full observability." |
| 8 | 0:30 | Export PDF with BoQ | "Attaches directly to an MGNREGA work proposal." |

**Three rules:** never demo on live external APIs (pre-seed everything) · keep the backup video open in another tab · end on the export, because that's the moment it stops looking like a student project.

---

# PART 5 — EVIDENCE REGISTER

Every mark needs an artifact an evaluator can see. Keep this table in `docs/evidence.md` and tick as you go.

| # | Artifact | Defends | Produced in |
|---|---|---|---|
| 1 | Repo tree + routers with zero business logic | Code layering 3 | P0 |
| 2 | `docker-compose.yml` + `Makefile` | SysDes DevOps 2 + Docs install 2 | P0 |
| 3 | 12 ADR files | SysDes scalability 1 + Docs 1 | P0 |
| 4 | CI badge (ruff + mypy + pytest) | Code quality 3 | P0 |
| 5 | `openapi.json` + Swagger screenshot | Docs API 2 | P0 |
| 6 | Sink fill before/after raster figure | Terrain 3 | P2 |
| 7 | Flow-accumulation raster image | Terrain 4 | P2 |
| 8 | Streams overlaid on satellite (visual match) | Terrain 4 | P2 |
| 9 | Contour layer at 2 intervals + vertex-reduction figure | Terrain 2 + FR2 3 | P2 |
| 10 | Slope/aspect/curvature/TWI layer screenshots | Terrain 2 | P2 |
| 11 | **GRASS `r.watershed` comparison table** | Terrain validation 2 | P2 |
| 12 | **Synthetic-DEM golden tests in CI** | Terrain validation 2 + Code 3 | P2 |
| 13 | Pour-point sensitivity plot | Terrain validation 2 | P2 |
| 14 | Rainfall statistics table (75 % dependable etc.) | FR5 4 | P3 |
| 15 | Runoff three-method comparison range | FR6 5 | P3 |
| 16 | EAV curve figure | FR7 6 | P3 |
| 17 | **Existing-pond comparison note** | FR7 6 + report credibility | P3 |
| 18 | AHP matrix + CR value | Code patterns 4 + report | P4 |
| 19 | NDWI water-mask before/after OpenCV cleanup | FR3 4 | P4 |
| 20 | ML AUC under spatial block CV | Report validation 2 | P4 |
| 21 | SHAP explanation panel screenshot | FR3 + report | P4 |
| 22 | All-overlays-on screenshot (six layers) | FR8 5 + FE 1 | P5 |
| 23 | Phone-viewport screenshot | FE 1 | P5 |
| 24 | Panel loading/error/stale state screenshots | FE 1 | P5 |
| 25 | **Chaos test video** | SysDes resilience 3 | P6 |
| 26 | Grafana dashboard screenshot | SysDes observability 2 | P6 |
| 27 | Locust load-test p95 numbers | SysDes scalability 1 | P6 |
| 28 | RBAC `403` demo + audit log rows | SysDes security 2 | P6 |
| 29 | Coverage report screenshot (≥70 %) | Code testing 3 | P7 |
| 30 | Installation guide with troubleshooting table | Docs install 2 | P7 |
| 31 | API cookbook + error catalogue | Docs API 2 | P7 |
| 32 | Technical report with citations | Docs report 3 | P7 |
| 33 | Clean `git log` + conventional commits + v1.0 tag | Code Git 2 | P7 |
| 34 | `docs/progress/DAY_01..19.md` | Feeds report | Daily |

---

# PART 6 — CONTINGENCY LADDER

## 6.1 Cut order (if behind schedule) — never cut upward

| Cut # | Feature | Marks lost | Why it's safe |
|---|---|---|---|
| 1 | Cascade correction | 0 | Not a PDF requirement; describe as designed future work |
| 2 | Water-balance / fill-reliability simulation | ~1 | FR7 satisfied by storage capacity alone |
| 3 | ML/XGBoost scoring (ship AHP, α=1.0) | 0 | Strategy pattern makes it a documented choice |
| 4 | Site comparison screen | ~1 | Not a PDF requirement |
| 5 | Hindi i18n depth (keep toggle + one screen) | ~0.5 | Proof of capability suffices |
| 6 | D-∞ flow routing | 0 | Strategy stub is evidence of extensibility |
| 7 | Cascade + water balance + compare together | ~2 | Recovers ~1.5 days |

**NEVER cut:** any of FR1–FR8 · the async job architecture · the GRASS validation · the installation guide · hydrology golden tests · the chaos test.

## 6.2 Floor scenarios

| Scenario | What you ship | Estimated marks |
|---|---|---|
| **Disaster floor** — only P0–P2 complete | FR1, FR2, FR4 + full architecture + docs + validation | **~58** |
| **Realistic floor** — P0–P3 + P7 | 5 of 8 FRs + architecture + docs + validation | **~74** |
| **Target** — all phases | All 8 FRs + hardening + full docs | **~95+** |

> **The rule:** all eight FRs working simply beats five working beautifully. "System functionality" is 35 marks and it measures **breadth**.

---

# PART 7 — DAILY OPERATING DISCIPLINE

## 7.1 The 15-minute daily ritual (non-negotiable)

1. **Commit and push** (conventional commit message)
2. **Write `docs/progress/DAY_NN.md`** — what worked, what broke, one screenshot
3. **List tomorrow's three tasks**

That progress log becomes ~40 % of your technical report for free, and it's the difference between assembling the report from notes and writing it from memory in a panic on 4 September.

## 7.2 Definition of Done (applies to every task)

- `ruff` clean · `mypy --strict` clean on `domain/`
- New engine code has unit tests; hydrology has a golden test
- **The feature is reachable and usable from the browser**, not just from pytest
- Docstring names the pattern or algorithm implemented
- Every numeric output carries units and an uncertainty statement

## 7.3 Weekly checkpoints

| Date | Must be true | If not |
|---|---|---|
| **20 Aug** | Walking skeleton runs end-to-end | Stop adding features. Fix integration. Nothing else matters. |
| **24 Aug** | P2 exit gate fully green | Do not start P3. A broken catchment engine invalidates FR6 and FR7. |
| **27 Aug** | Full pond-design payload returns | Begin cut ladder at item 1 |
| **31 Aug** | All 8 FRs demonstrable in browser | Cut items 2–4; protect P6 and P7 |
| **2 Sept** | Chaos test recorded, Grafana captured | Compress P7 to docs-only, drop MkDocs polish |

---

# PART 8 — MARK-LEAKAGE CHECKLIST

Cheap marks that are routinely lost. Each takes under an hour.

- [ ] **Features that work in tests but not in the UI.** Functionality is graded from the browser. Wire every engine to a visible control.
- [ ] **No units on numbers.** "Storage: 18950" scores less than "Gross storage: 18,950 m³ (±20 %)".
- [ ] **No uncertainty statements.** Overclaiming precision reads as naivety; stating ±15 % reads as engineering.
- [ ] **Uncalibrated stream threshold.** Visibly wrong streams cost Terrain marks and are fixed in 20 minutes.
- [ ] **No snap distance shown.** Makes the catchment look arbitrary.
- [ ] **Missing ADRs.** 12 one-page files = 1 mark + credibility in the viva.
- [ ] **No troubleshooting section in the install guide.** Half the install mark.
- [ ] **No error catalogue in API docs.** Half the API mark.
- [ ] **No citations in the report.** Methodology marks assume you can name your sources.
- [ ] **No validation section.** The single biggest avoidable loss: 2 direct marks plus every terrain mark becomes unverifiable.
- [ ] **Live API dependency during the demo.** Pre-seed. A failed demo costs functionality marks that the code deserved.
- [ ] **Secrets or large binaries in Git history.** Straight deduction from Git hygiene.
- [ ] **Deviating from the suggested stack without justifying it.** Write the reconciliation table (FastAPI over Flask, PostGIS over Mongo, full DEM rasters over point-elevation APIs). Justified deviation earns marks; unexplained deviation loses them.
- [ ] **OpenCV listed in the PDF but unused.** You use it genuinely in NDWI morphology and connected components — make sure that's visible in the report so the evaluator sees the stack was honoured.

---

# PART 9 — FUTURE WORK SECTION (for report §7)

Condensed distributed roadmap to cite as future work — signals that the prototype was designed with a production path, which supports the System Design marks.

| Phase | Window | Content |
|---|---|---|
| **P8 Field validation & pilot** | Months 1–4 | Ground-truth vs 20–30 existing ponds in one block; blind agreement test with a district minor-irrigation engineer; usability sessions with Panchayat staff; local CN calibration; **secure an institutional partner** (DRDA/Watershed Cell, KVK, agri-university, WOTR/FES/PRADAN, IIT/NIT lab) |
| **P9 Distributed refactor** | Months 5–7 | Strangler-Fig extraction along pre-drawn seams: Tile Service → ML Inference (KServe) → geoprocessing workers on Kubernetes (HPA on queue depth, spot nodes); NATS/Kafka bus; API Gateway; PostGIS read replicas + PgBouncer, shard by `state_code`; S3 + CDN; OpenTelemetry, SLOs; GitOps + Terraform |
| **P10 District scale** | Months 8–12 | Multi-tenancy State→District→Block→Village with row-level security; batch pre-computation (~800 villages ≈ 80 core-hours on spot); offline field app with per-field last-write-wins sync + manual merge queue; bulk cadastre ingestion + QGIS plugin |
| **P11 National + compliance** | Year 2 | GeoMGNREGA, Amrit Sarovar (75 ponds/district — the missing siting layer), Bhuvan/NRSC, WDC-PMKSY 2.0, state land portals; **DPDP Act 2023** (owner names are personal data → store ownership *class*), Geospatial Guidelines 2021, MeghRaj/MeitY-empanelled hosting, GIGW + WCAG 2.1 AA, CERT-In audit |
| **P12 Institutionalisation** | Year 2+ | Block-staff training, vernacular manuals; **impact metric: satellite-verified water spread pre/post construction**; convergence with Jal Jeevan source sustainability; release as a Digital Public Good; publish the weak-supervised suitability methodology |

**Scaling arithmetic:** block 100 villages / 6 GB / 10 core-h · district 800 / 48 GB / 80 core-h · state 55,000 / 3.3 TB / 5,500 core-h · India 650,000 / 39 TB / 65,000 core-h (≈₹2–4 lakh one-time on spot instances). Running cost: block ₹3–8 k/mo · district ₹15–40 k/mo · state ₹1.5–4 L/mo — against ₹5–20 lakh for **one** misplaced pond.

**Conclusion to state explicitly:** *the bottleneck to national deployment is cadastral data availability and institutional trust, not compute.* Identifying the true constraint is itself a system-design result.

---
*End of Marks-Driven Execution Roadmap*