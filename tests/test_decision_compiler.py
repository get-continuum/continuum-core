"""Tests for the LLM decision compiler (heuristic fallback path)."""

from __future__ import annotations

from datetime import datetime, timezone

from continuum.models import Decision, Option

from continuum_engine.compiler.decision_compiler import LLMDecisionCompiler


def _make_decision() -> Decision:
    now = datetime.now(timezone.utc)
    return Decision(
        id="comp-dec",
        title="Use REST over GraphQL",
        rationale="Simpler for public API consumers.",
        options_considered=[
            Option(id="opt-rest", title="REST API", selected=True),
            Option(id="opt-gql", title="GraphQL", selected=False, rejected_reason="Too complex"),
            Option(id="opt-grpc", title="gRPC", selected=False, rejected_reason="Not web-friendly"),
        ],
        created_at=now,
        updated_at=now,
    )


class TestHeuristicCompileCreatesRules:
    def test_creates_rules_for_all_options(self):
        result = LLMDecisionCompiler._heuristic_compile(_make_decision())
        assert len(result["rules"]) == 3

    def test_output_has_required_keys(self):
        result = LLMDecisionCompiler._heuristic_compile(_make_decision())
        assert "rules" in result
        assert "blocked_patterns" in result
        assert "required_confirmations" in result


class TestRejectedOptionsBecomeBlocks:
    def test_rejected_options_in_blocked_patterns(self):
        result = LLMDecisionCompiler._heuristic_compile(_make_decision())
        assert "GraphQL" in result["blocked_patterns"]
        assert "gRPC" in result["blocked_patterns"]

    def test_selected_option_not_in_blocked_patterns(self):
        result = LLMDecisionCompiler._heuristic_compile(_make_decision())
        assert "REST API" not in result["blocked_patterns"]

    def test_block_rules_have_correct_action(self):
        result = LLMDecisionCompiler._heuristic_compile(_make_decision())
        block_rules = [r for r in result["rules"] if r["action"] == "block"]
        assert len(block_rules) == 2


class TestCompileOutputStructure:
    def test_each_rule_has_required_fields(self):
        result = LLMDecisionCompiler._heuristic_compile(_make_decision())
        for rule in result["rules"]:
            assert "name" in rule
            assert "action" in rule
            assert "pattern" in rule
            assert "reason" in rule

    def test_prefer_rule_for_selected_option(self):
        result = LLMDecisionCompiler._heuristic_compile(_make_decision())
        prefer_rules = [r for r in result["rules"] if r["action"] == "prefer"]
        assert len(prefer_rules) == 1
        assert prefer_rules[0]["pattern"] == "REST API"
