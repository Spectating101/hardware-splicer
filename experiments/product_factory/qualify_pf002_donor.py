#!/usr/bin/env python3
"""Evaluate one PF-002 POS462 donor acceptance record.

A simulated record can exercise the entire acceptance workflow but can never satisfy
real-donor acceptance or unlock downstream physical/design authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "hardware_splicer.donor_acceptance_record.v1"
RESULT_SCHEMA = "hardware_splicer.donor_acceptance_result.v1"

REQUIRED_CHECKS = (
    "identity",
    "cold_boot",
    "lcd",
    "touch",
    "ethernet",
    "usb",
    "com_ports",
    "storage",
    "thermal",
    "power_system",
)


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8")


def evaluate(record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("schema") != SCHEMA:
        raise ValueError("unsupported donor acceptance schema")

    donor = record.get("donor")
    if not isinstance(donor, Mapping):
        raise ValueError("donor identity is required")

    checks = record.get("checks")
    if not isinstance(checks, Mapping):
        raise ValueError("checks mapping is required")

    blockers: list[str] = []
    warnings: list[str] = []

    if str(donor.get("manufacturer") or "").strip().casefold() != "flytech":
        blockers.append("manufacturer_not_flytech")
    if str(donor.get("model") or "").strip().upper() != "POS462":
        blockers.append("model_not_pos462")

    board = str(donor.get("motherboard") or "").strip().upper()
    if not board.startswith("B91"):
        blockers.append("motherboard_not_b91")

    if not str(donor.get("serial_or_asset_id") or "").strip():
        blockers.append("donor_identity_missing")

    for name in REQUIRED_CHECKS:
        row = checks.get(name)
        if not isinstance(row, Mapping):
            blockers.append(f"check_missing:{name}")
            continue
        state = str(row.get("state") or "").upper()
        if state != "PASS":
            blockers.append(f"check_not_pass:{name}:{state or 'MISSING'}")
        if not str(row.get("evidence") or "").strip():
            blockers.append(f"evidence_missing:{name}")

    if record.get("requires_mains_side_repair") is True:
        blockers.append("mains_side_repair_required")
    if record.get("internal_psu_opened_or_modified") is True:
        blockers.append("internal_psu_boundary_violated")

    simulated = record.get("simulated")
    if simulated is not False:
        blockers.append("real_physical_state_not_explicit")

    inspection_minutes = record.get("inspection_minutes")
    if not isinstance(inspection_minutes, (int, float)) or inspection_minutes <= 0:
        blockers.append("inspection_time_missing")

    purchase_price_twd = record.get("purchase_price_twd")
    if not isinstance(purchase_price_twd, (int, float)) or purchase_price_twd <= 0:
        blockers.append("purchase_price_missing")

    if record.get("storage_replacement_required") is True:
        warnings.append("storage_replacement_required")
    if record.get("cmos_battery_replacement_required") is True:
        warnings.append("cmos_battery_replacement_required")

    physical_checks_pass = not any(
        blocker.startswith("check_")
        or blocker in {
            "manufacturer_not_flytech",
            "model_not_pos462",
            "motherboard_not_b91",
            "donor_identity_missing",
            "mains_side_repair_required",
            "internal_psu_boundary_violated",
        }
        for blocker in blockers
    )
    real_acceptance = physical_checks_pass and "real_physical_state_not_explicit" not in blockers
    economics_observed = (
        "purchase_price_missing" not in blockers
        and "inspection_time_missing" not in blockers
    )

    if real_acceptance and economics_observed:
        decision = "ACCEPT_ONE_DONOR_FOR_PF002_ENGINEERING"
    elif physical_checks_pass and simulated is not False:
        decision = "SIMULATION_ONLY_NOT_ACCEPTED"
    else:
        decision = "HOLD_OR_REJECT_DONOR"

    source_hash = "sha256:" + hashlib.sha256(_canonical(record)).hexdigest()
    return {
        "schema": RESULT_SCHEMA,
        "product_id": "benchhmi-v0",
        "donor_record_sha256": source_hash,
        "decision": decision,
        "physical_checks_pass": physical_checks_pass,
        "real_donor_accepted": decision == "ACCEPT_ONE_DONOR_FOR_PF002_ENGINEERING",
        "blockers": blockers,
        "warnings": warnings,
        "observed": {
            "purchase_price_twd": purchase_price_twd,
            "inspection_minutes": inspection_minutes,
            "storage_replacement_required": bool(record.get("storage_replacement_required")),
            "cmos_battery_replacement_required": bool(record.get("cmos_battery_replacement_required")),
        },
        "authority": {
            "donor_qualified_for_this_run": decision == "ACCEPT_ONE_DONOR_FOR_PF002_ENGINEERING",
            "benchio_design_gate_may_open": decision == "ACCEPT_ONE_DONOR_FOR_PF002_ENGINEERING",
            "donor_disassembly_authorized": False,
            "fabrication_authorized": False,
            "power_on_new_hardware_authorized": False,
            "physical_correctness_proven": False,
            "sale_authorized": False,
        },
        "boundary": (
            "This result qualifies at most one exact donor for PF-002 engineering. "
            "It does not establish batch yield, supply depth, BenchIO correctness, "
            "fabrication authority, finished-product correctness, demand, or sale readiness."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    result = evaluate(record)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
