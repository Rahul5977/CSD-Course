"""Contour lines → gridded DEM.

Algorithm: **linear interpolation on a Delaunay triangulation** (a TIN) of the
densified contour vertices, evaluated at cell centres, followed by a light
Gaussian smoothing pass.

Why a TIN and not splines or kriging: the answer must be explainable in a
viva in one sentence — "each cell takes the plane through the three nearest
contour vertices" — and it is exact on the contours themselves, which is the
one property a contour-derived DEM must have. Its known weakness, flat
triangles where all three vertices come from one contour (terracing on
ridge and valley lines), is what the smoothing pass is for; the residual
flats are then handled by the hydrological conditioning stage, which is
built to resolve flats anyway.

Grid resolution is **derived from the data**: mean horizontal contour spacing
is ``area / total contour length`` (exact for parallel contours), and the cell
size is a quarter of that so the surface between two contours is resolved by
at least four cells — floored at the source DEM's resolution so we never
manufacture detail the source does not contain.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from pyproj import Transformer
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.ndimage import gaussian_filter
from scipy.spatial import ConvexHull

from app.domain.contours import ContourSet
from app.domain.geo import GridSpec, assert_crs, utm_epsg_for
from app.domain.raster import Raster

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class InterpolationResult:
    """The DEM and the numbers that justify its resolution."""

    raster: Raster
    epsg: int
    resolution_m: float
    contour_spacing_m: float
    total_contour_length_m: float
    hull_area_m2: float
    points_used: int
    extrapolated_fraction: float
    aoi_xy: FloatArray | None
    method: str = "Delaunay TIN linear interpolation + Gaussian smoothing (sigma 1 cell)"


def project_lines(contours: ContourSet, epsg: int) -> tuple[list[FloatArray], FloatArray | None]:
    """Reproject every line (and the AOI ring, if any) to the UTM zone."""
    assert_crs(epsg)
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    projected: list[FloatArray] = []
    for line in contours.lines:
        x, y = transformer.transform(line.coords[:, 0], line.coords[:, 1])
        projected.append(np.column_stack([x, y]).astype(np.float64))
    aoi_xy: FloatArray | None = None
    if contours.aoi is not None:
        ax, ay = transformer.transform(contours.aoi[:, 0], contours.aoi[:, 1])
        aoi_xy = np.column_stack([ax, ay]).astype(np.float64)
    return projected, aoi_xy


def polyline_length(xy: FloatArray) -> float:
    """Length of a polyline in the units of its coordinates."""
    if xy.shape[0] < 2:
        return 0.0
    return float(np.sum(np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))))


def densify(xy: FloatArray, step: float) -> FloatArray:
    """Insert vertices so no segment is longer than ``step``.

    Without this, a long straight contour segment contributes two vertices and
    the triangulation across it is controlled by whatever lies beyond.
    """
    if xy.shape[0] < 2:
        return xy
    seg = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
    cumulative = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(cumulative[-1])
    if total <= step:
        return xy
    n = int(np.ceil(total / step)) + 1
    targets = np.linspace(0.0, total, n)
    x = np.interp(targets, cumulative, xy[:, 0])
    y = np.interp(targets, cumulative, xy[:, 1])
    return np.column_stack([x, y]).astype(np.float64)


def derive_resolution(
    contour_spacing_m: float, *, floor_m: float, cap_m: float, cells_per_spacing: float = 4.0
) -> float:
    """Cell size from mean contour spacing, clamped to ``[floor_m, cap_m]``."""
    raw = contour_spacing_m / cells_per_spacing
    return float(min(max(raw, floor_m), cap_m))


def contours_to_dem(
    contours: ContourSet,
    *,
    floor_m: float,
    cap_m: float = 50.0,
    resolution_m: float | None = None,
    smoothing_sigma_cells: float = 1.0,
) -> InterpolationResult:
    """Build a DEM from a contour set. Every parameter is derived unless overridden.

    Args:
        contours: Parsed contour lines in EPSG:4326.
        floor_m: Finest permissible cell size — the source DEM's resolution.
        cap_m: Coarsest cell size, so a sparse map still gets a usable grid.
        resolution_m: Explicit override, for tests and expert users.
        smoothing_sigma_cells: Gaussian sigma applied after triangulation; 0 disables.
    """
    lon, lat = contours.centroid
    epsg = utm_epsg_for(lon, lat)
    lines_xy, aoi_xy = project_lines(contours, epsg)

    total_length = float(sum(polyline_length(xy) for xy in lines_xy))
    all_xy = np.vstack(lines_xy)
    hull_area = float(ConvexHull(all_xy).volume) if all_xy.shape[0] >= 3 else 0.0
    spacing = hull_area / total_length if total_length > 0 else floor_m * 4
    resolution = (
        float(resolution_m)
        if resolution_m is not None
        else derive_resolution(spacing, floor_m=floor_m, cap_m=cap_m)
    )

    points: list[FloatArray] = []
    values: list[FloatArray] = []
    for line, xy in zip(contours.lines, lines_xy, strict=True):
        dense = densify(xy, resolution)
        points.append(dense)
        values.append(np.full(dense.shape[0], line.elevation, dtype=np.float64))
    pts = np.vstack(points)
    z = np.concatenate(values)
    # Duplicate vertices (shared corners, closed rings) upset the triangulation.
    pts_rounded = np.round(pts, 3)
    _, keep = np.unique(pts_rounded, axis=0, return_index=True)
    pts, z = pts[np.sort(keep)], z[np.sort(keep)]

    extent = all_xy if aoi_xy is None else np.vstack([all_xy, aoi_xy])
    x_min, y_min = extent.min(axis=0)
    x_max, y_max = extent.max(axis=0)
    cols = int(np.ceil((x_max - x_min) / resolution)) + 1
    rows = int(np.ceil((y_max - y_min) / resolution)) + 1
    grid = GridSpec(
        epsg=epsg,
        x_min=float(x_min),
        y_max=float(y_min) + rows * resolution,
        cell_size=resolution,
        rows=rows,
        cols=cols,
    )

    xs = grid.x_min + (np.arange(cols) + 0.5) * resolution
    ys = grid.y_max - (np.arange(rows) + 0.5) * resolution
    gx, gy = np.meshgrid(xs, ys)
    linear = LinearNDInterpolator(pts, z)
    dem = np.asarray(linear(gx, gy), dtype=np.float64)

    outside = np.isnan(dem)
    extrapolated = float(outside.mean())
    if outside.any():
        nearest = NearestNDInterpolator(pts, z)
        dem[outside] = nearest(gx[outside], gy[outside])

    if smoothing_sigma_cells > 0:
        dem = gaussian_filter(dem, sigma=smoothing_sigma_cells, mode="nearest")

    return InterpolationResult(
        raster=Raster(grid, dem),
        epsg=epsg,
        resolution_m=resolution,
        contour_spacing_m=float(spacing),
        total_contour_length_m=total_length,
        hull_area_m2=hull_area,
        points_used=int(pts.shape[0]),
        extrapolated_fraction=extrapolated,
        aoi_xy=aoi_xy,
    )
