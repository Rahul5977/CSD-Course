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

from app.api.deps import FixtureRoute, ReposDep, RunnerDep, SettingsDep, StoreDep
from app.api.uploads import read_contour_upload
from app.domain.errors import NotFoundError
from app.jobs.tasks import CATCHMENT, CONTOUR_ANALYSIS, POND_DESIGN, RUNOFF
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

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _accepted(job_id: str, seconds: int) -> JobAccepted:
    """Build the standard 202 body. Shared so every route polls the same way."""
    return JobAccepted.model_validate(
        {"job_id": job_id, "poll_url": f"/api/v1/jobs/{job_id}", "estimated_seconds": seconds}
    )


@router.post("/catchment", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def analyse_catchment(payload: CatchmentRequest, repos: ReposDep, runner: RunnerDep) -> JobAccepted:
    """FR4: delineate the upstream contributing area of a clicked point.

    Real since P2. Snap → D8 upstream BFS → polygon, in a worker; the pipeline
    is :mod:`app.engines.workflows.catchment`.

    Result shape: :class:`~app.schemas.analysis.CatchmentResult`.
    """
    if repos.villages.get(payload.village_id) is None:
        msg = "no such village"
        raise NotFoundError(msg, {"village_id": str(payload.village_id)})
    job = repos.jobs.create(CATCHMENT_KIND, payload.model_dump(mode="json"), payload.village_id)
    runner.submit(CATCHMENT, job.id)
    return _accepted(str(job.id), 5)


@router.post("/runoff", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def analyse_runoff(payload: RunoffRequest, repos: ReposDep, runner: RunnerDep) -> JobAccepted:
    """FR6: runoff volume by three methods, reported as a range.

    Real since P3: land cover (WorldCover) + soil (SoilGrids) → curve number →
    daily rainfall → SCS-CN / rational / Strange on the daily series.

    Result shape: :class:`~app.schemas.analysis.RunoffResult`.
    """
    if repos.villages.get(payload.village_id) is None:
        msg = "no such village"
        raise NotFoundError(msg, {"village_id": str(payload.village_id)})
    job = repos.jobs.create(RUNOFF_KIND, payload.model_dump(mode="json"), payload.village_id)
    runner.submit(RUNOFF, job.id)
    return _accepted(str(job.id), 40)


@router.post("/pond-design", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def analyse_pond_design(
    payload: PondDesignRequest, repos: ReposDep, runner: RunnerDep
) -> JobAccepted:
    """FR7: the complete pond design payload — the project's headline result.

    Real since P3. Result shape: :class:`~app.schemas.analysis.PondDesignResult`,
    which assembles catchment, rainfall, runoff, dimensions, EAV curve,
    reliability, bill of quantities and a confidence label.
    """
    if repos.villages.get(payload.village_id) is None:
        msg = "no such village"
        raise NotFoundError(msg, {"village_id": str(payload.village_id)})
    job = repos.jobs.create(POND_DESIGN_KIND, payload.model_dump(mode="json"), payload.village_id)
    runner.submit(POND_DESIGN, job.id)
    return _accepted(str(job.id), 60)


@router.post(
    "/suitability",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[FixtureRoute],
)
def analyse_suitability(payload: SuitabilityRequest) -> JobAccepted:
    """FR3: rank candidate pond sites by AHP-weighted criteria.

    Result shape: :class:`~app.schemas.analysis.SuitabilityResult`.
    """
    return _accepted("c8f2a641-9d3b-4e7c-a512-6b8f3d9c2e47", 40)


# The Phase 2 submission route. Mounted outside /analysis at the path the brief
# names, and kept in this module because it shares the whole hydrology chain.
# Real since P1: no FixtureRoute dependency.
contour_router = APIRouter(tags=["analysis"])


@contour_router.post(
    "/analyzeContour",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Analyse an uploaded contour map (KML/KMZ)",
)
def analyze_contour(
    file: Annotated[UploadFile, File(description="Contour map, KML or KMZ")],
    repos: ReposDep,
    store: StoreDep,
    runner: RunnerDep,
    settings: SettingsDep,
    target_interval: Annotated[float | None, Form()] = None,
) -> JobAccepted:
    """Derive terrain — and, from P2, a pond location and its catchment — from an upload.

    Everything in the result is derived from the upload: the UTM zone from the
    file's own centroid, the grid resolution from its own mean contour spacing,
    the source accuracy from its own metadata. No coordinate, extent or CRS
    specific to any one map exists in this codebase.

    Validate → store the upload → create the job → dispatch → ``202``. The
    pipeline itself runs in :mod:`app.engines.workflows.contour_analysis`.

    Result shape: :class:`~app.schemas.analysis.ContourAnalysisResult`.
    """
    filename, payload = read_contour_upload(file, settings.max_upload_mb)
    job = repos.jobs.create(CONTOUR_ANALYSIS_KIND, {"filename": filename}, None)
    upload_key = f"uploads/{job.id}/{filename}"
    store.put(upload_key, payload, "application/vnd.google-earth.kml+xml")
    repos.jobs.update(
        job.id,
        params={"filename": filename, "upload_key": upload_key, "target_interval": target_interval},
    )
    runner.submit(CONTOUR_ANALYSIS, job.id)
    return _accepted(str(job.id), 35)


CONTOUR_ANALYSIS_KIND = "contour_analysis"
CATCHMENT_KIND = "catchment"
RUNOFF_KIND = "runoff"
POND_DESIGN_KIND = "pond_design"


# Result-shape routes. These exist so the OpenAPI document — and therefore the
# frontend and the API cookbook — carries the full payloads, not only the 202s.
results_router = APIRouter(prefix="/analysis/results", tags=["analysis"])


def _finished(repos: ReposDep, job_id: UUID, kind: str) -> dict[str, object]:
    job = repos.jobs.get(job_id)
    if job is None or job.kind != kind or job.status != "succeeded" or job.result is None:
        msg = f"no finished {kind} job with this id"
        raise NotFoundError(msg, {"job_id": str(job_id), "kind": kind})
    return job.result


@results_router.get("/catchment/{job_id}", response_model=CatchmentResult)
def catchment_result(job_id: UUID, repos: ReposDep) -> CatchmentResult:
    """FR4 result payload (real since P2)."""
    return CatchmentResult.model_validate(_finished(repos, job_id, CATCHMENT_KIND))


@results_router.get("/runoff/{job_id}", response_model=RunoffResult)
def runoff_result(job_id: UUID, repos: ReposDep) -> RunoffResult:
    """FR6 result payload (real since P3)."""
    return RunoffResult.model_validate(_finished(repos, job_id, RUNOFF_KIND))


@results_router.get("/pond-design/{job_id}", response_model=PondDesignResult)
def pond_design_result(job_id: UUID, repos: ReposDep) -> PondDesignResult:
    """FR7 result payload (real since P3)."""
    return PondDesignResult.model_validate(_finished(repos, job_id, POND_DESIGN_KIND))


@results_router.get(
    "/suitability/{job_id}", response_model=SuitabilityResult, dependencies=[FixtureRoute]
)
def suitability_result(job_id: UUID) -> SuitabilityResult:
    """FR3 result payload."""
    return SuitabilityResult.model_validate(fixtures.load("suitability"))


@results_router.get("/contour/{job_id}", response_model=ContourAnalysisResult)
def contour_result(job_id: UUID, repos: ReposDep) -> ContourAnalysisResult:
    """Phase 2 result payload (real since P2)."""
    return ContourAnalysisResult.model_validate(_finished(repos, job_id, CONTOUR_ANALYSIS_KIND))
