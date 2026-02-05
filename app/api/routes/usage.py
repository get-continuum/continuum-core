from __future__ import annotations

import uuid

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, effective_workspace_id, require_auth_context_if_required
from app.core.usage import log_correction, log_usage
from app.db.session import get_db
from app.schemas.usage import CorrectionCreate, CorrectionOut, UsageCreate, UsageOut


router = APIRouter(tags=["usage"])


@router.post("/usage", response_model=UsageOut)
def post_usage(
    body: UsageCreate,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    usage = log_usage(
        db=db,
        workspace_id=workspace_id,
        query_text=body.query_text,
        context=body.context or {},
        team=body.team,
        interface=body.interface,
        user_id=body.user_id or (ctx.user_id if ctx else None),
        agent_id=body.agent_id or (ctx.agent_id if ctx else None),
        surface=body.surface or (ctx.surface if ctx else None),
        auth_type=body.auth_type or (ctx.auth_type if ctx else None),
        input_hash=body.input_hash,
        candidate_metrics=body.candidate_metrics,
        resolved_metric_id=body.resolved_metric_id,
        resolved_version_id=body.resolved_version_id,
        confidence=body.confidence,
        clarifications_count=body.clarifications_count,
        feedback=body.feedback,
    )
    return UsageOut(
        workspace_id=usage.workspace_id,
        usage_id=str(usage.usage_id),
        timestamp=usage.timestamp.isoformat(),
        query_text=usage.query_text,
        context=usage.context,
        team=usage.team,
        interface=usage.interface,
        user_id=usage.user_id,
        agent_id=usage.agent_id,
        surface=usage.surface,
        auth_type=usage.auth_type,
        input_hash=usage.input_hash,
        candidate_metrics=usage.candidate_metrics,
        resolved_metric_id=usage.resolved_metric_id,
        resolved_version_id=int(usage.resolved_version_id) if usage.resolved_version_id else None,
        confidence=float(usage.confidence) if usage.confidence is not None else None,
        clarifications_count=int(usage.clarifications_count),
        feedback=usage.feedback,
    )


@router.post("/corrections", response_model=CorrectionOut)
def post_correction(
    body: CorrectionCreate,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    try:
        usage_id = uuid.UUID(body.usage_id)
    except Exception:
        raise HTTPException(status_code=400, detail="usage_id must be uuid")

    c = log_correction(
        db=db,
        workspace_id=workspace_id,
        usage_id=usage_id,
        correct_metric_id=body.correct_metric_id,
        note=body.note,
    )
    return CorrectionOut(
        workspace_id=c.workspace_id,
        correction_id=str(c.correction_id),
        usage_id=str(c.usage_id),
        correct_metric_id=c.correct_metric_id,
        note=c.note,
        timestamp=c.timestamp.isoformat(),
    )

