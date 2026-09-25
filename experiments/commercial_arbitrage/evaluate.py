#!/usr/bin/env python3
"""Fail-closed commercial design gate for Hardware Splicer experiments.

This is intentionally not a market-size model. It answers one narrower question:
is a product hypothesis economically and technically strong enough to justify
spending engineering time on a schematic?
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_SCAN = HERE / "market_scan_2026-09-23.json"
DEFAULT_CONTRACT = ROOT / "hardware" / "reference_designs" / "proofpod_v0" / "product_contract.json"


def evaluate(scan: dict, contract: dict) -> dict:
    economics = contract["economics"]
    board_margin = 1 - (
        economics["board_only_landed_cogs_ceiling_usd_at_100"]
        / economics["board_only_msrp_usd"]
    )
    kit_margin = 1 - (
        economics["kit_landed_cogs_ceiling_usd_at_100"]
        / economics["kit_msrp_usd"]
    )

    candidate = next(
        row for row in scan["candidate_products"]
        if row["id"] == contract["product_id"]
    )
    usd_benchmarks = [
        row for row in scan["benchmarks"]
        if row["currency"] == "USD" and "price" in row
    ]
    professional = [
        row for row in usd_benchmarks
        if row["id"] in {"dediprog-sf100", "total-phase-aardvark"}
    ]
    low_cost_floor = [
        row for row in usd_benchmarks
        if row["price"] <= 20
    ]

    checks = {
        "board_margin": board_margin >= economics["minimum_target_gross_margin_fraction"],
        "kit_margin": kit_margin >= economics["minimum_target_gross_margin_fraction"],
        "two_professional_anchors": len(professional) >= 2,
        "professional_price_gap": all(
            row["price"] >= economics["kit_msrp_usd"] * 2.5
            for row in professional
        ),
        "low_cost_floor_acknowledged": bool(low_cost_floor),
        "build_difficulty_bounded": candidate["build_difficulty"] <= 3,
        "calibration_burden_bounded": candidate["calibration_regulatory_burden"] <= 3,
        "hardware_splicer_leverage": candidate["hardware_splicer_leverage"] >= 4,
        "commercial_claims_still_unvalidated": (
            contract["authority"]["commercial_claims_validated"] is False
        ),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "product_id": contract["product_id"],
        "decision": "ADVANCE_TO_SCHEMATIC" if not blockers else "HOLD",
        "checks": checks,
        "blockers": blockers,
        "computed": {
            "board_margin_fraction_at_cogs_ceiling": round(board_margin, 4),
            "kit_margin_fraction_at_cogs_ceiling": round(kit_margin, 4),
            "professional_anchor_ids": [row["id"] for row in professional],
            "low_cost_floor_ids": [row["id"] for row in low_cost_floor],
        },
        "boundary": (
            "ADVANCE_TO_SCHEMATIC authorizes design work only; it does not validate "
            "market demand, physical correctness, fabrication, or commercial superiority."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", type=Path, default=DEFAULT_SCAN)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    result = evaluate(
        json.loads(args.scan.read_text()),
        json.loads(args.contract.read_text()),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["decision"] == "ADVANCE_TO_SCHEMATIC" else 2)


if __name__ == "__main__":
    main()
