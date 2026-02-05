from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def json_column():
    # Portable JSON type (JSONB on Postgres).
    return JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"

    workspace_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorkspaceApiKey(Base):
    __tablename__ = "workspace_api_keys"

    key_id: Mapped[str] = mapped_column(Text, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    env: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'live'"))
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    prefix: Mapped[str] = mapped_column(Text, nullable=False)  # safe to display/log
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        Index("ix_workspace_api_keys_workspace_status", "workspace_id", "status"),
    )


class Metric(Base):
    __tablename__ = "metrics"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    metric_id: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (PrimaryKeyConstraint("workspace_id", "metric_id"),)


class MetricAlias(Base):
    __tablename__ = "metric_aliases"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    alias_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    metric_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_system: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str] = mapped_column(Text, nullable=False)
    alias_name: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.5"))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
        UniqueConstraint("workspace_id", "source_system", "source_locator"),
    )


class SemanticEvent(Base):
    __tablename__ = "semantic_events"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    metric_id: Mapped[str] = mapped_column(Text, nullable=False)
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source_system: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[dict] = mapped_column(json_column(), nullable=False, server_default=text("'{}'"))
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    semantic_patch: Mapped[dict] = mapped_column(
        json_column(), nullable=False, server_default=text("'{}'")
    )
    snapshot: Mapped[dict] = mapped_column(json_column(), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
        UniqueConstraint("workspace_id", "metric_id", "version_id"),
        Index(
            "ix_semantic_events_workspace_metric_version_desc",
            "workspace_id",
            "metric_id",
            "version_id",
            postgresql_using="btree",
        ),
        Index(
            "ix_semantic_events_workspace_timestamp_desc",
            "workspace_id",
            "timestamp",
            postgresql_using="btree",
        ),
    )


class MetricLatest(Base):
    __tablename__ = "metric_latest"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    metric_id: Mapped[str] = mapped_column(Text, nullable=False)
    latest_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    latest_event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        PrimaryKeyConstraint("workspace_id", "metric_id"),
        ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
    )


class Overlay(Base):
    __tablename__ = "overlays"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    overlay_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    metric_id: Mapped[str] = mapped_column(Text, nullable=False)
    selector: Mapped[dict] = mapped_column(json_column(), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    overlay_patch: Mapped[dict] = mapped_column(json_column(), nullable=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "metric_id"],
            ["metrics.workspace_id", "metrics.metric_id"],
        ),
        Index("ix_overlays_selector_gin", "selector", postgresql_using="gin"),
        Index(
            "ix_overlays_workspace_metric_priority_created",
            "workspace_id",
            "metric_id",
            "priority",
            "created_at",
        ),
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    usage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    team: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interface: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    surface: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(json_column(), nullable=False, server_default=text("'{}'"))
    candidate_metrics: Mapped[list] = mapped_column(
        json_column(), nullable=False, server_default=text("'[]'")
    )
    resolved_metric_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clarifications_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "usage_id"),
    )


class Correction(Base):
    __tablename__ = "corrections"

    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    correction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    correct_metric_id: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "usage_id"],
            ["usage_events.workspace_id", "usage_events.usage_id"],
        ),
    )

