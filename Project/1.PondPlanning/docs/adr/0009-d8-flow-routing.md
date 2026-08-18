# ADR 0009 — D8 flow routing, with D-∞ documented as a stub

**Status:** Accepted · 2026-08-18 · Phase P0 (implemented in P2)

## Context

Flow routing decides how water leaves each DEM cell, and therefore what the
catchment boundary is. The choice is the single most consequential algorithm in
the project — FR4, FR6 and FR7 all sit downstream of it.

## Decision

**D8** (O'Callaghan & Mark, 1984): each cell drains entirely to the steepest of
its eight neighbours. D-∞ (Tarboton, 1997) is left as a documented stub behind
the same interface.

## Why

1. **Defensible under cross-examination.** D8 is four lines of logic that can be
   drawn on a whiteboard. The explainability policy means every algorithm may be
   questioned live; a documented simple choice beats an undefended sophisticated
   one.
2. **Deterministic and testable.** Single-neighbour routing gives an exact
   expected answer on a synthetic DEM, which is what the golden tests assert.
   Multiple-flow-direction results are approximate and harder to pin down.
3. **Appropriate to the input.** The source is SRTM at ~30 m. D-∞'s advantage is
   on divergent hillslopes at fine resolution; at 30 m over 31 m of relief, the
   DEM's own vertical error dominates the routing difference.

## Known limitation, stated rather than hidden

D8 cannot represent flow divergence — it produces parallel flow lines on planar
hillslopes where water actually spreads. It is accepted here because catchments
are delineated to *convergent* points (channels), where D8 and D-∞ largely agree.
This goes in the report's limitations section rather than being left for a viva
question to uncover.

## Consequences

The stub is evidence of extensibility, and it is item 6 on the cut ladder — the
last thing to be dropped, because it costs nothing to leave documented and
unimplemented.
