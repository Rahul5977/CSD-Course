# ADR 0017 — Suitability: Specification constraints, AHP weights, NDWI water; ML deferred

**Status:** Accepted · 2026-08-26 · Phase P4

## Context

FR3 asks the system to "identify available land suitable for pond excavation",
and the project title promises an "AI-based" method. `docs/PLAN.md` P4 lists a
Specification-pattern constraint set, fuzzy membership, AHP, an NDWI/OpenCV
water mask, and an XGBoost + SHAP scorer blended with AHP — with a *designed
fallback*: ship AHP-only (α = 1.0) if the ML underperforms or time runs out.

## Decision

1. **Eligibility is a Specification expression**, readable in one line:
   `SlopeUnder(15 %) & ~WithinBuffer(water, 150 m) & HabitationDistance(100–2000 m)
   & LandCoverIn(grass/crop/bare/wetland) & IsGovernmentLand()`, then
   `MinFlowAccumulation(5 ha)` and `MinContiguousArea(2 500 m²)`. Every leaf
   names itself, so the response lists exactly which rules were applied.
   Ownership without a cadastral layer is *unknown* and passes with a warning —
   never assumed government (ADR 0012).
2. **Existing water from Sentinel-2 NDWI**: post-monsoon median of the
   clearest scenes, Otsu threshold, OpenCV morphological open/close, connected
   components ≥ 200 m² — the OpenCV usage the assignment names, used for a real
   job. Pre-monsoon composite separates perennial from seasonal water. Fallback
   when STAC/AWS are unreachable: WorldCover class 80, flagged.
3. **Weights by AHP** (Saaty 1980): a declared pairwise matrix over the four
   siting criteria, principal-eigenvector weights, consistency ratio computed
   and returned (CR = 0.011 for the default matrix; anything ≥ 0.10 is reported
   as unacceptable). Criteria stay the P2 terrain memberships (upstream-area
   plateau, slope plateau, TWI, impoundment efficiency), so the ranking is the
   same explainable formula with defended weights, restricted to eligible cells.
4. **XGBoost + SHAP deferred** (cut-ladder item 3). Weak-supervision labels
   from the two OSM tanks in an 8.5 km² map are too few to train or to evaluate
   under spatial block CV; a model fitted to them would be theatre. The scoring
   sits behind the same interface (`weights`, constraints, candidates), so the
   ML path is a documented future strategy, not a missing feature. This is the
   plan's own fallback sentence, applied.

## Consequences

- `GET /villages/{id}/available-land` returns parcels with the constraint list
  and the ownership caveat; `POST /analysis/suitability` returns ranked sites
  with per-criterion raw value, membership, weight and contribution, plus the
  AHP matrix and CR in a warning row. The suitability heat-map and the water
  mask are COG layers.
- The "AI" in the title is honest: multi-criteria decision analysis with a
  consistency-checked weighting and a computer-vision water mask, each a
  named published method with a citation.
