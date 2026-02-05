from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthContext,
    effective_workspace_id,
    require_auth_context_if_required,
    require_workspace_key_if_required,
)
from app.core.usage import log_usage
from app.core.identity import create_metric, get_metric, upsert_alias
from app.db.models import MetricLatest
from app.db.session import get_db
from app.schemas.metric import AliasCreate, AliasOut, MetricCreate, MetricGetOut, MetricOut
from sqlalchemy import select

from app.db.models import Metric, MetricAlias
from app.schemas.intent import IntentResolveRequest, IntentResolveResponse, IntentResolvedMetric
from app.utils.hashing import sha256_hex


router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.post("", response_model=MetricOut)
def post_metric(
    body: MetricCreate,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_workspace_key_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    try:
        metric = create_metric(
            db=db,
            workspace_id=workspace_id,
            metric_id=body.metric_id,
            canonical_name=body.canonical_name,
            description=body.description,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MetricOut(
        workspace_id=metric.workspace_id,
        metric_id=metric.metric_id,
        canonical_name=metric.canonical_name,
        description=metric.description,
        status=metric.status,
    )


@router.get("/{metric_id}", response_model=MetricGetOut)
def get_metric_route(
    metric_id: str,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    metric = get_metric(db, workspace_id, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="metric not found")

    latest = db.get(MetricLatest, {"workspace_id": workspace_id, "metric_id": metric_id})
    latest_out = (
        {
            "latest_version_id": int(latest.latest_version_id),
            "latest_event_id": str(latest.latest_event_id),
            "updated_at": latest.updated_at.isoformat(),
        }
        if latest
        else None
    )

    return MetricGetOut(
        metric=MetricOut(
            workspace_id=metric.workspace_id,
            metric_id=metric.metric_id,
            canonical_name=metric.canonical_name,
            description=metric.description,
            status=metric.status,
        ),
        latest=latest_out,
    )


@router.post("/{metric_id}/aliases", response_model=AliasOut)
def post_alias(
    metric_id: str,
    body: AliasCreate,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_workspace_key_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    metric = get_metric(db, workspace_id, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail="metric not found")

    alias = upsert_alias(
        db=db,
        workspace_id=workspace_id,
        metric_id=metric_id,
        source_system=body.source_system,
        source_locator=body.source_locator,
        alias_name=body.alias_name,
        confidence=body.confidence,
    )
    return AliasOut(
        workspace_id=alias.workspace_id,
        alias_id=str(alias.alias_id),
        metric_id=alias.metric_id,
        source_system=alias.source_system,
        source_locator=alias.source_locator,
        alias_name=alias.alias_name,
        confidence=float(alias.confidence),
    )


@router.post("/resolve_intent", response_model=IntentResolveResponse)
def resolve_intent(
    body: IntentResolveRequest,
    workspace_id: str = Query(default="default"),
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(require_auth_context_if_required),
):
    workspace_id = effective_workspace_id(workspace_id, ctx)
    query = (body.query or "").strip()
    if not query:
        return IntentResolveResponse(status="no_match", confidence=0.0, reason="empty query")

    q_lower = query.lower()
    team = (body.context or {}).get("team")

    # 1) Memory hit: exact alias match via source_locator user_learning::<term>:<team>
    if team:
        locator = f"{q_lower}:{team}"
        alias = db.execute(
            select(MetricAlias).where(
                MetricAlias.workspace_id == workspace_id,
                MetricAlias.source_system == "user_learning",
                MetricAlias.source_locator == locator,
            )
        ).scalar_one_or_none()
        if alias is not None:
            m = db.get(Metric, {"workspace_id": workspace_id, "metric_id": alias.metric_id})
            if m is not None:
                model, measure = _model_measure_from_metric_id(m.metric_id)
                domain = _infer_domain(model)
                return IntentResolveResponse(
                    status="resolved",
                    resolved_metric=IntentResolvedMetric(
                        metric_id=m.metric_id,
                        description=m.description or m.canonical_name,
                        model=model,
                        measure_name=measure,
                        domain=domain,
                    ),
                    confidence=1.0,
                    reason=f"Meaning preserved: saved alias for '{q_lower}' in {team} context.",
                )

    # 2) Candidate collection: metrics + aliases match on substring
    metrics = list(
        db.execute(
            select(Metric).where(Metric.workspace_id == workspace_id, Metric.status == "active")
        ).scalars()
    )
    aliases = list(db.execute(select(MetricAlias).where(MetricAlias.workspace_id == workspace_id)).scalars())

    alias_by_metric: dict[str, list[MetricAlias]] = {}
    for a in aliases:
        alias_by_metric.setdefault(a.metric_id, []).append(a)

    def _matches_metric(m: Metric) -> bool:
        hay = " ".join([(m.metric_id or ""), (m.canonical_name or ""), (m.description or "")]).lower()
        if q_lower in hay:
            return True
        for a in alias_by_metric.get(m.metric_id, []):
            if q_lower in (a.alias_name or "").lower():
                return True
        return False

    matched_metrics = [m for m in metrics if _matches_metric(m)]

    # Revenue hook heuristic (demo-friendly, deterministic)
    if "revenue" in q_lower:
        rev = []
        for m in matched_metrics:
            if "revenue" in (m.metric_id or "").lower() or "revenue" in (m.canonical_name or "").lower() or "revenue" in (m.description or "").lower():
                rev.append(m)
        matched_metrics = rev or matched_metrics

    candidates: list[IntentResolvedMetric] = []
    for m in matched_metrics[:10]:
        model, measure = _model_measure_from_metric_id(m.metric_id)
        candidates.append(
            IntentResolvedMetric(
                metric_id=m.metric_id,
                description=m.description or m.canonical_name,
                model=model,
                measure_name=measure,
                domain=_infer_domain(model),
            )
        )

    if not candidates:
        out = IntentResolveResponse(status="no_match", confidence=0.0, reason="no matching metric")
        _log_intent_usage(db, workspace_id, body, ctx, out)
        return out

    # If campaign is mentioned, prefer marketing candidate.
    if "campaign" in q_lower:
        marketing = [c for c in candidates if c.domain == "marketing"]
        if marketing:
            out = IntentResolveResponse(
                status="resolved",
                resolved_metric=marketing[0],
                confidence=0.92,
                reason="Query mentions campaign; prefer marketing attribution definition.",
            )
            _log_intent_usage(db, workspace_id, body, ctx, out, candidates=candidates)
            return out

    # If team context is provided and matches, prefer it.
    if team in {"marketing", "finance"}:
        team_match = [c for c in candidates if c.domain == team]
        if team_match:
            out = IntentResolveResponse(
                status="resolved",
                resolved_metric=team_match[0],
                confidence=0.92,
                reason=f"Context team '{team}' matches candidate domain.",
            )
            _log_intent_usage(db, workspace_id, body, ctx, out, candidates=candidates)
            return out

    # Otherwise, ambiguous if multiple.
    if len(candidates) > 1:
        out = IntentResolveResponse(
            status="ambiguous",
            candidates=candidates[:5],
            confidence=0.6,
            reason="Multiple candidate definitions match; choose which meaning you intend.",
        )
        _log_intent_usage(db, workspace_id, body, ctx, out, candidates=candidates)
        return out

    out = IntentResolveResponse(
        status="resolved",
        resolved_metric=candidates[0],
        confidence=0.9,
        reason="Single matching candidate.",
    )
    _log_intent_usage(db, workspace_id, body, ctx, out, candidates=candidates)
    return out


def _model_measure_from_metric_id(metric_id: str) -> tuple[str, str]:
    parts = (metric_id or "").split(".")
    if len(parts) >= 2:
        return parts[0], ".".join(parts[1:])
    return "core", metric_id


def _infer_domain(model_name: str) -> str:
    m = (model_name or "").lower()
    if "marketing" in m or "paid" in m:
        return "marketing"
    if "finance" in m:
        return "finance"
    return "unknown"


def _log_intent_usage(
    db: Session,
    workspace_id: str,
    body: IntentResolveRequest,
    ctx: Optional[AuthContext],
    out: IntentResolveResponse,
    *,
    candidates: Optional[list[IntentResolvedMetric]] = None,
) -> None:
    """
    Best-effort audit logging. Never break the endpoint on logging failures.
    """
    try:
        input_hash = sha256_hex(
            json.dumps(
                {"endpoint": "resolve_intent", "query": body.query, "context": body.context},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        resolved_metric_id = out.resolved_metric.metric_id if out.resolved_metric else None
        team = (body.context or {}).get("team")
        surface = ctx.surface if ctx else None
        user_id = ctx.user_id if ctx else None
        agent_id = ctx.agent_id if ctx else None
        auth_type = ctx.auth_type if ctx else None
        log_usage(
            db=db,
            workspace_id=workspace_id,
            query_text=body.query,
            context=body.context or {},
            team=team,
            interface=surface or "api",
            user_id=user_id,
            agent_id=agent_id,
            surface=surface,
            auth_type=auth_type,
            input_hash=input_hash,
            candidate_metrics=[c.model_dump() for c in (candidates or (out.candidates or []))],
            resolved_metric_id=resolved_metric_id,
            resolved_version_id=None,
            confidence=float(out.confidence),
            clarifications_count=1 if out.status == "ambiguous" else 0,
            feedback=None,
        )
    except Exception:
        return

