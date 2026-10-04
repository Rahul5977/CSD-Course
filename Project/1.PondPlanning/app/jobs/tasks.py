"""Celery task definitions. Thin: each task resolves the context and calls a workflow.

Every analysis task is wrapped by :func:`_timed`, which sets the correlation
id to the job id (so worker log lines join the request's) and records the
job's duration and outcome in the Prometheus histogram.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.core.observability import (
    CACHE_EVENTS,
    QUEUE_DEPTH,
    observe_job,
    request_id_var,
)
from app.jobs.celery_app import HEAVY, INTERACTIVE, celery_app
from app.jobs.context import get_context

logger = logging.getLogger(__name__)


def _timed(kind: str, job_id: str, work: Callable[[], Any]) -> None:
    token = request_id_var.set(f"job:{job_id[:8]}")
    started = time.perf_counter()
    status = "succeeded"
    try:
        work()
    except Exception:
        status = "failed"
        raise
    finally:
        observe_job(kind, status, time.perf_counter() - started)
        request_id_var.reset(token)


CONTOUR_ANALYSIS = "analysis.contour"
CATCHMENT = "analysis.catchment"
RUNOFF = "analysis.runoff"
POND_DESIGN = "analysis.pond_design"
SUITABILITY = "analysis.suitability"


@celery_app.task(name=CONTOUR_ANALYSIS, ignore_result=True)  # type: ignore[untyped-decorator]
def contour_analysis_task(job_id: str) -> None:
    """Run ``POST /analyzeContour``'s pipeline for one job."""
    from app.engines.workflows.contour_analysis import run_contour_analysis

    _timed("contour_analysis", job_id, lambda: run_contour_analysis(UUID(job_id), get_context()))


@celery_app.task(name=CATCHMENT, ignore_result=True)  # type: ignore[untyped-decorator]
def catchment_task(job_id: str) -> None:
    """Run ``POST /analysis/catchment``'s pipeline for one job."""
    from app.engines.workflows.catchment import run_catchment

    ctx = get_context()
    _timed(
        "catchment",
        job_id,
        lambda: run_catchment(
            UUID(job_id),
            ctx.repos,
            ctx.store,
            snap_radius_m=ctx.snap_radius_m,
            min_channel_area_m2=ctx.snap_min_upstream_area_m2,
        ),
    )


@celery_app.task(name=RUNOFF, ignore_result=True)  # type: ignore[untyped-decorator]
def runoff_task(job_id: str) -> None:
    """Run ``POST /analysis/runoff``'s pipeline for one job."""
    from app.engines.workflows.runoff import run_runoff

    ctx = get_context()
    _timed("runoff", job_id, lambda: run_runoff(UUID(job_id), ctx.repos, ctx.store, ctx.rainfall))


@celery_app.task(name=POND_DESIGN, ignore_result=True)  # type: ignore[untyped-decorator]
def pond_design_task(job_id: str) -> None:
    """Run ``POST /analysis/pond-design``'s pipeline for one job."""
    from app.engines.workflows.pond_design import run_pond_design

    ctx = get_context()
    _timed(
        "pond_design",
        job_id,
        lambda: run_pond_design(
            UUID(job_id),
            ctx.repos,
            ctx.store,
            ctx.rainfall,
            snap_radius_m=ctx.snap_radius_m,
            min_channel_area_m2=ctx.snap_min_upstream_area_m2,
        ),
    )


@celery_app.task(name=SUITABILITY, ignore_result=True)  # type: ignore[untyped-decorator]
def suitability_task(job_id: str) -> None:
    """Run ``POST /analysis/suitability``'s pipeline for one job."""
    from app.engines.workflows.suitability import run_suitability

    ctx = get_context()
    _timed(
        "suitability",
        job_id,
        lambda: run_suitability(
            UUID(job_id),
            ctx.repos,
            ctx.store,
            stream_threshold_area_m2=ctx.stream_threshold_area_m2,
            siting_rise_m=ctx.siting_rise_m,
        ),
    )


# -- maintenance (beat) ---------------------------------------------------------
RAINFALL_REFRESH = "maintenance.rainfall_refresh"
OUTBOX_DRAIN = "maintenance.outbox_drain"
QUEUE_GAUGE = "maintenance.queue_depth"


@celery_app.task(name=RAINFALL_REFRESH, ignore_result=True)  # type: ignore[untyped-decorator]
def rainfall_refresh_task() -> None:
    """Nightly: re-fetch the rainfall record for every village, on one worker only."""
    from app.core.config import get_settings
    from app.engines.rainfall.service import fetch_record
    from app.engines.village import boundary_facts
    from app.providers.queues import leader_lock

    settings = get_settings()
    with leader_lock(settings.redis_url, "rainfall-refresh", ttl_s=3600) as leader:
        if not leader:
            logger.info("rainfall refresh: another worker holds the lock")
            return
        ctx = get_context()
        villages, _ = ctx.repos.villages.list(limit=200, offset=0, q=None)
        for village in villages:
            (lon, lat), _epsg, _area = boundary_facts(village.boundary)
            try:
                fetch_record(ctx.rainfall, lon, lat, settings.rainfall_years)
                CACHE_EVENTS.labels("rainfall", "refresh").inc()
            except Exception as exc:
                logger.warning(
                    "rainfall refresh failed", extra={"village": village.name, "reason": str(exc)}
                )


@celery_app.task(name=OUTBOX_DRAIN, ignore_result=True)  # type: ignore[untyped-decorator]
def outbox_drain_task() -> None:
    """Move pending outbox events into the append-only audit log."""
    ctx = get_context()
    drained = ctx.repos.outbox.drain(ctx.repos.audit.append)
    if drained:
        logger.info("outbox drained", extra={"events": drained})


@celery_app.task(name=QUEUE_GAUGE, ignore_result=True)  # type: ignore[untyped-decorator]
def queue_depth_task() -> None:
    """Sample both queue depths into the Prometheus gauge."""
    from app.core.config import get_settings
    from app.providers.queues import queue_depth

    url = get_settings().redis_url
    for queue in (INTERACTIVE, HEAVY):
        QUEUE_DEPTH.labels(queue).set(queue_depth(url, queue))
