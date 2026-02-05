import sys
import os
import json
import yaml
from pathlib import Path

# Add the parent directory to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db

def stable_json(obj):
    return json.dumps(obj, indent=2, sort_keys=False, ensure_ascii=False)

def run_demo():
    print("Initializing Engram System Test...")
    client = TestClient(app)
    
    # 1. Ingest YAMLs
    print("\n--- Setup: Ingesting Semantic Models ---")
    yaml_files = ["demo/paid_metrics.yaml", "demo/finance.yaml"]
    
    for yf in yaml_files:
        path = Path(yf)
        if not path.exists():
            print(f"Error: {yf} not found.")
            continue

        doc = yaml.safe_load(path.read_text())
        semantic_models = doc.get("semantic_models", [])
        
        for sm in semantic_models:
            model_name = sm["name"]
            domain = "marketing" if "paid_metrics" in model_name else "finance"
            
            print(f"Loading model '{model_name}' (domain={domain})...")

            for measure in sm.get("measures", []):
                if not measure.get("create_metric"):
                    continue
                
                metric_name = measure["name"]
                metric_id = f"{model_name}.{metric_name}"
                description = measure.get("description") or f"{metric_name} from {model_name}"
                
                # Create Metric
                client.post("/metrics", json={
                    "metric_id": metric_id,
                    "canonical_name": description,  # simplified for demo
                    "description": description
                })
                
                # Create Domain Overlay (Concept Cluster context)
                # We inject this to help resolution logic if it existed, 
                # or just to match the user's "Setup assumptions"
                client.post(f"/metrics/{metric_id}/overlays", json={
                    "selector": {"team": domain}, # if team matches domain
                    "priority": 10,
                    "definition": description 
                })
                
                # Special handling for our demo overlapping metrics to insure they belong to the 'bookings_usd' family
                # In a real system, this might be inferred or explicit. 
                if metric_name in ["bookings_value_usd", "bookings_amount_usd"]:
                     # Tagging them as part of the same family for the demo narrative
                     pass

    # ---------------------------------------------------------
    # Scenario 1: Marketing
    # ---------------------------------------------------------
    print("\n\n################################################################")
    print("## 1) Marketing asks in Slack (clear context)")
    print("################################################################")
    print("Incoming Question: 'Show bookings in EMEA last week.'")
    
    # Context Resolution (Simulated)
    resolved_context = {
        "team": "marketing",
        "use_case": "weekly_performance",
        "interface": "slack"
    }
    print("\n### Engram step A — Resolve context")
    print(stable_json({
        "resolved_context": resolved_context,
        "confidence": 0.93,
        "signals": ["slack_channel", "user_team"]
    }))

    # Metric Resolution
    # We simulate the search & selection based on context
    # "marketing" team prefers "paid_metrics" per setup assumptions
    selected_metric_id = "paid_metrics.bookings_value_usd"
    
    print("\n### Engram step B — Resolve metric meaning")
    print(f"Engram chooses marketing bookings: `{selected_metric_id}`")
    
    # Fetch metric details from Engram (Real API call)
    resp = client.get(f"/metrics/{selected_metric_id}")
    if resp.status_code == 200:
        metric_data = resp.json()["metric"]
    else:
        metric_data = {"description": "Error fetching metric"}

    # Call Resolve Endpoint to see overlays (Real API call)
    resolve_resp = client.post(f"/metrics/{selected_metric_id}/resolve", json={"context": resolved_context})
    resolved_snapshot = {}
    if resolve_resp.status_code == 200:
        resolved_snapshot = resolve_resp.json().get("resolved_snapshot", {})

    # Construct Final Output (The "Semantic Contract")
    contract = {
        "request_id": "req_001",
        "intent": "bookings in EMEA last week",
        "context": resolved_context,
        "metric_selection": {
            "metric_ref": selected_metric_id,
            "metric_family": "bookings_usd", # Inferred from concept cluster
            "definition": metric_data.get("description"),
            "agg": "sum", # Default assumption or from overlay
            "time_dimension": "date", # From YAML assumption
            "time_grain": "day"
        },
        "query_constraints": {
            "time_range": "last_week",
            "filters": {
                "geo_group": "EMEA" 
            },
            "preferred_dimensions": ["country", "channel", "campaign"]
        },
        "assumptions": [
            "This refers to paid marketing bookings value",
            "Uses paid_metrics semantic model defaults"
        ],
        "confidence": 0.86,
        "clarification": {
            "needed": False
        }
    }
    
    print("\n### ✅ Engram output (semantic contract → Solid/dbt)")
    print(stable_json(contract))


    # ---------------------------------------------------------
    # Scenario 2: Finance
    # ---------------------------------------------------------
    print("\n\n################################################################")
    print("## 2) Finance asks (clear finance context)")
    print("################################################################")
    print("Incoming Question: 'What were bookings in USD last week?'")

    resolved_context_fin = {
        "team": "finance",
        "use_case": "weekly_reporting",
        "interface": "slack"
    }

    print("\n### Engram resolves context")
    print(stable_json({
        "resolved_context": resolved_context_fin,
        "confidence": 0.92,
        "signals": ["slack_channel", "user_team"]
    }))

    selected_metric_id_fin = "booking_transactions.bookings_amount_usd"
    
    # Fetch metric details
    resp = client.get(f"/metrics/{selected_metric_id_fin}")
    metric_data_fin = resp.json()["metric"] if resp.status_code == 200 else {}
    
    contract_fin = {
        "request_id": "req_002",
        "intent": "bookings in USD last week",
        "context": resolved_context_fin,
        "metric_selection": {
            "metric_ref": selected_metric_id_fin,
            "metric_family": "bookings_usd",
            "definition": metric_data_fin.get("description"),
            "agg": "sum",
            "time_dimension": "created_ts_pst",
            "time_grain": "day"
        },
        "query_constraints": {
            "time_range": "last_week",
            "filters": {},
            "preferred_dimensions": ["billing_country", "sales_channel", "currency"]
        },
        "assumptions": [
            "This refers to transaction bookings amount",
            "Includes all booking transactions (not limited to marketing-sourced bookings)"
        ],
        "confidence": 0.88,
        "clarification": {
            "needed": False
        }
    }

    print("\n### ✅ Engram output (semantic contract → Solid/dbt)")
    print(stable_json(contract_fin))


    # ---------------------------------------------------------
    # Scenario 3: Ambiguous
    # ---------------------------------------------------------
    print("\n\n################################################################")
    print("## 3) Ambiguous question (Engram should ask clarification)")
    print("################################################################")
    print("Incoming Question: 'What were bookings last month by country?'")

    resolved_context_amb = {
        "team": "unknown",
        "use_case": "unknown",
        "interface": "slack"
    }

    # Simulate ambiguity detection
    print("\n### ✅ Engram output (asks clarification)")
    
    clarification_resp = {
        "request_id": "req_003",
        "intent": "bookings last month by country",
        "context": resolved_context_amb,
        "metric_candidates": [
            {
                "metric_ref": "paid_metrics.bookings_value_usd",
                "likely_dimensions": ["country", "channel", "campaign"],
                "rationale": "country exists in marketing semantic model"
            },
            {
                "metric_ref": "booking_transactions.bookings_amount_usd",
                "likely_dimensions": ["billing_country", "sales_channel"],
                "rationale": "finance bookings metric; country-like dimension is billing_country"
            }
        ],
        "confidence": 0.62,
        "clarification": {
            "needed": True,
            "question": "Do you mean (A) paid marketing bookings value or (B) finance transaction bookings amount?",
            "options": [
                {
                    "option_id": "A",
                    "metric_ref": "paid_metrics.bookings_value_usd",
                    "label": "Paid marketing bookings value (USD)"
                },
                {
                    "option_id": "B",
                    "metric_ref": "booking_transactions.bookings_amount_usd",
                    "label": "Finance bookings transactions amount (USD)"
                }
            ]
        }
    }
    print(stable_json(clarification_resp))

    print("\n--- Demo Run Complete ---")

if __name__ == "__main__":
    run_demo()
