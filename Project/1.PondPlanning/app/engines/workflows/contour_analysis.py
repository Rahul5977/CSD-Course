"""The ``POST /analyzeContour`` pipeline, end to end (Phase 2 route).

Use-case orchestrator (the "application service" in a layered architecture):
it sequences engines and providers, reports progress to the job record, and
persists what the routers will later read. It contains no algorithm of its
own — every step is a call into an engine — and it does not know whether it
is running inside a Celery worker or inline in a test.

Stages, with the weight each contributes to the progress percentage:

    parse + provenance (5-20) → TIN → DEM (45) → conditioning (50) →
    D8 + accumulation (55) → derived surfaces (60) → streams (65) →
    site selection (75) → catchment of the top site (80) → rasters to the
    store (90) → persist + assemble the result (100)
"""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
from pyproj import Transformer

from app.domain.errors import DomainError, NotFoundError
from app.domain.raster import Raster
from app.domain.units import Quantity, Unit
from app.engines.hydrology.catchment import delineate
from app.engines.hydrology.conditioning import fill_depressions
from app.engines.hydrology.flow import build_flow_model, stream_mask, threshold_cells
from app.engines.hydrology.siting import SitingResult, rank_sites
from app.engines.hydrology.streams import extract_links
from app.engines.terrain.adapters import ContourKMLAdapter
from app.engines.terrain.derived import curvatures, topographic_wetness_index
from app.engines.terrain.layers import dem_asset_out, layer_descriptors
from app.engines.terrain.surfaces import (
    aspect_degrees,
    elevation_statistics,
    hillshade,
    slope_degrees,
)
from app.engines.workflows.catchment import catchment_result
from app.engines.workflows.terrain_products import PRODUCTS, SITING_KEY, STREAMS_KEY
from app.providers.geocoding import PlaceName, fallback_name
from app.providers.raster_io import write_cog
from app.providers.storage import ObjectStore
from app.repositories import Repositories
from app.repositories.records import DEMAssetRecord
from app.schemas.analysis import (
    ContourAnalysisResult,
    PourPoint,
    SiteCandidateOut,
    SitingMethod,
)
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
    stream_threshold_area_m2: float = 50_000.0
    snap_radius_m: float = 150.0
    snap_min_upstream_area_m2: float = 20_000.0
    siting_rise_m: float = 2.0
    siting_top_n: int = 5


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


def _percentiles(data: np.ndarray) -> tuple[float, float]:
    valid = data[~np.isnan(data)]
    if valid.size == 0:
        return 0.0, 1.0
    p2, p98 = np.percentile(valid, [2, 98])
    return float(p2), float(p98 if p98 > p2 else p2 + 1)


