"""Deterministic repair benchmark for the SPI derived virtual lab."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .spi_derived_surrogate import build_default_surrogate, evaluate_surrogate_case

SCHEMA_VERSION = "hardware_splicer.spi_surrogate_repair_benchmark.v1"


def baseline_case() -> dict[str, Any]:
    return {
        "spi_clock_hz": 5_000_000,
        "direct_drive": False,
        "miso_direction": "dut_to_host",
        "translator_topology": "fixed_3_forward_1_reverse",
        "oe_enabled": True,
        "dut_rail_present": True,
        "dut_vcc_v": 1.8,
        "load_cap_pf": 20.0,
    }


def inject_fault(case: Mapping[str, Any], fault_id: str) -> dict[str, Any]:
    row = deepcopy(dict(case))
    if fault_id == "direct_3v3_drive":
        row["direct_drive"] = True
    elif fault_id == "reversed_miso":
        row["miso_direction"] = "host_to_dut"
    elif fault_id == "grouped_direction_translator":
        row["translator_topology"] = "grouped_2_plus_2"
    elif fault_id == "oe_with_dead_dut_rail":
        row["dut_rail_present"] = False
        row["oe_enabled"] = True
    elif fault_id == "overclock_25mhz":
        row["spi_clock_hz"] = 25_000_000
    elif fault_id == "dut_rail_low":
        row["dut_vcc_v"] = 1.65
    else:
        raise ValueError(f"unknown fault id: {fault_id}")
    return row


def scripted_repair(case: Mapping[str, Any], fault_id: str) -> dict[str, Any]:
    row = deepcopy(dict(case))
    if fault_id == "direct_3v3_drive":
        row["direct_drive"] = False
    elif fault_id == "reversed_miso":
        row["miso_direction"] = "dut_to_host"
    elif fault_id == "grouped_direction_translator":
        row["translator_topology"] = "fixed_3_forward_1_reverse"
    elif fault_id == "oe_with_dead_dut_rail":
        row["oe_enabled"] = False
    elif fault_id == "overclock_25mhz":
        row["spi_clock_hz"] = 5_000_000
    elif fault_id == "dut_rail_low":
        row["dut_vcc_v"] = 1.8
    else:
        raise ValueError(f"unknown fault id: {fault_id}")
    return row


def run_repair_benchmark() -> dict[str, Any]:
    model = build_default_surrogate()
    faults = (
        "direct_3v3_drive",
        "reversed_miso",
        "grouped_direction_translator",
        "oe_with_dead_dut_rail",
        "overclock_25mhz",
        "dut_rail_low",
    )
    rows = []
    successful = 0
    for fault_id in faults:
        broken = inject_fault(baseline_case(), fault_id)
        before = evaluate_surrogate_case(model, **broken)
        repaired_case = scripted_repair(broken, fault_id)
        after = evaluate_surrogate_case(model, **repaired_case)
        repaired = before["status"] == "fail_surrogate" and after["status"] == "pass_surrogate"
        successful += int(repaired)
        rows.append({
            "fault_id": fault_id,
            "before_status": before["status"],
            "before_failed_checks": before["failed_checks"],
            "after_status": after["status"],
            "after_failed_checks": after["failed_checks"],
            "repair_success": repaired,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": "hs-spi-scripted-surrogate-repair-v1",
        "fault_count": len(faults),
        "successful_repairs": successful,
        "repair_success_rate": successful / len(faults),
        "rows": rows,
        "model_inference_used": False,
        "evidence_class": "derived_surrogate_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaim": "Scripted repair success is a plumbing/control result, not evidence of AI engineering competence.",
    }
