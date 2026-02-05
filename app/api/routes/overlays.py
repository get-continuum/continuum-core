from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthContext,
    effective_workspace_id,
    require_auth_context_if_required,
    require_workspace_key_if_required,
)
from app.core.identity import get_metric
from app.core.overlays import create_overlay, list_overlays
from app.db.session import get_db
from app.schemas.overlays import OverlayCreate, OverlayOut


router = APIRouter(prefix="/metrics/{metric_id}", tags=["overlays"])


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    return datetime.fromisoformat(s)


@router.post("/overlays", response_model=OverlayOut)
def post_overlay(
    metric_id: str,
    body: OverlayCreate,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_workspace_key_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    metric = get_metric(db, workspace_id, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="metric not found")

    overlay = create_overlay(
        db=db,
        workspace_id=workspace_id,
        metric_id=metric_id,
        selector=body.selector or {},
        priority=body.priority if body.priority is not None else 0,
        overlay_patch=body.overlay_patch or {},
        valid_from=_parse_dt(body.valid_from),
        valid_to=_parse_dt(body.valid_to),
        author=body.author,
        reason=body.reason,
    )

    return OverlayOut(
        workspace_id=overlay.workspace_id,
        overlay_id=str(overlay.overlay_id),
        metric_id=overlay.metric_id,
        selector=overlay.selector,
        priority=int(overlay.priority),
        overlay_patch=overlay.overlay_patch,
        valid_from=overlay.valid_from.isoformat() if overlay.valid_from else None,
        valid_to=overlay.valid_to.isoformat() if overlay.valid_to else None,
        author=overlay.author,
        reason=overlay.reason,
        created_at=overlay.created_at.isoformat(),
    )


@router.get("/overlays")
def get_overlays(
    metric_id: str,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    metric = get_metric(db, workspace_id, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="metric not found")

    overlays = list_overlays(db, workspace_id, metric_id)
    return [
        {
            "workspace_id": o.workspace_id,
            "overlay_id": str(o.overlay_id),
            "metric_id": o.metric_id,
            "selector": o.selector,
            "priority": int(o.priority),
            "overlay_patch": o.overlay_patch,
            "valid_from": o.valid_from.isoformat() if o.valid_from else None,
            "valid_to": o.valid_to.isoformat() if o.valid_to else None,
            "author": o.author,
            "reason": o.reason,
            "created_at": o.created_at.isoformat(),
        }
        for o in overlays
    ]

