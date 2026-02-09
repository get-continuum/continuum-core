"""LLM-powered risk scorer with heuristic fallback."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from continuum.hooks import RiskScorer
from continuum.models import Decision

from continuum_engine.llm.client import FallbackRequired, LLMClient
from continuum_engine.llm.prompts import RISK_SCORE_SYSTEM, RISK_SCORE_TEMPLATE

if TYPE_CHECKING:
    from continuum_engine.config import EngineConfig


class LLMRiskScorer(RiskScorer):
    """Score action risk against a decision using an LLM, falling back to heuristics."""

    def __init__(self, config: EngineConfig) -> None:
        self._client = LLMClient(config)
        self._config = config

    def score(self, decision: Decision, context: dict) -> float:
        """Return a risk score in [0, 1]."""
        try:
            return self._llm_score(decision, context)
        except (FallbackRequired, json.JSONDecodeError, KeyError, ValueError):
            if self._config.fallback_to_heuristic:
                return self._heuristic_score(decision, context)
            raise

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_score(self, decision: Decision, context: dict) -> float:
        scope = ""
        if decision.enforcement:
            scope = decision.enforcement.scope
        prompt = RISK_SCORE_TEMPLATE.format(
            title=decision.title,
            scope=scope,
            rationale=decision.rationale or "(none)",
            status=decision.status,
            context=json.dumps(context, default=str),
        )
        result = self._client.complete_json(prompt, system=RISK_SCORE_SYSTEM)
        score = float(result["score"])
        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_score(decision: Decision, context: dict) -> float:
        """Rule-based risk scoring.

        - Exact scope match → 0.8
        - Parent scope match → 0.5
        - No match → 0.1
        """
        decision_scope = ""
        if decision.enforcement:
            decision_scope = decision.enforcement.scope

        action_scope = context.get("scope", "")

        if not decision_scope or not action_scope:
            return 0.1

        if decision_scope == action_scope:
            return 0.8

        if action_scope.startswith(decision_scope + "/"):
            return 0.5

        return 0.1
