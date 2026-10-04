# DAY_03 — 2026-08-26
**Phase:** P1 → P2 · **Gate:** G1 closed; G2 closed the same day

## What worked
- The whole walking skeleton in one day, KML-first: `POST /analyzeContour` → Celery worker →
  parse (lxml, ordered elevation strategy, KMZ) → provenance from the file's own metadata →
  Delaunay TIN → DEM at a derived 30 m grid → Horn slope + hillshade → COGs in MinIO → village
  row named by reverse-geocoding the centroid (**Khapri, Durg, CG**) → TiTiler tiles → MapLibre.
- Golden tests with analytic answers: an inclined plane is recovered to < 0.15 m RMS, a cone to
  < 0.25 m between its rings; the resolution rule and the CRS guard have their own tests.
- Ports and adapters (ADR 0013): the test suite runs the real pipeline on the real sample with
  the in-memory / inline / local-directory adapters — no Docker, no mocks, 137 tests in 2 s.
- Re-uploading the same extent updates the same village (PostGIS `ST_Equals`) instead of a twin.

## What broke
- `ImportError: libexpat.so.1` in the API image — the rasterio wheel links against libexpat,
  which `python:3.12-slim` lacks. Fix: `apt-get install libexpat1`. → install-guide troubleshooting row.
- TiTiler publishes amd64-only images and listens on port 80, not 8000. Fix: `platform:
  linux/amd64` (emulated on Apple Silicon) and the nginx upstream corrected. → troubleshooting row.
- Provenance heuristic picked *Copernicus* because Mapzen's attribution blurb names it once;
  the raw raster is `srtm/N21E081.tif`. Fix: evidence-weighted ranking (mentions + 5 × raw-file
  references, ties to the finer product) — general, not sample-specific.
- On a 30 m grid with 1-cell smoothing the 267 m and 298 m extremes (single cells) become
  268.7 / 295.7 m. Expected: SRTM is ±6 m relative; tests widened, limitation recorded.
- A parallel shell call inherited `cd web` and ran `npm install` in the repo root. Cleaned up.

## Screenshot
`docs/figures/p1-walking-skeleton.jpg` — satellite basemap, hillshade overlay, Khapri summary
card with units and uncertainty bands on every number.

## Decisions made
Seven rows in the `docs/PROGRESS.md` decision log: TIN interpolation, derived resolution rule,
metadata-driven provenance, geocoded village name, ports-and-adapters wiring, COG/TiTiler tile
path, Esri basemap for FR1. Plus the four user decisions from the planning session.

## Tomorrow's three tasks
1. P2 day 1 — priority-flood sink fill + flat resolution on the interpolated DEM; before/after
   figure; synthetic-pit golden test.
2. P2 day 2 — D8 flow direction, accumulation, stream extraction with a calibrated threshold
   (overlay on satellite), snap-to-drainage + upstream BFS catchment, pysheds cross-check.
3. Site-selection scorer (drainage candidates × slope × TWI × impoundment efficiency) and the
   full `ContourAnalysisResult` from `POST /analyzeContour`.

---

## P2 — Terrain & Catchment (same day, second half)

### What worked
- The whole hydrology chain in pure numpy, each stage a page of legible code: Priority-Flood + ε
  → D8 → accumulation (one descending-elevation pass) → 5 ha streams with Strahler order →
  nearest-channel snapping → upstream BFS → polygon; Zevenbergen–Thorne curvature, TWI; marching-
  squares contours with Douglas–Peucker (5 097 → 1 408 vertices at 2 m); a terrain-only siting
  score with non-maximum suppression (ADR 0014). `POST /analyzeContour` now returns the full
  Phase 2 payload: suggested location + rationale + catchment + 5 ranked candidates + method.
- 19 new golden tests with analytic answers; pysheds cross-check 2.0 % / 3.4 % / 22.5 %
  (ADR 0015); pour-point sensitivity CV 212 % → 48 % with snapping.
- In the browser: click anywhere → catchment polygon with the snapped outlet and the snap distance;
  streams over satellite reproduce the visible river; contours with labels and a 1/2/5/10 m
  selector; slope/aspect/curvature/TWI/flow-accumulation/fill-depth as TiTiler layers; ranked sites
  with per-criterion bars.

### What broke
- First siting run put every top site on the main river (345–406 ha upstream) — a monotone
  "more upstream area is better" term. Replaced by a plateau (10–150 ha). Recorded in ADR 0014.
- pysheds 0.5 calls `np.in1d`, removed in NumPy 2.x — aliased in the test.
- My "two tributaries" synthetic had a 3 m step that spawned extra junctions: Strahler 3 was the
  *correct* answer for that terrain. Rebuilt as a continuous Y-valley.
- Plan-curvature sign: Zevenbergen–Thorne's is the opposite of ArcGIS's; adopted ArcGIS.
- Priority-Flood on a fully enclosed synthetic bowl drains *outward* — correct (it is one closed
  depression), my test expectation was wrong.

### Figures
`docs/figures/p2-sink-fill-before-after.png` · `p2-flow-accumulation.png` ·
`p2-pour-point-sensitivity.png` · `p2-click-to-catchment.jpg` · `p2-streams-on-satellite.jpg` ·
`p2-layers-slope.jpg` · `p2-layers-twi.jpg` · `p2-contours-5m.jpg`

### Tomorrow's three tasks
1. P3 day 1 — `RainfallProvider` (Open-Meteo ERA5-Land daily, NASA POWER fallback), decorators,
   statistics engine (75 % dependable, JJAS share, rainy days, max 1-day).
2. P3 day 2 — CN grid (ESA WorldCover + HSG), SCS-CN on the daily series, Rational, Strange;
   three-method range.
3. P3 day 3 — EAV curve from the impoundment flood fill, depth optimiser, losses, 25-year water
   balance, BoQ, `POST /analysis/pond-design`.
