#!/usr/bin/env python3
"""Project one donor qualification record into PF-002 campaign state.

This never mutates the canonical run automatically. It emits the state transition that
may be reviewed/committed after a real donor is accepted.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
QUALIFIER = Path(__file__).with_name("qualify_pf002_donor.py")
SPEC = importlib.util.spec_from_file_location("pf002_qualifier", QUALIFIER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

SCHEMA = "hardware_splicer.pf002_campaign_status.v1"


def project_status(record: Mapping[str, Any]) -> dict[str, Any]:
    qualification = MODULE.evaluate(record)
    accepted = qualification["real_donor_accepted"]

    stages = {
        "SELECT": "PASS_ONE_DONOR_QUALIFIED_FOR_ENGINEERING" if accepted else "HOLD_ON_REAL_DONOR_ACCEPTANCE",
        "SPECIFY": "PASS_PRODUCT_AND_BENCHIO_REQUIREMENTS_FROZEN" if accepted else "DRAFT_PRODUCT_CONTRACT_FROZEN_FOR_REVIEW",
        "DESIGN_SCHEMATIC": "READY_BENCHIO_SCHEMATIC" if accepted else "BLOCKED_ON_REAL_DONOR_ACCEPTANCE",
        "VERIFY_SCHEMATIC": "BLOCKED_ON_DESIGN",
        "DESIGN_PCB": "BLOCKED_ON_VERIFIED_SCHEMATIC",
        "VERIFY_PCB": "BLOCKED_ON_PCB",
        "SOURCE": "DONOR_ACCEPTED_SIDE_CAR_NOT_SOURCED" if accepted else "ACTIVE_DONOR_EVIDENCE_REQUIRED",
        "BUILD": "BLOCKED_ON_VERIFIED_PCB_AND_HUMAN_AUTHORITY",
        "PROVE": "BLOCKED_ON_PHYSICAL_ARTIFACT",
        "BENCHMARK": "BLOCKED_ON_PHYSICAL_PROOF",
        "SELL": "BLOCKED_ON_BENCHMARK_AND_HUMAN_DECISION",
    }

    if qualification["decision"] == "SIMULATION_ONLY_NOT_ACCEPTED":
        state = "SIMULATION_REHEARSAL_COMPLETE_REAL_DONOR_REQUIRED"
    elif accepted:
        state = "REAL_DONOR_ACCEPTED_BENCHIO_DESIGN_MAY_START"
    else:
        state = "HOLD_REAL_DONOR_NOT_ACCEPTED"

    return {
        "schema": SCHEMA,
        "run_id": "PF-002",
        "product_id": "benchhmi-v0",
        "state": state,
        "qualification": qualification,
        "projected_stages": stages,
        "design_input": {
            "benchio_contract": "hardware/reference_designs/benchhmi_v0/benchio_contract.json",
            "schematic_design_authorized": accepted,
        },
        "authority": {
            "donor_purchase_authorized": False,
            "donor_disassembly_authorized": False,
            "benchio_schematic_design_authorized": accepted,
            "pcb_design_authorized": False,
            "fabrication_authorized": False,
            "power_on_authorized": False,
            "physical_correctness_proven": False,
            "commercial_conversion_authorized": False,
            "sale_authorized": False,
        },
        "next_action": (
            "Freeze the remaining BenchIO electrical parameters and begin schematic design."
            if accepted
            else "Obtain and qualify one real POS462/B91 donor using the real record template."
        ),
        "boundary": (
            "A real donor acceptance may open bounded BenchIO schematic engineering only. "
            "It cannot authorize PCB fabrication, assembly, power-on, finished-product proof, "
            "batch production, commercial claims, or sale."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    result = project_status(record)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
