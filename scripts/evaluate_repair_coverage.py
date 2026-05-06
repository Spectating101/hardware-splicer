#!/usr/bin/env python3
"""Evaluate Circuit-AI coverage against common repair/restoration item classes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.intelligence.repair_market_coverage import RepairMarketCoverage


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate repair market coverage")
    parser.add_argument("--query", action="append", default=[], help="video title/item query; repeatable")
    parser.add_argument("--output", required=True, help="JSON output path")
    args = parser.parse_args()

    coverage = RepairMarketCoverage()
    payload = {
        "portfolio": coverage.portfolio(),
        "queries": [coverage.evaluate_text(query) for query in args.query],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {output}")

    summary = payload["portfolio"]["summary"]
    print(f"weighted_coverage={summary['weighted_coverage']} strong={summary['strong_count']} partial={summary['partial_count']} weak={summary['weak_count']}")
    for result in payload["queries"]:
        top = result["top_matches"][0]
        print(f"{result['query']} -> {top['label']} coverage={top['coverage']} relevance={top['relevance']} level={top['coverage_level']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
