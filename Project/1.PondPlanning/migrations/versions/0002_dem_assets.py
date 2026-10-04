"""P1: dem_assets table and jobs.stage.

Revision ID: 0002_dem_assets
Revises: 0001_initial
Create Date: 2026-08-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_dem_assets"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("stage", sa.String(128)))

    op.create_table(
        "dem_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "village_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("villages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("source", sa.String(256), nullable=False),
        sa.Column("native_resolution_m", sa.Float(), nullable=False),
        sa.Column("working_resolution_m", sa.Float(), nullable=False),
        sa.Column("vertical_accuracy_relative_m", sa.Float(), nullable=False),
        sa.Column("vertical_accuracy_absolute_m", sa.Float(), nullable=False),
        sa.Column("epsg", sa.Integer(), nullable=False),
        sa.Column("bounds_lonlat", sa.JSON(), nullable=False),
        sa.Column("dem_key", sa.String(256), nullable=False),
        sa.Column("hillshade_key", sa.String(256)),
        sa.Column("statistics", sa.JSON(), nullable=False),
        sa.Column("attribution", sa.JSON(), nullable=False),
        sa.Column("acquired", sa.String(64)),
        sa.Column("method", sa.String(256), nullable=False),
        sa.Column("details", sa.JSON()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("dem_assets")
    op.drop_column("jobs", "stage")
