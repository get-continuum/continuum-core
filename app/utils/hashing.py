from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass


def _hash_secret() -> bytes:
    """
    Server-side secret used to hash workspace keys before storing them.
    """
    v = os.getenv("ENGRAM_KEY_HASH_SECRET", "").encode("utf-8")
    if not v:
        # Dev-friendly fallback; production should set ENGRAM_KEY_HASH_SECRET.
        v = b"dev-only-not-secure"
    return v


def sha256_hmac_hex(value: str) -> str:
    return hmac.new(_hash_secret(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def sha256_hex(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def random_b64url(nbytes: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).decode("utf-8").rstrip("=")


@dataclass(frozen=True)
class WorkspaceKeyParts:
    env: str  # live|test
    key_id: str
    secret: str


def new_workspace_key(env: str = "live") -> tuple[str, WorkspaceKeyParts]:
    """
    Generates a new workspace key token.

    Format: wk_<env>_<key_id>.<secret>
    Example: wk_live_2f1c3a9b.2YQm... (secret is base64url)
    """
    env = (env or "live").strip().lower()
    if env not in {"live", "test"}:
        env = "live"
    key_id = secrets.token_hex(8)
    secret = random_b64url(32)
    token = f"wk_{env}_{key_id}.{secret}"
    return token, WorkspaceKeyParts(env=env, key_id=key_id, secret=secret)


def parse_workspace_key(token: str) -> WorkspaceKeyParts:
    token = (token or "").strip()
    if not token.startswith("wk_"):
        raise ValueError("not a workspace key")
    try:
        prefix, secret = token.split(".", 1)
        _, env, key_id = prefix.split("_", 2)
    except Exception as e:
        raise ValueError(f"invalid workspace key format: {e}")
    if not env or not key_id or not secret:
        raise ValueError("invalid workspace key parts")
    return WorkspaceKeyParts(env=env, key_id=key_id, secret=secret)


def workspace_key_hash(token: str) -> str:
    """
    Hashes a workspace key token for storage/verification.
    """
    return sha256_hmac_hex(token)