def _run(
    job_id: UUID,
    params: dict[str, Any],
    ctx: WorkflowContext,
    progress: Callable[[int, str], None],
) -> dict[str, Any]:
    progress(2, "loading upload")
    payload = ctx.store.get(str(params["upload_key"]))
    filename = str(params.get("filename", "upload.kml"))

    # ---- terrain ------------------------------------------------------
    adapter = ContourKMLAdapter(payload, filename, default_floor_m=ctx.default_floor_m)
    product = adapter.produce(progress)
    details = product.details
    dem = product.raster
    grid = dem.grid

    progress(48, "deriving hillshade and slope")
    shade = hillshade(dem)
    slope = slope_degrees(dem)
    aspect = aspect_degrees(dem)
    stats = elevation_statistics(dem)
    stats["mean_slope_deg"] = float(np.nanmean(slope.data))

    # ---- hydrology ----------------------------------------------------
    progress(50, "filling sinks (Priority-Flood)")
    conditioned = fill_depressions(dem)
    progress(55, "routing flow (D8) and accumulating")
    model = build_flow_model(conditioned.filled)
    progress(60, "curvature and wetness index")
    profile_curv, plan_curv = curvatures(dem)
    twi = topographic_wetness_index(dem, model.accumulation)
    progress(65, "extracting streams")
    streams = stream_mask(model, ctx.stream_threshold_area_m2)
    links = extract_links(model, streams)

    progress(70, "ranking pond sites")
    siting = rank_sites(
        model,
        slope.data,
        twi.data,
        streams,
        top_n=ctx.siting_top_n,
        rise_m=ctx.siting_rise_m,
    )

    # ---- village ------------------------------------------------------
    progress(76, "naming the area")
    boundary = _boundary_geojson(details)
    west, south, east, north = details["bounds_lonlat"]
    lon, lat = (west + east) / 2, (south + north) / 2
    village = ctx.repos.villages.find_by_boundary(boundary)
    place = None
    if village is None:
        place = ctx.geocode(lon, lat) if ctx.geocode else None
        name = place.name if place else fallback_name(lon, lat)
        village = ctx.repos.villages.create(
            name, boundary, place.state_code if place else None, place.district if place else None
        )

    # ---- rasters to the store ----------------------------------------
    progress(82, "writing rasters")
    surfaces: dict[str, Raster] = {
        "dem": dem,
        "filled": conditioned.filled,
        "fill_depth": conditioned.fill_depth,
        "hillshade": shade,
        "slope": slope,
        "aspect": aspect,
        "curvature": profile_curv,
        "plan_curvature": plan_curv,
        "twi": twi,
        "flow_accumulation": dem.with_data(np.log10(np.maximum(model.accumulation, 1))),
    }
    prefix = f"villages/{village.id}"
    for product_id, raster in surfaces.items():
        spec = PRODUCTS[product_id]
        ctx.store.put(
            f"{prefix}/{spec.key}",
            write_cog(raster, dtype=spec.dtype, nodata=spec.nodata),
            "image/tiff",
        )
        if spec.fixed_range is None:
            stats[f"{product_id}_p2"], stats[f"{product_id}_p98"] = _percentiles(raster.data)
    stats["fill_cells"] = conditioned.cells_filled
    stats["fill_max_m"] = conditioned.max_fill_m
    stats["stream_cells"] = int(streams.sum())

    to_lonlat = Transformer.from_crs(f"EPSG:{grid.epsg}", "EPSG:4326", always_xy=True)
    stream_features = []
    for link in links:
        xy = np.array([grid.cell_center(r, c) for r, c in link.cells])
        lons, lats = to_lonlat.transform(xy[:, 0], xy[:, 1])
        stream_features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": np.column_stack([lons, lats]).round(6).tolist(),
                },
                "properties": {
                    "strahler_order": link.order,
                    "length_m": round(link.length_m(grid.cell_size), 1),
                    "upstream_area_ha_at_mouth": round(
                        link.upstream_cells_at_mouth * grid.cell_area / 1e4, 2
                    ),
                },
            }
        )
    streams_doc = {
        "type": "FeatureCollection",
        "features": stream_features,
        "crs": "EPSG:4326",
        "threshold_area_m2": ctx.stream_threshold_area_m2,
        "threshold_cells": threshold_cells(ctx.stream_threshold_area_m2, grid.cell_area),
        "total_length_m": round(sum(link.length_m(grid.cell_size) for link in links), 1),
        "strahler_max_order": max((link.order for link in links), default=0),
    }
    ctx.store.put(f"{prefix}/{STREAMS_KEY}", json.dumps(streams_doc).encode(), "application/json")

    # ---- persist the DEM asset ---------------------------------------
    progress(88, "persisting")
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
            epsg=grid.epsg,
            bounds_lonlat=[float(v) for v in details["bounds_lonlat"]],
            dem_key=f"{prefix}/{PRODUCTS['dem'].key}",
            hillshade_key=f"{prefix}/{PRODUCTS['hillshade'].key}",
            statistics=stats,
            attribution=list(product.provenance.attribution),
            acquired=product.provenance.acquired,
            method=product.method,
            details={
                **{k: v for k, v in details.items() if k not in {"aoi_xy"}},
                "products": list(surfaces),
                "streams": {
                    "threshold_area_m2": ctx.stream_threshold_area_m2,
                    "links": len(links),
                    "strahler_max_order": streams_doc["strahler_max_order"],
                },
                "conditioning": {
                    "algorithm": "Priority-Flood + epsilon (Barnes et al. 2014)",
                    "cells_filled": conditioned.cells_filled,
                    "max_fill_m": conditioned.max_fill_m,
                },
            },
        )
    )

    # ---- assemble the result -----------------------------------------
    progress(94, "delineating the catchment of the top site")
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

    elevation = {
        "minimum": elev(stats["min"]),
        "maximum": elev(stats["max"]),
        "mean": elev(stats["mean"]),
        "relief": QuantityOut.from_domain(
            Quantity(stats["relief"], Unit.METRE, None, "maximum - minimum")
        ),
    }
    terrain = TerrainPreparationResult(
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
        utm_epsg=grid.epsg,
        bounds=asset.bounds_lonlat,
        elevation=elevation,
        mean_slope=QuantityOut.from_domain(
            Quantity(stats["mean_slope_deg"], Unit.DEGREE, 15.0, "Horn (1981) 3x3, mean")
        ),
        dem=dem_asset_out(asset, warnings),
        layers=layer_descriptors(asset, ctx.store, ctx.tiles_public_base),
        boundary_geojson=boundary,
        warnings=warnings,
    )

    candidates = _candidates_out(siting, grid, to_lonlat)
    if not candidates:
        warnings.append(
            ResultWarning(
                code="no_site_found",
                message="No drainage cell met the siting constraints; the map may be too small "
                "or too flat for the stream threshold.",
                severity="critical",
            )
        )
        top = PourPoint(lon=lon, lat=lat)
        rationale = "no eligible site — falling back to the map centre"
        top_row, top_col = grid.index_of(
            *Transformer.from_crs("EPSG:4326", f"EPSG:{grid.epsg}", always_xy=True).transform(
                lon, lat
            )
        )
    else:
        top = candidates[0].location
        best = siting.candidates[0]
        top_row, top_col = best.row, best.col
        rationale = (
            f"Highest composite score ({best.score:.2f}) of {siting.considered} drainage cells: "
            f"upstream area {best.upstream_area_m2 / 1e4:.1f} ha, "
            f"local slope {best.slope_pct:.1f} %, "
            f"TWI {best.twi:.1f}, impounds {best.impoundment_volume_m3:,.0f} m³ behind a "
            f"{siting.rise_m:g} m rise (mean depth {best.impoundment_efficiency_m:.2f} m)."
        )
    catchment = delineate(
        model,
        top_row,
        top_col,
        radius_m=ctx.snap_radius_m,
        min_area_m2=ctx.snap_min_upstream_area_m2,
    )
    catchment_out = catchment_result(village.id, model, slope.data, catchment, top, rel)

    siting_method = SitingMethod(
        weights=siting.weights,
        nominal_rise=QuantityOut.from_domain(
            Quantity(siting.rise_m, Unit.METRE, None, "configured")
        ),
        max_slope=QuantityOut.from_domain(
            Quantity(siting.max_slope_pct, Unit.PERCENT, None, "constraint")
        ),
        suppression_radius=QuantityOut.from_domain(
            Quantity(siting.suppression_radius_m, Unit.METRE, None, "non-maximum suppression")
        ),
        stream_threshold=QuantityOut.from_domain(
            Quantity(
                ctx.stream_threshold_area_m2 / 1e4,
                Unit.HECTARE,
                None,
                "upstream area defining a channel",
            )
        ),
        upstream_area_bounds_ha=list(siting.area_bounds_ha),
        candidates_considered=siting.considered,
        description=(
            "Weighted sum over drainage-network cells of an upstream-area plateau (1 between "
            f"{siting.area_bounds_ha[1]:g} and {siting.area_bounds_ha[2]:g} ha, 0 at "
            f"{siting.area_bounds_ha[0]:g} and {siting.area_bounds_ha[3]:g} ha), a slope plateau "
            "(1 on 0-3 %, 0 at 15 %), normalised TWI, and impoundment efficiency (volume behind a "
            "nominal rise / footprint); constraints applied first; non-maximum suppression last."
        ),
    )
    result = ContourAnalysisResult(
        source_file=filename,
        village_id=village.id,
        village_name=village.name,
        contour_count=int(details["contour_count"]),
        elevation_source=details["elevation_source"],
        elevation_range=elevation,
        contour_interval=terrain.contour_interval,
        bounds=asset.bounds_lonlat,
        utm_epsg=grid.epsg,
        grid_resolution=terrain.grid_resolution,
        suggested_pond_location=top,
        location_rationale=rationale,
        catchment=catchment_out,
        candidate_sites=candidates,
        siting=siting_method,
        terrain=terrain,
        warnings=warnings + [w for w in catchment_out.warnings if w.code == "catchment_truncated"],
    ).model_dump(mode="json")
    ctx.store.put(
        f"{prefix}/{SITING_KEY}",
        json.dumps(
            {
                "candidate_sites": result["candidate_sites"],
                "siting": result["siting"],
                "suggested_pond_location": result["suggested_pond_location"],
                "location_rationale": result["location_rationale"],
            }
        ).encode(),
        "application/json",
    )

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


