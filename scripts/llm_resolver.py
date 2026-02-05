import os
import json
from openai import OpenAI

class LLMResolver:
    def __init__(self, api_key: str = None):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            self.client = None
            print("Warning: No OpenAI API Key found. LLM Resolver will not work.")
        else:
            self.client = OpenAI(api_key=key)

    def resolve(self, query: str, context: dict, candidates: list) -> dict:
        if not self.client:
            return {"status": "error", "reason": "No LLM Client available"}

        # Construct System Prompt
        system_prompt = """You are Engram, a Semantic Router for an Enterprise Data Warehouse. 
Your goal is to map a vaguely worded user question to a specific metric definition.

You have access to:
1. The User's Context (Who they are).
2. A list of Candidate Metrics (What is available).

Rules:
- If the user's intent clearly matches a metric given their context, select it.
- If the user's intent is ambiguous (could match multiple equally well), ask for clarification.
- If no metric matches, say "no_match".
- Output PURE JSON ONLY."""

        # Construct User Prompt
        candidates_preview = []
        for c in candidates:
            candidates_preview.append({
                "id": c["metric_id"],
                "description": c["description"],
                "domain": c["domain"],
                "model": c["model"]
            })

        user_content = json.dumps({
            "query": query,
            "user_context": context,
            "candidates": candidates_preview
        }, indent=2)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use a fast model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Resolve this:\n{user_content}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            return json.loads(raw_content)
        except Exception as e:
            return {"status": "error", "reason": str(e)}
