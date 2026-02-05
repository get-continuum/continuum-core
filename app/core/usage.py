from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Correction, UsageEvent


def log_usage(
    db: Session,
    workspace_id: str,
    query_text: str,
    context: dict,
    team: Optional[str],
    interface: Optional[str],
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    surface: Optional[str] = None,
    auth_type: Optional[str] = None,
    input_hash: Optional[str] = None,
    candidate_metrics: Optional[list] = None,
    resolved_metric_id: Optional[str] = None,
    resolved_version_id: Optional[int] = None,
    confidence: Optional[float] = None,
    clarifications_count: Optional[int] = None,
    feedback: Optional[str] = None,
) -> UsageEvent:
    usage = UsageEvent(
        workspace_id=workspace_id,
        query_text=query_text,
        context=context or {},
        team=team,
        interface=interface,
        user_id=user_id,
        agent_id=agent_id,
        surface=surface,
        auth_type=auth_type,
        input_hash=input_hash,
        candidate_metrics=candidate_metrics or [],
        resolved_metric_id=resolved_metric_id,
        resolved_version_id=resolved_version_id,
        confidence=confidence,
        clarifications_count=clarifications_count if clarifications_count is not None else 0,
        feedback=feedback,
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def log_correction(
    db: Session,
    workspace_id: str,
    usage_id: uuid.UUID,
    correct_metric_id: str,
    note: Optional[str],
) -> Correction:
    c = Correction(
        workspace_id=workspace_id,
        usage_id=usage_id,
        correct_metric_id=correct_metric_id,
        note=note,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

