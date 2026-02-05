from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UsageCreate(BaseModel):
    query_text: str
    context: dict
    team: Optional[str] = None
    interface: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    surface: Optional[str] = None
    auth_type: Optional[str] = None
    input_hash: Optional[str] = None
    candidate_metrics: Optional[list] = None
    resolved_metric_id: Optional[str] = None
    resolved_version_id: Optional[int] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    clarifications_count: Optional[int] = None
    feedback: Optional[str] = None


class UsageOut(BaseModel):
    workspace_id: str
    usage_id: str
    timestamp: str
    query_text: str
    context: dict
    team: Optional[str] = None
    interface: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    surface: Optional[str] = None
    auth_type: Optional[str] = None
    input_hash: Optional[str] = None
    candidate_metrics: list
    resolved_metric_id: Optional[str] = None
    resolved_version_id: Optional[int] = None
    confidence: Optional[float] = None
    clarifications_count: int
    feedback: Optional[str] = None


class CorrectionCreate(BaseModel):
    usage_id: str
    correct_metric_id: str
    note: Optional[str] = None


class CorrectionOut(BaseModel):
    workspace_id: str
    correction_id: str
    usage_id: str
    correct_metric_id: str
    note: Optional[str] = None
    timestamp: str

