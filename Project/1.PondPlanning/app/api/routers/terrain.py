"""Terrain layers: DEM provenance, contours, streams, derived surfaces (FR2)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query

from app.api.deps import FixtureRoute
from app.providers import fixtures
from app.schemas.terrain import (
    ContourResponse,
    DEMAsset,
    DerivedSurface,
    DerivedSurfaceResponse,
    StreamNetwork,
    TerrainLayers,
)

router = APIRouter(prefix="/terrain", tags=["terrain"], dependencies=[FixtureRoute])

VillageId = Annotated[UUID, Path(description="Village identifier")]


@router.get("/{village_id}/layers", response_model=TerrainLayers)
def list_layers(village_id: VillageId) -> TerrainLayers:
    """Every toggleable layer for this village — the source of FR8's overlay list."""
    return TerrainLayers.model_validate(fixtures.load("terrain_layers"))


@router.get("/{village_id}/dem", response_model=DEMAsset)
def get_dem_asset(village_id: VillageId) -> DEMAsset:
    """Provenance and accuracy of the elevation model underneath every terrain figure.

    A first-class endpoint rather than a footnote: the credibility of the storage
    estimate depends on the reader knowing the source is 30 m.
    """
    return DEMAsset.model_validate(fixtures.load("dem_asset"))


@router.get("/{village_id}/contours", response_model=ContourResponse)
def get_contours(
    village_id: VillageId,
    interval: Annotated[float, Query(gt=0, le=50, description="Contour interval in metres")] = 2.0,
) -> ContourResponse:
    """FR2: contours generated from the DEM pipeline at the requested interval."""
    return ContourResponse.model_validate(fixtures.load("contours"))


@router.get("/{village_id}/streams", response_model=StreamNetwork)
def get_streams(
    village_id: VillageId,
    threshold: Annotated[int | None, Query(gt=0, description="Flow-accumulation cells")] = None,
) -> StreamNetwork:
    """The modelled drainage network, with the threshold that produced it."""
    return StreamNetwork.model_validate(fixtures.load("streams"))


@router.get("/{village_id}/derived/{surface}", response_model=DerivedSurfaceResponse)
def get_derived_surface(
    village_id: VillageId,
    surface: Annotated[DerivedSurface, Path(description="Which surface to return")],
) -> DerivedSurfaceResponse:
    """Slope, aspect, curvature, TWI, hillshade or flow accumulation."""
    return DerivedSurfaceResponse.model_validate(fixtures.load_keyed("derived_surfaces", surface))
