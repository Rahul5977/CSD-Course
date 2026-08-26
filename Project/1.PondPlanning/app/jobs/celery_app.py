"""Celery application — the worker half of the async job architecture (ADR 0008).

Redis is the broker. Results are not stored in Celery: the job row in Postgres
is the single source of truth for status, progress and result, so a client
polling ``/jobs/{id}`` and a worker updating it agree by construction.

``task_acks_late`` + ``worker_prefetch_multiplier=1`` mean a job is only
acknowledged when it finishes, so a worker killed mid-pipeline hands the job
back to the queue rather than losing it.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("pond", broker=settings.redis_url, include=["app.jobs.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_default_queue="interactive",
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.job_runner == "inline",
    task_eager_propagates=True,
)
