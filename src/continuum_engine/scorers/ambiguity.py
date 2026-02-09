"""LLM-powered ambiguity scorer with heuristic fallback."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from continuum.hooks import AmbiguityScorer
from continuum.models import Decision

from continuum_engine.llm.client import FallbackRequired, LLMClient
from continuum_engine.llm.prompts import AMBIGUITY_SCORE_SYSTEM, AMBIGUITY_SCORE_TEMPLATE

if TYPE_CHECKING:
    from continuum_engine.config import EngineConfig


class LLMAmbiguityScorer(AmbiguityScorer):
    """Score decision ambiguity using an LLM, falling back to heuristics."""

    def __init__(self, config: EngineConfig) -> None:
        self._client = LLMClient(config)
        self._config = config

    def score(self, decision: Decision) -> float:
        """Return an ambiguity score in [0, 1]."""
        try:
            return self._llm_score(decision)
        except (FallbackRequired, json.JSONDecodeError, KeyError, ValueError):
            if self._config.fallback_to_heuristic:
                return self._heuristic_score(decision)
            raise

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_score(self, decision: Decision) -> float:
        prompt = AMBIGUITY_SCORE_TEMPLATE.format(
            title=decision.title,
            rationale=decision.rationale or "(none)",
            options=", ".join(o.title for o in decision.options_considered),
            stakeholders=", ".join(decision.stakeholders) if decision.stakeholders else "(none)",
        )
        result = self._client.complete_json(prompt, system=AMBIGUITY_SCORE_SYSTEM)
        score = float(result["score"])
        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_score(decision: Decision) -> float:
        """Rule-based ambiguity scoring.

        - More options → higher ambiguity (2 = 0.3, 3 = 0.5, 4+ = 0.7)
        - No rationale → +0.2
        - No context → +0.1
        - Clamped to [0.0, 1.0]
        """
        n_options = len(decision.options_considered)
        if n_options <= 1:
            base = 0.1
        elif n_options == 2:
            base = 0.3
        elif n_options == 3:
            base = 0.5
        else:
            base = 0.7

        if not decision.rationale:
            base += 0.2
        if decision.context is None:
            base += 0.1

        return max(0.0, min(1.0, base))
