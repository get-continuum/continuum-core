from __future__ import annotations

from datetime import datetime, timezone

from app.core.overlays import select_overlays_for_context
from app.db.models import Overlay


def _dt(i: int) -> datetime:
    return datetime(2026, 1, 1, 0, 0, i, tzinfo=timezone.utc)


def test_selector_matching_and_deterministic_ordering(db):
    # priority DESC, specificity DESC, created_at DESC
    o1 = Overlay(
        workspace_id="default",
        metric_id="revenue",
        selector={"team": "marketing"},
        priority=0,
        overlay_patch={"units": "usd"},
        created_at=_dt(1),
    )
    o2 = Overlay(
        workspace_id="default",
        metric_id="revenue",
        selector={"team": "marketing", "use_case": "weekly"},
        priority=0,
        overlay_patch={"grain": "week"},
        created_at=_dt(2),
    )
    o3 = Overlay(
        workspace_id="default",
        metric_id="revenue",
        selector={"team": "marketing"},
        priority=10,
        overlay_patch={"definition": {"display": "override"}},
        created_at=_dt(3),
    )
    db.add_all([o1, o2, o3])
    db.commit()

    chosen = select_overlays_for_context([o1, o2, o3], {"team": "marketing", "use_case": "weekly"})
    assert [c.overlay_patch for c in chosen] == [
        {"definition": {"display": "override"}},  # highest priority
        {"grain": "week"},  # higher specificity
        {"units": "usd"},  # lower specificity
    ]


def test_validity_window(db):
    now = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
    o = Overlay(
        workspace_id="default",
        metric_id="revenue",
        selector={"team": "finance"},
        priority=0,
        overlay_patch={"units": "usd"},
        valid_from=datetime(2026, 1, 1, 0, 0, 11, tzinfo=timezone.utc),
        valid_to=None,
        created_at=_dt(1),
    )
    chosen = select_overlays_for_context([o], {"team": "finance"}, now=now)
    assert chosen == []

