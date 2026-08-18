"""Village registry, FR1 summary, FR3 available land.

Every handler here validates, delegates once and maps the result. The delegate
is currently the fixture provider; in P1-P4 it becomes the corresponding engine
and nothing about these signatures changes.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, UploadFile, status

from app.api.deps import FixtureRoute, PaginationDep
from app.providers import fixtures
from app.schemas.common import JobAccepted, Page
from app.schemas.village import (
    AvailableLandResponse,
    ImageryLayer,
    VillageCreate,
    VillageOut,
    VillageSummary,
)

router = APIRouter(prefix="/villages", tags=["villages"], dependencies=[FixtureRoute])

VillageId = Annotated[UUID, Path(description="Village identifier")]


@router.get("", response_model=Page[VillageOut], summary="List villages")
def list_villages(
    paging: PaginationDep,
    q: Annotated[str | None, Query(description="Case-insensitive name search")] = None,
) -> Page[VillageOut]:
    """Return the registered villages, newest first."""
    return Page[VillageOut].model_validate(fixtures.load("villages"))


@router.post("", response_model=VillageOut, status_code=status.HTTP_201_CREATED)
def create_village(payload: VillageCreate) -> VillageOut:
    """Register a village from a name and a GeoJSON boundary.

    The UTM zone for every later computation is derived from this boundary's own
    centroid at creation time — never configured, never hard-coded.
    """
    return VillageOut.model_validate(fixtures.load("villages")["items"][0])


@router.get("/{village_id}", response_model=VillageOut, summary="Village detail")
def get_village(village_id: VillageId) -> VillageOut:
    """Return one village."""
    return VillageOut.model_validate(fixtures.load("villages")["items"][0])


@router.get("/{village_id}/summary", response_model=VillageSummary)
def get_village_summary(village_id: VillageId) -> VillageSummary:
    """FR1: area, elevation range and mean slope for the selected village."""
    return VillageSummary.model_validate(fixtures.load("village_summary"))


@router.get("/{village_id}/imagery", response_model=ImageryLayer)
def get_village_imagery(village_id: VillageId) -> ImageryLayer:
    """FR1: the satellite basemap descriptor, clipped to this village."""
    return ImageryLayer.model_validate(fixtures.load("imagery"))


@router.get("/{village_id}/available-land", response_model=AvailableLandResponse)
def get_available_land(
    village_id: VillageId,
    max_slope: Annotated[float, Query(ge=0, le=45)] = 5.0,
    min_area_ha: Annotated[float, Query(gt=0)] = 0.5,
) -> AvailableLandResponse:
    """FR3: land eligible for excavation, with the constraints that produced it."""
    return AvailableLandResponse.model_validate(fixtures.load("available_land"))


@router.post(
    "/{village_id}/parcels:import",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def import_parcels(village_id: VillageId, file: UploadFile) -> JobAccepted:
    """Import cadastral parcels from a zipped Shapefile or GeoJSON.

    Asynchronous because a district parcel set is large. Upload hardening
    (driver whitelist, zip-entry validation, size cap) lands with the engine in
    P4; the contract is fixed here.
    """
    return JobAccepted.model_validate(
        {
            "job_id": "b1c8f4a2-9d3e-4c7b-8a15-6f2e9d4c1b73",
            "poll_url": "/api/v1/jobs/b1c8f4a2-9d3e-4c7b-8a15-6f2e9d4c1b73",
            "estimated_seconds": 45,
        }
    )
