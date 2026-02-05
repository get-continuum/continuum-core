from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class OverlayCreate(BaseModel):
    selector: dict
    priority: Optional[int] = None
    overlay_patch: dict
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    author: Optional[str] = None
    reason: Optional[str] = None


class OverlayOut(BaseModel):
    workspace_id: str
    overlay_id: str
    metric_id: str
    selector: dict
    priority: int
    overlay_patch: dict
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    author: Optional[str] = None
    reason: Optional[str] = None
    created_at: str

