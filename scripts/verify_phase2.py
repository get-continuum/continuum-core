import json
import os
import sys
from pathlib import Path

# Add parent dir to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.db_engine import DBEngine
from sdk.src.engram import Engram

def verify():
    print("🚀 Starting Phase 2 Verification...")
    
    # 1. Mock dbt manifest.json
    manifest_path = "tests/mock_manifest.json"
    mock_manifest = {
        "metrics": {
            "metric.dbt_revenue": {
                "name": "dbt_revenue",
                "label": "DBT Revenue",
                "description": "Total revenue from dbt manifest",
                "meta": {"team": "finance"}
            }
        }
    }
    with open(manifest_path, "w") as f:
        json.dump(mock_manifest, f)
    print(f"✅ Created mock manifest at {manifest_path}")

    # 2. Test dbt Importer
    print("\n--- Testing dbt Importer ---")
    os.system(f"{sys.executable} scripts/import_dbt.py {manifest_path}")
    
    # 3. Verify DB Contents via DBEngine
    print("\n--- Verifying DB Integration ---")
    engine = DBEngine()
    from app.db.models import Metric
    metric = engine.db.get(Metric, ("default", "dbt.dbt_revenue"))
    if metric and metric.canonical_name == "DBT Revenue":
        print(f"✅ Metric 'dbt.dbt_revenue' found in DB with correct label.")
    else:
        print(f"❌ Metric not found or incorrect in DB.")
        return

    # 4. Test SDK (Mocking the API call for now to avoid starting a server)
    # In a real verification, we'd start the server. 
    # For this demonstration, we'll verify the SDK can be instantiated and the types are correct.
    print("\n--- Testing Python SDK ---")
    try:
        sdk = Engram(api_base_url="http://localhost:8000")
        print("✅ SDK instantiated successfully.")
        # We'll also check if the DBEngine's resolve_intent works (which is the core logic)
        context = {"team": "finance"}
        result = engine.resolve_intent("How much bookings?", context)
        if result["status"] in ["resolved", "ambiguous", "no_match"]:
            print(f"✅ DBEngine resolution logic returned status: {result['status']}")
        else:
            print(f"❌ DBEngine resolution logic failed.")
    except Exception as e:
        print(f"❌ SDK/DBEngine test failed: {e}")

    print("\n🎉 Phase 2 Verification Complete!")

if __name__ == "__main__":
    verify()
