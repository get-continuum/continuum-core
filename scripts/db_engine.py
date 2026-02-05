from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import json
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import Metric, MetricAlias, Overlay
from scripts.llm_resolver import LLMResolver

class DBEngine:
    def __init__(self, llm_api_key: Optional[str] = None):
        # We don't need the FastAPI TestClient anymore since we talk to DB directly for this script
        self.db: Session = SessionLocal()
        self.llm = LLMResolver(api_key=llm_api_key)
        self.workspace_id = "default"  # simplified for MVP

    def ingest_yamls(self, yaml_paths: List[str]) -> List[str]:
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
                
                logs.append(f"Loading model '{model_name}' (domain={domain})...")

                for measure in sm.get("measures", []):
                    if not measure.get("create_metric"):
                        continue
                    
                    metric_name = measure["name"]
                    metric_id = f"{model_name}.{metric_name}"
                    description = measure.get("description") or f"{metric_name} from {model_name}"
                    
                    # 1. Upsert Metric
                    existing_metric = self.db.get(Metric, (self.workspace_id, metric_id))
                    if not existing_metric:
                        metric = Metric(
                            workspace_id=self.workspace_id,
                            metric_id=metric_id,
                            canonical_name=description,
                            description=description
                        )
                        self.db.add(metric)
                    else:
                        existing_metric.canonical_name = description
                        existing_metric.description = description
                    
                    # 2. Upsert Overlays for domain context
                    # In this phase, we map team -> domain logic.
                    # We'll create an overlay that matches the team name.
                    overlay_stmt = select(Overlay).filter_by(
                        workspace_id=self.workspace_id,
                        metric_id=metric_id,
                        selector={"team": domain}
                    )
                    existing_overlay = self.db.execute(overlay_stmt).scalar_one_or_none()
                    if not existing_overlay:
                        overlay = Overlay(
                            workspace_id=self.workspace_id,
                            metric_id=metric_id,
                            selector={"team": domain},
                            priority=10,
                            overlay_patch={"definition": {"display": description}}
                        )
                        self.db.add(overlay)
        self.db.commit()
        return logs

    def save_alias(self, term: str, context_team: str, metric_id: str):
        # Maps to MetricAlias
        # source_system = "user_override"
        # source_locator = f"{term}:{context_team}"
        
        alias = MetricAlias(
            workspace_id=self.workspace_id,
            metric_id=metric_id,
            source_system="user_learning",
            source_locator=f"{term.lower()}:{context_team}",
            alias_name=term.lower(),
            confidence=1.0
        )
        
        # Upsert logic (simple deletion of collision for MVP)
        try:
            self.db.merge(alias) # Merge handles primary key or unique constraints if configured well, 
            # but MetricAlias PK is UUID. Unique constraint is (workspace, source_system, source_locator).
            # sqlalchemy merge might verify unique constraint? 
            # Safest is to check and delete usually, but let's try straight add and catch or use merge if PK was composite.
            # actually MetricAlias PK is random UUID. merge won't work on unique constraint without lookup.
            
            stmt = select(MetricAlias).filter_by(
                workspace_id=self.workspace_id,
                source_system="user_learning",
                source_locator=f"{term.lower()}:{context_team}"
            )
            existing = self.db.execute(stmt).scalar_one_or_none()
            if existing:
                existing.metric_id = metric_id
            else:
                self.db.add(alias)
            
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Error saving alias: {e}")

    def resolve_intent(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Database-backed resolution:
        1. Check DB Aliases
        2. LLM Resolution (with candidates from DB)
        3. Fallback
        """
        q_lower = question.lower()
        active_team = context.get("team")

        # 1. Check DB Aliases
        stmt = select(MetricAlias).filter_by(
            workspace_id=self.workspace_id,
            source_system="user_learning",
            source_locator=f"{q_lower}:{active_team}"
        )
        alias_match = self.db.execute(stmt).scalar_one_or_none()
        
        if alias_match:
            # Fetch full metric details
            m = self.db.get(Metric, (self.workspace_id, alias_match.metric_id))
            if m:
                # Reconstruct the dict format expected by the frontend
                # Need to infer 'model' and 'domain' from metric_id for display parity
                parts = m.metric_id.split(".")
                model_name = parts[0]
                domain = "marketing" if "paid_metrics" in model_name else "finance"
                
                return {
                    "status": "resolved",
                    "resolved_metric": {
                        "metric_id": m.metric_id,
                        "description": m.description,
                        "model": model_name,
                        "measure_name": parts[1],
                        "domain": domain
                    },
                    "confidence": 1.0,
                    "reason": f"Found saved alias for '{alias_match.alias_name}' in {active_team} context (DB)."
                }

        # 2. Fetch Candidates from DB
        # For simplicity, we fetch all active metrics. In prod, we'd use vector search or FTS.
        all_metrics = self.db.execute(select(Metric).filter_by(status="active")).scalars().all()
        
        candidates = []
        for m in all_metrics:
            parts = (m.metric_id or "").split(".")
            if len(parts) >= 2:
                model_name = parts[0]
                measure_name = ".".join(parts[1:])
            else:
                model_name = "core"
                measure_name = m.metric_id

            model_lower = (model_name or "").lower()
            if "marketing" in model_lower or "paid" in model_lower:
                domain = "marketing"
            elif "finance" in model_lower:
                domain = "finance"
            else:
                domain = "unknown"
            
            candidates.append({
                "metric_id": m.metric_id,
                "canonical_name": m.canonical_name,
                "description": m.description,
                "domain": domain,
                "model": model_name,
                "measure_name": measure_name
            })

        # 2b. Revenue-specific fallback (works without LLM key)
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

            # Strong hint: “by campaign” implies marketing attribution.
            if "campaign" in q_lower:
                marketing = [c for c in rev_candidates if c.get("domain") == "marketing"]
                if marketing:
                    return {
                        "status": "resolved",
                        "resolved_metric": marketing[0],
                        "confidence": 0.92,
                        "reason": "Query mentions campaign; prefer marketing attribution revenue.",
                    }

            if active_team in ("marketing", "finance"):
                domain_match = [c for c in rev_candidates if c.get("domain") == active_team]
                if domain_match:
                    return {
                        "status": "resolved",
                        "resolved_metric": domain_match[0],
                        "confidence": 0.92,
                        "reason": f"Active context '{active_team}' matches revenue metric domain.",
                    }

            if len(rev_candidates) == 1:
                return {
                    "status": "resolved",
                    "resolved_metric": rev_candidates[0],
                    "confidence": 0.9,
                    "reason": "Single revenue candidate matched.",
                }

            if len(rev_candidates) > 1:
                # Keep the list short and stable for UI.
                short = sorted(rev_candidates, key=lambda x: x.get("metric_id") or "")[:5]
                return {
                    "status": "ambiguous",
                    "candidates": short,
                    "confidence": 0.6,
                    "reason": "Revenue is ambiguous across domains; select which definition you mean.",
                }

            return {"status": "no_match", "reason": "No revenue metric found"}

        # 3. LLM Resolution
        if self.llm.client:
            result = self.llm.resolve(question, context, candidates)
            if "resolved_metric_id" in result:
                m_id = result["resolved_metric_id"]
                selected = next((c for c in candidates if c["metric_id"] == m_id), None)
                if selected:
                     return {
                        "status": "resolved",
                        "resolved_metric": selected,
                        "confidence": 0.95,
                        "reason": result.get("reason", "LLM Semantic Match (DB-backed)")
                    }
            if result.get("status") == "ambiguous":
                # Filter candidates based on LLM suggestion
                suggested_ids = result.get("candidate_ids", [])
                filtered = [c for c in candidates if c["metric_id"] in suggested_ids]
                return {
                     "status": "ambiguous",
                     "candidates": filtered if filtered else candidates[:3], # Fallback to top 3 if logic fails
                     "confidence": 0.60,
                     "reason": result.get("reason", "LLM detected ambiguity")
                }

        # 4. Fallback: Keyword Matching
        target_concept = "bookings"
        if "bookings" not in q_lower and "burn" not in q_lower:
             return {"status": "no_match", "reason": "Concept not understood"}
        
        # Re-using the logic from DemoEngine for consistency if no LLM
        filtered_candidates = [c for c in candidates if c["measure_name"] in ["bookings_value_usd", "bookings_amount_usd", "spend", "expenses"]]
        
        if "burn" in q_lower:
             # Burn logic
             spend_candidates = [c for c in filtered_candidates if c["measure_name"] in ["spend", "expenses"]]
             matched = [c for c in spend_candidates if c["domain"] == active_team]
             if matched:
                 return {"status": "resolved", "resolved_metric": matched[0], "confidence": 0.85, "reason": "Mock Brain (DB): burn -> spend"}
             elif spend_candidates:
                 return {"status": "ambiguous", "candidates": spend_candidates, "confidence": 0.60, "reason": "Mock Brain (DB): Ambiguous burn"}

        # Bookings Logic
        booking_candidates = [c for c in filtered_candidates if "bookings" in c["measure_name"]]
        matched = [c for c in booking_candidates if c["domain"] == active_team]
        
        if len(matched) == 1:
            return {
                "status": "resolved",
                "resolved_metric": matched[0],
                "confidence": 0.92,
                "reason": f"Active context '{active_team}' matches metric domain (DB)."
            }
        
        if len(booking_candidates) > 1:
            return {
                "status": "ambiguous",
                "candidates": booking_candidates,
                "confidence": 0.60,
                "reason": "Multiple metrics match 'bookings' (DB)."
            }

        return {"status": "no_match"}
