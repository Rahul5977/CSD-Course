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
