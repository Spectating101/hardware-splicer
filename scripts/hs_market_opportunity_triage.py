#!/usr/bin/env python3
"""HS opportunity triage over independently acquired market observations.

Uses PR #295's observed pack and PR #294's canonical release decision.
No network, no seller contact, no purchase or commercialization authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.market_opportunity_triage import (
    OpportunityEvidenceError, qualify,
)


def repo_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise OpportunityEvidenceError("missing evidence path")
    path = Path(relative)
    if path.is_absolute():
        raise OpportunityEvidenceError("absolute evidence paths not permitted")
    resolved = (ROOT / path).resolve()
    if not resolved.is_relative_to(ROOT):
        raise OpportunityEvidenceError("cannot access outside HS checkout")
    return resolved


def run(*, signals_path: str, handoff_path: str,
        plan_path: str = "examples/cyberdeck/dual_touch/market/discovery_plan.json",
        rules_path: str = "examples/cyberdeck/dual_touch/market/opportunity_rules.json",
        previous_path: str | None = None) -> dict:
    return qualify(
        source_bytes=repo_path(signals_path).read_bytes(),
        handoff=json.loads(repo_path(handoff_path).read_text(encoding="utf-8")),
        plan=json.loads(repo_path(plan_path).read_text(encoding="utf-8")),
        rules=json.loads(repo_path(rules_path).read_text(encoding="utf-8")),
        previous_bytes=repo_path(previous_path).read_bytes() if previous_path else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    base = "examples/cyberdeck/dual_touch/market/"
    parser.add_argument("--signals", default=base + "evidence/live_market_signals.json")
    parser.add_argument("--handoff", default=base + "evidence/live_commercial_handoff.json")
    parser.add_argument("--plan", default=base + "discovery_plan.json")
    parser.add_argument("--rules", default=base + "opportunity_rules.json")
    parser.add_argument("--previous-signals")
    parser.add_argument("--out", default=base + "evidence/live_opportunity_triage.json")
    opts = parser.parse_args()
    result = run(signals_path=opts.signals, handoff_path=opts.handoff,
                 plan_path=opts.plan, rules_path=opts.rules, previous_path=opts.previous_signals)
    out = repo_path(opts.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for lane in result["opportunities"]:
        print(f"{lane['research_lane_id']}: "
              f"{len(lane['problem_reports'])} issue reports, "
              f"{len(lane['competing_model_title_matches'])} model-title groups, "
              f"{lane['triage_decision']}")
    print(f"Review queue: {len(result['review_queue']['ambiguous_listings'])} ambiguous listings; "
          f"source requests with failures: {len(result['collection_failures'])}")
    print("Commercial state: research only; inventory permitted:", result["safe_to_order_inventory"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
