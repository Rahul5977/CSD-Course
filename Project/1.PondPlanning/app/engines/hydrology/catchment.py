"""Catchment delineation: snap the pour point to drainage, walk upstream.

**Snapping.** A click one cell off a channel returns a hillslope catchment
orders of magnitude too small — the single most visible failure in this
class of system. The pour point is therefore moved to the *nearest* cell
within a radius whose upstream area meets a minimum; nearest rather than
largest, so a click on a tributary is not dragged onto the main river. The
distance moved is returned and shown in the UI (``snap_distance``), because
a large snap is the signal to distrust the result.

**Delineation.** Breadth-first search over the inverse D8 graph (donor
lists) from the snapped outlet. Every cell reached drains through the
outlet by construction. O(catchment size).

**Truncation.** A catchment that touches the grid edge is cut by the map,
not by a divide; the result carries a ``catchment_truncated`` warning so
the number is never presented as complete.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import ValidationError
from app.engines.hydrology.conditioning import NEIGHBOURS
from app.engines.hydrology.flow import FlowModel, donors

BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class SnapResult:
    """Where the pour point ended up, and how far it moved."""

    row: int
    col: int
    requested_row: int
    requested_col: int
    distance_m: float
    accumulation_cells: int


@dataclass(frozen=True, slots=True)
class Catchment:
    """A delineated contributing area with its headline metrics."""

    mask: BoolArray
    outlet: SnapResult
    area_m2: float
    cell_count: int
    longest_flow_path_m: float
    relief_m: float
    outlet_elevation_m: float
    touches_edge: bool


def snap_to_drainage(
    model: FlowModel, row: int, col: int, *, radius_m: float, min_area_m2: float
) -> SnapResult:
    """Move ``(row, col)`` to the nearest cell with enough upstream area.

    Raises:
        ValidationError: If no cell within the radius drains the minimum area.
    """
    grid = model.filled.grid
    cell = grid.cell_size
    r_cells = max(1, int(np.ceil(radius_m / cell)))
    min_cells = max(1, round(min_area_m2 / grid.cell_area))
    r0, r1 = max(0, row - r_cells), min(grid.rows, row + r_cells + 1)
    c0, c1 = max(0, col - r_cells), min(grid.cols, col + r_cells + 1)
    window = model.accumulation[r0:r1, c0:c1]
    rr, cc = np.indices(window.shape)
    rr = rr + r0
    cc = cc + c0
    distance = np.hypot((rr - row) * cell, (cc - col) * cell)
    eligible = (window >= min_cells) & (distance <= radius_m + 1e-9)
    if not eligible.any():
        msg = "no modelled drainage within the snap radius of this point"
        raise ValidationError(
            msg,
            {
                "radius_m": radius_m,
                "min_area_m2": min_area_m2,
                "max_upstream_area_m2": float(window.max() * grid.cell_area),
            },
        )
    # Nearest first; among equals, the larger channel.
    score = np.where(eligible, distance - 1e-6 * window, np.inf)
    k = np.argmin(score)
    sr, sc = int(rr.flat[k]), int(cc.flat[k])
    return SnapResult(
        row=sr,
        col=sc,
        requested_row=row,
        requested_col=col,
        distance_m=float(distance.flat[k]),
        accumulation_cells=int(window.flat[k]),
    )


def upstream_mask(model: FlowModel, row: int, col: int) -> BoolArray:
    """Every cell that drains through ``(row, col)``, itself included (BFS)."""
    rows, cols = model.shape
    offsets, idx = donors(model.receiver)
    mask = np.zeros(rows * cols, dtype=bool)
    start = row * cols + col
    mask[start] = True
    queue: deque[int] = deque([start])
    while queue:
        cell = queue.popleft()
        for donor in idx[offsets[cell] : offsets[cell + 1]]:
            if not mask[donor]:
                mask[donor] = True
                queue.append(int(donor))
    return mask.reshape(rows, cols)


def flow_lengths_to_outlet(model: FlowModel, mask: BoolArray, row: int, col: int) -> float:
    """Longest D8 flow path (metres) from any cell in ``mask`` to the outlet."""
    rows, cols = model.shape
    cell = model.filled.grid.cell_size
    offsets, idx = donors(model.receiver)
    start = row * cols + col
    dist = np.full(rows * cols, -1.0)
    dist[start] = 0.0
    queue: deque[int] = deque([start])
    flat_mask = mask.ravel()
    while queue:
        current = queue.popleft()
        cr, cc = divmod(current, cols)
        for donor in idx[offsets[current] : offsets[current + 1]]:
            if not flat_mask[donor] or dist[donor] >= 0:
                continue
            dr, dc = divmod(int(donor), cols)
            step = cell * (np.sqrt(2.0) if (dr != cr and dc != cc) else 1.0)
            dist[donor] = dist[current] + step
            queue.append(int(donor))
    return float(dist.max())


def delineate(
    model: FlowModel, row: int, col: int, *, radius_m: float, min_area_m2: float
) -> Catchment:
    """Snap, then delineate, then measure."""
    snap = snap_to_drainage(model, row, col, radius_m=radius_m, min_area_m2=min_area_m2)
    mask = upstream_mask(model, snap.row, snap.col)
    grid = model.filled.grid
    z = model.filled.data[mask]
    edge = mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any()
    return Catchment(
        mask=mask,
        outlet=snap,
        area_m2=float(mask.sum() * grid.cell_area),
        cell_count=int(mask.sum()),
        longest_flow_path_m=flow_lengths_to_outlet(model, mask, snap.row, snap.col),
        relief_m=float(np.nanmax(z) - np.nanmin(z)),
        outlet_elevation_m=float(model.filled.data[snap.row, snap.col]),
        touches_edge=bool(edge),
    )


def neighbours_of(row: int, col: int, rows: int, cols: int) -> list[tuple[int, int]]:
    """In-grid 8-neighbours."""
    return [
        (row + dr, col + dc)
        for dr, dc in NEIGHBOURS
        if 0 <= row + dr < rows and 0 <= col + dc < cols
    ]
