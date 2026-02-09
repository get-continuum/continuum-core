"""Tests for the LLM ambiguity scorer (heuristic fallback path)."""

from __future__ import annotations

from datetime import datetime, timezone

from continuum.models import Decision, DecisionContext, Enforcement, Option

from continuum_engine.scorers.ambiguity import LLMAmbiguityScorer


def _make_decision(
    n_options: int = 2,
    rationale: str | None = "Some rationale",
    has_context: bool = True,
) -> Decision:
    options = [
        Option(id=f"opt-{i}", title=f"Option {i}", selected=(i == 0))
        for i in range(n_options)
    ]
    now = datetime.now(timezone.utc)
    context = (
        DecisionContext(trigger="test", source="human", timestamp=now, actor="tester")
        if has_context
        else None
    )
    return Decision(
        id="test-dec",
        title="Test decision",
        rationale=rationale,
        options_considered=options,
        context=context,
        enforcement=Enforcement(scope="project/test", decision_type="preference"),
        created_at=now,
        updated_at=now,
    )


class TestHeuristicFallbackScoring:
    """Test the _heuristic_score static method directly."""

    def test_two_options_base_score(self):
        score = LLMAmbiguityScorer._heuristic_score(_make_decision(n_options=2))
        assert score == 0.3

    def test_three_options_base_score(self):
        score = LLMAmbiguityScorer._heuristic_score(_make_decision(n_options=3))
        assert score == 0.5

    def test_four_plus_options_base_score(self):
        score = LLMAmbiguityScorer._heuristic_score(_make_decision(n_options=5))
        assert score == 0.7

    def test_single_option_base_score(self):
        score = LLMAmbiguityScorer._heuristic_score(_make_decision(n_options=1))
        assert score == 0.1


class TestScoreInValidRange:
    """Ambiguity score must always be in [0.0, 1.0]."""

    def test_minimum_case(self):
        score = LLMAmbiguityScorer._heuristic_score(
            _make_decision(n_options=1, rationale="present", has_context=True)
        )
        assert 0.0 <= score <= 1.0

    def test_maximum_case(self):
        score = LLMAmbiguityScorer._heuristic_score(
            _make_decision(n_options=6, rationale=None, has_context=False)
        )
        assert 0.0 <= score <= 1.0

    def test_edge_case_zero_options(self):
        score = LLMAmbiguityScorer._heuristic_score(
            _make_decision(n_options=0, rationale="x", has_context=True)
        )
        assert 0.0 <= score <= 1.0


class TestMissingRationaleIncreasesScore:
    """No rationale should add +0.2 to the score."""

    def test_no_rationale_penalty(self):
        with_rationale = LLMAmbiguityScorer._heuristic_score(
            _make_decision(n_options=2, rationale="present", has_context=True)
        )
        without_rationale = LLMAmbiguityScorer._heuristic_score(
            _make_decision(n_options=2, rationale=None, has_context=True)
        )
        assert without_rationale == with_rationale + 0.2

    def test_no_context_penalty(self):
        with_context = LLMAmbiguityScorer._heuristic_score(
            _make_decision(n_options=2, rationale="present", has_context=True)
        )
        without_context = LLMAmbiguityScorer._heuristic_score(
            _make_decision(n_options=2, rationale="present", has_context=False)
        )
        assert without_context == with_context + 0.1
