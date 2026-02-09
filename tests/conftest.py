"""Shared fixtures for core engine tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from continuum_engine.config import EngineConfig


@pytest.fixture()
def engine_config() -> EngineConfig:
    """Return a default engine config with heuristic fallback enabled."""
    return EngineConfig(
        llm_provider="openai",
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=1024,
        retry_attempts=1,
        backoff_factor=1.0,
        fallback_to_heuristic=True,
    )


@pytest.fixture()
def mock_llm_client():
    """Return a mock LLMClient that raises FallbackRequired."""
    with patch("continuum_engine.llm.client.LLMClient") as mock_cls:
        from continuum_engine.llm.client import FallbackRequired

        instance = MagicMock()
        instance.complete.side_effect = FallbackRequired("mocked")
        instance.complete_json.side_effect = FallbackRequired("mocked")
        mock_cls.return_value = instance
        yield instance


@pytest.fixture()
def sample_decisions() -> list[dict]:
    """Return a list of sample decisions for testing."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "id": "dec-001",
            "version": 1,
            "status": "active",
            "title": "Use PostgreSQL over MySQL",
            "rationale": "Better JSON support and more active community.",
            "options_considered": [
                {"id": "opt-pg", "title": "PostgreSQL", "selected": True, "rejected_reason": None},
                {"id": "opt-mysql", "title": "MySQL", "selected": False, "rejected_reason": "Weaker JSON support"},
            ],
            "context": {
                "trigger": "database selection",
                "source": "human",
                "timestamp": now,
                "actor": "alice",
            },
            "enforcement": {
                "scope": "project/backend/db",
                "decision_type": "rejection",
                "override_policy": "invalid_by_default",
            },
            "stakeholders": ["platform"],
            "metadata": {"team": "platform"},
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "dec-002",
            "version": 1,
            "status": "active",
            "title": "REST over GraphQL for public API",
            "rationale": "Simpler client integration and better caching.",
            "options_considered": [
                {"id": "opt-rest", "title": "REST", "selected": True, "rejected_reason": None},
                {"id": "opt-gql", "title": "GraphQL", "selected": False, "rejected_reason": "Complexity for public consumers"},
            ],
            "context": {
                "trigger": "api design review",
                "source": "pair",
                "timestamp": now,
                "actor": "bob",
            },
            "enforcement": {
                "scope": "project/backend/api",
                "decision_type": "rejection",
                "override_policy": "warn",
            },
            "stakeholders": ["growth"],
            "metadata": {"team": "growth"},
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "dec-003",
            "version": 0,
            "status": "draft",
            "title": "Consider event sourcing",
            "rationale": None,
            "options_considered": [],
            "context": None,
            "enforcement": {
                "scope": "project/backend",
                "decision_type": "preference",
                "override_policy": "allow",
            },
            "stakeholders": [],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        },
    ]
