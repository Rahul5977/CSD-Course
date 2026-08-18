"""Job polling — the client half of the async analysis architecture."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import FixtureRoute
from app.schemas.common import JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[FixtureRoute])


@router.get("/{job_id}", response_model=JobStatus, summary="Poll job status")
def get_job(job_id: UUID) -> JobStatus:
    """Return progress for one job.

    ``stage`` is returned alongside ``progress`` because a percentage alone is
    uninformative during a 25-second pipeline; "filling sinks" tells the user
    something is happening and roughly what.
    """
    return JobStatus.model_validate(
        {
            "job_id": job_id,
            "kind": "catchment",
            "status": "running",
            "progress": 60,
            "stage": "tracing upstream cells",
            "created_at": "2026-08-18T07:30:00Z",
            "result_url": f"/api/v1/jobs/{job_id}/result",
        }
    )


@router.get("/{job_id}/result", summary="Fetch a finished job's result")
def get_job_result(job_id: UUID) -> dict[str, object]:
    """Return the payload of a succeeded job.

    Untyped on purpose: the shape depends on ``kind``. The concrete payloads are
    documented under ``/analysis/results/*``, which is what a client should read.
    """
    return {
        "job_id": str(job_id),
        "kind": "catchment",
        "status": "succeeded",
        "result_shape": "CatchmentResult",
        "documented_at": "/api/v1/analysis/results/catchment/{job_id}",
    }


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel a job")
def cancel_job(job_id: UUID) -> None:
    """Request cancellation. Idempotent: cancelling a finished job is not an error."""
    return None
