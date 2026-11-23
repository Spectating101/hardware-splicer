"""Run the digital company study against HS with fictional inputs and temporary storage."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "circuit-ai"))
from src.intelligence.salvage_portfolio_planner import SalvagePortfolioPlanner
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine


def replay():
    pile = [
        {"title": "Flatbed scanner", "available_parts": ["carriage", "belt", "rail"]},
        {"title": "USB desk lamp", "available_parts": ["LED bar", "bracket"]},
        {"title": "USB webcam", "available_parts": ["USB camera module"]},
    ]
    portfolio = SalvagePortfolioPlanner().plan({"items": pile, "goal": "Make an inspection fixture"})
    listing = {
        "id": "sample-1", "title": "Uninspected USB controller offer",
        "price_usd": 6, "shipping_usd": 2, "labor_usd": 1.5,
        "expected_capabilities": ["controller"], "expected_parts": ["esp32"],
    }
    observations = []
    with TemporaryDirectory() as temp:
        workflow = SalvageWorkflowEngine(Path(temp) / "inventory.json")
        for _ in range(2):
            report = workflow.ingest_listing(listing)["report"]
            inventory = report["inventory"]
            offers = [row for row in report["opportunity_report"]["opportunities"]
                      if row["type"] == "ecommerce_arbitrage"]
            observations.append({
                "records": inventory["unique_records"],
                "status_counts": inventory["by_test_status"],
                "reported_inventory_usd": inventory["estimated_inventory_value_usd"],
                "adjusted_margin_estimates_usd": [o["adjusted_margin_usd"] for o in offers],
                "decision": report["decision"],
            })
    return {
        "inputs": {"pile": pile, "fictional_offer": listing},
        "physical_units_received": 0,
        "build_options": [{"name": row["name"], "sources": row["source_items"]}
                          for row in portfolio["build_portfolio"]],
        "successive_imports_of_same_offer": observations,
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
