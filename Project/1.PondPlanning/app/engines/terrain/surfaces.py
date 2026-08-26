"""First-derivative terrain surfaces: slope, aspect, hillshade.

Slope and aspect use **Horn's (1981) 3x3 finite-difference kernel**, the same
estimator as GDAL and ArcGIS, so the numbers are directly comparable to any
GIS the evaluator opens. Hillshade is the standard Lambertian illumination of
that surface from a light at azimuth 315°, altitude 45° — the cartographic
convention, chosen so the rendered relief reads correctly to a human eye.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from app.domain.raster import Raster

FloatArray = NDArray[np.float64]


def _padded(data: FloatArray) -> FloatArray:
    filled = np.where(np.isnan(data), np.nanmean(data), data)
    return np.pad(filled, 1, mode="edge")


def horn_gradients(dem: Raster) -> tuple[FloatArray, FloatArray]:
    """Return ``(dz/dx, dz/dy)`` by Horn's kernel, in metre per metre.

    Row 0 is north, so ``dz/dy`` is positive when the ground rises northward.
    """
    p = _padded(dem.data)
    cell = dem.grid.cell_size
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * cell)
    dzdy = ((a + 2 * b + c) - (g + 2 * h + i)) / (8.0 * cell)
    return dzdx, dzdy


def slope_degrees(dem: Raster) -> Raster:
    """Slope in degrees from the horizontal."""
    dzdx, dzdy = horn_gradients(dem)
    return dem.with_data(np.degrees(np.arctan(np.hypot(dzdx, dzdy))))


def aspect_degrees(dem: Raster) -> Raster:
    """Downslope direction, degrees clockwise from north; flat cells are NaN."""
    dzdx, dzdy = horn_gradients(dem)
    aspect = np.degrees(np.arctan2(dzdx, dzdy))  # 0 = north, 90 = east
    aspect = np.where(aspect < 0, aspect + 360.0, aspect)
    aspect = np.where(np.hypot(dzdx, dzdy) < 1e-9, np.nan, aspect)
    return dem.with_data(aspect)


def hillshade(dem: Raster, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> Raster:
    """Lambertian hillshade scaled to 1..255 (0 is reserved for nodata)."""
    dzdx, dzdy = horn_gradients(dem)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(dzdx, dzdy)
    zenith = np.radians(90.0 - altitude_deg)
    azimuth = np.radians(azimuth_deg)
    shade = np.cos(zenith) * np.cos(slope) + np.sin(zenith) * np.sin(slope) * np.cos(
        azimuth - aspect
    )
    scaled = 1.0 + 254.0 * np.clip(shade, 0.0, 1.0)
    return dem.with_data(np.round(scaled))


def elevation_statistics(dem: Raster) -> dict[str, float]:
    """Min, max, mean and relief over valid cells."""
    data = dem.data[dem.valid]
    lo, hi = float(data.min()), float(data.max())
    return {"min": lo, "max": hi, "mean": float(data.mean()), "relief": hi - lo}
