"""Village registry, FR1 summary, FR3 available land.

Every handler here validates, delegates once and maps the result. Since P1 the
registry, summary and imagery routes are real; available land and parcel
import stay fixture-backed until P4 and say so.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, UploadFile, status

from app.api.deps import FixtureRoute, PaginationDep, ReposDep
from app.domain.errors import NotFoundError
from app.engines.village import describe_village, imagery_layer, village_summary
from app.providers import fixtures
from app.repositories.records import DEMAssetRecord, VillageRecord
from app.schemas.common import JobAccepted, Page
from app.schemas.village import (
    AvailableLandResponse,
    ImageryLayer,
    VillageCreate,
    VillageOut,
    VillageSummary,
)

router = APIRouter(prefix="/villages", tags=["villages"])

VillageId = Annotated[UUID, Path(description="Village identifier")]


def _require_village(repos: ReposDep, village_id: UUID) -> VillageRecord:
    village = repos.villages.get(village_id)
    if village is None:
        msg = "no such village"
        raise NotFoundError(msg, {"village_id": str(village_id)})
    return village


def _require_dem(repos: ReposDep, village_id: UUID) -> DEMAssetRecord:
    asset = repos.dem_assets.get_for_village(village_id)
    if asset is None:
        msg = "this village has no terrain yet — analyse a contour map first"
        raise NotFoundError(msg, {"village_id": str(village_id)})
    return asset


@router.get("", response_model=Page[VillageOut], summary="List villages")
def list_villages(
    paging: PaginationDep,
    repos: ReposDep,
    q: Annotated[str | None, Query(description="Case-insensitive name search")] = None,
) -> Page[VillageOut]:
    """Return the registered villages, newest first."""
    rows, total = repos.villages.list(limit=paging.limit, offset=paging.offset, q=q)
    return Page[VillageOut](
        items=[describe_village(r) for r in rows],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.post("", response_model=VillageOut, status_code=status.HTTP_201_CREATED)
def create_village(payload: VillageCreate, repos: ReposDep) -> VillageOut:
    """Register a village from a name and a GeoJSON boundary.

    The UTM zone for every later computation is derived from this boundary's own
    centroid at creation time — never configured, never hard-coded.
    """
    record = repos.villages.create(
        payload.name, payload.boundary, payload.state_code, payload.district
    )
    return describe_village(record)


@router.get("/{village_id}", response_model=VillageOut, summary="Village detail")
def get_village(village_id: VillageId, repos: ReposDep) -> VillageOut:
    """Return one village."""
    return describe_village(_require_village(repos, village_id))


@router.get("/{village_id}/summary", response_model=VillageSummary)
def get_village_summary(village_id: VillageId, repos: ReposDep) -> VillageSummary:
    """FR1: area, elevation range and mean slope for the selected village."""
    return village_summary(_require_village(repos, village_id), _require_dem(repos, village_id))


@router.get("/{village_id}/imagery", response_model=ImageryLayer)
def get_village_imagery(village_id: VillageId, repos: ReposDep) -> ImageryLayer:
    """FR1: the satellite basemap descriptor; the client clips it to the boundary."""
    _require_village(repos, village_id)
    return imagery_layer()


@router.get(
    "/{village_id}/available-land",
    response_model=AvailableLandResponse,
    dependencies=[FixtureRoute],
)
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
    dependencies=[FixtureRoute],
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
