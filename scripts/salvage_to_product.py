#!/usr/bin/env python3
"""Run the full scan/listing-to-build-package pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.intelligence.salvage_pipeline import SalvageToProductPipeline
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="*", type=Path, help="Board/module image(s), front/back/crops accepted")
    parser.add_argument("--listing", action="append", type=Path, default=[], help="Listing JSON file or JSON list")
    parser.add_argument("--inventory", type=Path, default=Path("data/salvage_inventory.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("eval/salvage_to_product"))
    parser.add_argument("--backend", default="hybrid", choices=["auto", "hybrid", "yolo", "classical"])
    parser.add_argument("--ocr", action="store_true", help="Enable OCR for markings/labels")
    parser.add_argument("--no-commit", action="store_true", help="Do not write assets into the persistent inventory")
    args = parser.parse_args()

    backend = None if args.backend == "auto" else args.backend
    pipeline = SalvageToProductPipeline(workflow=SalvageWorkflowEngine(args.inventory))
    result = pipeline.run_from_paths(
        image_paths=args.images,
        listing_paths=args.listing,
        backend=backend,
        enable_ocr=args.ocr,
        commit=not args.no_commit,
        output_dir=args.output_dir,
    )
    report = result.get("workflow_report", {})
    decision = report.get("decision", {})
    package = report.get("build_package", {})
    print(f"Wrote artifacts to {args.output_dir}")
    print(f"Decision: {decision.get('action')} - {decision.get('reason')}")
    if package:
        print(f"Package: {package.get('package_type')} -> {(package.get('target') or {}).get('name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
