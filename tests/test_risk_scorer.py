"""Tests for the LLM risk scorer (heuristic fallback path)."""

from __future__ import annotations

from datetime import datetime, timezone

from continuum.models import Decision, Enforcement

from continuum_engine.scorers.risk import LLMRiskScorer


def _make_decision(scope: str = "project/backend/api") -> Decision:
    now = datetime.now(timezone.utc)
    return Decision(
        id="risk-dec",
        title="Test risk decision",
        rationale="Some rationale",
        enforcement=Enforcement(scope=scope, decision_type="rejection"),
        created_at=now,
        updated_at=now,
    )


class TestExactScopeMatchHighRisk:
    def test_exact_match_returns_0_8(self):
        decision = _make_decision(scope="project/backend/api")
        score = LLMRiskScorer._heuristic_score(decision, {"scope": "project/backend/api"})
        assert score == 0.8


class TestNoScopeMatchLowRisk:
    def test_no_match_returns_0_1(self):
        decision = _make_decision(scope="project/backend/api")
        score = LLMRiskScorer._heuristic_score(decision, {"scope": "project/frontend/ui"})
        assert score == 0.1

    def test_parent_scope_returns_0_5(self):
        decision = _make_decision(scope="project/backend")
        score = LLMRiskScorer._heuristic_score(decision, {"scope": "project/backend/api"})
        assert score == 0.5


class TestScoreRange:
    def test_empty_scope_in_context(self):
        decision = _make_decision(scope="project/backend")
        score = LLMRiskScorer._heuristic_score(decision, {"scope": ""})
        assert 0.0 <= score <= 1.0

    def test_empty_scope_in_decision(self):
        decision = _make_decision(scope="")
        score = LLMRiskScorer._heuristic_score(decision, {"scope": "project/backend"})
        assert 0.0 <= score <= 1.0

    def test_no_enforcement(self):
        now = datetime.now(timezone.utc)
        decision = Decision(
            id="no-enf", title="No enforcement", created_at=now, updated_at=now
        )
        score = LLMRiskScorer._heuristic_score(decision, {"scope": "anything"})
        assert score == 0.1
