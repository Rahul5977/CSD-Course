# ADR 0014 — Pond sites are selected by an explicit terrain score, before any land data

**Status:** Accepted · 2026-08-26 · Phase P2

## Context

The Phase 2 brief asks the contour route to "identify a suitable pond
location/region", and the professor flagged *how the area is selected* as the
examined topic. `docs/PLAN.md` only selects sites in P4, from a suitability
raster that needs land ownership, LULC and NDWI water masks — none of which
exist when a contour map is uploaded on its own.

## Decision

A first-class **terrain-only siting engine** (`app/engines/hydrology/siting.py`)
runs inside the contour-analysis job:

1. **Candidates** are cells on the modelled drainage network (upstream area ≥
   the stream threshold), because a pond that is not on a flow path does not fill.
2. **Hard constraints:** slope ≤ 15 %, not within 3 cells of the map edge
   (where the catchment would be truncated by the map, not by a divide).
3. **Score** = weighted sum of four normalised criteria:
   - *upstream area* as a **plateau**: 0 at 1 ha, 1 from 10 to 150 ha, 0 at
     1000 ha. Enough to fill a 10–20 000 m³ pond in a normal monsoon at Indian
     runoff rates; beyond ~150 ha the structure is a river dam whose spillway
     passes almost everything. (First version scored area monotonically and
     put every top site on the main river — the figure that prompted this rule.)
   - *flatness* as a trapezoid: 1 on 0–3 % slope, 0 at 15 % (an optimum at
     exactly 0 % would reward floodplains and DEM artefacts).
   - *wetness*: normalised TWI, ln(a / tan β) — convergent, wet positions.
   - *impoundment efficiency*: volume held by a nominal 2 m rise at the cell
     (flood fill of connected upstream cells below the pool level) divided by
     the pool footprint — a mean depth that rewards natural basins over open
     slopes and is the seed of P3's elevation–area–volume curve.
   Weights 0.35 / 0.20 / 0.15 / 0.30, declared in the result.
4. **Non-maximum suppression** at 200 m so the top-N are distinct places.
5. The top site's catchment is delineated and returned with it; every
   candidate carries its per-criterion scores so the ranking is checkable.

## Consequences

- The Phase 2 route answers "where" from the upload alone, and the answer is
  a formula an examiner can read off the response.
- P4 layers land ownership, LULC and existing-water buffers on the same
  scorer as constraints, and replaces the fixed weights with AHP — the
  interface (`weights`, constraints, candidates) does not change.
- The plateau bounds and weights are judgement calls, stated as such and
  parameterised; the AHP consistency check in P4 is what makes them defensible.

## Alternatives rejected

- Siting only in P4 — leaves the graded Phase 2 route without a location.
- Picking the maximum-accumulation cell — always the river outlet.
- Picking the maximum TWI cell — floodplain flats, again the river.
