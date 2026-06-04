#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


SKU_TABLE = {
    "draft_feasibility": {
        "label": "SKU-1 Draft Feasibility Pack",
        "base_price_usd": 149,
        "revisions": 1,
    },
    "verified_prototype": {
        "label": "SKU-2 Verified Prototype Pack",
        "base_price_usd": 499,
        "revisions": 3,
    },
    "execution_support": {
        "label": "SKU-3 Execution Support Retainer",
        "base_price_usd": 1200,
        "revisions": 999,
    },
}


def _score_complexity(intake: Dict[str, Any]) -> float:
    c = intake.get("constraints", {}) or {}
    score = 1.0
    if float(c.get("max_current_a", 1.0)) > 2.0:
        score += 0.15
    if float(c.get("envelope_w_mm", 120)) > 180:
        score += 0.1
    if intake.get("environment") == "outdoor":
        score += 0.1
    if intake.get("needs", {}).get("manufacturing_package"):
        score += 0.2
    if int(intake.get("deadline_days", 14)) < 7:
        score += 0.2
    return score


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate client proposal from intake JSON.")
    ap.add_argument("--intake", required=True, help="Path to intake JSON")
    ap.add_argument("--out", required=True, help="Output folder")
    args = ap.parse_args()

    intake = json.loads(Path(args.intake).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ptype = str(intake.get("project_type") or "verified_prototype")
    sku_key = ptype if ptype in SKU_TABLE else "verified_prototype"
    sku = SKU_TABLE[sku_key]

    complexity = _score_complexity(intake)
    price = round(float(sku["base_price_usd"]) * complexity, 2)

    if intake.get("needs", {}).get("ongoing_support") and sku_key != "execution_support":
        support_addon = 300.0
    else:
        support_addon = 0.0

    total = round(price + support_addon, 2)

    proposal = {
        "client_name": intake.get("client_name", ""),
        "project_title": intake.get("project_title", ""),
        "recommended_sku": sku["label"],
        "complexity_multiplier": complexity,
        "base_price_usd": sku["base_price_usd"],
        "support_addon_usd": support_addon,
        "total_price_usd": total,
        "included_revisions": sku["revisions"],
        "next_step": "Confirm scope and provide source files/constraints for kickoff.",
    }

    (out_dir / "PROPOSAL.json").write_text(json.dumps(proposal, indent=2), encoding="utf-8")

    md = []
    md.append("# Service Proposal\n")
    md.append(f"- Client: {proposal['client_name']}")
    md.append(f"- Project: {proposal['project_title']}")
    md.append(f"- Recommended SKU: **{proposal['recommended_sku']}**")
    md.append(f"- Base Price: ${proposal['base_price_usd']:.2f}")
    md.append(f"- Complexity Multiplier: {proposal['complexity_multiplier']:.2f}x")
    md.append(f"- Support Add-on: ${proposal['support_addon_usd']:.2f}")
    md.append(f"- Total Quote: **${proposal['total_price_usd']:.2f}**")
    md.append(f"- Included Revisions: {proposal['included_revisions']}")
    md.append("")
    md.append("## Scope Summary")
    md.append("- EE+ME validated design artifacts")
    md.append("- Gate reports (DFM/simulation/risk)")
    md.append("- Revision log and handoff package")
    md.append("")
    md.append("## Next Step")
    md.append(f"- {proposal['next_step']}")
    md.append("")

    (out_dir / "PROPOSAL.md").write_text("\n".join(md), encoding="utf-8")
    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
