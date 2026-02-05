from __future__ import annotations

from datetime import datetime, timezone

from app.core.events import append_event
from app.core.identity import create_metric
from app.core.overlays import create_overlay
from app.core.resolver import resolve_metric_state


def test_resolve_no_overlays_equals_base(db):
    create_metric(db, "default", "revenue", "Revenue", None)
    append_event(
        db,
        workspace_id="default",
        metric_id="revenue",
        event_type="snapshot",
        source_system="dbt",
        source_ref={},
        reason=None,
        actor=None,
        snapshot={
            "metric_id": "revenue",
            "definition": {"display": "rev", "logic": {"type": "sum", "field": "x", "filters": []}},
            "grain": "day",
            "dimensions": ["country"],
            "units": "usd",
            "meta": {},
        },
    )

    out = resolve_metric_state(db, "default", "revenue", {"team": "finance"})
    assert out["resolved_snapshot"]["definition"]["display"] == "rev"
    assert out["applied_overlays"] == []


def test_resolve_overlay_order_and_patch_application(db):
    create_metric(db, "default", "revenue", "Revenue", None)
    append_event(
        db,
        workspace_id="default",
        metric_id="revenue",
        event_type="snapshot",
        source_system="dbt",
        source_ref={"commit": "base"},
        reason=None,
        actor=None,
        snapshot={
            "metric_id": "revenue",
            "definition": {"display": "rev", "logic": {"type": "sum", "field": "x", "filters": []}},
            "grain": "day",
            "dimensions": ["country", "channel"],
            "units": "usd",
            "meta": {},
        },
    )

    # lower priority, lower specificity
    create_overlay(
        db,
        workspace_id="default",
        metric_id="revenue",
        selector={"team": "marketing"},
        priority=0,
        overlay_patch={"dimensions": ["campaign"]},
        valid_from=None,
        valid_to=None,
        author=None,
        reason=None,
    )

    # higher specificity
    create_overlay(
        db,
        workspace_id="default",
        metric_id="revenue",
        selector={"team": "marketing", "use_case": "weekly"},
        priority=0,
        overlay_patch={"definition": {"display": "rev weekly"}},
        valid_from=None,
        valid_to=None,
        author=None,
        reason=None,
    )

    # higher priority but created earlier/later shouldn't matter vs priority
    create_overlay(
        db,
        workspace_id="default",
        metric_id="revenue",
        selector={"team": "marketing"},
        priority=10,
        overlay_patch={"grain": "week"},
        valid_from=None,
        valid_to=None,
        author=None,
        reason=None,
    )

    out = resolve_metric_state(
        db, "default", "revenue", {"team": "marketing", "use_case": "weekly"}
    )
    snap = out["resolved_snapshot"]

    # Applied in correct order: priority(10) first, then specificity(2), then specificity(1)
    assert snap["grain"] == "week"
    assert snap["definition"]["display"] == "rev weekly"
    assert snap["dimensions"] == ["campaign"]


def test_search_ranking_exact_metric_id_beats_alias_substring(client, db):
    # Use API to exercise /search and alias path quickly
    r = client.post(
        "/metrics",
        params={"workspace_id": "default"},
        json={"metric_id": "revenue", "canonical_name": "Revenue", "description": None},
    )
    assert r.status_code == 200
    r = client.post(
        "/metrics",
        params={"workspace_id": "default"},
        json={"metric_id": "rev", "canonical_name": "Rev short", "description": None},
    )
    assert r.status_code == 200
    r = client.post(
        "/metrics/revenue/aliases",
        params={"workspace_id": "default"},
        json={
            "source_system": "custom",
            "source_locator": "x",
            "alias_name": "total rev",
            "confidence": 0.9,
        },
    )
    assert r.status_code == 200

    # Query "rev" should rank metric_id exact match for metric_id="rev" above alias substring match on "revenue"
    out = client.get("/search", params={"workspace_id": "default", "q": "rev"})
    assert out.status_code == 200
    results = out.json()["results"]
    assert results[0]["metric_id"] == "rev"

