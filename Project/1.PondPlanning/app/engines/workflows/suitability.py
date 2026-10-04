"""The ``POST /analysis/suitability`` pipeline (FR3 + the "AI-based" layer).

land context (DEM slope, D8 accumulation, WorldCover resampled to the grid,
NDWI water mask from Sentinel-2 or WorldCover water as fallback) →
Specification constraints → eligible land polygons → AHP weights (CR < 0.10)
→ terrain siting score restricted to eligible cells → ranked sites with a
per-criterion breakdown → suitability heat-map COG.

Stored per village: ``available_land.json``, ``suitability.json``,
``suitability.tif``, ``water_mask.tif`` — so ``GET /villages/{id}/available-land``
is a read, not a recomputation.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from pyproj import Transformer

from app.domain.errors import DomainError, NotFoundError, UpstreamUnavailableError
from app.domain.raster import Raster
from app.domain.units import Quantity, Unit
from app.engines.hydrology.flow import FlowModel, stream_mask
from app.engines.hydrology.siting import DEFAULT_AREA_BOUNDS_HA, _plateau, _trapezoid, rank_sites
from app.engines.suitability.ahp import DEFAULT_CRITERIA, DEFAULT_MATRIX, AHPResult, ahp_weights
from app.engines.suitability.constraints import (
    HabitationDistance,
    IsGovernmentLand,
    LandContext,
    LandCoverIn,
    MinContiguousArea,
    MinFlowAccumulation,
    SlopeUnder,
    Specification,
    WithinBuffer,
)
from app.engines.suitability.water_mask import ndwi, water_mask_from_ndwi
from app.engines.terrain.derived import topographic_wetness_index
from app.engines.workflows.catchment import FLOW_MODELS
from app.engines.workflows.terrain_products import PRODUCTS
from app.providers.landcover import ConstantLandCoverAdapter, LandCoverWindow, WorldCoverAdapter
from app.providers.raster_io import mask_to_polygon_lonlat, write_cog
from app.providers.sentinel import season_composite
from app.providers.storage import ObjectStore
from app.repositories import Repositories
from app.repositories.records import DEMAssetRecord
from app.schemas.analysis import CriterionScore, PourPoint, SuitabilityResult, SuitableSite
from app.schemas.common import GeoJSONFeature, GeoJSONFeatureCollection, QuantityOut, ResultWarning
from app.schemas.village import AvailableLandResponse, LandParcel

logger = logging.getLogger(__name__)

AVAILABLE_LAND_KEY = "available_land.json"
SUITABILITY_KEY = "suitability.json"
WATER_BUFFER_M = 150.0
HABITATION_M = (100.0, 2000.0)
MIN_PARCEL_M2 = 2500.0
MAX_SLOPE_PCT = 15.0
ELIGIBLE_LANDCOVER = (30, 40, 60, 90)  # grassland, cropland, bare, herbaceous wetland
q = QuantityOut.from_domain


def _sample_window_on_grid(
    window: LandCoverWindow | tuple[NDArray[Any], tuple[float, ...], int],
    grid_epsg: int,
    raster: Raster,
) -> NDArray[Any]:
    """Nearest-neighbour sample of a lon/lat (or projected) window at every DEM cell centre."""
    if isinstance(window, LandCoverWindow):
        codes, (a, _b, c, _d, e, f), src_epsg = window.codes, window.transform, 4326
    else:
        codes, transform, src_epsg = window
        a, _b, c, _d, e, f = transform
    grid = raster.grid
    xs = grid.x_min + (np.arange(grid.cols) + 0.5) * grid.cell_size
    ys = grid.y_max - (np.arange(grid.rows) + 0.5) * grid.cell_size
    gx, gy = np.meshgrid(xs, ys)
    if src_epsg != grid_epsg:
        to_src = Transformer.from_crs(f"EPSG:{grid_epsg}", f"EPSG:{src_epsg}", always_xy=True)
        sx, sy = to_src.transform(gx, gy)
    else:
        sx, sy = gx, gy
    col = np.floor((np.asarray(sx) - c) / a).astype(int)
    row = np.floor((np.asarray(sy) - f) / e).astype(int)
    inside = (row >= 0) & (row < codes.shape[0]) & (col >= 0) & (col < codes.shape[1])
    out = np.zeros(grid.shape, dtype=codes.dtype)
    out[inside] = codes[row[inside], col[inside]]
    return out


def _water_mask(
    asset: DEMAssetRecord,
    landcover_grid: NDArray[np.uint8],
    dem: Raster,
    warnings: list[ResultWarning],
) -> tuple[NDArray[np.bool_], dict[str, Any]]:
    """NDWI water on the DEM grid, falling back to WorldCover class 80."""
    bounds = tuple(asset.bounds_lonlat)
    year = date.today().year - 1
    try:
        post = season_composite(bounds, f"{year}-10-01", f"{year}-12-31", "post-monsoon")  # type: ignore[arg-type]
        index = ndwi(post.green, post.nir)
        mask = water_mask_from_ndwi(index, pixel_size_m=abs(post.transform[0]))
        on_grid = _sample_window_on_grid(
            (mask.mask.astype(np.uint8), post.transform, post.epsg), dem.grid.epsg, dem
        )
        info = {
            "source": "Sentinel-2 L2A NDWI, post-monsoon median composite",
            "scenes": post.scenes,
            "otsu_threshold": mask.otsu_threshold,
            "components_before": mask.components_before,
            "components_after": mask.components_after,
            "water_fraction": mask.water_fraction,
        }
        try:
            pre = season_composite(bounds, f"{year}-03-01", f"{year}-05-31", "pre-monsoon")  # type: ignore[arg-type]
            pre_mask = water_mask_from_ndwi(
                ndwi(pre.green, pre.nir), pixel_size_m=abs(pre.transform[0])
            )
            pre_grid = _sample_window_on_grid(
                (pre_mask.mask.astype(np.uint8), pre.transform, pre.epsg), dem.grid.epsg, dem
            )
            info["perennial_fraction_of_water"] = float(
                (on_grid.astype(bool) & pre_grid.astype(bool)).sum() / max(on_grid.sum(), 1)
            )
            info["pre_monsoon_scenes"] = pre.scenes
        except UpstreamUnavailableError as exc:
            info["pre_monsoon"] = f"unavailable: {exc.message}"
        return on_grid.astype(bool), info
    except UpstreamUnavailableError as exc:
        logger.warning("NDWI unavailable", extra={"reason": exc.message})
        warnings.append(
            ResultWarning(
                code="water_mask_fallback",
                message="Sentinel-2 was unreachable; existing water taken from ESA WorldCover "
                "(class 80) instead of a fresh NDWI mask.",
                severity="caution",
            )
        )
        return landcover_grid == 80, {"source": "ESA WorldCover class 80 (fallback)"}


def build_land_context(
    asset: DEMAssetRecord, store: ObjectStore, warnings: list[ResultWarning]
) -> tuple[LandContext, FlowModel, Raster, dict[str, Any]]:
    """Assemble every raster the constraints need, all on the DEM grid."""
    model, slope_deg = FLOW_MODELS.get(store, asset)
    dem = model.filled
    try:
        window = WorldCoverAdapter().window(tuple(asset.bounds_lonlat))  # type: ignore[arg-type]
    except UpstreamUnavailableError as exc:
        logger.warning("WorldCover unavailable", extra={"reason": exc.message})
        warnings.append(
            ResultWarning(
                code="landcover_assumed",
                message="ESA WorldCover was unreachable; cropland was assumed everywhere.",
                severity="caution",
            )
        )
        window = ConstantLandCoverAdapter().window(tuple(asset.bounds_lonlat))  # type: ignore[arg-type]
    landcover = _sample_window_on_grid(window, dem.grid.epsg, dem).astype(np.uint8)
    water, water_info = _water_mask(asset, landcover, dem, warnings)
    ctx = LandContext(
        cell_size_m=dem.grid.cell_size,
        slope_pct=np.tan(np.radians(slope_deg)) * 100.0,
        accumulation=model.accumulation,
        water=water,
        built=landcover == 50,
        landcover=landcover,
        ownership=None,
    )
    return ctx, model, dem, {"landcover_source": window.source, "water": water_info}


def eligibility_rule(min_flow_area_m2: float) -> Specification:
    """The FR3 rule set, as one readable expression."""
    base = (
        SlopeUnder(MAX_SLOPE_PCT)
        & ~WithinBuffer("water", WATER_BUFFER_M)
        & HabitationDistance(*HABITATION_M)
        & LandCoverIn(ELIGIBLE_LANDCOVER, "grassland/cropland/bare/wetland")
        & IsGovernmentLand()
    )
    return MinContiguousArea(base & MinFlowAccumulation(min_flow_area_m2), MIN_PARCEL_M2)


def available_land(
    village_id: UUID,
    ctx: LandContext,
    dem: Raster,
    rule: Specification,
    warnings: list[ResultWarning],
) -> AvailableLandResponse:
    """Eligible patches as parcels with their attributes."""
    from scipy import ndimage

    eligible = rule.is_satisfied_by(ctx)
    labels, count = ndimage.label(eligible, structure=np.ones((3, 3)))
    parcels: list[LandParcel] = []
    features: list[GeoJSONFeature] = []
    cell_area = dem.grid.cell_area
    for k in range(1, count + 1):
        patch = labels == k
        area = float(patch.sum() * cell_area)
        codes, counts = np.unique(ctx.landcover[patch], return_counts=True)
        dominant = int(codes[np.argmax(counts)])
        from app.engines.runoff.curve_number import WORLDCOVER_NAMES

        parcel_id = f"{village_id.hex[:8]}-{k:03d}"
        parcels.append(
            LandParcel(
                parcel_id=parcel_id,
                ownership_class="unknown",
                area=q(Quantity(area / 1e4, Unit.HECTARE, 15.0, "eligible cells x cell area")),
                mean_slope=q(
                    Quantity(float(ctx.slope_pct[patch].mean()), Unit.PERCENT, 15.0, "Horn (1981)")
                ),
                lulc_class=WORLDCOVER_NAMES.get(dominant, str(dominant)),
                excluded_by=[],
                eligible=True,
            )
        )
        features.append(
            GeoJSONFeature(
                geometry=mask_to_polygon_lonlat(patch, dem),
                properties={
                    "parcel_id": parcel_id,
                    "area_ha": round(area / 1e4, 2),
                    "lulc": WORLDCOVER_NAMES.get(dominant, str(dominant)),
                },
            )
        )
    warnings.append(
        ResultWarning(
            code="ownership_unknown",
            message="No cadastral layer was supplied, so ownership is 'unknown' for every parcel "
            "(never assumed government). Import parcels to apply the ownership rule (ADR 0012).",
            severity="caution",
        )
    )
    return AvailableLandResponse(
        village_id=village_id,
        constraints_applied=rule.names(),
        total_eligible_area=q(
            Quantity(
                float(eligible.sum() * cell_area / 1e4),
                Unit.HECTARE,
                15.0,
                "sum of eligible patches",
            )
        ),
        parcels=sorted(parcels, key=lambda p: -p.area.value),
        geojson=GeoJSONFeatureCollection(features=features),
        warnings=list(warnings),
    )


def suitability_raster(
    model: FlowModel,
    ctx: LandContext,
    twi: NDArray[np.float64],
    eligible: NDArray[np.bool_],
    weights: dict[str, float],
) -> Raster:
    """Weighted linear combination of the cheap criteria for every eligible cell (the heat-map)."""
    cell_area = model.filled.grid.cell_area
    area_ha = model.accumulation.astype(np.float64) * cell_area / 1e4
    lo, opt_lo, opt_hi, hi = (float(np.log10(b)) for b in DEFAULT_AREA_BOUNDS_HA)
    parts = {
        "upstream_area": _trapezoid(np.log10(np.maximum(area_ha, 1e-3)), lo, opt_lo, opt_hi, hi),
        "flatness": _plateau(ctx.slope_pct),
        "wetness": (twi - np.nanmin(twi)) / max(float(np.nanmax(twi) - np.nanmin(twi)), 1e-9),
    }
    total = sum(weights.get(k, 0.0) for k in parts)
    score = (
        sum(weights.get(k, 0.0) / total * parts[k] for k in parts)
        if total > 0
        else np.zeros_like(area_ha)
    )
    score = np.where(eligible, score, 0.0)
    return model.filled.with_data(np.asarray(score, dtype=np.float64))


def run_suitability(
    job_id: UUID,
    repos: Repositories,
    store: ObjectStore,
    *,
    stream_threshold_area_m2: float,
    siting_rise_m: float,
) -> dict[str, Any]:
    """Execute a queued suitability job."""
    jobs = repos.jobs
    job = jobs.get(job_id)
    if job is None:
        msg = "job not found"
        raise NotFoundError(msg, {"job_id": str(job_id)})
    try:
        params = job.params
        village_id = UUID(str(params["village_id"]))
        asset = repos.dem_assets.get_for_village(village_id)
        if asset is None:
            msg = "this village has no terrain yet — analyse a contour map first"
            raise NotFoundError(msg, {"village_id": str(village_id)})
        warnings: list[ResultWarning] = []
        jobs.update(job_id, status="running", progress=10, stage="land cover, water mask")
        ctx, model, dem, info = build_land_context(asset, store, warnings)
        prefix = f"villages/{village_id}"
        store.put(
            f"{prefix}/{PRODUCTS['water_mask'].key}",
            write_cog(dem.with_data(ctx.water.astype(np.float64)), dtype="uint8", nodata=None),
            "image/tiff",
        )

        jobs.update(job_id, status="running", progress=40, stage="applying land constraints")
        rule = eligibility_rule(stream_threshold_area_m2)
        land = available_land(village_id, ctx, dem, rule, list(warnings))
        store.put(
            f"{prefix}/{AVAILABLE_LAND_KEY}", land.model_dump_json().encode(), "application/json"
        )
        eligible = rule.is_satisfied_by(ctx)

        jobs.update(job_id, status="running", progress=60, stage="AHP weights and ranking")
        user_weights = params.get("weights")
        if user_weights:
            total = sum(float(v) for v in user_weights.values())
            weights = {k: float(v) / total for k, v in user_weights.items()}
            ahp: AHPResult | None = None
        else:
            ahp = ahp_weights(DEFAULT_MATRIX, DEFAULT_CRITERIA)
            weights = ahp.weights
        twi = topographic_wetness_index(dem, model.accumulation).data
        streams = stream_mask(model, stream_threshold_area_m2)
        ranking = rank_sites(
            model,
            np.degrees(np.arctan(ctx.slope_pct / 100.0)),
            twi,
            streams,
            top_n=int(params.get("top_n") or 10),
            weights=weights,
            rise_m=siting_rise_m,
            inside=eligible,
        )
        jobs.update(job_id, status="running", progress=80, stage="suitability raster")
        heat = suitability_raster(model, ctx, twi, eligible, weights)
        store.put(
            f"{prefix}/{PRODUCTS['suitability'].key}",
            write_cog(heat, dtype="float32", nodata=-9999.0),
            "image/tiff",
        )
        details = dict(asset.details)
        products = list(details.get("products", []))
        for extra in ("water_mask", "suitability"):
            if extra not in products:
                products.append(extra)
        details["products"] = products
        details["suitability"] = {
            "water": info["water"],
            "landcover_source": info["landcover_source"],
            "eligible_ha": land.total_eligible_area.value,
            "parcels": len(land.parcels),
        }
        from dataclasses import replace

        repos.dem_assets.upsert(replace(asset, details=details))

        to_lonlat = Transformer.from_crs(f"EPSG:{dem.grid.epsg}", "EPSG:4326", always_xy=True)
        sites: list[SuitableSite] = []
        for rank, c in enumerate(ranking.candidates, start=1):
            x, y = dem.grid.cell_center(c.row, c.col)
            lon, lat = to_lonlat.transform(x, y)
            raw = {
                "upstream_area": (c.upstream_area_m2 / 1e4, Unit.HECTARE),
                "flatness": (c.slope_pct, Unit.PERCENT),
                "wetness": (c.twi, Unit.RATIO),
                "impoundment": (c.impoundment_efficiency_m, Unit.METRE),
            }
            sites.append(
                SuitableSite(
                    rank=rank,
                    location=PourPoint(lon=float(lon), lat=float(lat)),
                    total_score=q(Quantity(c.score, Unit.RATIO, None, "AHP-weighted sum")),
                    criteria=[
                        CriterionScore(
                            criterion=k,
                            raw_value=q(Quantity(raw[k][0], raw[k][1], 15.0, None)),
                            normalised_score=q(
                                Quantity(c.criteria_scores[k], Unit.RATIO, None, "0-1 membership")
                            ),
                            weight=q(
                                Quantity(
                                    weights[k],
                                    Unit.RATIO,
                                    None,
                                    "AHP principal eigenvector" if ahp else "user",
                                )
                            ),
                            contribution=q(
                                Quantity(
                                    weights[k] * c.criteria_scores[k],
                                    Unit.RATIO,
                                    None,
                                    "weight x score",
                                )
                            ),
                        )
                        for k in weights
                    ],
                    catchment_area=q(
                        Quantity(c.upstream_area_m2 / 1e4, Unit.HECTARE, 15.0, "D8 accumulation")
                    ),
                    estimated_storage=q(
                        Quantity(
                            c.impoundment_volume_m3,
                            Unit.CUBIC_METRE,
                            30.0,
                            f"impounded behind a {siting_rise_m:g} m rise",
                        )
                    ),
                )
            )
        if ahp is not None:
            warnings.append(
                ResultWarning(
                    code="ahp_matrix",
                    message=(
                        f"Saaty matrix {ahp.matrix}; lambda_max {ahp.lambda_max:.3f}, "
                        f"CI {ahp.consistency_index:.3f}, CR {ahp.consistency_ratio:.3f} "
                        f"({'acceptable' if ahp.acceptable else 'NOT acceptable'} at 0.10)."
                    ),
                    severity="info",
                )
            )
        if not sites:
            warnings.append(
                ResultWarning(
                    code="no_site_found",
                    message="No eligible drainage cell met the constraints.",
                    severity="critical",
                )
            )
        result = SuitabilityResult(
            village_id=village_id,
            sites=sites,
            weights=weights,
            consistency_ratio=ahp.consistency_ratio if ahp else 0.0,
            consistency_acceptable=ahp.acceptable if ahp else True,
            warnings=warnings,
        ).model_dump(mode="json")
        store.put(f"{prefix}/{SUITABILITY_KEY}", json.dumps(result).encode(), "application/json")
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
