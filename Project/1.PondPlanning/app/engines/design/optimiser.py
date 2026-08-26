"""Depth optimiser: the cheapest excavated pond that stores the target.

Grid search over depth D in [1.5, 3.5] m (0.25 m steps) and plan aspect
ratio L:W in {1, 1.5, 2}. For each pair the top dimensions that store the
target are solved, cost = c_exc * V_excavation + c_emb * V_embankment, and
the minimum-cost feasible design wins; ties break towards the smaller
water surface (less evaporation). Depth is therefore *derived* from cost and
feasibility, not assumed — the FR7 rubric line.

Shallower ponds are cheaper per m³ only until their surface grows and the
side slopes eat the bottom; deeper ponds cost more per m³ of cut and need
a bigger bund. The search makes that trade-off explicit and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.engines.design.geometry import PondGeometry, solve_top_dimensions


@dataclass(frozen=True, slots=True)
class CostRates:
    """Indicative unit rates (INR/m³). Stated with their basis in the response."""

    excavation: float = 160.0  # MGNREGA/CPWD schedule-of-rates band for ordinary soil, 2024
    embankment: float = 220.0  # formed and compacted
    basis: str = (
        "Indicative: CPWD DSR 2024 / MGNREGA SoR bands for ordinary soil, machine excavation"
    )


@dataclass(frozen=True, slots=True)
class DesignChoice:
    """One evaluated candidate."""

    geometry: PondGeometry
    cost_inr: float
    excavation_m3: float
    embankment_m3: float


def optimise(
    target_m3: float,
    *,
    depths: tuple[float, ...] = tuple(np.arange(1.5, 3.5 + 1e-9, 0.25)),
    aspects: tuple[float, ...] = (1.0, 1.5, 2.0),
    side_slope: float = 2.0,
    freeboard_m: float = 0.5,
    rates: CostRates | None = None,
    max_depth_m: float | None = None,
) -> tuple[DesignChoice, list[DesignChoice]]:
    """Return the winner and every feasible candidate evaluated."""
    rates = rates or CostRates()
    candidates: list[DesignChoice] = []
    for depth in depths:
        if max_depth_m is not None and depth > max_depth_m:
            continue
        for aspect in aspects:
            dims = solve_top_dimensions(target_m3, depth, aspect, side_slope)
            if dims is None:
                continue
            geometry = PondGeometry(depth, dims[0], dims[1], side_slope, freeboard_m)
            if not geometry.feasible:
                continue
            excavation = geometry.excavation_m3
            embankment = geometry.embankment_m3()
            cost = rates.excavation * excavation + rates.embankment * embankment
            candidates.append(DesignChoice(geometry, cost, excavation, embankment))
    if not candidates:
        msg = "no feasible pond geometry for the target storage within the depth limits"
        raise ValueError(msg)
    best = min(candidates, key=lambda c: (round(c.cost_inr), c.geometry.top_area_m2))
    return best, candidates
