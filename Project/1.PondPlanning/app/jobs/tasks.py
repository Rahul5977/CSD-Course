"""Celery task definitions. Thin: each task resolves the context and calls a workflow."""

from __future__ import annotations

from uuid import UUID

from app.jobs.celery_app import celery_app
from app.jobs.context import get_context

CONTOUR_ANALYSIS = "analysis.contour"
CATCHMENT = "analysis.catchment"
RUNOFF = "analysis.runoff"
POND_DESIGN = "analysis.pond_design"
SUITABILITY = "analysis.suitability"


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


@celery_app.task(name=RUNOFF, ignore_result=True)  # type: ignore[untyped-decorator]
def runoff_task(job_id: str) -> None:
    """Run ``POST /analysis/runoff``'s pipeline for one job."""
    from app.engines.workflows.runoff import run_runoff

    ctx = get_context()
    run_runoff(UUID(job_id), ctx.repos, ctx.store, ctx.rainfall)


@celery_app.task(name=POND_DESIGN, ignore_result=True)  # type: ignore[untyped-decorator]
def pond_design_task(job_id: str) -> None:
    """Run ``POST /analysis/pond-design``'s pipeline for one job."""
    from app.engines.workflows.pond_design import run_pond_design

    ctx = get_context()
    run_pond_design(
        UUID(job_id),
        ctx.repos,
        ctx.store,
        ctx.rainfall,
        snap_radius_m=ctx.snap_radius_m,
        min_channel_area_m2=ctx.snap_min_upstream_area_m2,
    )


@celery_app.task(name=SUITABILITY, ignore_result=True)  # type: ignore[untyped-decorator]
def suitability_task(job_id: str) -> None:
    """Run ``POST /analysis/suitability``'s pipeline for one job."""
    from app.engines.workflows.suitability import run_suitability

    ctx = get_context()
    run_suitability(
        UUID(job_id),
        ctx.repos,
        ctx.store,
        stream_threshold_area_m2=ctx.stream_threshold_area_m2,
        siting_rise_m=ctx.siting_rise_m,
    )
