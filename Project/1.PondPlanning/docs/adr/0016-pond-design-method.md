# ADR 0016 — Pond design: excavated frustum, cost-derived depth, water-balance reliability

**Status:** Accepted · 2026-08-26 · Phase P3

## Context

FR7 asks for "an appropriate pond depth and approximate storage capacity",
and the rubric gives it the most marks of any feature (6) with the note
"depth *derived*, not assumed; storage from an EAV curve; dimensions given".
The inputs are planning-grade: a contour-interpolated DEM from a ~30 m
source, reanalysis rainfall, satellite land cover.

## Decision

1. **Target storage = harvestable runoff, capped.** Harvestable = 75 %
   dependable annual runoff (SCS-CN on the daily series, Weibull m/(n+1))
   × catchment area × 0.6 harvest efficiency. It is clamped to
   [2 000, 50 000] m³: below that a pond is a puddle, above it the structure
   is a reservoir with a different design code (the Amrit Sarovar minimum
   is 10 000 m³). When the cap binds, the response says so and reports the
   uncapped figure — the surplus is what the spillway passes.
2. **Geometry = excavated inverted frustum**, side slopes 2:1, prismoidal
   volume (exact for plane sides), 0.5 m freeboard, bottom ≥ 5 m each way.
   The natural depression's EAV curve (8-connected flood fill behind a bund)
   is reported alongside as "what a bund alone would impound", not added:
   combining cut and fill honestly needs a ground survey.
3. **Depth is chosen by cost**, not assumed: grid search over D ∈ [1.5, 3.5]
   m (0.25 m steps) × aspect ∈ {1, 1.5, 2}; each candidate's top dimensions
   are solved for the target; cost = ₹160/m³ cut + ₹220/m³ bund (indicative
   2024 SoR bands, stated in the response); ties go to the smaller surface
   (less evaporation). The whole candidate table is available for the viva.
4. **Losses and reliability by daily simulation** over the 25-year record:
   inflow = daily runoff × area × 0.6; evaporation = 0.7 × pan (monthly IMD
   climatology for central India); seepage 2 mm/day over the wetted area;
   dead storage 15 %. Fill reliability = share of years reaching ≥ 90 % —
   the number an administrator actually asks for ("fills in 22 of 25 years").
5. **Spillway** for the 25-year 1-day rainfall (Gumbel EV1 on annual
   maxima), IMD short-duration reduction ``P_t = P_24 (t/24)^{1/3}``,
   Kirpich time of concentration, rational peak, broad-crested weir length.
6. **Confidence label by the worst input**: assumed land cover or soil,
   cached rainfall, or an edge-limited catchment pull it to *low*; the DEM
   source keeps it at *moderate* at best. Every number carries ±20 % or
   worse. This is what stops a 30 m-DEM result reading as a survey.

## Alternatives rejected

- Sizing to demand (irrigation/livestock) — no demand data exists at upload
  time; supply-side sizing with a cap is honest about what is known.
- Depth from a "3 m rule" — assumes what the rubric asks us to derive.
- Storage from the natural EAV curve alone — reports a bund on the floodplain
  as a pond; the sample's top sites impound 100 000+ m³ behind 2 m, which is
  a river dam.
- Monthly water balance — cannot represent the 20–40 rainy days that fill
  the pond; daily is cheap on a 9 000-day record.

## Consequences

Every FR7 number is traceable to a named equation with a citation, the
parameters are declared constants at the top of the workflow, and the
Builder exposes each stage for a golden test. The existing-pond comparison
(evidence row 17) is the reality check on all of it.
