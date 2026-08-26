"""Golden tests: delineation, streams, derived surfaces, contours and siting on analytic terrain."""

import itertools

import numpy as np
import pytest

from app.domain.errors import ValidationError
from app.domain.geo import GridSpec
from app.domain.raster import Raster
from app.engines.hydrology.catchment import delineate, snap_to_drainage, upstream_mask
from app.engines.hydrology.conditioning import fill_depressions
from app.engines.hydrology.flow import build_flow_model, stream_mask
from app.engines.hydrology.siting import impoundment, rank_sites
from app.engines.hydrology.streams import extract_links
from app.engines.terrain.contours import generate_contours
from app.engines.terrain.derived import curvatures, topographic_wetness_index
from app.engines.terrain.surfaces import slope_degrees

pytestmark = pytest.mark.golden
CELL = 10.0
GRID = GridSpec(32644, 500_000.0, 2_350_000.0, CELL, 40, 60)


def v_valley(axis_col: float = 30.0, side: float = 0.10, along: float = 0.01) -> Raster:
    """Z = side*|x - axis| + along*y: a straight valley draining south (row increases)."""
    rows, cols = GRID.shape
    cc, rr = np.meshgrid(np.arange(cols), np.arange(rows))
    z = 100.0 + side * np.abs(cc - axis_col) * CELL + along * (rows - 1 - rr) * CELL
    return Raster(GRID, z)


def test_v_valley_catchment_is_the_rectangle_upstream_of_the_outlet() -> None:
    """Every cell north of the outlet row drains to the valley axis, then south."""
    model = build_flow_model(fill_depressions(v_valley()).filled)
    outlet_row = 30
    mask = upstream_mask(model, outlet_row, 30)
    # Analytic: all cells in rows 0..outlet_row (both flanks) — the whole width.
    expected_cells = (outlet_row + 1) * GRID.cols
    assert mask.sum() == expected_cells
    assert mask[: outlet_row + 1].all() and not mask[outlet_row + 1 :].any()


def test_snap_moves_a_flank_click_to_the_nearest_channel_cell() -> None:
    model = build_flow_model(fill_depressions(v_valley()).filled)
    snap = snap_to_drainage(model, 20, 25, radius_m=150.0, min_area_m2=100 * GRID.cell_area)
    assert (snap.row, snap.col) == (20, 30)
    assert snap.distance_m == pytest.approx(5 * CELL)
    with pytest.raises(ValidationError):
        snap_to_drainage(model, 20, 2, radius_m=30.0, min_area_m2=100 * GRID.cell_area)


def test_delineate_reports_area_relief_and_truncation() -> None:
    model = build_flow_model(fill_depressions(v_valley()).filled)
    result = delineate(model, 30, 30, radius_m=50.0, min_area_m2=10 * GRID.cell_area)
    assert result.area_m2 == pytest.approx(31 * 60 * GRID.cell_area)
    assert result.touches_edge is True, "the catchment reaches the north edge of the map"
    assert result.longest_flow_path_m >= 30 * CELL
    assert result.relief_m > 0


def test_streams_follow_the_valley_axis_with_order_one() -> None:
    model = build_flow_model(fill_depressions(v_valley()).filled)
    mask = stream_mask(model, 500 * GRID.cell_area)
    assert mask[:, 30].sum() > 20 and not mask[:, :25].any()
    links = extract_links(model, mask)
    assert links and all(link.order == 1 for link in links), "a single channel has order 1"
    longest = max(links, key=lambda link: len(link.cells))
    assert all(c == 30 for _, c in longest.cells)


def test_two_tributaries_make_an_order_two_stream() -> None:
    rows, cols = GRID.shape
    cc, rr = np.meshgrid(np.arange(cols), np.arange(rows))
    # A "Y": two valley axes converge from cols 20 and 40 to col 30 at row 25,
    # then a single trunk continues south. Continuous, so no artificial steps.
    t = np.clip(rr / 25.0, 0, 1)
    axis_left, axis_right = 20 + 10 * t, 40 - 10 * t
    across = np.minimum(np.abs(cc - axis_left), np.abs(cc - axis_right))
    z = 100.0 + 0.10 * across * CELL + 0.02 * (rows - rr) * CELL
    model = build_flow_model(fill_depressions(Raster(GRID, z)).filled)
    links = extract_links(model, stream_mask(model, 150 * GRID.cell_area))
    assert max(link.order for link in links) == 2


def test_curvature_signs_and_twi_ordering() -> None:
    dem = v_valley()
    _profile, plan = curvatures(dem)
    # The valley axis is concave across the slope: plan curvature is negative there.
    assert plan.data[20, 30] < 0
    model = build_flow_model(fill_depressions(dem).filled)
    twi = topographic_wetness_index(dem, model.accumulation)
    assert twi.data[30, 30] > twi.data[30, 5], "valley floor is wetter than the flank"


def test_contours_are_generated_at_the_requested_interval_and_simplified() -> None:
    result = generate_contours(v_valley(), 2.0, smoothing_sigma_cells=0.0)
    assert result.levels >= 5
    assert result.vertices_after <= result.vertices_before
    assert all(line.elevation % 2.0 == 0 for line in result.lines)
    lon, lat = result.lines[0].coords_lonlat[0]
    assert 80 < lon < 82 and 21 < lat < 22


def test_siting_prefers_the_valley_floor_and_separates_candidates() -> None:
    dem = v_valley()
    model = build_flow_model(fill_depressions(dem).filled)
    slope = slope_degrees(dem).data
    twi = topographic_wetness_index(dem, model.accumulation).data
    stream = stream_mask(model, 50 * GRID.cell_area)
    result = rank_sites(model, slope, twi, stream, top_n=3, suppression_radius_m=100.0)
    assert len(result.candidates) == 3
    assert all(c.col == 30 for c in result.candidates), "candidates sit on the valley axis"
    rows_chosen = sorted(c.row for c in result.candidates)
    assert all(b - a >= 10 for a, b in itertools.pairwise(rows_chosen))
    assert result.candidates[0].score >= result.candidates[-1].score
    volume, area = impoundment(model, 30, 30, 2.0)
    assert volume > 0 and area > 0
    assert sum(result.weights.values()) == pytest.approx(1.0)
