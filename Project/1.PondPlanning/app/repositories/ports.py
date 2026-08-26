"""Repository ports — the persistence interface the application is written against."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.repositories.records import DEMAssetRecord, JobRecord, VillageRecord


class VillageRepository(Protocol):
    """Villages: create, fetch, list."""

    def create(
        self, name: str, boundary: dict[str, Any], state_code: str | None, district: str | None
    ) -> VillageRecord:
        """Register a village from a GeoJSON geometry in EPSG:4326."""
        ...

    def get(self, village_id: UUID) -> VillageRecord | None:
        """Fetch one village."""
        ...

    def list(self, *, limit: int, offset: int, q: str | None) -> tuple[list[VillageRecord], int]:
        """Newest first, optionally filtered by name substring; returns (page, total)."""
        ...

    def find_by_boundary(self, boundary: dict[str, Any]) -> VillageRecord | None:
        """A village whose boundary equals this geometry (same map re-uploaded)."""
        ...


class JobRepository(Protocol):
    """Jobs: the record behind every 202."""

    def create(self, kind: str, params: dict[str, Any], village_id: UUID | None) -> JobRecord:
        """Insert a queued job."""
        ...

    def get(self, job_id: UUID) -> JobRecord | None:
        """Fetch one job."""
        ...

    def update(self, job_id: UUID, **fields: Any) -> JobRecord:
        """Patch status/progress/stage/result/error/finished_at/village_id."""
        ...


class DEMAssetRepository(Protocol):
    """One working DEM per village."""

    def upsert(self, record: DEMAssetRecord) -> DEMAssetRecord:
        """Insert or replace the village's DEM row."""
        ...

    def get_for_village(self, village_id: UUID) -> DEMAssetRecord | None:
        """Fetch the village's DEM row."""
        ...
