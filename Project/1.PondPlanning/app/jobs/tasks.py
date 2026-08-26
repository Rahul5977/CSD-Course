"""Celery task definitions. Thin: each task resolves the context and calls a workflow."""

from __future__ import annotations

from uuid import UUID

from app.jobs.celery_app import celery_app
from app.jobs.context import get_context

CONTOUR_ANALYSIS = "analysis.contour"


@celery_app.task(name=CONTOUR_ANALYSIS, ignore_result=True)  # type: ignore[untyped-decorator]
def contour_analysis_task(job_id: str) -> None:
    """Run ``POST /analyzeContour``'s pipeline for one job."""
    from app.engines.workflows.contour_analysis import run_contour_analysis

    run_contour_analysis(UUID(job_id), get_context())
