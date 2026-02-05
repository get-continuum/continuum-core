from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MetricCreate(BaseModel):
    metric_id: str
    canonical_name: str
    description: Optional[str] = None


class MetricOut(BaseModel):
    workspace_id: str
    metric_id: str
    canonical_name: str
    description: Optional[str] = None
    status: str


class MetricGetOut(BaseModel):
    metric: MetricOut
    latest: Optional[dict] = None  # {latest_version_id, latest_event_id, updated_at}


class AliasCreate(BaseModel):
    source_system: str
    source_locator: str
    alias_name: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AliasOut(BaseModel):
    workspace_id: str
    alias_id: str
    metric_id: str
    source_system: str
    source_locator: str
    alias_name: str
    confidence: float

