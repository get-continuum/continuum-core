"""LLM-powered decision compiler with heuristic fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

from continuum.hooks import DecisionCompiler
from continuum.models import Decision

from continuum_engine.llm.client import FallbackRequired, LLMClient
from continuum_engine.llm.prompts import COMPILE_DECISION_SYSTEM, COMPILE_DECISION_TEMPLATE

if TYPE_CHECKING:
    from continuum_engine.config import EngineConfig


class LLMDecisionCompiler(DecisionCompiler):
    """Compile a decision into enforcement rules using an LLM, with heuristic fallback."""

    def __init__(self, config: EngineConfig) -> None:
        self._client = LLMClient(config)
        self._config = config

    def compile(self, decision: Decision) -> dict:
        """Return compiled rules, blocked patterns, and required confirmations."""
        try:
            return self._llm_compile(decision)
        except (FallbackRequired, Exception):  # noqa: BLE001
            if self._config.fallback_to_heuristic:
                return self._heuristic_compile(decision)
            raise

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_compile(self, decision: Decision) -> dict:
        prompt = COMPILE_DECISION_TEMPLATE.format(
            title=decision.title,
            rationale=decision.rationale or "(none)",
            options=", ".join(
                f"{o.title} ({'selected' if o.selected else 'rejected'})"
                for o in decision.options_considered
            ),
        )
        return self._client.complete_json(prompt, system=COMPILE_DECISION_SYSTEM)

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_compile(decision: Decision) -> dict:
        """Deterministic rule extraction without an LLM.

        - Each rejected option becomes a ``block`` rule.
        - The selected option becomes a ``prefer`` rule.
        """
        rules: list[dict] = []
        blocked_patterns: list[str] = []
        required_confirmations: list[str] = []

        for option in decision.options_considered:
            if option.selected:
                rules.append({
                    "name": f"prefer-{option.id}",
                    "action": "prefer",
                    "pattern": option.title,
                    "reason": f"Selected option in decision '{decision.id}'",
                })
            else:
                rules.append({
                    "name": f"block-{option.id}",
                    "action": "block",
                    "pattern": option.title,
                    "reason": option.rejected_reason or f"Rejected in decision '{decision.id}'",
                })
                blocked_patterns.append(option.title)

        return {
            "rules": rules,
            "blocked_patterns": blocked_patterns,
            "required_confirmations": required_confirmations,
        }
