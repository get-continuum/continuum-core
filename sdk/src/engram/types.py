from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

class Metric(BaseModel):
    metric_id: str
    canonical_name: str
    description: Optional[str] = None
    status: str = "active"

class MetricLatest(BaseModel):
    latest_version_id: int
    latest_event_id: str
    updated_at: str


class MetricGetOut(BaseModel):
    metric: Metric
    latest: Optional[MetricLatest] = None


class ResolutionRequest(BaseModel):
    query: str
    context: Dict[str, Any] = Field(default_factory=dict)

class ResolvedMetric(BaseModel):
    metric_id: str
    description: str
    model: str
    measure_name: str
    domain: str

class ResolutionResponse(BaseModel):
    status: str
    resolved_metric: Optional[ResolvedMetric] = None
    candidates: Optional[List[ResolvedMetric]] = None
    confidence: float
    reason: str


class ResolveStateRequest(BaseModel):
    context: Dict[str, Any] = Field(default_factory=dict)


class ResolveStateResponse(BaseModel):
    metric_id: str
    base_version_id: int
    applied_overlays: List[str]
    resolved_snapshot: Dict[str, Any]
    provenance: Dict[str, Any]


class MintTokenRequest(BaseModel):
    user_id: str
    roles: List[str] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)
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
    roles: List[str] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)
    agent_id: Optional[str] = None
    surface: Optional[str] = None
