#!/usr/bin/env python3
"""Import a Refinery commercial-gate PASS into a bounded HS Product Factory run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


STAGES = [
    "DISCOVER",
    "SELECT",
    "SPECIFY",
    "DESIGN_SCHEMATIC",
    "VERIFY_SCHEMATIC",
    "DESIGN_PCB",
    "VERIFY_PCB",
    "SOURCE",
    "BUILD",
    "PROVE",
    "BENCHMARK",
    "SELL",
    "LEARN",
]


def import_seed(seed: Mapping[str, Any], *, run_id: str, opened_at: str) -> dict[str, Any]:
    if seed.get("schema") != "hardware_splicer.product_factory_seed.v1":
        raise ValueError("unsupported Product Factory seed schema")
    authority = seed.get("authority")
    if not isinstance(authority, Mapping):
        raise ValueError("seed authority is required")
    if authority.get("design_work_authorized") is not True:
        raise ValueError("seed does not authorize design work")
    if authority.get("fabrication_authorized") is not False:
        raise ValueError("Refinery seed may not authorize fabrication")
    if authority.get("physical_authority_granted") is not False:
        raise ValueError("Refinery seed may not grant physical authority")

    economics = seed.get("economics")
    engineering = seed.get("engineering_assessment")
    if not isinstance(economics, Mapping) or not isinstance(engineering, Mapping):
        raise ValueError("seed economics and engineering assessment are required")

    target = float(economics.get("target_msrp_usd") or 0)
    cogs = float(economics.get("landed_cogs_ceiling_usd") or 0)
    floor = float(economics.get("minimum_target_gross_margin_fraction") or 0)
    if target <= 0 or cogs <= 0 or not cogs < target:
        raise ValueError("seed economics are invalid")
    if 1 - cogs / target < floor:
        raise ValueError("seed no longer clears its own margin floor")

    stage_rows = []
    state_map = {
        "DISCOVER": "PASS_REFINERY_REVIEWED_MARKET",
        "SELECT": "PASS_REFINERY_COMMERCIAL_GATE",
        "SPECIFY": "READY_FOR_HS_PRODUCT_CONTRACT",
        "DESIGN_SCHEMATIC": "BLOCKED_ON_PRODUCT_CONTRACT",
        "VERIFY_SCHEMATIC": "BLOCKED_ON_DESIGN",
        "DESIGN_PCB": "BLOCKED_ON_SCHEMATIC",
        "VERIFY_PCB": "BLOCKED_ON_PCB",
        "SOURCE": "BLOCKED_ON_VERIFIED_PCB",
        "BUILD": "BLOCKED_ON_SOURCE_AND_HUMAN_AUTHORITY",
        "PROVE": "BLOCKED_ON_PHYSICAL_ARTIFACT",
        "BENCHMARK": "BLOCKED_ON_PHYSICAL_PROOF",
        "SELL": "BLOCKED_ON_BENCHMARK_AND_HUMAN_DECISION",
        "LEARN": "ACTIVE_CONTINUOUS",
    }
    for stage in STAGES:
        evidence = []
        if stage in {"DISCOVER", "SELECT"}:
            evidence.append(str(seed.get("source_candidate_id") or ""))
        stage_rows.append({"id": stage, "state": state_map[stage], "evidence": [e for e in evidence if e]})

    return {
        "schema": "hardware_splicer.product_factory_run.v1",
        "run_id": run_id,
        "product_id": seed.get("product_id"),
        "working_name": seed.get("working_name"),
        "opened_at": opened_at,
        "purpose": "Execute a Refinery-screened commercial hardware hypothesis through Hardware Splicer.",
        "source": {
            "type": "refinery_product_factory_seed",
            "candidate_id": seed.get("source_candidate_id"),
            "job": seed.get("source_job"),
        },
        "stages": stage_rows,
        "metrics": {
            "target_msrp_usd": target,
            "landed_cogs_ceiling_usd": cogs,
            "target_min_gross_margin_fraction": floor,
            "quantity_basis": economics.get("quantity_basis"),
            "cogs_basis": economics.get("cogs_basis"),
            "build_difficulty": engineering.get("build_difficulty"),
            "calibration_regulatory_burden": engineering.get("calibration_regulatory_burden"),
            "hardware_splicer_leverage": engineering.get("hardware_splicer_leverage"),
        },
        "market_evidence": seed.get("market_evidence"),
        "authority": {
            "design_work_authorized": True,
            "product_contract_complete": False,
            "schematic_complete": False,
            "pcb_complete": False,
            "fabrication_ready": False,
            "power_on_ready": False,
            "physical_correctness": "UNPROVEN",
            "commercial_superiority": "UNPROVEN",
            "physical_authority_granted": False,
        },
        "claim_boundary": (
            "A Refinery gate PASS authorizes bounded HS engineering only. Hardware Splicer must independently "
            "establish the product contract, design correctness, supplier evidence, physical proof and benchmark "
            "before any commercial or physical authority can advance."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--opened-at", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    seed = json.loads(args.seed.read_text())
    result = import_seed(seed, run_id=args.run_id, opened_at=args.opened_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
