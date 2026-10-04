"""Concrete :class:`~app.domain.dem.DEMProvider` implementations.

Adapter pattern over the DEM port. The hydrology chain downstream is written
once against :class:`DEMProduct`; these classes are the only places that know
where elevations come from.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from pyproj import Transformer
from scipy.interpolate import NearestNDInterpolator

from app.domain.contours import ContourSet
from app.domain.dem import DEMProduct, DEMProvenance, ProgressCallback
from app.domain.errors import AreaOutOfRangeError
from app.domain.geo import GridSpec, utm_epsg_for
from app.domain.raster import Raster
from app.engines.terrain.interpolate import contours_to_dem
from app.providers.contour_kml import parse_contours
from app.providers.dem_provenance import infer_provenance

GLO30_CELL_M = 30.0


class ContourKMLAdapter:
    """DEM from an uploaded KML/KMZ contour map — the Phase 2 path (ADR 0011).

    Everything is derived from the upload: elevation strategy, UTM zone, source
    provenance, grid resolution. ``default_floor_m`` is only used when the file
    does not identify its own source DEM, and the result then carries a warning.
    """

    name = "contour_kml"

    def __init__(self, payload: bytes, filename: str, *, default_floor_m: float) -> None:
        """Hold the raw upload; nothing is parsed until :meth:`produce`."""
        self._payload = payload
        self._filename = filename
        self._default_floor_m = default_floor_m

    def produce(self, on_progress: ProgressCallback | None = None) -> DEMProduct:
        """Parse → provenance → interpolate, reporting progress at each stage."""
        report = on_progress or (lambda _p, _s: None)
        report(5, "parsing contour map")
        contours = parse_contours(self._payload, self._filename)
        provenance = infer_provenance(
            contours.metadata_text, default_resolution_m=self._default_floor_m
        )
        report(20, "triangulating contours")
        result = contours_to_dem(contours, floor_m=provenance.native_resolution_m)
        report(45, "DEM gridded")
        return DEMProduct(
            raster=result.raster,
            provenance=provenance,
            working_resolution_m=result.resolution_m,
            method=result.method,
            warnings=self._warnings(contours, provenance, result.extrapolated_fraction),
            details={
                "contour_count": len(contours.lines),
                "vertex_count": contours.vertex_count,
                "elevation_source": contours.elevation_source,
                "strategy_counts": contours.strategy_counts,
                "skipped_lines": contours.skipped,
                "contour_interval_m": contours.interval,
                "contour_spacing_m": result.contour_spacing_m,
                "total_contour_length_m": result.total_contour_length_m,
                "bounds_lonlat": list(contours.bounds),
                "aoi_lonlat": None if contours.aoi is None else contours.aoi.tolist(),
                "aoi_xy": None if result.aoi_xy is None else result.aoi_xy.tolist(),
                "points_used": result.points_used,
                "extrapolated_fraction": result.extrapolated_fraction,
                "source_file": self._filename,
            },
        )

    @staticmethod
    def _warnings(
        contours: ContourSet, provenance: DEMProvenance, extrapolated: float
    ) -> tuple[tuple[str, str, str], ...]:
        warnings: list[tuple[str, str, str]] = []
        if provenance.assumed:
            warnings.append(
                (
                    "source_unknown",
                    "The upload does not identify its source DEM; a "
                    f"{provenance.native_resolution_m:g} m resolution and conservative "
                    "vertical accuracy were assumed.",
                    "caution",
                )
            )
        if contours.interval and provenance.native_resolution_m >= 10 * contours.interval:
            warnings.append(
                (
                    "interpolated_precision",
                    f"Contours are at {contours.interval:g} m but the source DEM is "
                    f"~{provenance.native_resolution_m:g} m with ±"
                    f"{provenance.vertical_accuracy_relative_m:g} m relative accuracy. "
                    "Relief below roughly that band is interpolated, not measured.",
                    "caution",
                )
            )
        if contours.skipped:
            warnings.append(
                (
                    "contours_skipped",
                    f"{contours.skipped} line(s) had no readable elevation and were ignored.",
                    "info",
                )
            )
        if extrapolated > 0.10:
            warnings.append(
                (
                    "extrapolated_margin",
                    f"{extrapolated:.0%} of the grid lies outside the contour coverage and was "
                    "filled by nearest-neighbour; treat results near the edge with care.",
                    "caution",
                )
            )
        return tuple(warnings)


def grid_for_bounds(bounds_lonlat: tuple[float, float, float, float], cell_m: float) -> GridSpec:
    """UTM grid over a lon/lat box: zone from its centroid, envelope of the projected corners."""
    west, south, east, north = bounds_lonlat
    epsg = utm_epsg_for((west + east) / 2, (south + north) / 2)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    xs, ys = to_utm.transform([west, east, east, west], [south, south, north, north])
    x_min, x_max, y_min, y_max = min(xs), max(xs), min(ys), max(ys)
    cols = int(np.ceil((x_max - x_min) / cell_m))
    rows = int(np.ceil((y_max - y_min) / cell_m))
    return GridSpec(
        epsg=epsg,
        x_min=float(x_min),
        y_max=float(y_min) + rows * cell_m,
        cell_size=cell_m,
        rows=rows,
        cols=cols,
    )


def box_area_km2(bounds_lonlat: tuple[float, float, float, float]) -> float:
    """Area of a lon/lat box in km², measured in its own UTM zone (never in degrees)."""
    west, south, east, north = bounds_lonlat
    epsg = utm_epsg_for((west + east) / 2, (south + north) / 2)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    xs, ys = to_utm.transform([west, east, east, west], [south, south, north, north])
    # Shoelace on the projected quadrilateral.
    area = 0.5 * abs(sum(xs[i] * ys[i - 1] - xs[i - 1] * ys[i] for i in range(4)))
    return float(area / 1e6)


def check_area(
    bounds_lonlat: tuple[float, float, float, float], min_km2: float, max_km2: float
) -> float:
    """Return the box area in km², or raise if it is outside ``[min_km2, max_km2]``.

    Raises:
        AreaOutOfRangeError: Too small to hold a catchment, or too large to analyse fast.
    """
    area = box_area_km2(bounds_lonlat)
    if not min_km2 <= area <= max_km2:
        msg = (
            f"selected area is {area:.2f} km²; select between {min_km2:g} and {max_km2:g} km² "
            "(a village-sized box)"
        )
        raise AreaOutOfRangeError(
            msg, {"area_km2": round(area, 3), "min_km2": min_km2, "max_km2": max_km2}
        )
    return area


class ProviderTileAdapter:
    """DEM for a box selected on the map, from Copernicus GLO-30 tiles (Phase 3).

    The second implementation of the :class:`~app.domain.dem.DEMProvider` port
    (ADR 0011, ADR 0020): the hydrology chain downstream is exactly the one the
    contour path uses and the golden tests cover. The grid is the source's
    native 30 m in the box's own UTM zone — no finer, because the source has
    no more detail, and no coarser, because a village catchment is only a few
    hundred cells.
    """

    name = "copernicus_glo30"

    def __init__(
        self,
        bounds_lonlat: tuple[float, float, float, float],
        *,
        read: Callable[[tuple[float, float, float, float], GridSpec], Raster],
        read_water: Callable[[GridSpec], NDArray[np.bool_] | None] | None = None,
    ) -> None:
        """Hold the box and the tile readers (injected, so tests read local tiles)."""
        self._bounds = bounds_lonlat
        self._read = read
        self._read_water = read_water

    def produce(self, on_progress: ProgressCallback | None = None) -> DEMProduct:
        """Grid → windowed tile read + warp → gap fill, reporting progress."""
        report = on_progress or (lambda _p, _s: None)
        provenance = infer_provenance("Copernicus GLO-30", default_resolution_m=GLO30_CELL_M)
        grid = grid_for_bounds(self._bounds, provenance.native_resolution_m)
        report(10, "reading Copernicus GLO-30 elevation tiles")
        raster = self._read(self._bounds, grid)
        data = raster.data
        gaps = float(np.isnan(data).mean())
        if gaps:
            rows, cols = np.nonzero(~np.isnan(data))
            nearest = NearestNDInterpolator(np.column_stack([rows, cols]), data[rows, cols])
            hr, hc = np.nonzero(np.isnan(data))
            data = data.copy()
            data[hr, hc] = nearest(hr, hc)
        water = self._read_water(grid) if self._read_water else None
        report(45, "DEM gridded")
        west, south, east, north = self._bounds
        ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
        warnings: list[tuple[str, str, str]] = [
            (
                "surface_model",
                "Copernicus GLO-30 is a surface model: tree canopy and buildings are included "
                f"in the elevations (±{provenance.vertical_accuracy_relative_m:g} m relative). "
                "Check the suggested site on the satellite layer.",
                "info",
            )
        ]
        if gaps > 0:
            warnings.append(
                (
                    "dem_gaps_filled",
                    f"{gaps:.1%} of the box had no elevation and was filled by nearest-neighbour.",
                    "caution",
                )
            )
        return DEMProduct(
            raster=Raster(grid, data),
            provenance=provenance,
            working_resolution_m=grid.cell_size,
            method="Copernicus GLO-30 COG windowed read, bilinear warp to UTM at native 30 m",
            warnings=tuple(warnings),
            details={
                "contour_count": 0,
                "vertex_count": 0,
                "elevation_source": "dem_raster",
                "contour_interval_m": None,
                "resolution_note": f"native resolution of {provenance.source}",
                "bounds_lonlat": [west, south, east, north],
                "aoi_lonlat": ring,
                "area_km2": round(box_area_km2(self._bounds), 3),
                "gap_fraction": gaps,
                "water_fraction": None if water is None else float(water.mean()),
                "source_file": "map selection",
            },
            water=water,
        )
