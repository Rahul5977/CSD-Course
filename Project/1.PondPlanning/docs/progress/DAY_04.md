# DAY_04 — 2026-08-26 (evening)
**Phase:** P3 · **Gate:** G3 closed — the ideal prototype-demo point (6 of 8 FRs real)

## What worked
- FR5: Open-Meteo ERA5-Land (45 years in 2 s) → NASA POWER fallback, behind Retry ∘ CircuitBreaker
  ∘ Cached + FallbackChain; the AOI's 1981–2025 record checked in so tests, CI and the demo never
  touch the network. Weibull 75 % dependable = 1 192 mm/yr for Khapri; monsoon share > 85 %.
- FR6: WorldCover read as a 300 KB window from the public COG — cropland 46 %, grassland 26 %,
  built 9.5 %, water 8 %; TR-55 CN 88 on HSG C; three methods on the daily series (SCS 99 k m³,
  rational 244 k, Strange 18 k — spread 188 %, flagged). A test shows the annual-total shortcut
  overestimates SCS-CN runoff > 3×.
- FR7: Builder pattern over EAV → capped target → cost-optimised frustum → daily water balance →
  spillway → BoQ → confidence. Live design in 6 s: 50 000 m³, 3.5 m deep, fills every year.
- Reality check at OSM's mapped tanks (`docs/figures/p3-existing-pond-comparison.md`): local runoff
  is a tenth of their capacity — canal-fed tanks, honestly recorded.

## What broke
- Donor-only flood fill excluded the cells beside the bund (cone test: 2 100 m² vs 7 850) — replaced
  with an upstream-side 8-connected fill, shared by EAV and siting.
- A Gumbel test chased a 368 mm outlier; a synthetic bowl's channel evaluated to 199 m (operator
  precedence) — engine right, test wrong, both times.
- SoilGrids takes ~40 s and timed out inside the container → default HSG C with a warning and a
  30-day cache; confidence drops to *low*, as it should.
- pysheds 0.5 calls `np.in1d` (NumPy 2 removed it) — aliased in the test only.

## Screenshots
`docs/figures/p3-rainfall-panel.jpg`, `p3-design-panel.jpg`

## Decisions made
Seven rows in the decision log + ADR 0016.

## Tomorrow's three tasks
1. P4 — Specification-pattern constraints and `GET /villages/{id}/available-land` real (slope, water
   buffer from the NDWI/OpenCV mask, min contiguous area, habitation distance from WorldCover built-up).
2. P4 — AHP weights (Saaty matrix, CR < 0.10) replacing the fixed siting weights; suitability heat-map
   COG; `POST /analysis/suitability` real with per-criterion breakdown.
3. P4 — Sentinel-2 NDWI via STAC → Otsu → OpenCV morphology → connected components (the OpenCV usage
   the PDF names), seasonal vs perennial water; sanity check: do top sites land near existing tanks?
