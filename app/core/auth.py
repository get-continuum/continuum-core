from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WorkspaceApiKey
from app.db.session import get_db
from app.utils.hashing import parse_workspace_key, workspace_key_hash


@dataclass(frozen=True)
class AuthContext:
    workspace_id: str
    auth_type: str  # workspace_key|user_token
    # workspace key metadata
    key_id: Optional[str] = None
    # user token claims
    user_id: Optional[str] = None
    roles: Optional[list[str]] = None
    scopes: Optional[list[str]] = None
    agent_id: Optional[str] = None
    surface: Optional[str] = None


def _auth_required() -> bool:
    return os.getenv("ENGRAM_AUTH_REQUIRED", "").strip().lower() in {"1", "true", "yes"}


def _jwt_secret() -> str:
    v = os.getenv("ENGRAM_JWT_SECRET", "").strip()
    if not v:
        # Dev-friendly fallback; production MUST set ENGRAM_JWT_SECRET.
        v = "dev-only-not-secure"
    return v


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _jwt_sign(unsigned: str, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), unsigned.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def mint_user_jwt(
    *,
    workspace_id: str,
    user_id: str,
    roles: Optional[list[str]] = None,
    scopes: Optional[list[str]] = None,
    agent_id: Optional[str] = None,
    surface: Optional[str] = None,
    ttl_seconds: int = 1800,
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": os.getenv("ENGRAM_JWT_ISSUER", "continuum"),
        "iat": now,
        "exp": now + int(ttl_seconds),
        "workspace_id": workspace_id,
        "sub": user_id,
        "roles": roles or [],
        "scopes": scopes or [],
    }
    if agent_id:
        payload["agent_id"] = agent_id
    if surface:
        payload["surface"] = surface

    h = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    unsigned = f"{h}.{p}"
    sig = _jwt_sign(unsigned, _jwt_secret())
    return f"{unsigned}.{sig}"


def verify_user_jwt(token: str) -> dict:
    try:
        h, p, s = token.split(".", 2)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    unsigned = f"{h}.{p}"
    expected = _jwt_sign(unsigned, _jwt_secret())
    if not hmac.compare_digest(expected, s):
        raise HTTPException(status_code=401, detail="invalid token signature")
    try:
        payload = json.loads(_b64url_decode(p))
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token payload")
    exp = int(payload.get("exp") or 0)
    if exp and int(time.time()) > exp:
        raise HTTPException(status_code=401, detail="token expired")
    return payload


def _bearer_token(request: Request) -> Optional[str]:
    h = request.headers.get("Authorization") or ""
    if not h:
        return None
    if not h.lower().startswith("bearer "):
        return None
    return h[7:].strip()


def _validate_workspace_key(db: Session, token: str) -> AuthContext:
    try:
        parts = parse_workspace_key(token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid workspace key")
    row = db.execute(select(WorkspaceApiKey).where(WorkspaceApiKey.key_id == parts.key_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="invalid workspace key")
    if (row.status or "").lower() != "active":
        raise HTTPException(status_code=401, detail="workspace key revoked")
    if not hmac.compare_digest(row.key_hash, workspace_key_hash(token)):
        raise HTTPException(status_code=401, detail="invalid workspace key")
    return AuthContext(workspace_id=row.workspace_id, auth_type="workspace_key", key_id=row.key_id)


def _validate_user_token(token: str) -> AuthContext:
    payload = verify_user_jwt(token)
    ws = payload.get("workspace_id")
    sub = payload.get("sub")
    if not ws or not sub:
        raise HTTPException(status_code=401, detail="invalid token claims")
    return AuthContext(
        workspace_id=str(ws),
        auth_type="user_token",
        user_id=str(sub),
        roles=list(payload.get("roles") or []),
        scopes=list(payload.get("scopes") or []),
        agent_id=payload.get("agent_id"),
        surface=payload.get("surface"),
    )


def get_auth_context_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[AuthContext]:
    token = _bearer_token(request)
    if not token:
        return None
    if token.startswith("wk_"):
        return _validate_workspace_key(db, token)
    # treat everything else as user JWT for MVP
    return _validate_user_token(token)


def require_auth_context(
    ctx: Optional[AuthContext] = Depends(get_auth_context_optional),
) -> AuthContext:
    if ctx is None:
        raise HTTPException(status_code=401, detail="missing authorization")
    return ctx


def require_workspace_key(
    ctx: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    if ctx.auth_type != "workspace_key":
        raise HTTPException(status_code=403, detail="workspace key required")
    return ctx


def require_auth_context_if_required(
    ctx: Optional[AuthContext] = Depends(get_auth_context_optional),
) -> Optional[AuthContext]:
    """
    Convenience dependency: enforce auth only when ENGRAM_AUTH_REQUIRED=1.
    """
    if _auth_required() and ctx is None:
        raise HTTPException(status_code=401, detail="missing authorization")
    return ctx


def require_workspace_key_if_required(
    ctx: Optional[AuthContext] = Depends(get_auth_context_optional),
) -> Optional[AuthContext]:
    """
    Convenience dependency: enforce workspace key only when ENGRAM_AUTH_REQUIRED=1.
    This keeps local demos usable by default, while making production safe when enabled.
    """
    if not _auth_required():
        return ctx
    if ctx is None:
        raise HTTPException(status_code=401, detail="missing authorization")
    if ctx.auth_type != "workspace_key":
        raise HTTPException(status_code=403, detail="workspace key required")
    return ctx


def effective_workspace_id(workspace_id_query: str, ctx: Optional[AuthContext]) -> str:
    """
    Backward-compatible: prefer auth-derived workspace_id when present.
    """
    if ctx is not None:
        return ctx.workspace_id
    if _auth_required():
        raise HTTPException(status_code=401, detail="missing authorization")
    return workspace_id_query

