"""The ``POST /analysis/catchment`` pipeline (FR4), and the shared flow-model loader.

Rebuilding D8 from the stored conditioned DEM costs well under a second at
village scale, so nothing but the rasters is persisted; a per-process LRU
keeps the model warm so a second click on the same village is near-instant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
from pyproj import Transformer

from app.domain.errors import DomainError, NotFoundError
from app.domain.units import Quantity, Unit
from app.engines.hydrology.catchment import Catchment, delineate
from app.engines.hydrology.flow import FlowModel, build_flow_model
from app.engines.workflows.terrain_products import PRODUCTS
from app.providers.raster_io import mask_to_polygon_lonlat, polygon_perimeter_m, read_cog
from app.providers.storage import ObjectStore
from app.repositories import Repositories
from app.repositories.records import DEMAssetRecord
from app.schemas.analysis import CatchmentResult, PourPoint
from app.schemas.common import GeoJSONFeature, GeoJSONFeatureCollection, QuantityOut, ResultWarning

FLOW_ROUTING = "D8 (O'Callaghan & Mark 1984) on a Priority-Flood+epsilon conditioned DEM"


def asset_key(asset: DEMAssetRecord, product: str) -> str:
    """Object-store key of one of a village's rasters."""
    return f"villages/{asset.village_id}/{PRODUCTS[product].key}"


class FlowModelCache:
    """Small per-process cache of flow models keyed by village."""

    def __init__(self, capacity: int = 8) -> None:
        """Hold at most ``capacity`` models."""
        self._items: dict[str, tuple[FlowModel, np.ndarray]] = {}
        self._capacity = capacity

    def get(self, store: ObjectStore, asset: DEMAssetRecord) -> tuple[FlowModel, np.ndarray]:
        """``(flow model, slope degrees)`` for the village, loading on a miss."""
        key = f"{asset.village_id}:{asset.created_at}"
        hit = self._items.get(key)
        if hit is not None:
            return hit
        filled = read_cog(store.get(asset_key(asset, "filled")))
        slope = read_cog(store.get(asset_key(asset, "slope"))).data
        model = build_flow_model(filled)
        if len(self._items) >= self._capacity:
            self._items.pop(next(iter(self._items)))
        self._items[key] = (model, slope)
        return model, slope


FLOW_MODELS = FlowModelCache()


