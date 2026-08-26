"""The ``POST /analyzeContour`` pipeline, end to end.

Use-case orchestrator (the "application service" in a layered architecture):
it sequences engines and providers, reports progress to the job record, and
persists what the routers will later read. It contains no algorithm of its
own — every step is a call into an engine — and it does not know whether it
is running inside a Celery worker or inline in a test.

Stage weights are declared once so that the percentage a client sees means
the same thing on every run.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np

from app.domain.errors import DomainError, NotFoundError
from app.domain.units import Quantity, Unit
from app.engines.terrain.adapters import ContourKMLAdapter
from app.engines.terrain.layers import dem_asset_out, layer_descriptors
from app.engines.terrain.surfaces import elevation_statistics, hillshade, slope_degrees
from app.providers.geocoding import PlaceName, fallback_name
from app.providers.raster_io import write_cog
from app.providers.storage import ObjectStore
from app.repositories import Repositories
from app.repositories.records import DEMAssetRecord
from app.schemas.common import QuantityOut, ResultWarning
from app.schemas.terrain import TerrainPreparationResult

logger = logging.getLogger(__name__)

Geocoder = Callable[[float, float], PlaceName | None]


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    """Everything the workflow needs, injected — no globals, no settings lookups."""

    repos: Repositories
    store: ObjectStore
    default_floor_m: float
    tiles_public_base: str
    geocode: Geocoder | None = None


def _boundary_geojson(details: dict[str, Any]) -> dict[str, Any]:
    """The upload's AOI ring if it drew one, else the contour extent rectangle."""
    aoi = details.get("aoi_lonlat")
    if isinstance(aoi, list) and len(aoi) >= 4:
        ring = [list(map(float, p)) for p in aoi]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return {"type": "Polygon", "coordinates": [ring]}
    w, s, e, n = details["bounds_lonlat"]
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def run_contour_analysis(job_id: UUID, ctx: WorkflowContext) -> dict[str, Any]:
    """Execute the pipeline for a queued job and return the stored result.

    Raises:
        NotFoundError: If the job does not exist.
        DomainError: Re-raised after the job is marked failed, so the runner sees it.
    """
    jobs = ctx.repos.jobs
    job = jobs.get(job_id)
    if job is None:
        msg = "job not found"
        raise NotFoundError(msg, {"job_id": str(job_id)})

    def progress(percent: int, stage: str) -> None:
        jobs.update(job_id, status="running", progress=percent, stage=stage)

    try:
        return _run(job_id, job.params, ctx, progress)
    except DomainError as exc:
        jobs.update(
            job_id,
            status="failed",
            stage="failed",
            error=f"{exc.code}: {exc.message}",
            result={"code": exc.code, "message": exc.message, "detail": exc.detail},
            finished_at=datetime.now(UTC),
        )
        raise
    except Exception as exc:
        logger.exception("contour analysis crashed", extra={"job_id": str(job_id)})
        jobs.update(
            job_id,
            status="failed",
            stage="failed",
            error=f"internal_error: {exc}",
            result={"code": "internal_error", "message": str(exc), "trace": traceback.format_exc()},
            finished_at=datetime.now(UTC),
        )
        raise


