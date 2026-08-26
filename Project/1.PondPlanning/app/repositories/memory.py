"""In-memory repositories — the adapter used by tests and Docker-less runs.

Process-local dictionaries behind the same ports as the SQL adapters. Not a
mock: the workflow, the routers and the job runner exercise exactly the code
they run in production, only the storage differs.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.errors import NotFoundError
from app.repositories.records import (
    DEMAssetRecord,
    JobRecord,
    OutboxEvent,
    RecommendationRecord,
    VillageRecord,
)


def boundary_key(boundary: dict[str, Any]) -> str:
    """Canonical text for a GeoJSON geometry, rounded to 1e-5 degrees (~1 m)."""
    import json

    def rnd(obj: Any) -> Any:
        if isinstance(obj, float):
            return round(obj, 5)
        if isinstance(obj, list):
            return [rnd(v) for v in obj]
        return obj

    return json.dumps(rnd(boundary), sort_keys=True)


class InMemoryVillageRepository:
    """Dict-backed villages."""

    def __init__(self) -> None:
        """Start empty."""
        self._rows: dict[UUID, VillageRecord] = {}
        self._lock = threading.Lock()

    def create(
        self, name: str, boundary: dict[str, Any], state_code: str | None, district: str | None
    ) -> VillageRecord:
        """Insert with a fresh id."""
        record = VillageRecord(
            id=uuid.uuid4(),
            name=name,
            state_code=state_code,
            district=district,
            boundary=boundary,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._rows[record.id] = record
        return record

    def get(self, village_id: UUID) -> VillageRecord | None:
        """Lookup by id."""
        return self._rows.get(village_id)

    def list(self, *, limit: int, offset: int, q: str | None) -> tuple[list[VillageRecord], int]:
        """Newest first."""
        rows = sorted(self._rows.values(), key=lambda r: r.created_at, reverse=True)
        if q:
            rows = [r for r in rows if q.lower() in r.name.lower()]
        return rows[offset : offset + limit], len(rows)

    def find_by_boundary(self, boundary: dict[str, Any]) -> VillageRecord | None:
        """Exact geometry match after rounding to ~1 m."""
        wanted = boundary_key(boundary)
        return next((r for r in self._rows.values() if boundary_key(r.boundary) == wanted), None)

    def delete(self, village_id: UUID) -> None:
        """Drop the row."""
        self._rows.pop(village_id, None)


class InMemoryJobRepository:
    """Dict-backed jobs."""

    def __init__(self) -> None:
        """Start empty."""
        self._rows: dict[UUID, JobRecord] = {}
        self._lock = threading.Lock()

    def create(
        self,
        kind: str,
        params: dict[str, Any],
        village_id: UUID | None,
        idempotency_key: str | None = None,
    ) -> JobRecord:
        """Insert a queued job."""
        record = JobRecord(
            id=uuid.uuid4(),
            kind=kind,
            status="queued",
            progress=0,
            stage=None,
            village_id=village_id,
            idempotency_key=idempotency_key,
            params=params,
            result=None,
            error=None,
            created_at=datetime.now(UTC),
            finished_at=None,
        )
        with self._lock:
            self._rows[record.id] = record
        return record

    def get(self, job_id: UUID) -> JobRecord | None:
        """Lookup by id."""
        return self._rows.get(job_id)

    def find_by_idempotency_key(self, key: str) -> JobRecord | None:
        """The job created with this client key, if any."""
        return next((r for r in self._rows.values() if r.idempotency_key == key), None)

    def update(self, job_id: UUID, **fields: Any) -> JobRecord:
        """Replace fields on the record."""
        with self._lock:
            current = self._rows.get(job_id)
            if current is None:
                msg = "job not found"
                raise NotFoundError(msg, {"job_id": str(job_id)})
            updated = replace(current, **fields)
            self._rows[job_id] = updated
        return updated


class InMemoryDEMAssetRepository:
    """Dict-backed DEM assets, keyed by village."""

    def __init__(self) -> None:
        """Start empty."""
        self._rows: dict[UUID, DEMAssetRecord] = {}

    def upsert(self, record: DEMAssetRecord) -> DEMAssetRecord:
        """Insert or replace by village."""
        stamped = replace(record, created_at=record.created_at or datetime.now(UTC))
        self._rows[record.village_id] = stamped
        return stamped

    def get_for_village(self, village_id: UUID) -> DEMAssetRecord | None:
        """Lookup by village."""
        return self._rows.get(village_id)

    def delete_for_village(self, village_id: UUID) -> None:
        """Drop the row."""
        self._rows.pop(village_id, None)


class InMemoryRecommendationRepository:
    """Dict-backed recommendations."""

    def __init__(self) -> None:
        """Start empty."""
        self._rows: dict[UUID, RecommendationRecord] = {}

    def create(self, record: RecommendationRecord) -> RecommendationRecord:
        """Insert as given."""
        self._rows[record.id] = record
        return record

    def get(self, recommendation_id: UUID) -> RecommendationRecord | None:
        """Lookup by id."""
        return self._rows.get(recommendation_id)

    def list(self, *, limit: int, offset: int) -> tuple[list[RecommendationRecord], int]:
        """Newest first."""
        rows = sorted(self._rows.values(), key=lambda r: r.created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)

    def update_status(self, recommendation_id: UUID, status: str) -> RecommendationRecord:
        """Set the lifecycle state."""
        current = self._rows[recommendation_id]
        updated = replace(current, status=status, updated_at=datetime.now(UTC))
        self._rows[recommendation_id] = updated
        return updated


class InMemoryOutboxRepository:
    """Dict-backed outbox."""

    def __init__(self) -> None:
        """Start empty."""
        self._rows: list[OutboxEvent] = []

    def enqueue(
        self,
        event_type: str,
        actor: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any] | None,
    ) -> OutboxEvent:
        """Append a pending event."""
        event = OutboxEvent(
            uuid.uuid4(),
            event_type,
            actor,
            entity_type,
            entity_id,
            payload,
            datetime.now(UTC),
            None,
        )
        self._rows.append(event)
        return event

    def pending(self) -> list[OutboxEvent]:
        """Events not yet processed."""
        return [e for e in self._rows if e.processed_at is None]

    def drain(self, handler: Callable[[OutboxEvent], None]) -> int:
        """Hand each pending event to ``handler`` and mark it processed."""
        count = 0
        for i, event in enumerate(self._rows):
            if event.processed_at is None:
                handler(event)
                self._rows[i] = replace(event, processed_at=datetime.now(UTC))
                count += 1
        return count


class InMemoryAuditRepository:
    """List-backed append-only audit log."""

    def __init__(self) -> None:
        """Start empty."""
        self.rows: list[dict[str, Any]] = []

    def append(self, event: OutboxEvent) -> None:
        """Append one audit row derived from an event."""
        self.rows.append(
            {
                "actor": event.actor,
                "action": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "detail": event.payload,
                "created_at": datetime.now(UTC),
            }
        )

    def for_entity(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        """Rows for one entity, oldest first."""
        return [
            r for r in self.rows if r["entity_type"] == entity_type and r["entity_id"] == entity_id
        ]
