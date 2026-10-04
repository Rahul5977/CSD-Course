"""Job runner port: how a router hands a job to a worker.

``CeleryJobRunner`` sends the task to Redis. ``InlineJobRunner`` executes it in
the calling process — used by the tests and by a laptop without Docker.
``ThreadJobRunner`` is the one-process deployment's worker (the lab VMs, which
cannot run Redis/Celery): the POST returns ``202`` at once and the job runs on
a bounded thread pool per queue — the same ``interactive``/``heavy`` bulkheads
as the Celery workers, so a village analysis cannot delay a catchment click.
All three are identical from the router's point of view.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, Protocol
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


def _task(task_name: str) -> Callable[[str], Any]:
    from app.jobs import tasks

    task = {
        tasks.CONTOUR_ANALYSIS: tasks.contour_analysis_task,
        tasks.CATCHMENT: tasks.catchment_task,
        tasks.RUNOFF: tasks.runoff_task,
        tasks.POND_DESIGN: tasks.pond_design_task,
        tasks.SUITABILITY: tasks.suitability_task,
    }[task_name]
    return task.run  # type: ignore[no-any-return]


def _run_logged(task_name: str, job_id: UUID) -> None:
    """Run one task; failures are already written to the job row, so only log them."""
    try:
        _task(task_name)(str(job_id))
    except DomainError as exc:
        logger.info("job failed", extra={"job_id": str(job_id), "code": exc.code})
    except Exception:
        logger.exception("job crashed", extra={"job_id": str(job_id)})


class InlineJobRunner:
    """Run the task synchronously in the caller's process."""

    def submit(self, task_name: str, job_id: UUID) -> None:
        """Execute immediately; failures are already written to the job row."""
        _run_logged(task_name, job_id)


#: Which bulkhead each task runs in — mirrors ``celery_app.task_routes``.
HEAVY_TASKS = frozenset({"analysis.contour", "analysis.suitability"})


class ThreadJobRunner:
    """Bounded thread pools per queue, shared by the whole process."""

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _pools: ClassVar[dict[str, ThreadPoolExecutor]] = {}
    _pending: ClassVar[dict[str, int]] = {"interactive": 0, "heavy": 0}

    def __init__(self, interactive_workers: int, heavy_workers: int) -> None:
        """Create the pools once per process; later instances share them."""
        with self._lock:
            if not self._pools:
                self._pools["interactive"] = ThreadPoolExecutor(
                    interactive_workers, thread_name_prefix="job-interactive"
                )
                self._pools["heavy"] = ThreadPoolExecutor(
                    heavy_workers, thread_name_prefix="job-heavy"
                )

    @classmethod
    def pending(cls, queue: str) -> int:
        """Jobs queued or running on a pool — the backpressure signal."""
        with cls._lock:
            return cls._pending.get(queue, 0)

    def submit(self, task_name: str, job_id: UUID) -> None:
        """Queue the task on its bulkhead and return immediately."""
        queue = "heavy" if task_name in HEAVY_TASKS else "interactive"
        with self._lock:
            self._pending[queue] += 1

        def run() -> None:
            try:
                _run_logged(task_name, job_id)
            finally:
                with self._lock:
                    self._pending[queue] -= 1

        self._pools[queue].submit(run)


def build_job_runner(settings: Settings) -> JobRunner:
    """Factory from settings."""
    if settings.job_runner == "inline":
        return InlineJobRunner()
    if settings.job_runner == "thread":
        return ThreadJobRunner(settings.thread_workers_interactive, settings.thread_workers_heavy)
    return CeleryJobRunner()
