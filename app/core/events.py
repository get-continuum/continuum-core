from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import MetricLatest, SemanticEvent


def get_latest_version_id(db: Session, workspace_id: str, metric_id: str) -> int:
    latest = db.execute(
        select(MetricLatest).where(
            MetricLatest.workspace_id == workspace_id,
            MetricLatest.metric_id == metric_id,
        )
    ).scalar_one_or_none()
    return int(latest.latest_version_id) if latest else 0


def append_event(
    db: Session,
    workspace_id: str,
    metric_id: str,
    event_type: str,
    source_system: str,
    source_ref: dict,
    reason: Optional[str],
    actor: Optional[str],
    snapshot: dict,
) -> SemanticEvent:
    # Append-only: compute next version id from MetricLatest.
    latest_version = get_latest_version_id(db, workspace_id, metric_id)
    next_version = latest_version + 1

    event = SemanticEvent(
        workspace_id=workspace_id,
        metric_id=metric_id,
        version_id=next_version,
        event_type=event_type,
        source_system=source_system,
        source_ref=source_ref or {},
        reason=reason,
        actor=actor,
        semantic_patch={},
        snapshot=snapshot,
    )
    db.add(event)
    db.flush()  # get event_id

    # Upsert metric_latest pointer.
    latest = db.execute(
        select(MetricLatest).where(
            MetricLatest.workspace_id == workspace_id,
            MetricLatest.metric_id == metric_id,
        )
    ).scalar_one_or_none()
    if latest is None:
        latest = MetricLatest(
            workspace_id=workspace_id,
            metric_id=metric_id,
            latest_version_id=next_version,
            latest_event_id=event.event_id,
        )
        db.add(latest)
    else:
        latest.latest_version_id = next_version
        latest.latest_event_id = event.event_id

    db.commit()
    db.refresh(event)
    return event


def get_history(db: Session, workspace_id: str, metric_id: str, limit: int = 50) -> list[SemanticEvent]:
    rows = db.execute(
        select(SemanticEvent)
        .where(SemanticEvent.workspace_id == workspace_id, SemanticEvent.metric_id == metric_id)
        .order_by(desc(SemanticEvent.version_id))
        .limit(limit)
    ).scalars()
    return list(rows)


def get_event_by_id(db: Session, workspace_id: str, event_id: uuid.UUID) -> Optional[SemanticEvent]:
    return db.execute(
        select(SemanticEvent).where(
            SemanticEvent.workspace_id == workspace_id,
            SemanticEvent.event_id == event_id,
        )
    ).scalar_one_or_none()

