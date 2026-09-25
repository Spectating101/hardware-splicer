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
        "SELECT": "PASS_ONE_DONOR_QUALIFIED_FOR_ENGINEERING" if accepted else "AWAITING_REAL_DONOR_ACCEPTANCE",
        "SPECIFY": "PASS_PRODUCT_AND_BENCHIO_REQUIREMENTS_FROZEN" if accepted else "PASS_BENCHIO_ARCHITECTURE_FROZEN_DONOR_INTEGRATION_PENDING",
        "DESIGN_SCHEMATIC": "READY_BENCHIO_STANDALONE_SCHEMATIC",
        "VERIFY_SCHEMATIC": "QUEUED_AFTER_BENCHIO_SCHEMATIC",
        "DESIGN_PCB": "QUEUED_AFTER_VERIFIED_BENCHIO_SCHEMATIC",
        "VERIFY_PCB": "QUEUED_AFTER_PCB",
        "SOURCE": "DONOR_ACCEPTED_SIDE_CAR_NOT_SOURCED" if accepted else "ACTIVE_DONOR_EVIDENCE_REQUIRED",
        "BUILD": "QUEUED_AFTER_VERIFIED_PCB_AND_HUMAN_AUTHORITY",
        "PROVE": "QUEUED_AFTER_PHYSICAL_ARTIFACT",
        "BENCHMARK": "QUEUED_AFTER_PHYSICAL_PROOF",
        "SELL": "QUEUED_AFTER_BENCHMARK_AND_HUMAN_DECISION",
    }

    if qualification["decision"] == "SIMULATION_REHEARSAL_COMPLETE_REAL_EVIDENCE_PENDING":
        state = "SIMULATION_REHEARSAL_COMPLETE_REAL_DONOR_REQUIRED"
    elif accepted:
        state = "REAL_DONOR_ACCEPTED_BENCHIO_DESIGN_MAY_START"
    else:
        state = "AWAITING_REAL_DONOR_ACCEPTANCE"

    return {
        "schema": SCHEMA,
        "run_id": "PF-002",
        "product_id": "benchhmi-v0",
        "state": state,
        "qualification": qualification,
        "projected_stages": stages,
        "design_input": {
            "benchio_contract": "hardware/reference_designs/benchhmi_v0/benchio_contract.json",
            "schematic_design_authorized": True,
            "system_integration_authorized": accepted,
        },
        "authority": {
            "donor_purchase_authorized": False,
            "donor_disassembly_authorized": False,
            "benchio_schematic_design_authorized": True,
            "benchio_system_integration_authorized": accepted,
            "pcb_design_authorized": False,
            "fabrication_authorized": False,
            "power_on_authorized": False,
            "physical_correctness_proven": False,
            "commercial_conversion_authorized": False,
            "sale_authorized": False,
        },
        "next_action": (
            "Begin standalone BenchIO schematic design and integrate with the accepted donor in parallel."
            if accepted
            else "Begin standalone BenchIO schematic design; obtain a real POS462/B91 in parallel for later system integration."
        ),
        "status_vocabulary": {
            "normal_dependency": ["AWAITING_*", "QUEUED_AFTER_*", "READY_*", "EVIDENCE_PENDING_*"],
            "blocked_reserved_for": "actual defect, contradiction, failed verification, or safety stop",
        },
        "boundary": (
            "BenchIO standalone schematic engineering is open because its donor boundary is standard external USB. "
            "A real donor remains mandatory for BenchHMI system integration. Neither state authorizes PCB fabrication, assembly, power-on, finished-product proof, "
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
