"""Concrete :class:`~app.domain.dem.DEMProvider` implementations.

Adapter pattern over the DEM port. The hydrology chain downstream is written
once against :class:`DEMProduct`; these classes are the only places that know
where elevations come from.
"""

from __future__ import annotations

from app.domain.contours import ContourSet
from app.domain.dem import DEMProduct, DEMProvenance, ProgressCallback
from app.domain.errors import NotImplementedYetError
from app.engines.terrain.interpolate import contours_to_dem
from app.providers.contour_kml import parse_contours
from app.providers.dem_provenance import infer_provenance


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


class ProviderTileAdapter:
    """DEM from provider tiles (Copernicus GLO-30 / ALOS) — designed, not yet built.

    Kept as an explicit stub rather than omitted: it is the second implementation
    of the same port, and its existence is what makes the contour path an
    *adapter* rather than the whole system. Documented in ADR 0007 and 0011.
    """

    name = "provider_tiles"

    def __init__(self, bounds_lonlat: tuple[float, float, float, float]) -> None:
        """Record the bounding box the tiles would be fetched for."""
        self._bounds = bounds_lonlat

    def produce(self, on_progress: ProgressCallback | None = None) -> DEMProduct:
        """Not implemented in this phase.

        Raises:
            NotImplementedYetError: Always.
        """
        msg = "provider DEM tiles are a documented future adapter; upload a contour map instead"
        raise NotImplementedYetError(msg, {"bounds": list(self._bounds)})
