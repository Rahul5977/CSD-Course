"""Celery task definitions. Thin: each task resolves the context and calls a workflow."""

from __future__ import annotations

from uuid import UUID

from app.jobs.celery_app import celery_app
from app.jobs.context import get_context

CONTOUR_ANALYSIS = "analysis.contour"
CATCHMENT = "analysis.catchment"


@celery_app.task(name=CONTOUR_ANALYSIS, ignore_result=True)  # type: ignore[untyped-decorator]
def contour_analysis_task(job_id: str) -> None:
    """Run ``POST /analyzeContour``'s pipeline for one job."""
    from app.engines.workflows.contour_analysis import run_contour_analysis

    run_contour_analysis(UUID(job_id), get_context())


@celery_app.task(name=CATCHMENT, ignore_result=True)  # type: ignore[untyped-decorator]
def catchment_task(job_id: str) -> None:
    """Run ``POST /analysis/catchment``'s pipeline for one job."""
    from app.engines.workflows.catchment import run_catchment

    ctx = get_context()
    run_catchment(
        UUID(job_id),
        ctx.repos,
        ctx.store,
        snap_radius_m=ctx.snap_radius_m,
        min_channel_area_m2=ctx.snap_min_upstream_area_m2,
    )
