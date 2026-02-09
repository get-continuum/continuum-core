# Continuum Engine (core)

Private engine implementations for Continuum. This directory will be extracted into its own repository (`get-continuum/continuum-engine`) when ready.

## License

BSL-1.1 (Business Source License). See [LICENSE](LICENSE).

## What this contains

Full implementations of the abstract hooks defined in the OSS SDK:

- **AmbiguityScorer** -- LLM-based ambiguity scoring with heuristic fallback
- **DecisionCompiler** -- Extract enforcement rules from decision rationale via LLM
- **RiskScorer** -- Assess action risk against existing decisions
- **Advanced Policies** -- Gradual rollout, team-scoped, override approval, temporal decay
- **Intent Resolver** -- Memory-hit + candidate + context matching + ambiguity detection
- **Context Resolver** -- Overlay-based resolution with selector matching and specificity ordering
- **LLM Layer** -- Unified OpenAI/Anthropic client with retry, fallback, and structured output

## Architecture

```
core/ imports from continuum (OSS SDK)
continuum (OSS SDK) NEVER imports from core/
```

## Development

```bash
pip install -e oss/sdk/python
pip install -e "core[dev]"
pytest core/tests/ -v
```
