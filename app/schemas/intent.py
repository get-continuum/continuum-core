from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IntentResolveRequest(BaseModel):
    query: str
    context: Dict[str, Any] = Field(default_factory=dict)


class IntentResolvedMetric(BaseModel):
    metric_id: str
    description: str
    model: str
    measure_name: str
    domain: str


class IntentResolveResponse(BaseModel):
    status: str  # resolved|ambiguous|no_match|error
    resolved_metric: Optional[IntentResolvedMetric] = None
    candidates: Optional[List[IntentResolvedMetric]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

