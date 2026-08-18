"""The analysis routes — FR4, FR6, FR7, FR3, and the Phase 2 contour upload.

Every route here returns ``202 Accepted`` with a job id rather than a result.
Terrain analysis takes tens of seconds; holding a connection open for that long
invites proxy timeouts and gives the user no progress feedback. The async job
architecture is on the never-cut list.

The exception is the fixture-backed *result* shape, which each route documents in
its ``responses`` so the frontend can be built against it before any worker
exists.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import FixtureRoute
from app.providers import fixtures
from app.schemas.analysis import (
    CatchmentRequest,
    CatchmentResult,
    ContourAnalysisResult,
    PondDesignRequest,
    PondDesignResult,
    RunoffRequest,
    RunoffResult,
    SuitabilityRequest,
    SuitabilityResult,
)
from app.schemas.common import JobAccepted

router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[FixtureRoute])


def _accepted(job_id: str, seconds: int) -> JobAccepted:
    """Build the standard 202 body. Shared so every route polls the same way."""
    return JobAccepted.model_validate(
        {"job_id": job_id, "poll_url": f"/api/v1/jobs/{job_id}", "estimated_seconds": seconds}
    )


@router.post("/catchment", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def analyse_catchment(payload: CatchmentRequest) -> JobAccepted:
    """FR4: delineate the upstream contributing area of a clicked point.

    Result shape: :class:`~app.schemas.analysis.CatchmentResult`.
    """
    return _accepted("d4e7a913-2c6b-4f8d-9a15-3e7b2c9f6d41", 12)


@router.post("/runoff", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def analyse_runoff(payload: RunoffRequest) -> JobAccepted:
    """FR6: runoff volume by three methods, reported as a range.

    Result shape: :class:`~app.schemas.analysis.RunoffResult`.
    """
    return _accepted("a7c2e845-6b1d-4e9f-8c37-5a2d9e6b4f18", 8)


@router.post("/pond-design", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def analyse_pond_design(payload: PondDesignRequest) -> JobAccepted:
    """FR7: the complete pond design payload — the project's headline result.

    Result shape: :class:`~app.schemas.analysis.PondDesignResult`, which assembles
    catchment, rainfall, runoff, dimensions, EAV curve, reliability, bill of
    quantities and a confidence label.
    """
    return _accepted("f3b9d128-4a7c-4d2e-b6f1-8c3a5e9d2b74", 25)


@router.post("/suitability", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def analyse_suitability(payload: SuitabilityRequest) -> JobAccepted:
    """FR3: rank candidate pond sites by AHP-weighted criteria.

    Result shape: :class:`~app.schemas.analysis.SuitabilityResult`.
    """
    return _accepted("c8f2a641-9d3b-4e7c-a512-6b8f3d9c2e47", 40)


# The Phase 2 submission route. Mounted outside /analysis at the path the brief
# names, and kept in this module because it shares the whole hydrology chain.
contour_router = APIRouter(tags=["analysis"], dependencies=[FixtureRoute])


@contour_router.post(
    "/analyzeContour",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Analyse an uploaded contour map (KML/KMZ)",
)
def analyze_contour(
    file: Annotated[UploadFile, File(description="Contour map, KML or KMZ")],
    target_interval: Annotated[float | None, Form()] = None,
) -> JobAccepted:
    """Derive a pond location and its catchment from an uploaded contour map.

    Everything in the result is derived from the upload: the UTM zone from the
    file's own centroid, the grid resolution from its own mean contour spacing,
    the pour point from its own modelled drainage. No coordinate, extent or CRS
    specific to any one map exists in this codebase.

    Result shape: :class:`~app.schemas.analysis.ContourAnalysisResult`.
    """
    return _accepted("e5d1c937-8b4a-4f6d-9e23-7c1f4a8d3b95", 35)


# Result-shape routes. These exist so the OpenAPI document — and therefore the
# frontend and the API cookbook — carries the full payloads, not only the 202s.
results_router = APIRouter(
    prefix="/analysis/results", tags=["analysis"], dependencies=[FixtureRoute]
)


@results_router.get("/catchment/{job_id}", response_model=CatchmentResult)
def catchment_result(job_id: UUID) -> CatchmentResult:
    """FR4 result payload."""
    return CatchmentResult.model_validate(fixtures.load("catchment"))


@results_router.get("/runoff/{job_id}", response_model=RunoffResult)
def runoff_result(job_id: UUID) -> RunoffResult:
    """FR6 result payload."""
    return RunoffResult.model_validate(fixtures.load("runoff"))


@results_router.get("/pond-design/{job_id}", response_model=PondDesignResult)
def pond_design_result(job_id: UUID) -> PondDesignResult:
    """FR7 result payload."""
    return PondDesignResult.model_validate(fixtures.load("pond_design"))


@results_router.get("/suitability/{job_id}", response_model=SuitabilityResult)
def suitability_result(job_id: UUID) -> SuitabilityResult:
    """FR3 result payload."""
    return SuitabilityResult.model_validate(fixtures.load("suitability"))


@results_router.get("/contour/{job_id}", response_model=ContourAnalysisResult)
def contour_result(job_id: UUID) -> ContourAnalysisResult:
    """Phase 2 result payload."""
    return ContourAnalysisResult.model_validate(fixtures.load("contour_analysis"))