def catchment_result(
    village_id: UUID,
    model: FlowModel,
    slope_deg: np.ndarray,
    catchment: Catchment,
    requested: PourPoint,
    accuracy_rel_m: float,
) -> CatchmentResult:
    """Project a delineated catchment onto the wire contract."""
    grid = model.filled.grid
    to_lonlat = Transformer.from_crs(f"EPSG:{grid.epsg}", "EPSG:4326", always_xy=True)
    sx, sy = grid.cell_center(catchment.outlet.row, catchment.outlet.col)
    slon, slat = to_lonlat.transform(sx, sy)
    geometry = mask_to_polygon_lonlat(catchment.mask, model.filled)
    # Uncertainty: at least one cell ring around the perimeter, plus a floor
    # for the DEM source; both stated, neither pretended away.
    perimeter = polygon_perimeter_m(catchment.mask, model.filled)
    ring_pct = 100.0 * perimeter * grid.cell_size / max(catchment.area_m2, 1.0)
    area_pct = float(min(50.0, max(15.0, ring_pct)))
    warnings: list[ResultWarning] = []
    if catchment.touches_edge:
        warnings.append(
            ResultWarning(
                code="catchment_truncated",
                message="The catchment reaches the edge of the uploaded map; the true "
                "contributing area may be larger than shown.",
                severity="caution",
            )
        )
    if catchment.outlet.distance_m > 0:
        warnings.append(
            ResultWarning(
                code="pour_point_snapped",
                message=f"The pour point was moved {catchment.outlet.distance_m:.0f} m onto "
                "the nearest modelled channel.",
                severity="info",
            )
        )
    mean_slope = float(np.nanmean(slope_deg[catchment.mask]))
    q = QuantityOut.from_domain
    return CatchmentResult(
        village_id=village_id,
        requested_point=requested,
        snapped_point=PourPoint(lon=float(slon), lat=float(slat)),
        snap_distance=q(Quantity(catchment.outlet.distance_m, Unit.METRE, None, "nearest channel")),
        area=q(Quantity(catchment.area_m2 / 1e4, Unit.HECTARE, area_pct, "D8 upstream cell count")),
        perimeter=q(Quantity(perimeter, Unit.METRE, 10.0, "dissolved cell polygon")),
        longest_flow_path=q(
            Quantity(catchment.longest_flow_path_m, Unit.METRE, 10.0, "longest D8 path to outlet")
        ),
        mean_slope=q(Quantity(mean_slope, Unit.DEGREE, 15.0, "Horn (1981), mean over catchment")),
        relief=q(
            Quantity(
                catchment.relief_m,
                Unit.METRE,
                100.0 * accuracy_rel_m * 1.41 / max(catchment.relief_m, 1e-6),
                "max - min conditioned elevation",
            )
        ),
        outlet_elevation=q(
            Quantity(
                catchment.outlet_elevation_m,
                Unit.METRE,
                100.0 * accuracy_rel_m / catchment.outlet_elevation_m,
                "conditioned DEM",
            )
        ),
        flow_routing=FLOW_ROUTING,
        cell_size=q(Quantity(grid.cell_size, Unit.METRE, None, "working grid")),
        geojson=GeoJSONFeatureCollection(
            features=[
                GeoJSONFeature(
                    geometry=geometry,
                    properties={
                        "kind": "catchment",
                        "area_ha": round(catchment.area_m2 / 1e4, 2),
                        "cells": catchment.cell_count,
                    },
                ),
                GeoJSONFeature(
                    geometry={"type": "Point", "coordinates": [float(slon), float(slat)]},
                    properties={"kind": "outlet", "snap_distance_m": catchment.outlet.distance_m},
                ),
            ]
        ),
        warnings=warnings,
    )


def run_catchment(
    job_id: UUID,
    repos: Repositories,
    store: ObjectStore,
    *,
    snap_radius_m: float,
    min_channel_area_m2: float,
) -> dict[str, Any]:
    """Execute a queued catchment job: snap → delineate → measure → persist."""
    jobs = repos.jobs
    job = jobs.get(job_id)
    if job is None:
        msg = "job not found"
        raise NotFoundError(msg, {"job_id": str(job_id)})
    try:
        jobs.update(job_id, status="running", progress=10, stage="loading terrain")
        village_id = UUID(str(job.params["village_id"]))
        asset = repos.dem_assets.get_for_village(village_id)
        if asset is None:
            msg = "this village has no terrain yet — analyse a contour map first"
            raise NotFoundError(msg, {"village_id": str(village_id)})
        model, slope = FLOW_MODELS.get(store, asset)
        point = PourPoint(**job.params["pour_point"])
        radius = float(job.params.get("snap_radius") or snap_radius_m)
        jobs.update(job_id, status="running", progress=40, stage="snapping to drainage")
        grid = model.filled.grid
        to_xy = Transformer.from_crs("EPSG:4326", f"EPSG:{grid.epsg}", always_xy=True)
        x, y = to_xy.transform(point.lon, point.lat)
        row, col = grid.index_of(x, y)
        if not job.params.get("snap_to_drainage", True):
            radius = grid.cell_size * 0.5
        jobs.update(job_id, status="running", progress=60, stage="tracing upstream cells")
        catchment = delineate(model, row, col, radius_m=radius, min_area_m2=min_channel_area_m2)
        result = catchment_result(
            village_id, model, slope, catchment, point, asset.vertical_accuracy_relative_m
        ).model_dump(mode="json")
        jobs.update(
            job_id,
            status="succeeded",
            progress=100,
            stage="done",
            result=result,
            village_id=village_id,
            finished_at=datetime.now(UTC),
        )
        return result
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
