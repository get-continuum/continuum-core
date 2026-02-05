from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.overlays import list_overlays, select_overlays_for_context
from app.db.models import MetricLatest, SemanticEvent
from app.utils.json_patch import apply_overlay_patch


def resolve_metric_state(db: Session, workspace_id: str, metric_id: str, context: dict) -> dict:
    latest = db.execute(
        select(MetricLatest).where(
            MetricLatest.workspace_id == workspace_id,
            MetricLatest.metric_id == metric_id,
        )
    ).scalar_one_or_none()
    if latest is None:
        raise KeyError(f"metric_id {metric_id} has no events")

    event = db.execute(
        select(SemanticEvent).where(
            SemanticEvent.workspace_id == workspace_id,
            SemanticEvent.event_id == latest.latest_event_id,
        )
    ).scalar_one()

    base_snapshot = event.snapshot

    overlays = list_overlays(db, workspace_id, metric_id)
    matching = select_overlays_for_context(overlays, context or {})

    resolved = base_snapshot
    applied_overlay_ids: list[str] = []
    for o in matching:
        resolved = apply_overlay_patch(resolved, o.overlay_patch)
        applied_overlay_ids.append(str(o.overlay_id))

    return {
        "metric_id": metric_id,
        "base_version_id": int(event.version_id),
        "applied_overlays": applied_overlay_ids,
        "resolved_snapshot": resolved,
        "provenance": {
            "source_system": event.source_system,
            "source_ref": event.source_ref,
            "timestamp": event.timestamp.isoformat(),
        },
    }

