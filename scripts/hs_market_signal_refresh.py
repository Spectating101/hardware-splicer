#!/usr/bin/env python3
"""Refresh public market observations. No orders, messages, or build authorization."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.market_signal_acquisition import AcquisitionError, acquire, _check_plan


def inside_repo(path: str) -> Path:
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT):
        raise AcquisitionError("output/input outside repository")
    return p


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="examples/cyberdeck/dual_touch/market/discovery_plan.json")
    parser.add_argument("--out", default="examples/cyberdeck/dual_touch/market/evidence/live_market_signals.json")
    parser.add_argument("--plan-only", action="store_true", help="validate/describe jobs without external requests")
    parser.add_argument("--strict", action="store_true", help="fail if any external query failed")
    args = parser.parse_args()
    plan = json.loads(inside_repo(args.plan).read_text(encoding="utf-8"))
    _check_plan(plan)
    if args.plan_only:
        print(json.dumps({"jobs": [x["id"] for x in plan["jobs"]], "network_calls": 0}))
        return 0
    result = acquire(plan, observed=datetime.now(timezone.utc))
    path = inside_repo(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    d = result["discovery"]
    print(f"Signals: {len(result['signals'])}; failures: {len(d['failures'])}; saved: {path}")
    if not result["signals"]:
        return 2  # never disguise a dead source network as refreshed research
    if args.strict and d["failures"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
