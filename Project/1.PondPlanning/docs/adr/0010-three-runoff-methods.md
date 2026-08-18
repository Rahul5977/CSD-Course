# ADR 0010 — Three runoff methods, reported as a range

**Status:** Accepted · 2026-08-18 · Phase P0 (implemented in P3)

## Context

FR6 asks for a runoff volume. The obvious implementation returns one number. The
honest one does not, because runoff estimation methods routinely disagree by 25 %
or more on the same catchment, and that disagreement is real information about
how well the quantity is known.

## Decision

Compute runoff by three methods and return all three plus their spread:

| Method | Reference | Role |
|---|---|---|
| SCS Curve Number | USDA SCS (1972), TR-55 | Primary — accounts for soil and land cover |
| Rational | Kuichling (1889); IS 4410 | Cross-check — widely used in Indian practice |
| Strange's table | Maharashtra PWD | Regional empirical sanity check |

Implemented behind a common interface so a method is a strategy, not a branch.

## The one rule that must not be broken

**SCS-CN is applied to the daily rainfall series and then summed.** Applying it
to an annual total overestimates runoff two- to three-fold, because the method is
non-linear in rainfall depth: `Q = (P - 0.2S)² / (P + 0.8S)`. Feeding it
`P = 1284 mm` instead of 60-odd daily depths is not an approximation, it is a
different and much larger number. This is why `GET /rainfall/series` exposes the
daily record and not just the statistics.

## Why a range rather than a best estimate

The rubric rewards stated uncertainty and penalises false precision. "560,000 to
700,000 m³ depending on method, SCS-CN preferred because it accounts for soil and
land cover" is a defensible engineering answer. A single figure to five
significant digits invites the question of where the other four came from.

## Consequences

`RunoffResult` carries every method's result, its parameters, its citation, and
the spread. The pond design consumes the recommended method but the range travels
with it into the report.
