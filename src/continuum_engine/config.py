"""Configuration for the Continuum engine."""

from __future__ import annotations

import os

from pydantic import BaseModel


class EngineConfig(BaseModel):
    """Engine configuration with sensible defaults.

    Values can be overridden via environment variables with the
    ``CONTINUUM_ENGINE_`` prefix (e.g. ``CONTINUUM_ENGINE_LLM_PROVIDER``).
    """

    llm_provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 1024
    retry_attempts: int = 3
    backoff_factor: float = 2.0
    fallback_to_heuristic: bool = True

    @classmethod
    def from_env(cls) -> EngineConfig:
        """Build config from ``CONTINUUM_ENGINE_*`` environment variables."""
        prefix = "CONTINUUM_ENGINE_"
        overrides: dict = {}
        for field_name, field_info in cls.model_fields.items():
            env_key = f"{prefix}{field_name.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                # Coerce to the expected type
                annotation = field_info.annotation
                if annotation is bool:
                    overrides[field_name] = env_val.lower() in ("1", "true", "yes")
                elif annotation is int:
                    overrides[field_name] = int(env_val)
                elif annotation is float:
                    overrides[field_name] = float(env_val)
                else:
                    overrides[field_name] = env_val
        return cls(**overrides)
