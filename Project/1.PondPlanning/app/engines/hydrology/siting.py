"""Pond site selection from terrain alone — the Phase 2 "where" answer.

A pond wants a place that (1) receives a lot of runoff, (2) sits on gentle
ground where water spreads and stays, (3) is a convergent, wet position,
and (4) impounds a lot of water for a little earthwork. Each of those is a
terrain quantity this engine already computes, so the selection is an
explicit **multi-criteria score over drainage-network cells**:

    score = w_area · plateau(log10 upstream area)   # 1 on 10-150 ha, 0 at 1 ha and 1000 ha
          + w_flat · plateau(slope)                # 1 on 0-3 %, falling to 0 at 15 %
          + w_twi  · norm(TWI)
          + w_imp  · norm(impoundment efficiency)

where *impoundment efficiency* is the volume stored behind a nominal 2 m
rise at the cell (flood-fill of connected upstream cells below that level)
divided by the footprint area — a dimensionless "average depth" that
rewards natural basins over open slopes.

Upstream area is scored as a *plateau*, not monotonically: a catchment must
be large enough to fill the pond in a normal monsoon (about 10 ha at Indian
runoff rates for a 10-20 000 m³ pond) but a site draining hundreds of
hectares is a river — the structure becomes a dam with a spillway passing
almost everything, which is not a village pond. The bounds are parameters.

Hard constraints first (slope ≤ 15 %, on the drainage network, not within
a margin of the grid edge where the catchment would be truncated), then the
score, then **non-maximum suppression** so the top-N are distinct places
rather than ten adjacent cells on the same reach. Weights are declared,
returned in the result, and revisited with AHP in P4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from app.engines.hydrology.conditioning import NEIGHBOURS
from app.engines.hydrology.flow import FlowModel

FloatArray = NDArray[np.float64]

#: Upstream-area plateau in hectares: (too small, ideal from, ideal to, too large).
DEFAULT_AREA_BOUNDS_HA: tuple[float, float, float, float] = (1.0, 10.0, 150.0, 1000.0)

DEFAULT_WEIGHTS: dict[str, float] = {
    "upstream_area": 0.35,
    "flatness": 0.20,
    "wetness": 0.15,
    "impoundment": 0.30,
}


@dataclass(frozen=True, slots=True)
class SiteCandidate:
    """One ranked location with the criterion values that ranked it."""

    row: int
    col: int
    score: float
    upstream_area_m2: float
    slope_pct: float
    twi: float
    impoundment_volume_m3: float
    impoundment_area_m2: float
    impoundment_efficiency_m: float
    criteria_scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SitingResult:
    """Ranked candidates and the rules that produced them."""

    candidates: list[SiteCandidate]
    weights: dict[str, float]
    rise_m: float
    max_slope_pct: float
    suppression_radius_m: float
    edge_margin_cells: int
    considered: int
    area_bounds_ha: tuple[float, float, float, float] = DEFAULT_AREA_BOUNDS_HA


def impoundment(
    model: FlowModel, row: int, col: int, rise_m: float, max_cells: int = 20000
) -> tuple[float, float]:
    """Volume (m³) and area (m²) impounded by raising the water level ``rise_m`` at a cell.

    The same flood fill as the elevation-area-volume curve (``design.eav``):
    8-connected over cells below the pool level on the upstream side of a
    bund at the cell.
    """
    from app.engines.design.eav import flood_pool, pool_domain

    level = float(model.filled.data[row, col]) + rise_m
    volume, count = flood_pool(model, row, col, level, pool_domain(model, row, col), max_cells)
    return volume, float(count * model.filled.grid.cell_area)


def _plateau(slope_pct: FloatArray, optimum_hi: float = 3.0, limit: float = 15.0) -> FloatArray:
    """1 up to ``optimum_hi`` %, linear to 0 at ``limit`` % — a trapezoid, not a peak at 0."""
    return np.clip((limit - slope_pct) / (limit - optimum_hi), 0.0, 1.0)


def _trapezoid(x: FloatArray, lo: float, opt_lo: float, opt_hi: float, hi: float) -> FloatArray:
    """0 at ``lo``, rising to 1 across [opt_lo, opt_hi], falling to 0 at ``hi``."""
    rise = np.clip((x - lo) / max(opt_lo - lo, 1e-12), 0.0, 1.0)
    fall = np.clip((hi - x) / max(hi - opt_hi, 1e-12), 0.0, 1.0)
    return np.minimum(rise, fall)


def _norm(values: FloatArray) -> FloatArray:
    lo, hi = float(np.nanmin(values)), float(np.nanmax(values))
    return np.zeros_like(values) if hi - lo < 1e-12 else (values - lo) / (hi - lo)


def rank_sites(
    model: FlowModel,
    slope_deg: FloatArray,
    twi: FloatArray,
    stream: NDArray[np.bool_],
    *,
    top_n: int = 5,
    weights: dict[str, float] | None = None,
    rise_m: float = 2.0,
    max_slope_pct: float = 15.0,
    suppression_radius_m: float = 200.0,
    edge_margin_cells: int = 3,
    inside: NDArray[np.bool_] | None = None,
    area_bounds_ha: tuple[float, float, float, float] = DEFAULT_AREA_BOUNDS_HA,
) -> SitingResult:
    """Score every eligible drainage cell and return the top-N distinct sites."""
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    slope_pct = np.tan(np.radians(slope_deg)) * 100.0
    eligible = stream & (slope_pct <= max_slope_pct)
    m = edge_margin_cells
    eligible[:m, :] = eligible[-m:, :] = eligible[:, :m] = eligible[:, -m:] = False
    if inside is not None:
        eligible &= inside
    rr, cc = np.nonzero(eligible)
    if rr.size == 0:
        return SitingResult(
            [], w, rise_m, max_slope_pct, suppression_radius_m, m, 0, area_bounds_ha
        )

    area = model.accumulation[rr, cc].astype(np.float64) * model.filled.grid.cell_area
    vol_area = np.array(
        [impoundment(model, int(r), int(c), rise_m) for r, c in zip(rr, cc, strict=True)]
    )
    volume, footprint = vol_area[:, 0], vol_area[:, 1]
    efficiency = np.where(footprint > 0, volume / np.maximum(footprint, 1e-9), 0.0)

    lo, opt_lo, opt_hi, hi = (float(np.log10(b)) for b in area_bounds_ha)
    parts = {
        "upstream_area": _trapezoid(np.log10(np.maximum(area / 1e4, 1e-3)), lo, opt_lo, opt_hi, hi),
        "flatness": _plateau(slope_pct[rr, cc]),
        "wetness": _norm(twi[rr, cc]),
        "impoundment": _norm(efficiency),
    }
    score: FloatArray = np.zeros(rr.size)
    for k in w:
        score = score + w[k] * parts[k]

    # Non-maximum suppression: greedy by score, reject within the radius.
    cell = model.filled.grid.cell_size
    order = np.argsort(-score)
    chosen: list[int] = []
    for i in order:
        if all(
            np.hypot(rr[i] - rr[j], cc[i] - cc[j]) * cell >= suppression_radius_m for j in chosen
        ):
            chosen.append(int(i))
        if len(chosen) >= top_n:
            break

    candidates = [
        SiteCandidate(
            row=int(rr[i]),
            col=int(cc[i]),
            score=float(score[i]),
            upstream_area_m2=float(area[i]),
            slope_pct=float(slope_pct[rr[i], cc[i]]),
            twi=float(twi[rr[i], cc[i]]),
            impoundment_volume_m3=float(volume[i]),
            impoundment_area_m2=float(footprint[i]),
            impoundment_efficiency_m=float(efficiency[i]),
            criteria_scores={k: float(parts[k][i]) for k in w},
        )
        for i in chosen
    ]
    return SitingResult(
        candidates=candidates,
        weights=w,
        rise_m=rise_m,
        max_slope_pct=max_slope_pct,
        suppression_radius_m=suppression_radius_m,
        edge_margin_cells=m,
        considered=int(rr.size),
        area_bounds_ha=area_bounds_ha,
    )


__all__ = ["NEIGHBOURS", "SiteCandidate", "SitingResult", "impoundment", "rank_sites"]
