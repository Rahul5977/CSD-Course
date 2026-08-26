"""P6: idempotency keys on jobs, recommendations, outbox.

Revision ID: 0003_hardening
Revises: 0002_dem_assets
Create Date: 2026-08-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_hardening"
down_revision = "0002_dem_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("idempotency_key", sa.String(128)))
    op.create_index("ux_jobs_idempotency_key", "jobs", ["idempotency_key"], unique=True)

    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "village_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("villages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("village_name", sa.String(128), nullable=False),
        sa.Column("design_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("catchment_area_ha", sa.Float(), nullable=False),
        sa.Column("gross_storage_m3", sa.Float(), nullable=False),
        sa.Column("depth_m", sa.Float(), nullable=False),
        sa.Column("indicative_cost_inr", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft','submitted','approved','rejected')",
            name="ck_recommendations_status",
        ),
    )
    op.create_index("ix_recommendations_village", "recommendations", ["village_id"])

    # Transactional outbox: written in the same transaction as the state change,
    # drained by the beat task into the append-only audit_log.
    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_outbox_pending", "outbox", ["processed_at", "created_at"])


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("recommendations")
    op.drop_index("ux_jobs_idempotency_key", table_name="jobs")
    op.drop_column("jobs", "idempotency_key")
