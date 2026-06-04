#!/usr/bin/env python3
"""Create a salvage-to-product workflow report from analyses or listings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("data/salvage_inventory.json"))
    parser.add_argument("--analysis", type=Path, action="append", default=[], help="Analysis JSON from analyze_board_understanding.py")
    parser.add_argument("--listing", type=Path, action="append", default=[], help="Listing JSON with price_usd/expected_capabilities")
    parser.add_argument("--no-commit", action="store_true", help="Do not write assets into inventory")
    parser.add_argument("--output", type=Path, default=Path("eval/salvage_workflow_report.json"))
    args = parser.parse_args()

    engine = SalvageWorkflowEngine(args.inventory)
    reports = []
    for analysis_path in args.analysis:
        payload = _load_json(analysis_path)
        analysis = payload.get("results") or payload
        if "board_understanding" not in analysis and "summary" in payload:
            analysis = {
                "board_understanding": payload.get("board_understanding", {}),
                "marking_analysis": payload.get("marking_analysis", {}),
                "machine_connection_map": payload.get("machine_connection_map", {}),
                "defect_inspection": payload.get("defect_inspection", {}),
                "salvage_opportunities": payload.get("salvage_opportunities", {}),
            }
        reports.append(engine.ingest_analysis(analysis, source=str(analysis_path), commit=not args.no_commit))

    market_context = {"listings": []}
    for listing_path in args.listing:
        listing_payload = _load_json(listing_path)
        listings = listing_payload if isinstance(listing_payload, list) else [listing_payload]
        for listing in listings:
            market_context["listings"].append(listing)
            reports.append(engine.ingest_listing(listing, commit=not args.no_commit))

    final_report = engine.plan_from_inventory(market_context=market_context if market_context["listings"] else None)
    payload = {
        "ingest_reports": reports,
        "final_report": final_report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    decision = final_report.get("decision", {})
    package = final_report.get("build_package", {})
    print(f"Decision: {decision.get('action')} - {decision.get('reason')}")
    if package.get("target"):
        print(f"Build package: {package.get('package_type')} -> {package.get('target', {}).get('name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
