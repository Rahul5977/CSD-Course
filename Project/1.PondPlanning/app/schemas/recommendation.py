"""Recommendation lifecycle and export contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import QuantityOut

RecommendationStatus = Literal["draft", "submitted", "approved", "rejected"]


class RecommendationOut(BaseModel):
    """A saved pond recommendation, in its current lifecycle state."""

    id: UUID
    village_id: UUID
    village_name: str
    location: list[float] = Field(description="[lon, lat] in EPSG:4326")
    catchment_area: QuantityOut
    gross_storage: QuantityOut
    depth: QuantityOut
    indicative_cost: QuantityOut
    confidence: Literal["low", "moderate", "high"]
    status: RecommendationStatus
    created_by: str
    created_at: datetime
    updated_at: datetime


class StatusChangeRequest(BaseModel):
    """Approve or reject a recommendation.

    Role-gated: a viewer receives ``403``. Every transition writes an
    ``audit_log`` row, which is append-only in the database — both are G6 exit
    criteria, and the reason field is what makes the trail worth reading.
    """

    status: RecommendationStatus
    reason: str = Field(min_length=1, max_length=1000)


class ExportDescriptor(BaseModel):
    """A generated export artifact.

    Returns a URL rather than bytes so that a large PDF or GeoJSON does not
    occupy an application worker while it streams, and so the link can be shared.
    """

    export_id: UUID
    recommendation_id: UUID
    format: Literal["pdf", "geojson", "csv"]
    url: str
    size_bytes: int
    expires_at: datetime
