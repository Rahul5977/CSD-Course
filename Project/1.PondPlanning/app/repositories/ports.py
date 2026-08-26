"""Repository ports — the persistence interface the application is written against."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from app.repositories.records import (
    DEMAssetRecord,
    JobRecord,
    OutboxEvent,
    RecommendationRecord,
    VillageRecord,
)


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

    def delete(self, village_id: UUID) -> None:
        """Remove a village (saga compensation); no error if absent."""
        ...


class JobRepository(Protocol):
    """Jobs: the record behind every 202."""

    def create(
        self,
        kind: str,
        params: dict[str, Any],
        village_id: UUID | None,
        idempotency_key: str | None = None,
    ) -> JobRecord:
        """Insert a queued job."""
        ...

    def find_by_idempotency_key(self, key: str) -> JobRecord | None:
        """The job created with this client key, if any."""
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

    def delete_for_village(self, village_id: UUID) -> None:
        """Remove the village's DEM row (saga compensation)."""
        ...


class RecommendationRepository(Protocol):
    """Saved recommendations and their lifecycle state."""

    def create(self, record: RecommendationRecord) -> RecommendationRecord:
        """Insert."""
        ...

    def get(self, recommendation_id: UUID) -> RecommendationRecord | None:
        """Fetch one."""
        ...

    def list(self, *, limit: int, offset: int) -> tuple[list[RecommendationRecord], int]:
        """Newest first; returns (page, total)."""
        ...

    def update_status(self, recommendation_id: UUID, status: str) -> RecommendationRecord:
        """Set the lifecycle state."""
        ...


class OutboxRepository(Protocol):
    """Transactional outbox."""

    def enqueue(
        self,
        event_type: str,
        actor: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any] | None,
    ) -> OutboxEvent:
        """Record a pending event."""
        ...

    def pending(self) -> list[OutboxEvent]:
        """Unprocessed events."""
        ...

    def drain(self, handler: Callable[[OutboxEvent], None]) -> int:
        """Process pending events; returns the count."""
        ...


class AuditRepository(Protocol):
    """Append-only audit trail."""

    def append(self, event: OutboxEvent) -> None:
        """Write one row (never updated or deleted)."""
        ...

    def for_entity(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        """Rows for one entity, oldest first."""
        ...
