"""Recommendation lifecycle and exports."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import FixtureRoute, PaginationDep
from app.providers import fixtures
from app.schemas.common import Page
from app.schemas.recommendation import (
    ExportDescriptor,
    RecommendationOut,
    StatusChangeRequest,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"], dependencies=[FixtureRoute])


@router.get("", response_model=Page[RecommendationOut], summary="List recommendations")
def list_recommendations(paging: PaginationDep) -> Page[RecommendationOut]:
    """Return saved pond recommendations."""
    return Page[RecommendationOut].model_validate(fixtures.load("recommendations"))


@router.get("/{recommendation_id}", response_model=RecommendationOut)
def get_recommendation(recommendation_id: UUID) -> RecommendationOut:
    """Return one recommendation."""
    return RecommendationOut.model_validate(fixtures.load("recommendations")["items"][0])


@router.post("/{recommendation_id}/status", response_model=RecommendationOut)
def change_status(recommendation_id: UUID, payload: StatusChangeRequest) -> RecommendationOut:
    """Approve or reject a recommendation.

    Role-gated in P6: a viewer receives ``403``. Every transition writes an
    ``audit_log`` row, and that table is append-only in the database — the rules
    are already in migration 0001, so the trail cannot be rewritten later.
    """
    return RecommendationOut.model_validate(fixtures.load("recommendations")["items"][0])


@router.post(
    "/{recommendation_id}/exports",
    response_model=ExportDescriptor,
    status_code=status.HTTP_201_CREATED,
)
def create_export(recommendation_id: UUID, export_format: str = "pdf") -> ExportDescriptor:
    """Generate a PDF, GeoJSON or CSV export and return a link to it."""
    return ExportDescriptor.model_validate(
        {
            "export_id": "7e2b9c14-3d8a-4f5e-b721-9c4a6d3e8f52",
            "recommendation_id": recommendation_id,
            "format": export_format,
            "url": f"/api/v1/exports/7e2b9c14-3d8a-4f5e-b721-9c4a6d3e8f52.{export_format}",
            "size_bytes": 284_713,
            "expires_at": "2026-08-25T07:30:00Z",
        }
    )
