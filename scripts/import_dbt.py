import json
import sys
from pathlib import Path
from typing import List, Optional

# Add parent dir to path if needed for imports
sys.path.append(str(Path(__file__).parent.parent))

from scripts.db_engine import DBEngine

def import_from_manifest(manifest_path: str):
    path = Path(manifest_path)
    if not path.exists():
        print(f"Error: manifest.json not found at {manifest_path}")
        return

    print(f"Reading manifest from {manifest_path}...")
    with open(path, "r") as f:
        manifest = json.load(f)

    # dbt manifest.json structure: "metrics" is a top-level key
    metrics = manifest.get("metrics", {})
    if not metrics:
        print("No metrics found in manifest.")
        return

    print(f"Found {len(metrics)} metrics. Initializing DB engine...")
    engine = DBEngine()
    
    import_count = 0
    for metric_unique_id, node in metrics.items():
        # Extact dbt metric details
        metric_name = node.get("name")
        label = node.get("label") or metric_name
        description = node.get("description") or f"dbt metric: {metric_name}"
        
        # dbt metrics usually belong to a model or source, but in the manifest 
        # we can just use the unique_id or name.
        # For Engram parity, we'll use 'dbt' as the source system if we were doing aliases,
        # but here we are creating the base Metric.
        
        metric_id = f"dbt.{metric_name}"
        
        print(f"  -> Importing {metric_id} ({label})")
        
        # We can reuse the DBEngine's logic for upserting metrics
        # but DBEngine.ingest_yamls is specific to YAMLs. 
        # Let's add a direct add_metric method to DBEngine or just do it here.
        # Actually, adding 'add_metric' to DBEngine is cleaner for the SDK too.
        
        # For now, let's just use the DB directly since we have it in DBEngine
        from app.db.models import Metric
        
        existing_metric = engine.db.get(Metric, (engine.workspace_id, metric_id))
        if not existing_metric:
            metric = Metric(
                workspace_id=engine.workspace_id,
                metric_id=metric_id,
                canonical_name=label,
                description=description
            )
            engine.db.add(metric)
        else:
            existing_metric.canonical_name = label
            existing_metric.description = description
            
        import_count += 1

    engine.db.commit()
    print(f"Done. Imported {import_count} metrics.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_dbt.py path/to/manifest.json")
    else:
        import_from_manifest(sys.argv[1])
