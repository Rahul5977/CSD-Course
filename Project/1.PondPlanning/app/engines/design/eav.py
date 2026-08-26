"""Elevation-area-volume curve of the natural depression behind a bund at a point.

For each water level above the outlet cell, the pool is the **8-connected
flood fill** from the outlet over cells below that level, restricted to the
upstream side of the bund: a cell qualifies if it drains through the outlet
(D8 upstream) *or* is no lower than the outlet — cells that are both lower
and not upstream are the channel below the bund and stay dry. Area is the
flooded cell count x cell area; volume is the exact sum of water columns
``(level - z) x cell area``. Steps of 0.25 m from 0 to ``max_rise``.

This is what a bund of a given height at the point would impound before
any excavation; the excavated design in :mod:`geometry` adds to it. The
same fill scores impoundment efficiency in the siting engine.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.engines.hydrology.catchment import upstream_mask
from app.engines.hydrology.conditioning import NEIGHBOURS
from app.engines.hydrology.flow import FlowModel


@dataclass(frozen=True, slots=True)
class EAVPoint:
    """One level of the curve."""

    level_m: float  # rise above the outlet cell
    elevation_m: float  # absolute
    area_m2: float
    volume_m3: float


def flood_pool(
    model: FlowModel,
    row: int,
    col: int,
    level: float,
    allowed: NDArray[np.bool_],
    max_cells: int = 50_000,
) -> tuple[float, int]:
    """``(volume m3, cells)`` of the pool at absolute ``level`` behind a bund at (row, col)."""
    z = model.filled.data
    rows, cols = model.shape
    cell_area = model.filled.grid.cell_area
    seen = np.zeros(z.shape, dtype=bool)
    seen[row, col] = True
    queue: deque[tuple[int, int]] = deque([(row, col)])
    volume = 0.0
    count = 0
    while queue and count < max_cells:
        r, c = queue.popleft()
        depth = level - z[r, c]
        if depth <= 0:
            continue
        volume += depth * cell_area
        count += 1
        for dr, dc in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not seen[nr, nc] and allowed[nr, nc]:
                seen[nr, nc] = True
                queue.append((nr, nc))
    return float(volume), count


def pool_domain(model: FlowModel, row: int, col: int) -> NDArray[np.bool_]:
    """Cells a pool behind a bund at (row, col) may occupy: upstream, or not below the outlet."""
    z = model.filled.data
    return np.asarray(upstream_mask(model, row, col) | (z >= z[row, col]), dtype=bool)


def eav_curve(
    model: FlowModel, row: int, col: int, *, max_rise_m: float = 4.0, step_m: float = 0.25
) -> list[EAVPoint]:
    """Curve at ``step_m`` increments up to ``max_rise_m`` above the outlet."""
    z0 = float(model.filled.data[row, col])
    cell_area = model.filled.grid.cell_area
    allowed = pool_domain(model, row, col)
    points: list[EAVPoint] = []
    for rise in np.arange(0.0, max_rise_m + 1e-9, step_m):
        volume, count = flood_pool(model, row, col, z0 + float(rise), allowed)
        points.append(EAVPoint(float(rise), z0 + float(rise), count * cell_area, volume))
    return points
