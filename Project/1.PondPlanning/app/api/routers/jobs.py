"""Job polling — the client half of the async analysis architecture.

Real since P1: reads the job row the worker writes. No fixture header.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import ReposDep
from app.domain.errors import JobFailedError, NotFoundError
from app.repositories.records import JobRecord
from app.schemas.common import JobStatus, ProblemDetail

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _require(repos_jobs: Any, job_id: UUID) -> JobRecord:
    job = repos_jobs.get(job_id)
    if job is None:
        msg = "no such job"
        raise NotFoundError(msg, {"job_id": str(job_id)})
    return job  # type: ignore[no-any-return]


def _status(job: JobRecord) -> JobStatus:
    error = None
    if job.status == "failed" and job.result:
        error = ProblemDetail(
            type=f"#{job.result.get('code', 'job_failed')}",
            title=str(job.result.get("message", job.error or "job failed")),
            status=409,
            code=str(job.result.get("code", "job_failed")),
            detail=dict(job.result.get("detail") or {}),
        )
    return JobStatus(
        job_id=job.id,
        kind=job.kind,
        status=job.status,  # type: ignore[arg-type]
        progress=job.progress,
        stage=job.stage,
        created_at=job.created_at,
        finished_at=job.finished_at,
        error=error,
        result_url=f"/api/v1/jobs/{job.id}/result" if job.status == "succeeded" else None,
    )


@router.get("/{job_id}", response_model=JobStatus, summary="Poll job status")
def get_job(job_id: UUID, repos: ReposDep) -> JobStatus:
    """Return progress for one job.

    ``stage`` is returned alongside ``progress`` because a percentage alone is
    uninformative during a 25-second pipeline; "filling sinks" tells the user
    something is happening and roughly what.
    """
    return _status(_require(repos.jobs, job_id))


@router.get("/{job_id}/result", summary="Fetch a finished job's result")
def get_job_result(job_id: UUID, repos: ReposDep) -> dict[str, Any]:
    """Return the payload of a succeeded job.

    Untyped on purpose: the shape depends on ``kind``. The concrete payloads are
    documented under ``/analysis/results/*``, which is what a client should read.

    Raises:
        JobFailedError: ``409`` when the job failed or has not finished.
    """
    job = _require(repos.jobs, job_id)
    if job.status != "succeeded" or job.result is None:
        msg = "job has not produced a result"
        raise JobFailedError(msg, {"job_id": str(job_id), "status": job.status, "error": job.error})
    return {"job_id": str(job.id), "kind": job.kind, "status": job.status, "result": job.result}


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel a job")
def cancel_job(job_id: UUID, repos: ReposDep) -> None:
    """Request cancellation. Idempotent: cancelling a finished job is not an error."""
    job = _require(repos.jobs, job_id)
    if job.status in {"queued", "running"}:
        repos.jobs.update(
            job_id, status="cancelled", stage="cancelled", finished_at=datetime.now(UTC)
        )
