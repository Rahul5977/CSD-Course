"""In-memory repositories — the adapter used by tests and Docker-less runs.

Process-local dictionaries behind the same ports as the SQL adapters. Not a
mock: the workflow, the routers and the job runner exercise exactly the code
they run in production, only the storage differs.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.errors import NotFoundError
from app.repositories.records import DEMAssetRecord, JobRecord, VillageRecord


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


class InMemoryJobRepository:
    """Dict-backed jobs."""

    def __init__(self) -> None:
        """Start empty."""
        self._rows: dict[UUID, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, params: dict[str, Any], village_id: UUID | None) -> JobRecord:
        """Insert a queued job."""
        record = JobRecord(
            id=uuid.uuid4(),
            kind=kind,
            status="queued",
            progress=0,
            stage=None,
            village_id=village_id,
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
