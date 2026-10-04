"""Recommendation lifecycle, exports and the audit trail (P6 — real).

State changes are validated by the domain state machine, gated by role, and
written together with an outbox event that the beat task drains into the
append-only ``audit_log``. The audit rows for a recommendation are readable
here so the trail is visible, not merely claimed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field

from app.api.auth import PrincipalDep
from app.api.deps import PaginationDep, ReposDep, StoreDep
from app.core.security import AuthorizationError
from app.domain.errors import NotFoundError
from app.domain.recommendation import required_role, role_allows, transition
from app.domain.units import Quantity, Unit
from app.reports.exports import EXPORTERS
from app.repositories.records import RecommendationRecord
from app.schemas.common import Page, QuantityOut
from app.schemas.recommendation import ExportDescriptor, RecommendationOut, StatusChangeRequest

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
exports_router = APIRouter(prefix="/exports", tags=["recommendations"])
q = QuantityOut.from_domain


class RecommendationCreate(BaseModel):
    """Save a finished pond design as a draft recommendation."""

    design_job_id: UUID = Field(description="A succeeded pond-design job")


def _out(rec: RecommendationRecord) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        village_id=rec.village_id,
        village_name=rec.village_name,
        location=[rec.lon, rec.lat],
        catchment_area=q(Quantity(rec.catchment_area_ha, Unit.HECTARE, 15.0, "D8 upstream")),
        gross_storage=q(
            Quantity(rec.gross_storage_m3, Unit.CUBIC_METRE, 20.0, "prismoidal frustum")
        ),
        depth=q(Quantity(rec.depth_m, Unit.METRE, None, "cost-optimised")),
        indicative_cost=q(Quantity(rec.indicative_cost_inr, Unit.INR, 30.0, "indicative rates")),
        confidence=rec.confidence,  # type: ignore[arg-type]
        status=rec.status,  # type: ignore[arg-type]
        created_by=rec.created_by,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


def _require(repos: ReposDep, recommendation_id: UUID) -> RecommendationRecord:
    rec = repos.recommendations.get(recommendation_id)
    if rec is None:
        msg = "no such recommendation"
        raise NotFoundError(msg, {"recommendation_id": str(recommendation_id)})
    return rec


@router.get("", response_model=Page[RecommendationOut], summary="List recommendations")
def list_recommendations(paging: PaginationDep, repos: ReposDep) -> Page[RecommendationOut]:
    """Saved pond recommendations, newest first."""
    rows, total = repos.recommendations.list(limit=paging.limit, offset=paging.offset)
    return Page[RecommendationOut](
        items=[_out(r) for r in rows], total=total, limit=paging.limit, offset=paging.offset
    )


@router.post(
    "",
    response_model=RecommendationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save a design",
)
def create_recommendation(
    payload: RecommendationCreate, repos: ReposDep, principal: PrincipalDep
) -> RecommendationOut:
    """Turn a succeeded pond-design job into a draft recommendation (planner role)."""
    if not role_allows(principal.role, "planner"):
        msg = "saving a recommendation requires the planner role"
        raise AuthorizationError(msg, {"role": principal.role, "required": "planner"})
    job = repos.jobs.get(payload.design_job_id)
    if job is None or job.kind != "pond_design" or job.status != "succeeded" or not job.result:
        msg = "design job not found or not finished"
        raise NotFoundError(msg, {"design_job_id": str(payload.design_job_id)})
    design: dict[str, Any] = job.result
    village = repos.villages.get(UUID(str(design["village_id"])))
    point = design["catchment"]["snapped_point"]
    now = datetime.now(UTC)
    rec = repos.recommendations.create(
        RecommendationRecord(
            id=uuid.uuid4(),
            village_id=UUID(str(design["village_id"])),
            village_name=village.name if village else "unknown",
            design_job_id=job.id,
            lon=float(point["lon"]),
            lat=float(point["lat"]),
            catchment_area_ha=float(design["catchment"]["area"]["value"]),
            gross_storage_m3=float(design["gross_storage"]["value"]),
            depth_m=float(design["dimensions"]["depth"]["value"]),
            indicative_cost_inr=float(design["bill_of_quantities"]["indicative_cost"]["value"]),
            confidence=str(design["confidence"]),
            status="draft",
            created_by=principal.username,
            payload=design,
            created_at=now,
            updated_at=now,
        )
    )
    repos.outbox.enqueue(
        "recommendation.created",
        principal.username,
        "recommendation",
        str(rec.id),
        {"village": rec.village_name, "storage_m3": rec.gross_storage_m3},
    )
    return _out(rec)


@router.get("/{recommendation_id}", response_model=RecommendationOut)
def get_recommendation(recommendation_id: UUID, repos: ReposDep) -> RecommendationOut:
    """Return one recommendation."""
    return _out(_require(repos, recommendation_id))


@router.post("/{recommendation_id}/status", response_model=RecommendationOut)
def change_status(
    recommendation_id: UUID, payload: StatusChangeRequest, repos: ReposDep, principal: PrincipalDep
) -> RecommendationOut:
    """Move a recommendation through its lifecycle.

    The state machine rejects illegal moves (``409 illegal_transition``); the
    role table rejects under-privileged callers (``403``); every accepted move
    writes an outbox event that becomes an append-only audit row.
    """
    rec = _require(repos, recommendation_id)
    transition(rec.status, payload.status)
    needed = required_role(rec.status, payload.status)
    if not role_allows(principal.role, needed):
        msg = f"moving {rec.status} → {payload.status} requires the {needed} role"
        raise AuthorizationError(msg, {"role": principal.role, "required": needed})
    updated = repos.recommendations.update_status(rec.id, payload.status)
    repos.outbox.enqueue(
        "recommendation.status_changed",
        principal.username,
        "recommendation",
        str(rec.id),
        {"from": rec.status, "to": payload.status, "reason": payload.reason},
    )
    return _out(updated)


@router.get("/{recommendation_id}/audit", summary="Audit trail")
def audit_trail(recommendation_id: UUID, repos: ReposDep) -> dict[str, Any]:
    """Audit rows (drained from the outbox) plus any events still pending."""
    _require(repos, recommendation_id)
    rows = repos.audit.for_entity("recommendation", str(recommendation_id))
    pending = [e for e in repos.outbox.pending() if e.entity_id == str(recommendation_id)]
    return {
        "recommendation_id": str(recommendation_id),
        "audit": rows,
        "pending_outbox": len(pending),
    }


@router.post(
    "/{recommendation_id}/exports",
    response_model=ExportDescriptor,
    status_code=status.HTTP_201_CREATED,
)
def create_export(
    recommendation_id: UUID,
    repos: ReposDep,
    store: StoreDep,
    export_format: Annotated[Literal["pdf", "geojson", "csv"], Query()] = "pdf",
) -> ExportDescriptor:
    """Generate a PDF, GeoJSON or CSV export and return a link to it."""
    rec = _require(repos, recommendation_id)
    build, content_type = EXPORTERS[export_format]
    payload = build(rec)
    export_id = uuid.uuid4()
    key = f"exports/{export_id}.{export_format}"
    store.put(key, payload, content_type)
    return ExportDescriptor(
        export_id=export_id,
        recommendation_id=rec.id,
        format=export_format,
        url=f"/api/v1/exports/{export_id}.{export_format}",
        size_bytes=len(payload),
        expires_at=datetime.now(UTC).replace(microsecond=0)
        + __import__("datetime").timedelta(days=7),
    )


@exports_router.get("/{export_id}.{export_format}", summary="Download an export")
def download_export(
    export_id: UUID, export_format: Literal["pdf", "geojson", "csv"], store: StoreDep
) -> Response:
    """Serve a generated export from the object store."""
    key = f"exports/{export_id}.{export_format}"
    if not store.exists(key):
        msg = "no such export"
        raise NotFoundError(msg, {"export_id": str(export_id)})
    _, content_type = EXPORTERS[export_format]
    return Response(
        store.get(key),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="pond-{export_id}.{export_format}"'},
    )
