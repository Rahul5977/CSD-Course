# ADR 0020 — Land area selected on the map: Copernicus GLO-30 behind the DEM port

**Status:** Accepted · 2026-09-27 · Phase P9 (Phase 3 submission)

## Context

The updated Phase 3 brief requires "an option to select the land area on a
map", with the suggested pond location, catchment area and expected water
volume generated for that area and overlaid on the map. v1.0 derived terrain
only from an uploaded KML/KMZ contour map. A user who draws a box has no
contour file, so the elevations must come from a global DEM.

The architecture already had the seam: `DEMProvider` (ADR 0011) with the
contour adapter and a documented `ProviderTileAdapter` stub.

## Decisions

1. **Source: Copernicus DEM GLO-30**, read as Cloud-Optimised GeoTIFFs from the
   AWS Open Data bucket (`copernicus-dem-30m`). No key, no registration, global,
   2011–15 TanDEM-X, ±2 m relative / ±4 m absolute (LE90). A COG window read
   fetches only the bytes under the box (~hundreds of kB), so a village takes
   ~2 s.
2. **Same chain, second adapter.** `ProviderTileAdapter` builds the UTM grid
   (zone from the box's centroid, native 30 m cells), mosaics and warps the
   1°×1° tiles (bilinear), and returns a `DEMProduct`. Everything downstream
   (Priority-Flood, D8, streams, siting, catchment, the saga) is unchanged
   and already covered by the golden tests. The workflow's only branch on
   input kind is the choice of adapter.
3. **`POST /analyzeArea {bbox}`** returns the same `202` job and the same
   `ContourAnalysisResult` shape as `/analyzeContour`; the frontend handles
   both results with one code path.
4. **Size limits 0.25–25 km²** (settings), enforced in UTM metres, else
   `422 area_out_of_range`. Too small cannot hold a 10 ha catchment; the upper
   limit is the per-request stress guard for the lab VMs (~28 000 cells,
   seconds on one core).
5. **Water Body Mask.** GLO-30 flattens water surfaces. On a flattened river
   D8 splits the flow into parallel lines, no cell reaches the river threshold,
   and siting would put a pond in the river (observed on the sample AOI). The
   tile's own `AUXFILES/*_WBM.tif` (lake/river classes) is read with the DEM
   (nearest resampling) and treated like a major channel: excluded, with the
   200 m flood belt.
6. **Read the grid's footprint, not the box.** The UTM grid is the envelope
   of the projected box, so its corners lie outside the lon/lat box; reading
   only the box left NaN corners that were silently gap-filled. The window is
   now the grid's own lon/lat bounds plus two source cells, rounded outward.
7. **Complete-catchment constraint** (in siting, for both paths): a candidate
   whose upstream area reaches the map edge has a truncated catchment, so its
   area and runoff are lower bounds. Such cells are excluded (`edge_fed`, one
   topological pass), unless nothing else remains — then the constraint is
   relaxed and a `no_complete_catchment` warning says so. This corrected the
   sample's own top site: the v1.0 answer (38.2 ha, one cell from the top edge)
   had a truncated catchment; the new top site is 28.0 ha and complete.
8. **Volume without a second click.** When an analysis finishes, the frontend
   immediately runs the pond design (SCS-CN on the daily series, 75 %
   dependable) on the top site, so the location, catchment and expected water
   volume appear on the map together.

## Alternatives rejected

- **Point-elevation APIs (OpenTopoData, Open-Elevation).** One HTTP call per
  cell or rate-limited batches; ~10 000 points per village; public instances
  throttle at 1 req/s. A COG window read is one request.
- **SRTM via OpenTopography.** Needs an API key; the key would be a secret in
  a student deployment.
- **Drawing a free polygon.** A rectangle is two clicks, trivially validated,
  and matches the raster grid; polygons add a drawing library and self-
  intersection handling for no analytic gain.

## Validation

`scripts/crosscheck_dem_sources.py` → `docs/figures/p9-dem-crosscheck.md`.
On the sample AOI, GLO-30 and the contour DEM agree as surfaces (RMSE 1.8 m
after a −5 m datum offset, r = 0.94), and the total drainage agrees within
17 %. Small flow paths diverge on this very flat terrain: the uncertainty is
the source DEM, not the algorithm (pysheds on the same DEM agreed within 2–3 %,
ADR 0015). The report states this, and every catchment carries its band.

## Consequences

- Any village in GLO-30 coverage (±60° latitude outside the polar
  exclusions) can be analysed with two clicks and no file.
- The deployment needs outbound HTTPS to S3; the lab VMs have it. The DEM
  window is cached in-process (LRU, 32 grids).
- GLO-30 is a *surface* model: canopy and buildings are in the elevations. The
  result carries a `surface_model` warning.
