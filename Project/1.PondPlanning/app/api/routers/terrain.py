"""Terrain layers: DEM provenance, contours, streams, derived surfaces (FR2)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query

from app.api.deps import FixtureRoute, ReposDep, SettingsDep, StoreDep
from app.domain.errors import NotFoundError
from app.engines.terrain.layers import dem_asset_out, terrain_layers
from app.providers import fixtures
from app.repositories.records import DEMAssetRecord
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


@router.get("/{village_id}/contours", response_model=ContourResponse, dependencies=[FixtureRoute])
def get_contours(
    village_id: VillageId,
    interval: Annotated[float, Query(gt=0, le=50, description="Contour interval in metres")] = 2.0,
) -> ContourResponse:
    """FR2: contours generated from the DEM pipeline at the requested interval."""
    return ContourResponse.model_validate(fixtures.load("contours"))


@router.get("/{village_id}/streams", response_model=StreamNetwork, dependencies=[FixtureRoute])
def get_streams(
    village_id: VillageId,
    threshold: Annotated[int | None, Query(gt=0, description="Flow-accumulation cells")] = None,
) -> StreamNetwork:
    """The modelled drainage network, with the threshold that produced it."""
    return StreamNetwork.model_validate(fixtures.load("streams"))


@router.get(
    "/{village_id}/derived/{surface}",
    response_model=DerivedSurfaceResponse,
    dependencies=[FixtureRoute],
)
def get_derived_surface(
    village_id: VillageId,
    surface: Annotated[DerivedSurface, Path(description="Which surface to return")],
) -> DerivedSurfaceResponse:
    """Slope, aspect, curvature, TWI, hillshade or flow accumulation."""
    return DerivedSurfaceResponse.model_validate(fixtures.load_keyed("derived_surfaces", surface))
