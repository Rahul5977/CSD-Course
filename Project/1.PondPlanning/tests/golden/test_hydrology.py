"""Golden tests for conditioning and D8 on surfaces with known answers."""

import numpy as np
import pytest

from app.domain.geo import GridSpec
from app.domain.raster import Raster
from app.engines.hydrology.conditioning import fill_depressions
from app.engines.hydrology.flow import (
    build_flow_model,
    donors,
    flow_accumulation,
    flow_direction,
    stream_mask,
    threshold_cells,
)

pytestmark = pytest.mark.golden
GRID = GridSpec(32644, 0.0, 1000.0, 10.0, 20, 30)


def plane(gradient_x: float = 0.01, gradient_y: float = 0.0) -> Raster:
    rows, cols = GRID.shape
    cc, rr = np.meshgrid(np.arange(cols), np.arange(rows))
    return Raster(GRID, 100.0 + gradient_x * cc * 10 + gradient_y * rr * 10)


def test_priority_flood_fills_an_artificial_pit_and_nothing_else() -> None:
    dem = plane()
    data = dem.data.copy()
    data[10, 15] -= 5.0  # a 5 m pit in the middle of the slope
    result = fill_depressions(dem.with_data(data))
    # The pit rises to its spill level: the lowest neighbour + epsilon.
    spill = min(data[r, c] for r, c in [(10, 14), (9, 14), (11, 14)])
    assert result.filled.data[10, 15] == pytest.approx(spill + result.epsilon, abs=1e-6)
    assert result.cells_filled == 1
    assert result.max_fill_m == pytest.approx(spill - data[10, 15], abs=1e-3)
    untouched = np.ones(data.shape, bool)
    untouched[10, 15] = False
    assert np.allclose(result.filled.data[untouched], data[untouched])


def test_priority_flood_resolves_a_flat_so_every_cell_drains() -> None:
    dem = plane()
    data = dem.data.copy()
    data[5:15, 5:25] = 100.5  # a big flat terrace, higher than the ground to its west
    filled = fill_depressions(dem.with_data(data)).filled
    _direction, receiver = flow_direction(filled)
    interior = receiver[1:-1, 1:-1]
    assert (interior >= 0).all(), "every interior cell must have a receiver after +epsilon"


def test_plane_accumulation_is_the_number_of_cells_upslope_in_the_row() -> None:
    """Z rises eastward, so every cell drains west; accumulation at column c = cols - c."""
    model = build_flow_model(plane())
    rows, cols = GRID.shape
    expected = np.tile(np.arange(cols, 0, -1), (rows, 1))
    assert np.array_equal(model.accumulation, expected)
    assert (model.direction[:, 1:] == 16).all()  # W
    assert (model.receiver[:, 0] == -1).all()  # west edge cells are outlets


def test_bowl_drains_everything_to_its_centre_and_fills_to_its_rim() -> None:
    rows, cols = GRID.shape
    cc, rr = np.meshgrid(np.arange(cols), np.arange(rows))
    r = np.hypot((cc - 14.5) * 10, (rr - 9.5) * 10)
    dem = Raster(GRID, 100.0 + 0.05 * r)  # a bowl, lowest at the four centre cells
    # Unconditioned: D8 sends every cell to the centre (four symmetric outlets).
    model = build_flow_model(dem)
    assert int(model.accumulation[9:11, 14:16].sum()) == rows * cols
    # Conditioned: the bowl is one closed depression, so Priority-Flood raises
    # it to its spill point on the grid edge and every cell drains outward.
    filled = fill_depressions(dem).filled
    assert filled.data.min() >= dem.data[0, :].min() - 1e-9
    model = build_flow_model(filled)
    assert (model.receiver[1:-1, 1:-1] >= 0).all()


def test_threshold_is_expressed_as_an_area() -> None:
    assert threshold_cells(50_000.0, 100.0) == 500
    assert threshold_cells(1.0, 100.0) == 10, "floor of ten cells"
    model = build_flow_model(plane())
    mask = stream_mask(model, 100.0 * 20)  # ≥ 20 cells upstream → the westmost 11 columns
    assert mask[:, :11].all() and not mask[:, 11:].any()


def test_donor_lists_invert_the_receivers() -> None:
    model = build_flow_model(plane())
    offsets, idx = donors(model.receiver)
    cols = GRID.cols
    cell = 5 * cols + 10  # row 5, col 10 receives from row 5, col 11 only
    assert list(idx[offsets[cell] : offsets[cell + 1]]) == [5 * cols + 11]
    acc = flow_accumulation(model.filled, model.receiver)
    assert acc[5, 10] == cols - 10
