"""Advanced enforcement policies for the Continuum engine."""

from __future__ import annotations

import hashlib


class GradualRolloutPolicy:
    """Enforce decisions for a percentage of actions (hash-based, deterministic)."""

    def __init__(self, percentage: float) -> None:
        if not 0.0 <= percentage <= 100.0:
            raise ValueError("percentage must be between 0 and 100")
        self._percentage = percentage

    def should_enforce(self, action_id: str) -> bool:
        """Return True if the action falls within the rollout percentage.

        Uses a stable hash so the same *action_id* always yields the
        same result for a given percentage.
        """
        digest = hashlib.sha256(action_id.encode()).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return bucket < self._percentage


class TeamScopedPolicy:
    """Per-team enforcement strictness levels."""

    def __init__(self, team_strictness: dict[str, str]) -> None:
        self._team_strictness = team_strictness  # e.g. {"platform": "strict", "growth": "relaxed"}

    def enforcement_level(self, team: str) -> str:
        """Return the enforcement level for *team*, defaulting to ``"normal"``."""
        return self._team_strictness.get(team, "normal")


class OverrideApprovalPolicy:
    """Require a minimum number of approvals before an override is accepted."""

    def __init__(self, required_approvals: int) -> None:
        if required_approvals < 1:
            raise ValueError("required_approvals must be >= 1")
        self._required_approvals = required_approvals

    def can_override(self, approvals: list[str]) -> bool:
        """Return True if enough unique approvals have been collected."""
        unique_approvals = set(approvals)
        return len(unique_approvals) >= self._required_approvals


class TemporalDecayPolicy:
    """Reduce enforcement weight as decisions age.

    Weight decays linearly from 1.0 to 0.1 over *decay_days*.
    """

    def __init__(self, decay_days: int) -> None:
        if decay_days < 1:
            raise ValueError("decay_days must be >= 1")
        self._decay_days = decay_days

    def enforcement_weight(self, decision_age_days: int) -> float:
        """Return the enforcement weight for a decision of the given age."""
        if decision_age_days <= 0:
            return 1.0
        if decision_age_days >= self._decay_days:
            return 0.1
        # Linear decay from 1.0 → 0.1
        return 1.0 - (0.9 * decision_age_days / self._decay_days)
