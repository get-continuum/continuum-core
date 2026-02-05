from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, mint_user_jwt, require_auth_context, require_workspace_key
from app.db.models import Workspace, WorkspaceApiKey
from app.db.session import get_db
from app.schemas.auth import (
    MintTokenRequest,
    MintTokenResponse,
    WhoAmIResponse,
    WorkspaceCreate,
    WorkspaceKeyCreate,
    WorkspaceKeyOut,
    WorkspaceOut,
)
from app.utils.hashing import new_workspace_key, workspace_key_hash


router = APIRouter(prefix="/auth", tags=["auth"])


def _bootstrap_allowed(x_bootstrap_token: Optional[str]) -> bool:
    """
    MVP bootstrap: if ENGRAM_BOOTSTRAP_TOKEN is set, require it.
    If not set, allow (dev mode).
    """
    required = os.getenv("ENGRAM_BOOTSTRAP_TOKEN", "").strip()
    if not required:
        return True
    return (x_bootstrap_token or "").strip() == required


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(
    body: WorkspaceCreate,
    x_bootstrap_token: Optional[str] = Header(default=None, alias="X-Bootstrap-Token"),
    db: Session = Depends(get_db),
):
    if not _bootstrap_allowed(x_bootstrap_token):
        raise HTTPException(status_code=403, detail="bootstrap token required")

    ws_id = str(uuid.uuid4())
    ws = Workspace(workspace_id=ws_id, name=body.name)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return WorkspaceOut(
        workspace_id=ws.workspace_id,
        name=ws.name,
        created_at=ws.created_at.isoformat(),
    )


@router.post("/workspaces/{workspace_id}/keys", response_model=WorkspaceKeyOut)
def create_workspace_key(
    workspace_id: str,
    body: WorkspaceKeyCreate,
    x_bootstrap_token: Optional[str] = Header(default=None, alias="X-Bootstrap-Token"),
    db: Session = Depends(get_db),
):
    # MVP bootstrap: require bootstrap token to create keys.
    if not _bootstrap_allowed(x_bootstrap_token):
        raise HTTPException(status_code=403, detail="bootstrap token required")

    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    token, parts = new_workspace_key(env=body.env)
    prefix = token.split(".", 1)[0]

    rec = WorkspaceApiKey(
        key_id=parts.key_id,
        workspace_id=workspace_id,
        env=parts.env,
        key_hash=workspace_key_hash(token),
        prefix=prefix,
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    return WorkspaceKeyOut(
        workspace_id=workspace_id,
        key_id=rec.key_id,
        env=rec.env,
        prefix=rec.prefix,
        status=rec.status,
        created_at=rec.created_at.isoformat(),
        token=token,
    )


@router.post("/token", response_model=MintTokenResponse)
def mint_token(
    body: MintTokenRequest,
    ctx: AuthContext = Depends(require_workspace_key),
):
    token = mint_user_jwt(
        workspace_id=ctx.workspace_id,
        user_id=body.user_id,
        roles=body.roles,
        scopes=body.scopes,
        agent_id=body.agent_id,
        surface=body.surface,
        ttl_seconds=body.ttl_seconds,
    )
    return MintTokenResponse(token=token, expires_in=body.ttl_seconds)


@router.get("/whoami", response_model=WhoAmIResponse)
def whoami(ctx: AuthContext = Depends(require_auth_context)):
    return WhoAmIResponse(
        workspace_id=ctx.workspace_id,
        auth_type=ctx.auth_type,
        user_id=ctx.user_id,
        roles=ctx.roles or [],
        scopes=ctx.scopes or [],
        agent_id=ctx.agent_id,
        surface=ctx.surface,
    )

