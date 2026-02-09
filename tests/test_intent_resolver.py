"""Tests for the intent resolver."""

from __future__ import annotations

from unittest.mock import MagicMock

from continuum_engine.resolution.intent_resolver import IntentResolver


def _make_decisions() -> list[dict]:
    return [
        {
            "id": "dec-001",
            "title": "Use PostgreSQL over MySQL",
            "enforcement": {"scope": "project/backend/db"},
            "stakeholders": ["platform"],
            "metadata": {"team": "platform"},
        },
        {
            "id": "dec-002",
            "title": "REST over GraphQL for public API",
            "enforcement": {"scope": "project/backend/api"},
            "stakeholders": ["growth"],
            "metadata": {"team": "growth"},
        },
    ]


class TestMemoryHitReturnsResolved:
    def test_exact_title_and_scope_match(self):
        """When query matches a decision title exactly and scope matches,
        the memory index should yield a resolved result."""
        scorer = MagicMock()
        decisions = _make_decisions()
        resolver = IntentResolver(scorer=scorer, decisions=decisions)

        result = resolver.resolve(
            query="Use PostgreSQL over MySQL",
            context={"scope": "project/backend/db"},
        )
        assert result["status"] == "resolved"
        assert result["decision"]["id"] == "dec-001"
        assert result["confidence"] == 1.0


class TestNoMatchReturnsNoMatch:
    def test_unrelated_scope(self):
        scorer = MagicMock()
        decisions = _make_decisions()
        resolver = IntentResolver(scorer=scorer, decisions=decisions)

        result = resolver.resolve(
            query="Something about frontend styles",
            context={"scope": "project/frontend/css"},
        )
        assert result["status"] == "no_match"
        assert result["decision"] is None
        assert result["confidence"] == 0.0


class TestMultipleCandidatesReturnsAmbiguous:
    def test_scope_matches_multiple_decisions(self):
        """When scope matches multiple decisions and no context narrows them,
        the result should be ambiguous."""
        scorer = MagicMock()
        # Both decisions share a parent scope
        decisions = [
            {
                "id": "dec-A",
                "title": "Approach A",
                "enforcement": {"scope": "project/backend"},
                "stakeholders": [],
                "metadata": {},
            },
            {
                "id": "dec-B",
                "title": "Approach B",
                "enforcement": {"scope": "project/backend"},
                "stakeholders": [],
                "metadata": {},
            },
        ]
        resolver = IntentResolver(scorer=scorer, decisions=decisions)

        result = resolver.resolve(
            query="How to handle backend caching?",
            context={"scope": "project/backend/cache"},
        )
        assert result["status"] == "ambiguous"
        assert len(result["candidates"]) == 2
        assert result["confidence"] == 0.5
