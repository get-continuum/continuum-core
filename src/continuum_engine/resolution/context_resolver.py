"""Context-aware decision resolution with overlay support."""

from __future__ import annotations

import copy


class ContextResolver:
    """Resolve a decision by applying matching overlays based on context selectors.

    Overlays are stored in ``decision["metadata"]["overlays"]`` and each overlay
    has a ``selector`` dict and a ``patch`` dict.  The resolver applies all
    matching overlays in order of specificity (most specific last) to produce
    a resolved snapshot.
    """

    def __init__(self, decisions: list[dict]) -> None:
        self._decisions = {d["id"]: d for d in decisions if "id" in d}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, decision_id: str, context: dict) -> dict:
        """Return a resolved snapshot of *decision_id* with overlays applied.

        The result includes a ``_provenance`` key listing which overlays
        were applied and in what order.
        """
        base = self._decisions.get(decision_id)
        if base is None:
            raise KeyError(f"Decision '{decision_id}' not found")

        snapshot = copy.deepcopy(base)
        overlays = snapshot.get("metadata", {}).get("overlays", [])

        # Sort by specificity (least specific first → most specific applied last)
        matching = [
            o for o in overlays
            if self._selector_matches(o.get("selector", {}), context)
        ]
        matching.sort(key=lambda o: self._selector_specificity(o.get("selector", {})))

        provenance: list[dict] = []
        for overlay in matching:
            patch = overlay.get("patch", {})
            self._apply_patch(snapshot, patch)
            provenance.append({
                "selector": overlay.get("selector", {}),
                "specificity": self._selector_specificity(overlay.get("selector", {})),
            })

        snapshot["_provenance"] = provenance
        return snapshot

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _selector_matches(selector: dict, context: dict) -> bool:
        """Return True if all keys in *selector* match values in *context*."""
        if not selector:
            return True
        return all(context.get(k) == v for k, v in selector.items())

    @staticmethod
    def _selector_specificity(selector: dict) -> int:
        """Return the specificity of a selector (number of keys)."""
        return len(selector)

    @staticmethod
    def _apply_patch(target: dict, patch: dict) -> None:
        """Shallow-merge *patch* into *target*."""
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                target[key].update(value)
            else:
                target[key] = value
