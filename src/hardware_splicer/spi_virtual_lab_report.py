"""Aggregate the SPI Derived Virtual Lab into one bounded experiment report."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .spi_behavioral_oracle import transact
from .spi_surrogate_repair_benchmark import run_repair_benchmark
from .spi_surrogate_sensitivity import run_sensitivity_sweep
from .spi_virtual_lab_benchmark import run_benchmark

SCHEMA_VERSION = "hardware_splicer.spi_virtual_lab_report.v1"


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_virtual_lab_report() -> dict[str, Any]:
    benchmark = run_benchmark()
    repair = run_repair_benchmark()
    sensitivity = run_sensitivity_sweep()
    protocol = transact(0x9F)

    controls_pass = bool(
        benchmark["confusion"]["false_negative"] == 0
        and benchmark["confusion"]["false_positive"] == 0
        and repair["successful_repairs"] == repair["fault_count"]
        and protocol["response_bytes"] == [0xEF, 0x60, 0x18]
        and protocol["write_or_erase_side_effect"] is False
    )

    summary = {
        "benchmark_case_count": benchmark["case_count"],
        "benchmark_false_negative": benchmark["confusion"]["false_negative"],
        "benchmark_false_positive": benchmark["confusion"]["false_positive"],
        "repair_fault_count": repair["fault_count"],
        "repair_successful": repair["successful_repairs"],
        "sensitivity_case_count": sensitivity["case_count"],
        "sensitivity_pass_count": sensitivity["pass_count"],
        "sensitivity_fail_count": sensitivity["fail_count"],
        "jedec_hex": "".join(f"{x:02X}" for x in protocol["response_bytes"]),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": "hs-spi-derived-virtual-lab-report-v1",
        "status": "controls_passed" if controls_pass else "controls_failed",
        "controls_pass": controls_pass,
        "summary": summary,
        "result_hashes": {
            "benchmark": _digest(benchmark),
            "repair": _digest(repair),
            "sensitivity": _digest(sensitivity),
            "protocol": _digest(protocol),
        },
        "evidence_class": "derived_surrogate_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "model_inference_used": False,
        "astra_used": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaims": [
            "Control success validates the deterministic virtual-lab plumbing, not physical correctness.",
            "Derived surrogate results cannot substitute for manufacturer IBIS/Verilog evidence.",
            "Scripted repair success is not evidence of AI competence.",
        ],
    }
