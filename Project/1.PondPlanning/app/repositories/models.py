"""SQLAlchemy ORM models for the first migration.

P0 created the analysis subject (``villages``), the async work record (``jobs``)
and the tamper-evident trail (``audit_log``). P1 adds ``dem_assets`` and a
``stage`` column on jobs. Rainfall and recommendation tables arrive with the
phases that need them, each behind its own Alembic revision.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


class Village(Base):
    """An analysis subject: a named settlement with an administrative boundary.

    Geometry is stored in EPSG:4326 because that is the interchange CRS for
    GeoJSON and the map client. Every *computation* reprojects to the UTM zone
    derived from the geometry's own centroid — areas and distances are never
    measured in degrees. ``app.core.geo.assert_crs`` (P1) enforces that.
    """

    __tablename__ = "villages"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    state_code: Mapped[str | None] = mapped_column(String(8))
    district: Mapped[str | None] = mapped_column(String(128))
    # MultiPolygon, not Polygon: real village boundaries include exclaves.
    boundary: Mapped[object] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_villages_name", "name"),)


class Job(Base):
    """One asynchronous analysis run.

    Analysis routes return ``202`` plus this row's id; the client polls it. The
    payload/result columns are JSON rather than typed columns so that a new
    analysis kind does not require a migration.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(default=0)
    # Human-readable pipeline stage ("filling sinks"); a percentage alone is
    # uninformative during a 25-second pipeline.
    stage: Mapped[str | None] = mapped_column(String(128))
    # Client-supplied key so a double-tap enqueues one job, not two (P6).
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    village_id: Mapped[uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("villages.id", ondelete="SET NULL")
    )
    params: Mapped[dict[str, object] | None] = mapped_column(JSON)
    result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Mirrored in migration 0001. The job lifecycle is enforced in the database
    # as well as in the code: a worker crash must not be able to leave a row in
    # a status the polling route cannot interpret.
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="ck_jobs_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_jobs_progress"),
        Index("ix_jobs_status_created", "status", "created_at"),
    )


class AuditLog(Base):
    """Append-only record of every recommendation and status change.

    Required by G6. Append-only by convention *and* by grant: the application
    role gets INSERT and SELECT on this table but not UPDATE or DELETE, so the
    trail cannot be rewritten by the code that writes it.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


class DEMAsset(Base):
    """Provenance and storage keys of the working DEM for one village.

    One row per village (the latest analysis wins). Everything an evaluator
    needs to judge the honesty of a terrain number — source, native and working
    resolution, vertical accuracy — is a column here, not a log line.
    """

    __tablename__ = "dem_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    village_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("villages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    native_resolution_m: Mapped[float] = mapped_column(Float, nullable=False)
    working_resolution_m: Mapped[float] = mapped_column(Float, nullable=False)
    vertical_accuracy_relative_m: Mapped[float] = mapped_column(Float, nullable=False)
    vertical_accuracy_absolute_m: Mapped[float] = mapped_column(Float, nullable=False)
    epsg: Mapped[int] = mapped_column(Integer, nullable=False)
    bounds_lonlat: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    dem_key: Mapped[str] = mapped_column(String(256), nullable=False)
    hillshade_key: Mapped[str | None] = mapped_column(String(256))
    statistics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    attribution: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    acquired: Mapped[str | None] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(256), nullable=False)
    details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Recommendation(Base):
    """A saved pond recommendation with its lifecycle state (draft → submitted → approved)."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    village_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), ForeignKey("villages.id", ondelete="CASCADE"), nullable=False
    )
    village_name: Mapped[str] = mapped_column(String(128), nullable=False)
    design_job_id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    catchment_area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    gross_storage_m3: Mapped[float] = mapped_column(Float, nullable=False)
    depth_m: Mapped[float] = mapped_column(Float, nullable=False)
    indicative_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','submitted','approved','rejected')",
            name="ck_recommendations_status",
        ),
        Index("ix_recommendations_village", "village_id"),
    )


class Outbox(Base):
    """Transactional outbox: events written with the change, drained to the audit log."""

    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_outbox_pending", "processed_at", "created_at"),)
