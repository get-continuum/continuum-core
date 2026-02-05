from app.utils.json_patch import apply_overlay_patch


def test_deep_merge_and_array_replace():
    base = {
        "definition": {"display": "A", "logic": {"type": "sum", "field": "x", "filters": []}},
        "dimensions": ["country", "channel"],
        "meta": {"tags": ["a"]},
    }
    patch = {"definition": {"display": "B"}, "dimensions": ["channel", "campaign"]}

    out = apply_overlay_patch(base, patch)
    assert out["definition"]["display"] == "B"
    assert out["definition"]["logic"]["field"] == "x"  # preserved via deep merge
    assert out["dimensions"] == ["channel", "campaign"]  # replaced


def test_dimensions_ops_add_remove():
    base = {"dimensions": ["a", "b", "c"]}
    patch = {"dimensions_remove": ["b"], "dimensions_add": ["d", "a"]}
    out = apply_overlay_patch(base, patch)
    assert out["dimensions"] == ["a", "c", "d"]


def test_filters_ops_add_remove():
    base = {"definition": {"logic": {"filters": [{"field": "x", "op": "=", "value": 1}]}}}
    patch = {
        "filters_remove": [{"field": "x", "op": "=", "value": 1}],
        "filters_add": [{"field": "y", "op": "=", "value": 2}],
    }
    out = apply_overlay_patch(base, patch)
    assert out["definition"]["logic"]["filters"] == [{"field": "y", "op": "=", "value": 2}]

