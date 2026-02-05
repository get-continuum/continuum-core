from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, effective_workspace_id, require_auth_context_if_required
from app.core.identity import get_metric
from app.core.resolver import resolve_metric_state
from app.core.usage import log_usage
from app.db.session import get_db
from app.schemas.resolve import ResolveRequest, ResolveResponse
from app.utils.hashing import sha256_hex


router = APIRouter(prefix="/metrics/{metric_id}", tags=["resolve"])


@router.post("/resolve", response_model=ResolveResponse)
def resolve(
    metric_id: str,
    body: ResolveRequest,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    metric = get_metric(db, workspace_id, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="metric not found")

    try:
        result = resolve_metric_state(db, workspace_id, metric_id, body.context or {})
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Best-effort audit logging.
    try:
        input_hash = sha256_hex(
            json.dumps(
                {"endpoint": "resolve_contract", "metric_id": metric_id, "context": body.context or {}},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        surface = ctx.surface if ctx else None
        user_id = ctx.user_id if ctx else None
        agent_id = ctx.agent_id if ctx else None
        auth_type = ctx.auth_type if ctx else None
        team = (body.context or {}).get("team")
        log_usage(
            db=db,
            workspace_id=workspace_id,
            query_text=f"resolve:{metric_id}",
            context=body.context or {},
            team=team,
            interface=surface or "api",
            user_id=user_id,
            agent_id=agent_id,
            surface=surface,
            auth_type=auth_type,
            input_hash=input_hash,
            candidate_metrics=[],
            resolved_metric_id=metric_id,
            resolved_version_id=int(result.get("base_version_id") or 0) or None,
            confidence=None,
            clarifications_count=0,
            feedback=None,
        )
    except Exception:
        pass

    return ResolveResponse(**result)
