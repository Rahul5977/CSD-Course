"""SQLAlchemy ORM models for the first migration.

Three tables only, matching P0's scope: the analysis subject (``villages``),
the async work record (``jobs``) and the tamper-evident trail (``audit_log``).
Terrain, rainfall and recommendation tables arrive with the phases that need
them, each behind its own Alembic revision.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