def _run(
    job_id: UUID,
    params: dict[str, Any],
    ctx: WorkflowContext,
    progress: Callable[[int, str], None],
) -> dict[str, Any]:
    progress(2, "loading upload")
    payload = ctx.store.get(str(params["upload_key"]))
    filename = str(params.get("filename", "upload.kml"))

    adapter = ContourKMLAdapter(payload, filename, default_floor_m=ctx.default_floor_m)
    product = adapter.produce(progress)
    details = product.details
    dem = product.raster

    progress(50, "deriving hillshade and slope")
    shade = hillshade(dem)
    slope = slope_degrees(dem)
    stats = elevation_statistics(dem)
    stats["mean_slope_deg"] = float(np.nanmean(slope.data))
    # Contrast stretch for the hillshade layer: on gentle terrain the raw
    # Lambertian values sit in a narrow band and render as a flat grey wash.
    p2, p98 = np.percentile(shade.data, [2, 98])
    stats["hillshade_p2"], stats["hillshade_p98"] = float(p2), float(max(p98, p2 + 1))

    progress(60, "naming the area")
    boundary = _boundary_geojson(details)
    west, south, east, north = details["bounds_lonlat"]
    lon, lat = (west + east) / 2, (south + north) / 2
    # Re-analysing the same extent updates that village rather than adding a twin.
    village = ctx.repos.villages.find_by_boundary(boundary)
    place = None
    if village is None:
        place = ctx.geocode(lon, lat) if ctx.geocode else None
        name = place.name if place else fallback_name(lon, lat)
        village = ctx.repos.villages.create(
            name, boundary, place.state_code if place else None, place.district if place else None
        )

    progress(70, "writing rasters")
    dem_key = f"villages/{village.id}/dem.tif"
    shade_key = f"villages/{village.id}/hillshade.tif"
    ctx.store.put(dem_key, write_cog(dem, dtype="float32", nodata=-9999.0), "image/tiff")
    ctx.store.put(shade_key, write_cog(shade, dtype="uint8", nodata=0), "image/tiff")

    progress(85, "persisting")
    asset = ctx.repos.dem_assets.upsert(
        DEMAssetRecord(
            id=job_id,
            village_id=village.id,
            provider=adapter.name,
            source=product.provenance.source,
            native_resolution_m=product.provenance.native_resolution_m,
            working_resolution_m=product.working_resolution_m,
            vertical_accuracy_relative_m=product.provenance.vertical_accuracy_relative_m,
            vertical_accuracy_absolute_m=product.provenance.vertical_accuracy_absolute_m,
            epsg=dem.grid.epsg,
            bounds_lonlat=[float(v) for v in details["bounds_lonlat"]],
            dem_key=dem_key,
            hillshade_key=shade_key,
            statistics=stats,
            attribution=list(product.provenance.attribution),
            acquired=product.provenance.acquired,
            method=product.method,
            details={k: v for k, v in details.items() if k not in {"aoi_xy"}},
        )
    )

    warnings = [ResultWarning(code=c, message=m, severity=s) for c, m, s in product.warnings]  # type: ignore[arg-type]
    if place is None and village.name == fallback_name(lon, lat):
        warnings.append(
            ResultWarning(
                code="geocode_unavailable",
                message="The area could not be named from OpenStreetMap; named by coordinates.",
                severity="info",
            )
        )
    rel = product.provenance.vertical_accuracy_relative_m

    def elev(value: float) -> QuantityOut:
        pct = 100.0 * rel / value if value else None
        return QuantityOut.from_domain(Quantity(value, Unit.METRE, pct, product.provenance.source))

    result = TerrainPreparationResult(
        village_id=village.id,
        village_name=village.name,
        provider=adapter.name,
        elevation_source=str(details["elevation_source"]),
        contour_count=int(details["contour_count"]),
        contour_interval=QuantityOut.from_domain(
            Quantity(float(details["contour_interval_m"]), Unit.METRE, None, "median level gap")
        ),
        grid_resolution=QuantityOut.from_domain(
            Quantity(
                product.working_resolution_m,
                Unit.METRE,
                None,
                f"mean contour spacing {float(details['contour_spacing_m']):.0f} m / 4, "
                f"floored at {product.provenance.native_resolution_m:g} m",
            )
        ),
        utm_epsg=dem.grid.epsg,
        bounds=asset.bounds_lonlat,
        elevation={
            "minimum": elev(stats["min"]),
            "maximum": elev(stats["max"]),
            "mean": elev(stats["mean"]),
            "relief": QuantityOut.from_domain(
                Quantity(stats["relief"], Unit.METRE, None, "maximum - minimum")
            ),
        },
        mean_slope=QuantityOut.from_domain(
            Quantity(stats["mean_slope_deg"], Unit.DEGREE, 15.0, "Horn (1981) 3x3, mean")
        ),
        dem=dem_asset_out(asset, warnings),
        layers=layer_descriptors(asset, ctx.store, ctx.tiles_public_base),
        boundary_geojson=boundary,
        warnings=warnings,
    ).model_dump(mode="json")

    ctx.repos.jobs.update(
        job_id,
        status="succeeded",
        progress=100,
        stage="done",
        result=result,
        village_id=village.id,
        finished_at=datetime.now(UTC),
    )
    return result
