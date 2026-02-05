from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: Optional[str] = None


class WorkspaceOut(BaseModel):
    workspace_id: str
    name: Optional[str] = None
    created_at: str


class WorkspaceKeyCreate(BaseModel):
    env: str = Field(default="live", pattern="^(live|test)$")


class WorkspaceKeyOut(BaseModel):
    workspace_id: str
    key_id: str
    env: str
    prefix: str
    status: str
    created_at: str
    # Only returned at creation time:
    token: Optional[str] = None


class MintTokenRequest(BaseModel):
    user_id: str
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    agent_id: Optional[str] = None
    surface: Optional[str] = None
    ttl_seconds: int = Field(default=1800, ge=60, le=60 * 60 * 24)


class MintTokenResponse(BaseModel):
    token: str
    expires_in: int


class WhoAmIResponse(BaseModel):
    workspace_id: str
    auth_type: str
    user_id: Optional[str] = None
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    agent_id: Optional[str] = None
    surface: Optional[str] = None

