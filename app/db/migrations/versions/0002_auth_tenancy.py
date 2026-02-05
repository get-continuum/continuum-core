"""auth + tenancy

Revision ID: 0002_auth_tenancy
Revises: 0001_memory_core_initial
Create Date: 2026-02-05

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_auth_tenancy"
down_revision = "0001_memory_core_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "workspace_api_keys",
        sa.Column("key_id", sa.Text(), primary_key=True),
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("env", sa.Text(), server_default=sa.text("'live'"), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
    )
    op.create_index(
        "ix_workspace_api_keys_workspace_status",
        "workspace_api_keys",
        ["workspace_id", "status"],
    )

    # Extend usage_events for audit metadata.
    op.add_column("usage_events", sa.Column("user_id", sa.Text(), nullable=True))
    op.add_column("usage_events", sa.Column("agent_id", sa.Text(), nullable=True))
    op.add_column("usage_events", sa.Column("surface", sa.Text(), nullable=True))
    op.add_column("usage_events", sa.Column("auth_type", sa.Text(), nullable=True))
    op.add_column("usage_events", sa.Column("input_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("usage_events", "input_hash")
    op.drop_column("usage_events", "auth_type")
    op.drop_column("usage_events", "surface")
    op.drop_column("usage_events", "agent_id")
    op.drop_column("usage_events", "user_id")

    op.drop_index("ix_workspace_api_keys_workspace_status", table_name="workspace_api_keys")
    op.drop_table("workspace_api_keys")
    op.drop_table("workspaces")

