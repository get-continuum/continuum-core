import yaml
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from scripts.llm_resolver import LLMResolver

class DemoEngine:
    def __init__(self, client, llm_api_key: Optional[str] = None):
        self.client = client
        self.metrics_db: Dict[str, Any] = {}
        self.models: Dict[str, Any] = {}
        self.llm = LLMResolver(api_key=llm_api_key)
        self.aliases_path = Path("demo/user_aliases.json")
        self.aliases_db = self.load_aliases()

    def load_aliases(self) -> List[Dict]:
        if not self.aliases_path.exists():
            return []
        try:
            return json.loads(self.aliases_path.read_text())
        except:
            return []

    def save_alias(self, term: str, context_team: str, metric_id: str):
        self.aliases_db.append({
            "term": term.lower(),
            "context_team": context_team,
            "metric_id": metric_id
        })
        self.aliases_path.write_text(json.dumps(self.aliases_db, indent=2))

    def ingest_yamls(self, yaml_paths: List[str]) -> List[str]:
        # ... (same as before) ...
        logs = []
        for yf in yaml_paths:
            path = Path(yf)
            if not path.exists():
                logs.append(f"Error: {yf} not found.")
                continue

            doc = yaml.safe_load(path.read_text())
            semantic_models = doc.get("semantic_models", [])
            
            for sm in semantic_models:
                model_name = sm["name"]
                model_lower = (model_name or "").lower()
                if "marketing" in model_lower or "paid" in model_lower:
                    domain = "marketing"
                elif "finance" in model_lower:
                    domain = "finance"
                else:
                    domain = "unknown"
                self.models[model_name] = {"domain": domain, "metrics": []}
                
                logs.append(f"Loading model '{model_name}' (domain={domain})...")

                for measure in sm.get("measures", []):
                    if not measure.get("create_metric"):
                        continue
                    
                    metric_name = measure["name"]
                    metric_id = f"{model_name}.{metric_name}"
                    description = measure.get("description") or f"{metric_name} from {model_name}"
                    
                    # Store in local DB for fast lookup in demo
                    self.metrics_db[metric_id] = {
                        "metric_id": metric_id,
                        "canonical_name": description,
                        "description": description,
                        "domain": domain,
                        "model": model_name,
                        "measure_name": metric_name
                    }
                    self.models[model_name]["metrics"].append(metric_id)

                    # Create Metric in Backend
                    self.client.post("/metrics", json={
                        "metric_id": metric_id,
                        "canonical_name": description,
                        "description": description
                    })
                    
                    # Create Domain Overlay
                    self.client.post(f"/metrics/{metric_id}/overlays", json={
                        "selector": {"team": domain},
                        "priority": 10,
                        "overlay_patch": {"definition": {"display": description}}
                    })
        return logs

    def resolve_intent(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate the "Agent" resolving intent.
        Try Memory (Aliases) -> LLM -> Fallback.
        """
        # 0. Check Memory (Active Learning)
        q_lower = question.lower()
        active_team = context.get("team")
        
        for alias in self.aliases_db:
            if alias["term"] in q_lower and alias["context_team"] == active_team:
                m_id = alias["metric_id"]
                if m_id in self.metrics_db:
                    return {
                        "status": "resolved",
                        "resolved_metric": self.metrics_db[m_id],
                        "confidence": 1.0,
                        "reason": f"Found saved alias for '{alias['term']}' in {active_team} context."
                    }

        candidates = list(self.metrics_db.values())
        
        # Revenue fallback (works without LLM key)
        if "revenue" in q_lower:
            rev_candidates = []
            for c in candidates:
                hay = " ".join(
                    [
                        (c.get("metric_id") or ""),
                        (c.get("canonical_name") or ""),
                        (c.get("description") or ""),
                        (c.get("model") or ""),
                        (c.get("measure_name") or ""),
                    ]
                ).lower()
                if "revenue" in hay:
                    rev_candidates.append(c)

            if "campaign" in q_lower:
                marketing = [c for c in rev_candidates if c.get("domain") == "marketing"]
                if marketing:
                    return {
                        "status": "resolved",
                        "resolved_metric": marketing[0],
                        "confidence": 0.92,
                        "reason": "Query mentions campaign; prefer marketing attribution revenue.",
                    }

            user_team = context.get("team")
            if user_team in ("marketing", "finance"):
                matched = [c for c in rev_candidates if c.get("domain") == user_team]
                if matched:
                    return {
                        "status": "resolved",
                        "resolved_metric": matched[0],
                        "confidence": 0.92,
                        "reason": f"Active context '{user_team}' matches revenue metric domain.",
                    }

            if len(rev_candidates) > 1:
                short = sorted(rev_candidates, key=lambda x: x.get("metric_id") or "")[:5]
                return {
                    "status": "ambiguous",
                    "candidates": short,
                    "confidence": 0.6,
                    "reason": "Revenue is ambiguous across domains; select which definition you mean.",
                }
            if len(rev_candidates) == 1:
                return {
                    "status": "resolved",
                    "resolved_metric": rev_candidates[0],
                    "confidence": 0.9,
                    "reason": "Single revenue candidate matched.",
                }
            return {"status": "no_match", "reason": "No revenue metric found"}

        # 1. Try LLM
        if self.llm.client:
            result = self.llm.resolve(question, context, candidates)
            # Normalize LLM output to internal format (simple map for demo)
            if "resolved_metric_id" in result:
                m_id = result["resolved_metric_id"]
                if m_id in self.metrics_db:
                     return {
                        "status": "resolved",
                        "resolved_metric": self.metrics_db[m_id],
                        "confidence": 0.95,
                        "reason": result.get("reason", "LLM Semantic Match")
                    }
            if result.get("status") == "ambiguous":
                # Filter candidates based on LLM suggestion if provided, or fallback
                return {
                     "status": "ambiguous",
                     "candidates": [self.metrics_db[c] for c in result.get("candidate_ids", []) if c in self.metrics_db],
                     "confidence": 0.60,
                     "reason": result.get("reason", "LLM detected ambiguity")
                }
        
        # 2. Fallback: Keyword Matching
        q_lower = question.lower()
        
        # Mock "Brain" for Demo purposes (if no API key)
        if "burn" in q_lower:
             # Find spend/cost metrics
             spend_candidates = []
             for m_id, m_data in self.metrics_db.items():
                 if m_data["measure_name"] in ["spend", "sku_cost", "expenses"]:
                     spend_candidates.append(m_data)
             
             # Filter by context
             user_team = context.get("team")
             matched = [c for c in spend_candidates if c["domain"] == user_team]
             if matched:
                 return {
                    "status": "resolved",
                    "resolved_metric": matched[0],
                    "confidence": 0.85,
                    "reason": f"Mock Brain (Fallback): 'burn' implies '{matched[0]['measure_name']}' in {user_team} context."
                 }
             elif spend_candidates:
                  return {
                     "status": "ambiguous",
                     "candidates": spend_candidates,
                     "confidence": 0.60,
                     "reason": "Mock Brain (Fallback): 'burn' maps to multiple spend metrics."
                }


        target_concept = "bookings"
        if "bookings" not in q_lower:
            return {"status": "no_match", "reason": "Concept not understood"}
        candidates = []
        for m_id, m_data in self.metrics_db.items():
            if m_data["measure_name"] in ["bookings_value_usd", "bookings_amount_usd"]:
                candidates.append(m_data)

        # 1. Exact Context Match
        user_team = context.get("team")
        matched = [c for c in candidates if c["domain"] == user_team]
        
        if len(matched) == 1:
            selected = matched[0]
            return {
                "status": "resolved",
                "resolved_metric": selected,
                "confidence": 0.92,
                "reason": f"Active context '{user_team}' matches metric domain."
            }
        
        # 2. Ambiguity
        if len(candidates) > 1:
            return {
                "status": "ambiguous",
                "candidates": candidates,
                "confidence": 0.60,
                "reason": "Multiple metrics match 'bookings' and no specific context was provided."
            }

        return {"status": "no_match"}
