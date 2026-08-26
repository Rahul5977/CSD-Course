"""Golden tests: contour → DEM on surfaces whose elevation is known analytically."""

import numpy as np
import pytest
from pyproj import Transformer

from app.domain.contours import ContourLine, ContourSet
from app.engines.terrain.interpolate import contours_to_dem, densify, derive_resolution
from app.engines.terrain.surfaces import elevation_statistics, hillshade, slope_degrees

pytestmark = pytest.mark.golden

EPSG = 32644
TO_LONLAT = Transformer.from_crs(f"EPSG:{EPSG}", "EPSG:4326", always_xy=True)
# Any UTM-44N location; the tests care about geometry, not place.
X0, Y0 = 400_000.0, 2_350_000.0


def _line_lonlat(xy: np.ndarray, elevation: float) -> ContourLine:
    lon, lat = TO_LONLAT.transform(xy[:, 0], xy[:, 1])
    return ContourLine(elevation, np.column_stack([lon, lat]), "z_coordinate")


def inclined_plane_contours(
    gradient: float = 0.02, size: float = 1000.0, step: float = 5.0
) -> ContourSet:
    """Contours of z = gradient * x are vertical lines every step/gradient metres."""
    lines = []
    for z in np.arange(0.0, gradient * size + 1e-9, step):
        x = z / gradient
        xy = np.array([[X0 + x, Y0], [X0 + x, Y0 + size]])
        lines.append(_line_lonlat(xy, z))
    return ContourSet(tuple(lines), "z_coordinate")


def cone_contours(slope: float = 0.05, radius: float = 500.0, step: float = 5.0) -> ContourSet:
    """Contours of z = slope * (radius - r) are concentric circles."""
    lines = []
    theta = np.linspace(0, 2 * np.pi, 181)
    for z in np.arange(0.0, slope * radius - 1e-9, step):
        r = radius - z / slope
        xy = np.column_stack([X0 + r * np.cos(theta), Y0 + r * np.sin(theta)])
        lines.append(_line_lonlat(xy, z))
    return ContourSet(tuple(lines), "z_coordinate")


def test_inclined_plane_is_recovered_exactly_between_contours() -> None:
    result = contours_to_dem(inclined_plane_contours(), floor_m=10.0, resolution_m=10.0)
    dem = result.raster
    assert dem.grid.epsg == EPSG
    xs = dem.grid.x_min + (np.arange(dem.grid.cols) + 0.5) * dem.grid.cell_size
    expected = np.tile(0.02 * (xs - X0), (dem.grid.rows, 1))
    interior = slice(3, -3)
    rms = np.sqrt(np.mean((dem.data[interior, interior] - expected[interior, interior]) ** 2))
    # Reprojection round-trip and smoothing contribute a few centimetres at most.
    assert rms < 0.15, rms

    slope = slope_degrees(dem).data[interior, interior]
    assert abs(np.median(slope) - np.degrees(np.arctan(0.02))) < 0.05


def test_cone_is_recovered_radially() -> None:
    result = contours_to_dem(cone_contours(), floor_m=10.0, resolution_m=10.0)
    dem = result.raster
    rows, cols = dem.grid.shape
    xs = dem.grid.x_min + (np.arange(cols) + 0.5) * dem.grid.cell_size
    ys = dem.grid.y_max - (np.arange(rows) + 0.5) * dem.grid.cell_size
    gx, gy = np.meshgrid(xs, ys)
    r = np.hypot(gx - X0, gy - Y0)
    # Between the outermost and innermost rings the cone must be recovered.
    # Inside the innermost ring there is no contour above 20 m, so any
    # contour-derived DEM flattens the summit — a known, documented limitation.
    inside = (r < 450.0) & (r > 120.0)
    expected = 0.05 * (500.0 - r)
    rms = np.sqrt(np.mean((dem.data[inside] - expected[inside]) ** 2))
    assert rms < 0.25, rms
    stats = elevation_statistics(dem)
    assert stats["max"] == pytest.approx(20.0, abs=1.0), "summit flattened at the top contour"
    assert stats["min"] == pytest.approx(0.0, abs=1.0)


def test_resolution_is_derived_from_contour_spacing_and_floored() -> None:
    # 5 lines across 1000 m: true spacing 250 m. The estimator area/length
    # gives W/n = 200 m (bias (n-1)/n, negligible for real maps with hundreds of
    # lines), so the analytic expectation is stated in the estimator's terms.
    contours = inclined_plane_contours(gradient=0.02, step=5.0)
    result = contours_to_dem(contours, floor_m=10.0)
    assert result.contour_spacing_m == pytest.approx(1000.0 / 5, rel=0.02)
    assert result.resolution_m == pytest.approx(200.0 / 4, rel=0.02)

    dense = inclined_plane_contours(gradient=0.2, step=1.0)  # spacing 5 m
    result = contours_to_dem(dense, floor_m=10.0)
    assert result.resolution_m == 10.0, "must not go finer than the source floor"

    assert derive_resolution(1000.0, floor_m=10.0, cap_m=50.0) == 50.0


def test_densify_bounds_segment_length() -> None:
    xy = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 30.0]])
    dense = densify(xy, 10.0)
    assert np.all(np.hypot(*np.diff(dense, axis=0).T) <= 10.0 + 1e-9)
    assert np.allclose(dense[0], xy[0]) and np.allclose(dense[-1], xy[-1])


def test_hillshade_is_uniform_on_flat_ground_and_within_range() -> None:
    from app.domain.geo import GridSpec
    from app.domain.raster import Raster

    grid = GridSpec(EPSG, 0.0, 100.0, 10.0, 10, 10)
    flat = Raster(grid, np.full((10, 10), 250.0))
    shade = hillshade(flat).data
    assert shade.min() == shade.max()
    assert 1 <= shade.min() <= 255
    assert slope_degrees(flat).data.max() == 0.0
