from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthContext,
    effective_workspace_id,
    require_auth_context_if_required,
    require_workspace_key_if_required,
)
from app.core.events import append_event, get_history
from app.core.identity import get_metric
from app.db.session import get_db
from app.schemas.events import EventCreate, EventOut


router = APIRouter(prefix="/metrics/{metric_id}", tags=["events"])


@router.post("/events", response_model=EventOut)
def post_event(
    metric_id: str,
    body: EventCreate,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_workspace_key_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    metric = get_metric(db, workspace_id, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="metric not found")

    # Enforce minimal snapshot shape: must include definition.logic object.
    snap = body.snapshot or {}
    if "definition" not in snap or not isinstance(snap.get("definition"), dict):
        raise HTTPException(status_code=400, detail="snapshot.definition required")
    logic = snap["definition"].get("logic")
    if not isinstance(logic, dict):
        raise HTTPException(status_code=400, detail="snapshot.definition.logic required")

    event = append_event(
        db=db,
        workspace_id=workspace_id,
        metric_id=metric_id,
        event_type=body.event_type,
        source_system=body.source_system,
        source_ref=body.source_ref or {},
        reason=body.reason,
        actor=body.actor,
        snapshot=snap,
    )

    return EventOut(
        workspace_id=event.workspace_id,
        event_id=str(event.event_id),
        metric_id=event.metric_id,
        version_id=int(event.version_id),
        event_type=event.event_type,
        timestamp=event.timestamp.isoformat(),
        source_system=event.source_system,
        source_ref=event.source_ref,
        reason=event.reason,
        actor=event.actor,
        semantic_patch=event.semantic_patch,
        snapshot=event.snapshot,
    )


@router.get("/history")
def get_history_route(
    metric_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    metric = get_metric(db, workspace_id, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="metric not found")

    events = get_history(db, workspace_id, metric_id, limit=limit)
    return [
        {
            "workspace_id": e.workspace_id,
            "event_id": str(e.event_id),
            "metric_id": e.metric_id,
            "version_id": int(e.version_id),
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "source_system": e.source_system,
            "source_ref": e.source_ref,
            "reason": e.reason,
            "actor": e.actor,
            "semantic_patch": e.semantic_patch,
            "snapshot": e.snapshot,
        }
        for e in events
    ]

