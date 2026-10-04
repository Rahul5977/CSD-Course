"""Terrain layers: DEM provenance, contours, streams, derived surfaces (FR2).

Real since P2. Contours are generated on request from the stored DEM (a few
milliseconds at village scale), streams and derived surfaces are read back
from what the analysis job wrote.
"""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query

from app.api.deps import ReposDep, SettingsDep, StoreDep
from app.domain.errors import NotFoundError
from app.domain.units import Quantity, Unit
from app.engines.terrain.contours import generate_contours
from app.engines.terrain.layers import dem_asset_out, raster_layer, terrain_layers
from app.engines.workflows.terrain_products import PRODUCTS, STREAMS_KEY
from app.providers.raster_io import read_cog
from app.repositories.records import DEMAssetRecord
from app.schemas.common import GeoJSONFeature, GeoJSONFeatureCollection, QuantityOut
from app.schemas.terrain import (
    ContourResponse,
    DEMAsset,
    DerivedSurface,
    DerivedSurfaceResponse,
    StreamNetwork,
    TerrainLayers,
)

router = APIRouter(prefix="/terrain", tags=["terrain"])

VillageId = Annotated[UUID, Path(description="Village identifier")]


def _require_dem(repos: ReposDep, village_id: UUID) -> DEMAssetRecord:
    asset = repos.dem_assets.get_for_village(village_id)
    if asset is None:
        msg = "this village has no terrain yet — analyse a contour map first"
        raise NotFoundError(msg, {"village_id": str(village_id)})
    return asset


@router.get("/{village_id}/layers", response_model=TerrainLayers)
def list_layers(
    village_id: VillageId, repos: ReposDep, store: StoreDep, settings: SettingsDep
) -> TerrainLayers:
    """Every toggleable layer for this village — the source of FR8's overlay list."""
    return terrain_layers(
        village_id, _require_dem(repos, village_id), store, settings.tiles_public_base
    )


@router.get("/{village_id}/dem", response_model=DEMAsset)
def get_dem_asset(village_id: VillageId, repos: ReposDep) -> DEMAsset:
    """Provenance and accuracy of the elevation model underneath every terrain figure.

    A first-class endpoint rather than a footnote: the credibility of the storage
    estimate depends on the reader knowing the source is 30 m.
    """
    return dem_asset_out(_require_dem(repos, village_id))


@router.get("/{village_id}/contours", response_model=ContourResponse)
def get_contours(
    village_id: VillageId,
    repos: ReposDep,
    store: StoreDep,
    interval: Annotated[float, Query(gt=0, le=50, description="Contour interval in metres")] = 2.0,
) -> ContourResponse:
    """FR2: contours generated from the DEM pipeline at the requested interval."""
    asset = _require_dem(repos, village_id)
    dem = read_cog(store.get(asset.dem_key))
    generated = generate_contours(dem, interval)
    q = QuantityOut.from_domain
    return ContourResponse(
        village_id=village_id,
        interval=q(Quantity(interval, Unit.METRE, None, "requested")),
        levels=generated.levels,
        vertices_before_simplification=generated.vertices_before,
        vertices_after_simplification=generated.vertices_after,
        simplification_tolerance=q(
            Quantity(generated.tolerance_m, Unit.METRE, None, "Douglas-Peucker, half a cell")
        ),
        geojson=GeoJSONFeatureCollection(
            features=[
                GeoJSONFeature(
                    geometry={"type": "LineString", "coordinates": line.coords_lonlat},
                    properties={"elevation": line.elevation},
                )
                for line in generated.lines
            ]
        ),
    )


@router.get("/{village_id}/streams", response_model=StreamNetwork)
def get_streams(
    village_id: VillageId,
    repos: ReposDep,
    store: StoreDep,
    threshold: Annotated[int | None, Query(gt=0, description="Flow-accumulation cells")] = None,
) -> StreamNetwork:
    """The modelled drainage network, with the threshold that produced it."""
    _require_dem(repos, village_id)
    doc = json.loads(store.get(f"villages/{village_id}/{STREAMS_KEY}"))
    q = QuantityOut.from_domain
    return StreamNetwork(
        village_id=village_id,
        accumulation_threshold=q(
            Quantity(
                float(doc["threshold_cells"]),
                Unit.COUNT,
                None,
                f"{float(doc['threshold_area_m2']) / 1e4:g} ha upstream",
            )
        ),
        total_length=q(Quantity(float(doc["total_length_m"]), Unit.METRE, 10.0, "sum of links")),
        strahler_max_order=int(doc["strahler_max_order"]),
        geojson=GeoJSONFeatureCollection(features=doc["features"]),
    )


@router.get("/{village_id}/derived/{surface}", response_model=DerivedSurfaceResponse)
def get_derived_surface(
    village_id: VillageId,
    surface: Annotated[DerivedSurface, Path(description="Which surface to return")],
    repos: ReposDep,
    store: StoreDep,
    settings: SettingsDep,
) -> DerivedSurfaceResponse:
    """Slope, aspect, curvature, TWI, hillshade or flow accumulation."""
    asset = _require_dem(repos, village_id)
    product = PRODUCTS[surface]
    stats = asset.statistics
    q = QuantityOut.from_domain
    unit = {"deg": Unit.DEGREE, "m": Unit.METRE}.get(product.units or "", Unit.RATIO)
    statistics = {
        key: q(Quantity(float(stats[f"{surface}_{key}"]), unit, None, "over the grid"))
        for key in ("p2", "p98")
        if f"{surface}_{key}" in stats
    }
    if surface == "slope":
        statistics["mean"] = q(Quantity(float(stats["mean_slope_deg"]), Unit.DEGREE, 15.0, "mean"))
    return DerivedSurfaceResponse(
        village_id=village_id,
        surface=surface,
        algorithm=product.algorithm,
        statistics=statistics,
        layer=raster_layer(asset, surface, store, settings.tiles_public_base),
    )
