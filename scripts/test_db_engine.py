from scripts.db_engine import DBEngine
from sqlalchemy import text

print("Initializing DBEngine...")
engine = DBEngine()

print("Ingesting YAMLs...")
logs = engine.ingest_yamls(["demo/paid_metrics.yaml", "demo/finance.yaml"])
for l in logs:
    print(l)

print("\nVerifying DB Content...")
with engine.db as session:
    metrics = session.execute(text("SELECT * FROM metrics")).fetchall()
    print(f"Metrics count: {len(metrics)}")
    for m in metrics:
        print(f" - {m.metric_id} ({m.status})")

print("\nDBEngine verification complete.")
