"""Celery application — the worker half of the async job architecture (ADR 0008).

Redis is the broker. Results are not stored in Celery: the job row in Postgres
is the single source of truth for status, progress and result, so a client
polling ``/jobs/{id}`` and a worker updating it agree by construction.

``task_acks_late`` + ``worker_prefetch_multiplier=1`` mean a job is only
acknowledged when it finishes, so a worker killed mid-pipeline hands the job
back to the queue rather than losing it.

**Bulkheads (P6):** two queues, two worker pools. ``interactive`` carries the
jobs a user is waiting on (catchment, runoff, pond design; seconds);
``heavy`` carries contour analysis and suitability (minutes, external reads).
A backlog of heavy jobs cannot delay a click.

**Beat:** the nightly rainfall refresh (leader-elected via a Redis lock) and
the outbox drain that turns pending events into append-only audit rows.
"""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import worker_ready

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

INTERACTIVE = "interactive"
HEAVY = "heavy"

celery_app = Celery("pond", broker=settings.redis_url, include=["app.jobs.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_default_queue=INTERACTIVE,
    task_routes={
        "analysis.catchment": {"queue": INTERACTIVE},
        "analysis.runoff": {"queue": INTERACTIVE},
        "analysis.pond_design": {"queue": INTERACTIVE},
        "analysis.contour": {"queue": HEAVY},
        "analysis.suitability": {"queue": HEAVY},
        "maintenance.*": {"queue": HEAVY},
    },
    beat_schedule={
        "rainfall-refresh-nightly": {
            "task": "maintenance.rainfall_refresh",
            "schedule": 24 * 3600.0,
        },
        "outbox-drain": {"task": "maintenance.outbox_drain", "schedule": 10.0},
        "queue-depth-gauge": {"task": "maintenance.queue_depth", "schedule": 15.0},
    },
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.job_runner == "inline",
    task_eager_propagates=True,
)


@worker_ready.connect  # type: ignore[untyped-decorator]
def _start_metrics_server(**_kwargs: object) -> None:
    """Expose Prometheus metrics from the worker process when a port is configured."""
    if settings.metrics_port:
        from prometheus_client import start_http_server

        start_http_server(settings.metrics_port)
        logger.info("worker metrics on :%d", settings.metrics_port)
