from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Metric, MetricAlias


def create_metric(
    db: Session,
    workspace_id: str,
    metric_id: str,
    canonical_name: str,
    description: Optional[str],
) -> Metric:
    metric = Metric(
        workspace_id=workspace_id,
        metric_id=metric_id,
        canonical_name=canonical_name,
        description=description,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def get_metric(db: Session, workspace_id: str, metric_id: str) -> Optional[Metric]:
    return db.execute(
        select(Metric).where(Metric.workspace_id == workspace_id, Metric.metric_id == metric_id)
    ).scalar_one_or_none()


def upsert_alias(
    db: Session,
    workspace_id: str,
    metric_id: str,
    source_system: str,
    source_locator: str,
    alias_name: str,
    confidence: Optional[float],
) -> MetricAlias:
    existing = db.execute(
        select(MetricAlias).where(
            MetricAlias.workspace_id == workspace_id,
            MetricAlias.source_system == source_system,
            MetricAlias.source_locator == source_locator,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.metric_id = metric_id
        existing.alias_name = alias_name
        if confidence is not None:
            existing.confidence = confidence
        # last_seen_at is not being auto-updated; keeping MVP minimal.
        db.commit()
        db.refresh(existing)
        return existing

    alias = MetricAlias(
        workspace_id=workspace_id,
        metric_id=metric_id,
        source_system=source_system,
        source_locator=source_locator,
        alias_name=alias_name,
        confidence=confidence if confidence is not None else 0.5,
    )
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias

