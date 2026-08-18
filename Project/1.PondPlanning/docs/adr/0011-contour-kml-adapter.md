# ADR 0011 — Uploaded contour maps as a `DEMProvider`, not a second pipeline

**Status:** Accepted · 2026-08-18 · Phase P0 (implemented in P2)

## Context

`docs/assignment/Phase2.txt` requires a route that accepts an uploaded KML/KMZ contour map
and returns catchment information. `docs/PLAN.md` builds terrain from provider
DEM tiles and treats contours as an output. Two sources of elevation, one
hydrology chain.

## Decision

`ContourKMLAdapter` implements the same `DEMProvider` Protocol as the
Copernicus/ALOS adapters: parse contours → interpolate to a grid → hand the
raster to the **existing, unchanged** sink-fill → D8 → accumulation → snap → BFS
chain.

## Parsing rules, derived from the provided sample

The sample (`data/samples/contours_1m.kml`) contains three traps, each of which
would fail silently:

1. **Root element is `<Folder>`, not `<kml><Document>`.** Strict parsers reject
   the file. Parse with `lxml` and namespace-agnostic local-name matching.
2. **Elevation lives only in `<Placemark><name>`.** Coordinates are 2-D; there is
   no Z. The 1355 `Point` placemarks are duplicate labels and must be filtered
   out, or they double-weight the interpolation.
3. **`ExtendedData` carries `SimpleData name="ID"` (0…1354).** Numeric,
   sequential, and *not* elevation. An adapter that takes "the first numeric
   field" builds a plausible-looking terrain model out of row numbers.

So elevation is read by an ordered strategy — Z coordinate → whitelisted
`ExtendedData` field name (`elev|elevation|contour|level|height`) → placemark
`<name>` — with `ID` explicitly rejected, and `ElevationNotFoundError` raised
when every strategy fails. **Never guess.** The strategy that succeeded is
returned in the response so the result is auditable.

## Derived, never configured

- **UTM zone** from the uploaded file's own centroid.
- **Grid resolution** from the file's own mean contour spacing, floored at the
  source resolution. The sample's contours are interpolated from SRTM ~30 m;
  gridding them at 1 m would manufacture detail the source does not contain.
- **Pour point** from the modelled drainage of the uploaded extent.

This is the assignment's explicit anti-hard-coding requirement, and it is what
"extensibility to generalized contour maps" is graded on.

## Alternatives rejected

- **A separate parallel pipeline for uploads.** Duplicate hydrology code, two
  code paths to validate, and double the viva surface.
- **Trusting a KML library to find elevations.** No library knows that this
  file's `ID` field is a decoy.

## Consequences

Roughly one day of work inside P2, because everything downstream is reused. A
second contour KML with elevation in Z or `ExtendedData` is kept as a test
fixture (evidence register row 37) to prove the adapter is not sample-specific.
