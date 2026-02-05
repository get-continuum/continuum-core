from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EventCreate(BaseModel):
    event_type: str
    source_system: str
    source_ref: dict
    reason: Optional[str] = None
    actor: Optional[str] = None
    snapshot: dict


class EventOut(BaseModel):
    workspace_id: str
    event_id: str
    metric_id: str
    version_id: int
    event_type: str
    timestamp: str
    source_system: str
    source_ref: dict
    reason: Optional[str] = None
    actor: Optional[str] = None
    semantic_patch: dict
    snapshot: dict