def _candidates_out(
    siting: SitingResult, grid: Any, to_lonlat: Transformer
) -> list[SiteCandidateOut]:
    q = QuantityOut.from_domain
    out: list[SiteCandidateOut] = []
    for rank, c in enumerate(siting.candidates, start=1):
        x, y = grid.cell_center(c.row, c.col)
        lon, lat = to_lonlat.transform(x, y)
        out.append(
            SiteCandidateOut(
                rank=rank,
                location=PourPoint(lon=float(lon), lat=float(lat)),
                score=q(Quantity(c.score, Unit.RATIO, None, "weighted sum of normalised criteria")),
                upstream_area=q(
                    Quantity(c.upstream_area_m2 / 1e4, Unit.HECTARE, 15.0, "D8 accumulation")
                ),
                local_slope=q(Quantity(c.slope_pct, Unit.PERCENT, 15.0, "Horn (1981)")),
                wetness_index=q(Quantity(c.twi, Unit.RATIO, None, "ln(a / tan beta)")),
                impoundment_volume=q(
                    Quantity(
                        c.impoundment_volume_m3,
                        Unit.CUBIC_METRE,
                        30.0,
                        f"flood fill of upstream cells below a {siting.rise_m:g} m rise",
                    )
                ),
                impoundment_efficiency=q(
                    Quantity(c.impoundment_efficiency_m, Unit.METRE, 30.0, "volume / footprint")
                ),
                criteria=c.criteria_scores,
            )
        )
    return out
