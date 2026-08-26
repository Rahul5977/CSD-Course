"""SQLAlchemy repositories — the Postgres/PostGIS adapter behind the ports.

Each method is its own short transaction. The heavy work in this system is
raster processing in the worker; holding a database transaction across it
would only pin a connection for no benefit (ADR 0003).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.errors import NotFoundError
from app.repositories import models
from app.repositories.records import DEMAssetRecord, JobRecord, VillageRecord

SessionFactory = Callable[[], Session]


def _village(row: models.Village) -> VillageRecord:
    return VillageRecord(
        id=row.id,
        name=row.name,
        state_code=row.state_code,
        district=row.district,
        boundary=mapping(to_shape(row.boundary)),  # type: ignore[arg-type]
        created_at=row.created_at,
    )


def _job(row: models.Job) -> JobRecord:
    return JobRecord(
        id=row.id,
        kind=row.kind,
        status=row.status,
        progress=row.progress,
        stage=row.stage,
        village_id=row.village_id,
        params=dict(row.params or {}),
        result=None if row.result is None else dict(row.result),
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


def _asset(row: models.DEMAsset) -> DEMAssetRecord:
    return DEMAssetRecord(
        id=row.id,
        village_id=row.village_id,
        provider=row.provider,
        source=row.source,
        native_resolution_m=row.native_resolution_m,
        working_resolution_m=row.working_resolution_m,
        vertical_accuracy_relative_m=row.vertical_accuracy_relative_m,
        vertical_accuracy_absolute_m=row.vertical_accuracy_absolute_m,
        epsg=row.epsg,
        bounds_lonlat=list(row.bounds_lonlat),
        dem_key=row.dem_key,
        hillshade_key=row.hillshade_key,
        statistics=dict(row.statistics),
        attribution=list(row.attribution),
        acquired=row.acquired,
        method=row.method,
        details=dict(row.details or {}),
        created_at=row.created_at,
    )


class SqlVillageRepository:
    """Villages in PostGIS; boundaries stored as MultiPolygon SRID 4326."""

    def __init__(self, session_factory: SessionFactory) -> None:
        """Bind to a session factory, not a session — one transaction per call."""
        self._sessions = session_factory

    def create(
        self, name: str, boundary: dict[str, Any], state_code: str | None, district: str | None
    ) -> VillageRecord:
        """Insert; a Polygon is promoted to a MultiPolygon to match the column."""
        geometry = shape(boundary)
        if isinstance(geometry, Polygon):
            geometry = MultiPolygon([geometry])
        with self._sessions() as session:
            row = models.Village(
                name=name,
                state_code=state_code,
                district=district,
                boundary=from_shape(geometry, srid=4326),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _village(row)

    def get(self, village_id: UUID) -> VillageRecord | None:
        """Fetch by id."""
        with self._sessions() as session:
            row = session.get(models.Village, village_id)
            return None if row is None else _village(row)

    def find_by_boundary(self, boundary: dict[str, Any]) -> VillageRecord | None:
        """PostGIS ST_Equals against the stored boundary."""
        geometry = shape(boundary)
        if isinstance(geometry, Polygon):
            geometry = MultiPolygon([geometry])
        with self._sessions() as session:
            row = session.scalar(
                select(models.Village)
                .where(func.ST_Equals(models.Village.boundary, from_shape(geometry, srid=4326)))
                .order_by(models.Village.created_at.desc())
            )
            return None if row is None else _village(row)

    def list(self, *, limit: int, offset: int, q: str | None) -> tuple[list[VillageRecord], int]:
        """Newest first, with an optional case-insensitive name filter."""
        with self._sessions() as session:
            stmt = select(models.Village)
            if q:
                stmt = stmt.where(models.Village.name.ilike(f"%{q}%"))
            total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            rows = session.scalars(
                stmt.order_by(models.Village.created_at.desc()).limit(limit).offset(offset)
            ).all()
            return [_village(r) for r in rows], int(total)


class SqlJobRepository:
    """Jobs table."""

    def __init__(self, session_factory: SessionFactory) -> None:
        """Bind to a session factory."""
        self._sessions = session_factory

    def create(self, kind: str, params: dict[str, Any], village_id: UUID | None) -> JobRecord:
        """Insert a queued job."""
        with self._sessions() as session:
            row = models.Job(kind=kind, params=params, village_id=village_id, status="queued")
            session.add(row)
            session.commit()
            session.refresh(row)
            return _job(row)

    def get(self, job_id: UUID) -> JobRecord | None:
        """Fetch by id."""
        with self._sessions() as session:
            row = session.get(models.Job, job_id)
            return None if row is None else _job(row)

    def update(self, job_id: UUID, **fields: Any) -> JobRecord:
        """Patch columns by name."""
        with self._sessions() as session:
            row = session.get(models.Job, job_id)
            if row is None:
                msg = "job not found"
                raise NotFoundError(msg, {"job_id": str(job_id)})
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return _job(row)


class SqlDEMAssetRepository:
    """dem_assets table."""

    def __init__(self, session_factory: SessionFactory) -> None:
        """Bind to a session factory."""
        self._sessions = session_factory

    def upsert(self, record: DEMAssetRecord) -> DEMAssetRecord:
        """Insert, or replace the existing row for the village."""
        with self._sessions() as session:
            row = session.scalar(
                select(models.DEMAsset).where(models.DEMAsset.village_id == record.village_id)
            )
            if row is None:
                row = models.DEMAsset(village_id=record.village_id)
                session.add(row)
            for key in (
                "provider",
                "source",
                "native_resolution_m",
                "working_resolution_m",
                "vertical_accuracy_relative_m",
                "vertical_accuracy_absolute_m",
                "epsg",
                "bounds_lonlat",
                "dem_key",
                "hillshade_key",
                "statistics",
                "attribution",
                "acquired",
                "method",
                "details",
            ):
                setattr(row, key, getattr(record, key))
            row.created_at = datetime.now(UTC)
            session.commit()
            session.refresh(row)
            return _asset(row)

    def get_for_village(self, village_id: UUID) -> DEMAssetRecord | None:
        """Fetch by village."""
        with self._sessions() as session:
            row = session.scalar(
                select(models.DEMAsset).where(models.DEMAsset.village_id == village_id)
            )
            return None if row is None else _asset(row)
