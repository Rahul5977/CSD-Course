"""D8 flow direction, flow accumulation and stream extraction.

**D8** (O'Callaghan & Mark 1984): every cell drains to the one of its eight
neighbours with the steepest downward slope, diagonals divided by sqrt(2).
Deterministic, single-receiver, and the model every GIS the evaluator may
open uses by default — see ADR 0009 for why D-infinity is a documented stub.

**Accumulation** is computed by processing cells from highest to lowest and
handing each cell's count (its own cell plus everything it has received) to
its receiver. On a filled+ε surface every cell has a strictly lower receiver
or is an outlet, so descending-elevation order *is* a topological order;
one pass over the sorted cells is exact. O(n log n) for the sort.

**Streams** are the cells whose upstream area exceeds a threshold. The
threshold is the one visibly consequential knob in the chain, so it is
expressed as an *area* (m²) rather than a cell count — the same 5 ha means
the same thing on a 10 m and a 30 m grid — and calibrated by overlaying the
result on satellite imagery (see the P2 decision log).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.raster import Raster
from app.engines.hydrology.conditioning import NEIGHBOURS

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

#: D8 code per neighbour index (ESRI convention: E=1, SE=2, S=4, SW=8, W=16, NW=32, N=64, NE=128).
D8_CODES: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128)
NO_FLOW = 0
_SQRT2 = float(np.sqrt(2.0))


@dataclass(frozen=True, slots=True)
class FlowModel:
    """Routing state for a conditioned DEM, reused by every downstream engine."""

    filled: Raster
    direction: NDArray[np.uint8]  # D8 code, 0 = outlet / nodata
    receiver: IntArray  # flat index of the receiving cell, -1 for outlets
    accumulation: IntArray  # cells draining through each cell, itself included

    @property
    def shape(self) -> tuple[int, int]:
        """``(rows, cols)``."""
        return self.filled.grid.shape

    def upstream_area_m2(self) -> FloatArray:
        """Accumulation converted to square metres."""
        return self.accumulation.astype(np.float64) * self.filled.grid.cell_area


def flow_direction(filled: Raster) -> tuple[NDArray[np.uint8], IntArray]:
    """D8 direction codes and receiver indices for a filled DEM.

    Vectorised: eight shifted copies of the surface give eight slope arrays;
    the argmax over them is the receiver. Cells with no lower neighbour (grid
    edge outlets, nodata borders) get code 0 and receiver -1.
    """
    z = filled.data
    rows, cols = z.shape
    padded = np.pad(z, 1, mode="constant", constant_values=np.nan)
    best_slope = np.full(z.shape, 0.0)
    best_index = np.full(z.shape, -1, dtype=np.int64)
    for k, (dr, dc) in enumerate(NEIGHBOURS):
        neighbour = padded[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        distance = _SQRT2 if dr and dc else 1.0
        slope = (z - neighbour) / distance
        slope = np.where(np.isnan(slope), -np.inf, slope)
        better = slope > best_slope
        best_slope = np.where(better, slope, best_slope)
        best_index = np.where(better, k, best_index)

    direction = np.zeros(z.shape, dtype=np.uint8)
    receiver = np.full(z.shape, -1, dtype=np.int64)
    rr, cc = np.indices(z.shape)
    for k, (dr, dc) in enumerate(NEIGHBOURS):
        mask = best_index == k
        direction[mask] = D8_CODES[k]
        receiver[mask] = (rr[mask] + dr) * cols + (cc[mask] + dc)
    receiver[np.isnan(z)] = -1
    direction[np.isnan(z)] = NO_FLOW
    return direction, receiver


def flow_accumulation(filled: Raster, receiver: IntArray) -> IntArray:
    """Number of cells draining through each cell, itself included."""
    z = filled.data.ravel()
    flat_receiver = receiver.ravel()
    order = np.argsort(-z, kind="stable")  # highest first; NaN sorts last
    acc = np.ones(z.size, dtype=np.int64)
    acc[np.isnan(z)] = 0
    for index in order:
        target = flat_receiver[index]
        if target >= 0:
            acc[target] += acc[index]
    return acc.reshape(filled.grid.shape)


def build_flow_model(filled: Raster) -> FlowModel:
    """Direction + accumulation in one object."""
    direction, receiver = flow_direction(filled)
    acc = flow_accumulation(filled, receiver)
    return FlowModel(filled=filled, direction=direction, receiver=receiver, accumulation=acc)


def threshold_cells(threshold_area_m2: float, cell_area_m2: float, minimum: int = 10) -> int:
    """Convert an area threshold to a cell count for this grid."""
    return max(minimum, round(threshold_area_m2 / cell_area_m2))


def stream_mask(model: FlowModel, threshold_area_m2: float) -> NDArray[np.bool_]:
    """Cells whose upstream area meets the threshold."""
    cells = threshold_cells(threshold_area_m2, model.filled.grid.cell_area)
    return model.accumulation >= cells


def donors(receiver: IntArray) -> tuple[IntArray, IntArray]:
    """Inverse D8 as CSR: ``(offsets, donor_indices)`` so upstream walks are O(degree)."""
    flat = receiver.ravel()
    has = flat >= 0
    targets = flat[has]
    sources = np.nonzero(has)[0]
    order = np.argsort(targets, kind="stable")
    counts = np.bincount(targets[order], minlength=flat.size)
    offsets = np.concatenate([[0], np.cumsum(counts)])
    return offsets, sources[order]
