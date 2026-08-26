"""The CRS guard and the grid arithmetic — the two things that stop degree-area bugs."""

import numpy as np
import pytest

from app.domain.errors import CRSError, GeometryError
from app.domain.geo import GridSpec, assert_crs, utm_epsg_for
from app.domain.raster import Raster


@pytest.mark.parametrize(
    ("lon", "lat", "expected"),
    [
        (81.297, 21.2517, 32644),  # the sample's centroid → UTM 44N
        (77.2, 28.6, 32643),  # Delhi → 43N
        (-3.7, 40.4, 32630),  # Madrid → 30N
        (151.2, -33.9, 32756),  # Sydney → 56S
        (-179.9, 10.0, 32601),
        (179.9, 10.0, 32660),
    ],
)
def test_utm_zone_is_derived_from_the_point(lon: float, lat: float, expected: int) -> None:
    assert utm_epsg_for(lon, lat) == expected


def test_utm_rejects_impossible_coordinates() -> None:
    with pytest.raises(GeometryError):
        utm_epsg_for(200.0, 0.0)


def test_assert_crs_fails_on_a_geographic_grid() -> None:
    """The G1 exit criterion: an EPSG:4326 array must be refused."""
    with pytest.raises(CRSError) as excinfo:
        assert_crs(4326)
    assert excinfo.value.code == "crs_error"
    with pytest.raises(CRSError):
        GridSpec(epsg=4326, x_min=0, y_max=0, cell_size=1, rows=1, cols=1)


def test_assert_crs_fails_on_a_zone_mismatch() -> None:
    with pytest.raises(CRSError):
        assert_crs(32644, expected=32645)
    assert_crs(32644, expected=32644)


def test_grid_index_round_trips_through_cell_centres() -> None:
    grid = GridSpec(epsg=32644, x_min=1000.0, y_max=2000.0, cell_size=10.0, rows=5, cols=8)
    for row in range(5):
        for col in range(8):
            assert grid.index_of(*grid.cell_center(row, col)) == (row, col)
    assert grid.bounds == (1000.0, 1950.0, 1080.0, 2000.0)
    assert grid.cell_area == 100.0
    with pytest.raises(GeometryError):
        grid.index_of(999.0, 2000.0)


def test_raster_shape_must_match_grid() -> None:
    grid = GridSpec(epsg=32644, x_min=0, y_max=0, cell_size=1, rows=2, cols=3)
    Raster(grid, np.zeros((2, 3)))
    with pytest.raises(GeometryError):
        Raster(grid, np.zeros((3, 2)))
