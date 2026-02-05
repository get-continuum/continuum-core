from app.core.events import append_event, get_history
from app.core.identity import create_metric


def test_append_only_events_increment_version(db):
    create_metric(db, "default", "revenue", "Revenue", None)

    e1 = append_event(
        db,
        workspace_id="default",
        metric_id="revenue",
        event_type="snapshot",
        source_system="dbt",
        source_ref={"commit": "a"},
        reason=None,
        actor=None,
        snapshot={
            "metric_id": "revenue",
            "definition": {"display": "rev", "logic": {"type": "sum", "field": "x", "filters": []}},
            "grain": "day",
            "dimensions": [],
            "units": "usd",
            "meta": {},
        },
    )
    e2 = append_event(
        db,
        workspace_id="default",
        metric_id="revenue",
        event_type="definition_changed",
        source_system="dbt",
        source_ref={"commit": "b"},
        reason="change",
        actor="bot",
        snapshot={
            "metric_id": "revenue",
            "definition": {
                "display": "rev2",
                "logic": {"type": "sum", "field": "y", "filters": []},
            },
            "grain": "day",
            "dimensions": [],
            "units": "usd",
            "meta": {},
        },
    )

    assert int(e1.version_id) == 1
    assert int(e2.version_id) == 2

    hist = get_history(db, "default", "revenue", limit=10)
    assert [int(h.version_id) for h in hist] == [2, 1]
    # Ensure no overwrite: original snapshot preserved.
    assert hist[-1].snapshot["definition"]["logic"]["field"] == "x"

