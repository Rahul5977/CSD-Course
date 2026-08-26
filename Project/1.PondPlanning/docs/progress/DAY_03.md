# DAY_03 — 2026-08-26
**Phase:** P1 → P2 · **Gate:** G1 closed, G2 open

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
