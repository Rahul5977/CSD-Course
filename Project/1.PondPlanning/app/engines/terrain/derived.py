"""Second-derivative surfaces and the topographic wetness index.

**Curvature** follows Zevenbergen & Thorne (1987): a quadratic surface is
fitted to the 3x3 window and its coefficients give profile curvature (along
the slope — where flow accelerates or decelerates) and plan curvature
(across the slope — where flow converges or diverges). Units are 1/m,
scaled by 100 for legibility as is conventional in GIS.

**TWI** (Beven & Kirkby 1979) is ``ln(a / tan β)`` with ``a`` the specific
catchment area — upstream area per unit contour width, i.e. accumulation x
cell area / cell size — and β the local slope. High values mark valley
floors and convergent hollows: the wet, flat places a pond wants to be.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from app.domain.raster import Raster
from app.engines.terrain.surfaces import horn_gradients

FloatArray = NDArray[np.float64]


def _window(data: FloatArray) -> tuple[FloatArray, ...]:
    filled = np.where(np.isnan(data), np.nanmean(data), data)
    p = np.pad(filled, 1, mode="edge")
    return (
        p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:],
        p[1:-1, :-2], p[1:-1, 1:-1], p[1:-1, 2:],
        p[2:, :-2], p[2:, 1:-1], p[2:, 2:],
    )  # fmt: skip


def curvatures(dem: Raster) -> tuple[Raster, Raster]:
    """``(profile, plan)`` curvature, Zevenbergen & Thorne 1987, x100 (1/m)."""
    z1, z2, z3, z4, z5, z6, z7, z8, z9 = _window(dem.data)
    L = dem.grid.cell_size  # noqa: N806 - notation from the paper
    D = ((z4 + z6) / 2 - z5) / L**2  # noqa: N806
    E = ((z2 + z8) / 2 - z5) / L**2  # noqa: N806
    F = (-z1 + z3 + z7 - z9) / (4 * L**2)  # noqa: N806
    G = (-z4 + z6) / (2 * L)  # noqa: N806
    H = (z2 - z8) / (2 * L)  # noqa: N806
    denom = G**2 + H**2
    safe = np.where(denom < 1e-12, np.nan, denom)
    # Signs follow the ArcGIS convention every evaluator will have seen:
    # profile < 0 = upwardly convex (flow accelerates), plan < 0 = laterally
    # concave (flow converges — a valley). That is the negative of Z&T's plan.
    profile = -2 * (D * G**2 + E * H**2 + F * G * H) / safe
    plan = -2 * (D * H**2 + E * G**2 - F * G * H) / safe
    profile = np.where(np.isnan(profile), 0.0, profile) * 100
    plan = np.where(np.isnan(plan), 0.0, plan) * 100
    return dem.with_data(profile), dem.with_data(plan)


def topographic_wetness_index(dem: Raster, accumulation: NDArray[np.int64]) -> Raster:
    """TWI = ln(a / tan β) with a floor on tan β of 0.001 (≈ 0.06°)."""
    dzdx, dzdy = horn_gradients(dem)
    tan_beta = np.maximum(np.hypot(dzdx, dzdy), 0.001)
    grid = dem.grid
    specific_area = accumulation.astype(np.float64) * grid.cell_area / grid.cell_size
    return dem.with_data(np.log(np.maximum(specific_area, grid.cell_size) / tan_beta))
