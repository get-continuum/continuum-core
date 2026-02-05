from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import Overlay
from app.utils.time import now_utc


def selector_matches(selector: dict, context: dict) -> bool:
    # All keys in selector must exist in context and equal.
    for k, v in selector.items():
        if k not in context:
            return False
        if context[k] != v:
            return False
    return True


def selector_specificity(selector: dict) -> int:
    return len(selector.keys())


def _within_window(now: datetime, valid_from: Optional[datetime], valid_to: Optional[datetime]) -> bool:
    if valid_from is not None and now < valid_from:
        return False
    if valid_to is not None and now > valid_to:
        return False
    return True


def create_overlay(
    db: Session,
    workspace_id: str,
    metric_id: str,
    selector: dict,
    priority: int,
    overlay_patch: dict,
    valid_from: Optional[datetime],
    valid_to: Optional[datetime],
    author: Optional[str],
    reason: Optional[str],
) -> Overlay:
    overlay = Overlay(
        workspace_id=workspace_id,
        metric_id=metric_id,
        selector=selector,
        priority=priority,
        overlay_patch=overlay_patch,
        valid_from=valid_from,
        valid_to=valid_to,
        author=author,
        reason=reason,
    )
    db.add(overlay)
    db.commit()
    db.refresh(overlay)
    return overlay


def list_overlays(db: Session, workspace_id: str, metric_id: str) -> list[Overlay]:
    rows = db.execute(
        select(Overlay)
        .where(Overlay.workspace_id == workspace_id, Overlay.metric_id == metric_id)
        .order_by(desc(Overlay.priority), desc(Overlay.created_at))
    ).scalars()
    return list(rows)


def select_overlays_for_context(
    overlays: list[Overlay],
    context: dict,
    now: Optional[datetime] = None,
) -> list[Overlay]:
    now = now or now_utc()
    matching: list[Overlay] = []
    for o in overlays:
        if not _within_window(now, o.valid_from, o.valid_to):
            continue
        if selector_matches(o.selector or {}, context or {}):
            matching.append(o)

    # Deterministic ordering:
    # 1) priority DESC
    # 2) specificity DESC
    # 3) created_at DESC
    matching.sort(
        key=lambda o: (
            int(o.priority),
            selector_specificity(o.selector or {}),
            o.created_at,
        ),
        reverse=True,
    )
    return matching

