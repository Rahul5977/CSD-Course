"""Hydrological conditioning: depression filling and flat resolution.

Algorithm: **Priority-Flood + ε** (Barnes, Lehman & Mulla 2014, building on
Wang & Liu 2006). Cells are popped from a priority queue in order of
elevation starting from the grid edge; each neighbour is raised to at least
the popped cell's elevation *plus a tiny increment* before being pushed.
One pass therefore both fills every closed depression and imposes a
monotone gradient across the resulting flat surfaces, so D8 can route flow
off them. O(n log n) on the heap.

Why this and not a "breach" algorithm: a filled DEM is the textbook input
to D8, the result is deterministic, and the before/after difference raster
(:func:`fill_depth`) is itself an evidence figure — it shows exactly which
cells were altered and by how much. On a contour-interpolated DEM the
"sinks" are mostly TIN artefacts between contours, and filling them is the
right correction.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.raster import Raster

FloatArray = NDArray[np.float64]

#: Eight neighbours, row/col offsets, in D8 code order (E, SE, S, SW, W, NW, N, NE).
NEIGHBOURS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 1),
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, -1),
    (-1, 0),
    (-1, 1),
)


@dataclass(frozen=True, slots=True)
class ConditionedDEM:
    """The filled surface and the record of what was changed."""

    filled: Raster
    fill_depth: Raster  # metres added per cell; 0 where untouched
    cells_filled: int
    max_fill_m: float
    epsilon: float


def fill_depressions(dem: Raster, epsilon: float = 1e-4) -> ConditionedDEM:
    """Priority-Flood + ε over a DEM. ``NaN`` cells are treated as off-grid.

    Args:
        dem: Working DEM in a UTM grid.
        epsilon: The gradient imposed across flats, in metres per cell. Small
            enough to be physically negligible, large enough to be resolved in
            float64 over the longest plausible flat.
    """
    z = dem.data
    rows, cols = z.shape
    valid = ~np.isnan(z)
    filled = np.where(valid, z, np.inf)
    closed = ~valid  # NaN cells are never processed
    heap: list[tuple[float, int, int]] = []

    # Seed the queue with every valid cell on the grid edge (or adjacent to nodata).
    for r in range(rows):
        for c in range(cols):
            if not valid[r, c]:
                continue
            on_edge = r in (0, rows - 1) or c in (0, cols - 1)
            if not on_edge:
                on_edge = any(
                    not valid[r + dr, c + dc]
                    for dr, dc in NEIGHBOURS
                    if 0 <= r + dr < rows and 0 <= c + dc < cols
                )
            if on_edge:
                heapq.heappush(heap, (float(filled[r, c]), r, c))
                closed[r, c] = True

    while heap:
        zc, r, c = heapq.heappop(heap)
        for dr, dc in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or closed[nr, nc]:
                continue
            closed[nr, nc] = True
            if filled[nr, nc] <= zc:
                filled[nr, nc] = zc + epsilon
            heapq.heappush(heap, (float(filled[nr, nc]), nr, nc))

    out = np.where(valid, filled, np.nan)
    depth = np.where(valid, out - z, 0.0)
    changed = depth > epsilon * 1.5
    return ConditionedDEM(
        filled=dem.with_data(out),
        fill_depth=dem.with_data(depth),
        cells_filled=int(changed.sum()),
        max_fill_m=float(depth.max()) if depth.size else 0.0,
        epsilon=epsilon,
    )
