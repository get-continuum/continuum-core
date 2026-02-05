from __future__ import annotations

from pydantic import BaseModel


class ResolveRequest(BaseModel):
    context: dict


class ResolveResponse(BaseModel):
    metric_id: str
    base_version_id: int
    applied_overlays: list[str]
    resolved_snapshot: dict
    provenance: dict

