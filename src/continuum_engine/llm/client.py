"""Unified LLM client with retry, fallback, and structured output."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from continuum_engine.config import EngineConfig


class FallbackRequired(Exception):
    """Raised when the LLM is unavailable and heuristic fallback is enabled."""


class LLMClient:
    """Thin wrapper around OpenAI and Anthropic APIs.

    Provides retry with exponential back-off and optional heuristic fallback.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._client = self._build_client()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(self, prompt: str, system: str = "") -> str:
        """Return a text completion from the configured LLM provider."""
        last_err: Exception | None = None
        for attempt in range(self._config.retry_attempts):
            try:
                return self._call(prompt, system)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt < self._config.retry_attempts - 1:
                    time.sleep(self._config.backoff_factor ** attempt)

        if self._config.fallback_to_heuristic:
            raise FallbackRequired(
                f"LLM unavailable after {self._config.retry_attempts} attempts: {last_err}"
            )
        raise RuntimeError(
            f"LLM call failed after {self._config.retry_attempts} attempts"
        ) from last_err

    def complete_json(self, prompt: str, system: str = "") -> dict:
        """Return a structured JSON response from the LLM."""
        raw = self.complete(prompt, system)
        # Strip markdown fences if the model wraps output
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned.strip())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_client(self):
        """Lazily import and build the provider-specific client."""
        provider = self._config.llm_provider.lower()
        if provider == "openai":
            from openai import OpenAI  # type: ignore[import-untyped]

            return OpenAI()
        if provider in ("anthropic", "claude"):
            from anthropic import Anthropic  # type: ignore[import-untyped]

            return Anthropic()
        raise ValueError(f"Unsupported LLM provider: {provider}")

    def _call(self, prompt: str, system: str) -> str:
        """Dispatch to the correct provider."""
        provider = self._config.llm_provider.lower()
        if provider == "openai":
            return self._call_openai(prompt, system)
        return self._call_anthropic(prompt, system)

    def _call_openai(self, prompt: str, system: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=messages,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str, system: str) -> str:
        kwargs: dict = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return response.content[0].text
