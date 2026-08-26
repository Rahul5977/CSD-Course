"""Plain records the repositories hand to the rest of the system.

Engines and routers never see an ORM instance; they see these frozen
dataclasses. That is what allows an in-memory repository to be a drop-in for
the SQL one, and what keeps SQLAlchemy out of the pure core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class VillageRecord:
    """A registered analysis subject."""

    id: UUID
    name: str
    state_code: str | None
    district: str | None
    boundary: dict[str, Any]  # GeoJSON geometry, EPSG:4326
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JobRecord:
    """One asynchronous analysis run."""

    id: UUID
    kind: str
    status: str
    progress: int
    stage: str | None
    village_id: UUID | None
    idempotency_key: str | None
    params: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class DEMAssetRecord:
    """Provenance and storage keys for a village's working DEM."""

    id: UUID
    village_id: UUID
    provider: str
    source: str
    native_resolution_m: float
    working_resolution_m: float
    vertical_accuracy_relative_m: float
    vertical_accuracy_absolute_m: float
    epsg: int
    bounds_lonlat: list[float]
    dem_key: str
    hillshade_key: str | None
    statistics: dict[str, Any]
    attribution: list[str]
    acquired: str | None
    method: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecommendationRecord:
    """A saved pond recommendation."""

    id: UUID
    village_id: UUID
    village_name: str
    design_job_id: UUID
    lon: float
    lat: float
    catchment_area_ha: float
    gross_storage_m3: float
    depth_m: float
    indicative_cost_inr: float
    confidence: str
    status: str
    created_by: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """A pending or processed event."""

    id: UUID
    event_type: str
    actor: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any] | None
    created_at: datetime
    processed_at: datetime | None
