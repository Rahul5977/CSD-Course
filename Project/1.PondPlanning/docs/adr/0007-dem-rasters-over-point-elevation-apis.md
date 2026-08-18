# ADR 0007 — Full DEM rasters, not point-elevation APIs

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

The assignment suggests "an elevation API (OpenZenith etc.)". Those APIs return
the elevation of a coordinate. This ADR records why that shape of data cannot
produce the answers the assignment asks for.

## Decision

Download DEM tiles for the area of interest, mosaic, clip, reproject to the local
UTM zone, and store as a Cloud-Optimised GeoTIFF. All terrain analysis runs on
the raster.

## Why

Catchment delineation is not a point query. It requires, over a *grid*:

1. sink filling (Planchon & Darboux) — needs every neighbouring cell;
2. D8 flow direction — the steepest descent among eight neighbours;
3. flow accumulation — an upstream cell count per cell;
4. upslope traversal from the pour point — a graph search over the whole grid.

A village of 8.5 km² at 30 m is roughly 9,400 cells. Fetching those individually
from a rate-limited public API is tens of thousands of requests for one analysis
— slow, fragile, and it makes the system unusable the moment the network is
unavailable, which is precisely the failure the P6 chaos test demonstrates
surviving.

## Alternatives rejected

- **Point-elevation API per cell.** As above: the request count is the problem,
  not the data.
- **Interpolating a DEM from contours only.** Kept, but as an *additional*
  adapter rather than the primary source — see ADR 0011.

## Consequences

The system carries a real geospatial stack (rasterio, pysheds/richdem) and needs
object storage for the COGs. That is the cost of being able to answer FR4 at all.
Attribution is owed to NASA/USGS SRTM, USGS GMTED2010, HydroSHEDS © WWF and
Mapzen terrain tiles, and appears in the report's licence register.
