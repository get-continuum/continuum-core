"""memory core initial

Revision ID: 0001_memory_core_initial
Revises: 
Create Date: 2026-02-01

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_memory_core_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metrics",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("workspace_id", "metric_id"),
    )

    op.create_table(
        "metric_aliases",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("alias_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("alias_name", sa.Text(), nullable=False),
        sa.Column("confidence", sa.REAL(), server_default=sa.text("0.5"), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("alias_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
        sa.UniqueConstraint("workspace_id", "source_system", "source_locator"),
    )

    op.create_table(
        "semantic_events",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column(
            "source_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column(
            "semantic_patch",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
        sa.UniqueConstraint("workspace_id", "metric_id", "version_id"),
    )

    op.create_index(
        "ix_semantic_events_workspace_metric_version_desc",
        "semantic_events",
        [
            "workspace_id",
            "metric_id",
            sa.text("version_id DESC"),
        ],
    )
    op.create_index(
        "ix_semantic_events_workspace_timestamp_desc",
        "semantic_events",
        [
            "workspace_id",
            sa.text('"timestamp" DESC'),
        ],
    )

    op.create_table(
        "metric_latest",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("latest_version_id", sa.BigInteger(), nullable=False),
        sa.Column("latest_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("workspace_id", "metric_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
    )

    op.create_table(
        "overlays",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("overlay_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column(
            "selector",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "overlay_patch",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("overlay_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
    )

    op.create_index("ix_overlays_selector_gin", "overlays", ["selector"], postgresql_using="gin")
    op.create_index(
        "ix_overlays_workspace_metric_priority_created",
        "overlays",
        ["workspace_id", "metric_id", sa.text("priority DESC"), sa.text("created_at DESC")],
    )

    op.create_table(
        "usage_events",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("usage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("interface", sa.Text(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "candidate_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("resolved_metric_id", sa.Text(), nullable=True),
        sa.Column("resolved_version_id", sa.BigInteger(), nullable=True),
        sa.Column("confidence", sa.REAL(), nullable=True),
        sa.Column(
            "clarifications_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("usage_id"),
        sa.UniqueConstraint("workspace_id", "usage_id"),
    )

    op.create_table(
        "corrections",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("correction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correct_metric_id", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("correction_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "usage_id"],
            ["usage_events.workspace_id", "usage_events.usage_id"],
        ),
    )


def downgrade() -> None:
    op.drop_table("corrections")
    op.drop_table("usage_events")
    op.drop_index("ix_overlays_workspace_metric_priority_created", table_name="overlays")
    op.drop_index("ix_overlays_selector_gin", table_name="overlays")
    op.drop_table("overlays")
    op.drop_table("metric_latest")
    op.drop_index("ix_semantic_events_workspace_timestamp_desc", table_name="semantic_events")
    op.drop_index("ix_semantic_events_workspace_metric_version_desc", table_name="semantic_events")
    op.drop_table("semantic_events")
    op.drop_table("metric_aliases")
    op.drop_table("metrics")

