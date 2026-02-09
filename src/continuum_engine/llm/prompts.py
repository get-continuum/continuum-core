"""Prompt templates for LLM-powered scoring and compilation."""

# ---------------------------------------------------------------------------
# Ambiguity scoring
# ---------------------------------------------------------------------------

AMBIGUITY_SCORE_SYSTEM = (
    "You are a decision-analysis assistant. You evaluate how ambiguous a "
    "software-engineering decision is.  Respond ONLY with valid JSON."
)

AMBIGUITY_SCORE_TEMPLATE = """\
Given this decision context, score the ambiguity from 0.0 (crystal-clear) to 1.0 (totally ambiguous).

Decision:
  Title: {title}
  Rationale: {rationale}
  Options considered: {options}
  Stakeholders: {stakeholders}

Return JSON: {{"score": <float>, "reason": "<brief explanation>"}}
"""

# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

RISK_SCORE_SYSTEM = (
    "You are a risk-analysis assistant. You evaluate how risky it is to "
    "perform an action given existing decisions.  Respond ONLY with valid JSON."
)

RISK_SCORE_TEMPLATE = """\
Given the following decision and action context, score the risk from 0.0 (no risk) to 1.0 (critical risk).

Decision:
  Title: {title}
  Scope: {scope}
  Rationale: {rationale}
  Status: {status}

Action context:
  {context}

Return JSON: {{"score": <float>, "reason": "<brief explanation>"}}
"""

# ---------------------------------------------------------------------------
# Decision compilation
# ---------------------------------------------------------------------------

COMPILE_DECISION_SYSTEM = (
    "You are a decision-compiler assistant.  Extract enforcement rules from "
    "a decision record.  Respond ONLY with valid JSON."
)

COMPILE_DECISION_TEMPLATE = """\
Extract enforcement rules from this decision:

Decision:
  Title: {title}
  Rationale: {rationale}
  Options considered: {options}

Return JSON:
{{
  "rules": [
    {{"name": "<rule name>", "action": "block|prefer|confirm", "pattern": "<what it matches>", "reason": "<why>"}}
  ],
  "blocked_patterns": ["<pattern>", ...],
  "required_confirmations": ["<condition>", ...]
}}
"""
