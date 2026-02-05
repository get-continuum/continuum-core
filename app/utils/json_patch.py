from __future__ import annotations

import copy
from typing import Any


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    """
    Deep-merge objects. Arrays are replaced (not merged).
    Scalars are replaced.
    """
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            dst[k] = _deep_merge(dst[k], v)  # type: ignore[arg-type]
        elif isinstance(v, list):
            dst[k] = copy.deepcopy(v)
        else:
            dst[k] = copy.deepcopy(v)
    return dst


def apply_overlay_patch(snapshot: dict[str, Any], overlay_patch: dict[str, Any]) -> dict[str, Any]:
    """
    MVP semantics:
    - deep merge for objects
    - arrays replaced fully
    - optional op keys:
      - dimensions_add / dimensions_remove
      - filters_add / filters_remove (applies to definition.logic.filters)
    """
    base = copy.deepcopy(snapshot)

    # Ops first (so explicit replacements in overlay_patch can still override later).
    dims_add = overlay_patch.get("dimensions_add")
    dims_remove = overlay_patch.get("dimensions_remove")
    if dims_add is not None or dims_remove is not None:
        dims = list(base.get("dimensions") or [])
        if dims_remove:
            dims = [d for d in dims if d not in set(dims_remove)]
        if dims_add:
            for d in dims_add:
                if d not in dims:
                    dims.append(d)
        base["dimensions"] = dims

    filters_add = overlay_patch.get("filters_add")
    filters_remove = overlay_patch.get("filters_remove")
    if filters_add is not None or filters_remove is not None:
        definition = base.setdefault("definition", {})
        logic = definition.setdefault("logic", {})
        filters = list(logic.get("filters") or [])
        if filters_remove:
            remove_set = {repr(f) for f in filters_remove}
            filters = [f for f in filters if repr(f) not in remove_set]
        if filters_add:
            existing = {repr(f) for f in filters}
            for f in filters_add:
                if repr(f) not in existing:
                    filters.append(f)
                    existing.add(repr(f))
        logic["filters"] = filters

    # Standard deep merge for the rest (excluding op keys).
    patch_no_ops = {
        k: v
        for k, v in overlay_patch.items()
        if k
        not in {
            "dimensions_add",
            "dimensions_remove",
            "filters_add",
            "filters_remove",
        }
    }
    if patch_no_ops:
        _deep_merge(base, patch_no_ops)

    return base

