# ADR 0015 — Catchment validation: golden tests + an independent implementation, not GRASS

**Status:** Accepted · 2026-08-26 · Phase P2

## Context

`docs/PLAN.md` validates the catchment engine against GRASS `r.watershed`
via QGIS. Neither QGIS nor GRASS nor the GDAL CLI is installed on the
development machine, and installing them costs wall-clock the schedule does
not have (10 days to submission at the start of P2).

## Decision

Three layers of evidence, all runnable by `make check` on a fresh clone:

1. **Synthetic golden tests** with analytic answers (`tests/golden/`): an
   inclined plane, a cone, a V-valley (catchment = the rectangle upstream of
   the outlet), a Y-valley (Strahler order 2), an artificial pit (filled to
   its spill level, nothing else touched), a flat terrace (every cell drains
   after +ε).
2. **Cross-check against pysheds** (Bartos 2020), an independent, published
   implementation of the same chain, on the provided sample
   (`tests/test_pysheds_crosscheck.py`). Outlets are snapped to the highest-
   accumulation cell within two cells *in each model*, because the two
   flat-resolution schemes (our Priority-Flood + ε, pysheds' `resolve_flats`)
   route a floodplain cell differently. Policy: the majority of outlets within
   the plan's ±15 %, none beyond 25 %, Jaccard overlap ≥ 0.75. First run:
   2.0 %, 3.4 % and 22.5 % (the floodplain case) with overlaps 0.98 / 0.97 / 0.77.
3. **Pour-point sensitivity** (`make figures`): catchment area for every cell
   in a ±3-cell window around a channel cell, with and without snapping.
   First run: coefficient of variation 212 % raw, 48 % snapped.

GRASS remains an optional fourth layer if QGIS is installed later.

## Consequences

- The validation section of the report has real numbers from the first day
  the engine existed, and CI re-derives them on every push.
- pysheds 0.5 still calls `np.in1d`, removed in NumPy 2.x; the test aliases
  it. It is a dev-only dependency and never ships in the image.
- The 22 % floodplain case is reported, not hidden: it is the same effect
  the snap step exists to control, and the sensitivity figure shows it.
