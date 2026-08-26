"""Job runner port: how a router hands a job to a worker.

``CeleryJobRunner`` sends the task to Redis. ``InlineJobRunner`` executes it in
the calling process — used by the tests and by a laptop without Docker, and
deliberately identical from the router's point of view.
"""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID

from app.core.config import Settings
from app.domain.errors import DomainError

logger = logging.getLogger(__name__)


class JobRunner(Protocol):
    """Submit a named task for a job id."""

    def submit(self, task_name: str, job_id: UUID) -> None:
        """Dispatch; never raises for a job failure — that is recorded on the job."""
        ...


class CeleryJobRunner:
    """Dispatch through the Celery broker."""

    def submit(self, task_name: str, job_id: UUID) -> None:
        """Send the task by name so the API process never imports the worker code."""
        from app.jobs.celery_app import celery_app

        celery_app.send_task(task_name, args=[str(job_id)])


class InlineJobRunner:
    """Run the task synchronously in the caller's process."""

    def submit(self, task_name: str, job_id: UUID) -> None:
        """Execute immediately; failures are already written to the job row."""
        from app.jobs import tasks

        task = {
            tasks.CONTOUR_ANALYSIS: tasks.contour_analysis_task,
            tasks.CATCHMENT: tasks.catchment_task,
            tasks.RUNOFF: tasks.runoff_task,
            tasks.POND_DESIGN: tasks.pond_design_task,
            tasks.SUITABILITY: tasks.suitability_task,
        }[task_name]
        try:
            task.run(str(job_id))
        except DomainError as exc:
            logger.info("inline job failed", extra={"job_id": str(job_id), "code": exc.code})
        except Exception:
            logger.exception("inline job crashed", extra={"job_id": str(job_id)})


def build_job_runner(settings: Settings) -> JobRunner:
    """Factory from settings."""
    return InlineJobRunner() if settings.job_runner == "inline" else CeleryJobRunner()
