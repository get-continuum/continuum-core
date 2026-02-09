"""Tests for advanced enforcement policies."""

from __future__ import annotations

import pytest

from continuum_engine.enforcement.policies import (
    GradualRolloutPolicy,
    OverrideApprovalPolicy,
    TeamScopedPolicy,
    TemporalDecayPolicy,
)


class TestGradualRolloutPercentage:
    def test_zero_percent_never_enforces(self):
        policy = GradualRolloutPolicy(percentage=0.0)
        results = [policy.should_enforce(f"action-{i}") for i in range(100)]
        assert not any(results)

    def test_hundred_percent_always_enforces(self):
        policy = GradualRolloutPolicy(percentage=100.0)
        results = [policy.should_enforce(f"action-{i}") for i in range(100)]
        assert all(results)

    def test_deterministic_for_same_id(self):
        policy = GradualRolloutPolicy(percentage=50.0)
        result1 = policy.should_enforce("stable-action")
        result2 = policy.should_enforce("stable-action")
        assert result1 == result2

    def test_invalid_percentage_raises(self):
        with pytest.raises(ValueError):
            GradualRolloutPolicy(percentage=-1.0)
        with pytest.raises(ValueError):
            GradualRolloutPolicy(percentage=101.0)


class TestTeamScopedStrictness:
    def test_known_team_returns_level(self):
        policy = TeamScopedPolicy(team_strictness={"platform": "strict", "growth": "relaxed"})
        assert policy.enforcement_level("platform") == "strict"
        assert policy.enforcement_level("growth") == "relaxed"

    def test_unknown_team_returns_normal(self):
        policy = TeamScopedPolicy(team_strictness={"platform": "strict"})
        assert policy.enforcement_level("unknown-team") == "normal"


class TestOverrideApprovalCount:
    def test_enough_approvals(self):
        policy = OverrideApprovalPolicy(required_approvals=2)
        assert policy.can_override(["alice", "bob"]) is True

    def test_not_enough_approvals(self):
        policy = OverrideApprovalPolicy(required_approvals=2)
        assert policy.can_override(["alice"]) is False

    def test_duplicate_approvals_not_counted(self):
        policy = OverrideApprovalPolicy(required_approvals=2)
        assert policy.can_override(["alice", "alice"]) is False

    def test_invalid_required_approvals(self):
        with pytest.raises(ValueError):
            OverrideApprovalPolicy(required_approvals=0)


class TestTemporalDecayWeight:
    def test_fresh_decision_full_weight(self):
        policy = TemporalDecayPolicy(decay_days=90)
        assert policy.enforcement_weight(0) == 1.0

    def test_expired_decision_minimum_weight(self):
        policy = TemporalDecayPolicy(decay_days=90)
        assert policy.enforcement_weight(90) == 0.1
        assert policy.enforcement_weight(180) == 0.1

    def test_midway_decay(self):
        policy = TemporalDecayPolicy(decay_days=100)
        weight = policy.enforcement_weight(50)
        assert 0.4 < weight < 0.7  # ~0.55

    def test_negative_age_full_weight(self):
        policy = TemporalDecayPolicy(decay_days=90)
        assert policy.enforcement_weight(-5) == 1.0

    def test_invalid_decay_days(self):
        with pytest.raises(ValueError):
            TemporalDecayPolicy(decay_days=0)
