"""Isolated runner: imports the Circuit-AI SalvageWorkflowEngine in a fresh interpreter.

Circuit-AI imports as ``src.intelligence``; other HS packages also use the top-level name ``src`` and a
combined pytest process binds it to the wrong one. A subprocess avoids the collision entirely.
stdin: JSON {repo, inventory_path, listings: [{listing, notes}]}; stdout: JSON summary.
"""
import json
import sys

payload = json.load(sys.stdin)
sys.path.insert(0, payload["repo"] + "/apps/circuit-ai")
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine  # noqa: E402

engine = SalvageWorkflowEngine(inventory_path=payload["inventory_path"])
ids = []
for row in payload["listings"]:
    asset = engine.ingest_listing(row["listing"], commit=True)["created_asset"]["asset_id"]
    engine.record_test_result(asset, "bench_verified", condition="used_tested", notes=row["notes"])
    ids.append(asset)
print(json.dumps({"ingested_assets": ids, "inventory": engine.inventory_summary()}))
