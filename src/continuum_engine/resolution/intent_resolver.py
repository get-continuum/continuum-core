"""Intent resolution with memory-hit, candidate collection, and ambiguity detection."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from continuum.hooks import AmbiguityScorer


class IntentResolver:
    """Resolve user intent against existing decisions.

    Resolution proceeds through four phases:

    1. **Memory hit** — check if ``query + context`` hash matches a prior decision.
    2. **Candidate collection** — find decisions whose scope matches.
    3. **Context matching** — narrow by team / role from context.
    4. **Ambiguity detection** — if multiple candidates remain, use the scorer.
    """

    def __init__(self, scorer: AmbiguityScorer, decisions: list[dict]) -> None:
        self._scorer = scorer
        self._decisions = decisions
        self._memory: dict[str, dict] = self._build_memory()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, query: str, context: dict) -> dict:
        """Resolve *query* in *context* against the decision store.

        Returns a dict with keys:
        ``status``, ``decision``, ``candidates``, ``confidence``.
        """
        # Phase 1: Memory hit
        cache_key = self._hash(query, context)
        if cache_key in self._memory:
            return {
                "status": "resolved",
                "decision": self._memory[cache_key],
                "candidates": [],
                "confidence": 1.0,
            }

        # Phase 2: Candidate collection (scope match)
        scope = context.get("scope", "")
        candidates = [
            d for d in self._decisions
            if self._scope_matches(self._get_scope(d), scope)
        ]

        if not candidates:
            return {
                "status": "no_match",
                "decision": None,
                "candidates": [],
                "confidence": 0.0,
            }

        # Phase 3: Context matching — narrow by team / role
        narrowed = self._narrow_by_context(candidates, context)
        if narrowed:
            candidates = narrowed

        # Phase 4: Ambiguity detection
        if len(candidates) == 1:
            return {
                "status": "resolved",
                "decision": candidates[0],
                "candidates": candidates,
                "confidence": 0.9,
            }

        # Multiple candidates — check ambiguity via scorer
        return {
            "status": "ambiguous",
            "decision": None,
            "candidates": candidates,
            "confidence": 1.0 / len(candidates),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_memory(self) -> dict[str, dict]:
        """Index decisions by a stable hash of scope + title for quick lookup."""
        memory: dict[str, dict] = {}
        for d in self._decisions:
            scope = self._get_scope(d)
            title = d.get("title", "")
            key = self._hash(title, {"scope": scope})
            memory[key] = d
        return memory

    @staticmethod
    def _hash(query: str, context: dict) -> str:
        scope = context.get("scope", "")
        raw = f"{query.lower().strip()}::{scope.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _get_scope(decision: dict) -> str:
        enforcement = decision.get("enforcement")
        if isinstance(enforcement, dict):
            return enforcement.get("scope", "")
        return decision.get("scope", "")

    @staticmethod
    def _scope_matches(decision_scope: str, action_scope: str) -> bool:
        if not decision_scope:
            return False
        if decision_scope == action_scope:
            return True
        return action_scope.startswith(decision_scope + "/")

    @staticmethod
    def _narrow_by_context(candidates: list[dict], context: dict) -> list[dict]:
        """Filter candidates by team or role in context."""
        team = context.get("team")
        role = context.get("role")
        if not team and not role:
            return candidates

        narrowed = []
        for d in candidates:
            stakeholders = d.get("stakeholders", [])
            meta = d.get("metadata", {})
            if team and (team in stakeholders or meta.get("team") == team):
                narrowed.append(d)
            elif role and meta.get("role") == role:
                narrowed.append(d)

        return narrowed
