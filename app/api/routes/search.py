from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, effective_workspace_id, require_auth_context_if_required
from app.core.search import search_metrics
from app.db.session import get_db


router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(..., min_length=1),
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    return {"query": q, "results": search_metrics(db, workspace_id, q, limit=limit)}

