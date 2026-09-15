"""Scripted control for the SPI virtual repair loop.

This is deliberately not an engineering agent. It exists to prove that fault injection,
verifier feedback, candidate mutation, and re-verification can be exercised end-to-end
without spending frontier-model allowance.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .spi_virtual_verification import (
    EXPECTED_SPI_DIRECTIONS,
    apply_spi_fault,
    build_raw_document_v4_candidate,
    verify_spi_virtual_candidate,
)

SCHEMA_VERSION = "hardware_splicer.spi_virtual_repair_control.v1"


def scripted_repair(candidate: Mapping[str, Any], *, fault_id: str) -> dict[str, Any]:
    """Repair only the explicitly injected control fault; do not close real blockers."""

    repaired = deepcopy(dict(candidate))
    baseline = build_raw_document_v4_candidate()

    if fault_id == "direct_3v3_drive":
        repaired["direct_connection"] = False
        repaired["translator"] = deepcopy(baseline["translator"])
    elif fault_id == "reversed_miso":
        repaired["signals"] = dict(EXPECTED_SPI_DIRECTIONS)
    elif fault_id == "grouped_direction_translator":
        repaired["translator"] = deepcopy(baseline["translator"])
        refs = dict(repaired.get("source_claim_ids") or {})
        refs["translator_topology"] = list(
            baseline["source_claim_ids"]["translator_topology"]
        )
        repaired["source_claim_ids"] = refs
    elif fault_id == "missing_absmax_provenance":
        refs = dict(repaired.get("source_claim_ids") or {})
        refs["dut_pin_abs_max_rule"] = list(
            baseline["source_claim_ids"]["dut_pin_abs_max_rule"]
        )
        repaired["source_claim_ids"] = refs
    else:
        raise ValueError(f"unsupported scripted control fault: {fault_id}")

    repaired["repair_control"] = {
        "kind": "scripted_zero_inference",
        "fault_id": fault_id,
        "model_inference_used": False,
    }
    return repaired


def run_scripted_repair_control(fault_id: str) -> dict[str, Any]:
    """Inject one fault, apply the scripted control repair, then re-run verification."""

    baseline = build_raw_document_v4_candidate()
    faulted = apply_spi_fault(baseline, fault_id)
    before = verify_spi_virtual_candidate(faulted)
    repaired = scripted_repair(faulted, fault_id=fault_id)
    after = verify_spi_virtual_candidate(repaired)

    expected_before = "blocked" if fault_id == "missing_absmax_provenance" else "failed"
    expected_after = "blocked"
    control_pass = (
        before["verification_status"] == expected_before
        and after["verification_status"] == expected_after
        and after["counts"]["fail"] == 0
        and after["physical_authority_granted"] is False
        and after["physical_correctness"] == "UNPROVEN"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "fault_id": fault_id,
        "model_inference_used": False,
        "before": before,
        "after": after,
        "expected_transition": f"{expected_before}->{expected_after}",
        "observed_transition": (
            f"{before['verification_status']}->{after['verification_status']}"
        ),
        "control_pass": control_pass,
        "real_blockers_preserved": after["verification_status"] == "blocked",
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def run_scripted_repair_control_matrix() -> dict[str, Any]:
    """Exercise every current SPI adversarial case through the zero-inference repair loop."""

    fault_ids = (
        "direct_3v3_drive",
        "reversed_miso",
        "grouped_direction_translator",
        "missing_absmax_provenance",
    )
    cases = {fault_id: run_scripted_repair_control(fault_id) for fault_id in fault_ids}
    return {
        "schema_version": "hardware_splicer.spi_virtual_repair_control_matrix.v1",
        "model_inference_used": False,
        "all_controls_pass": all(case["control_pass"] for case in cases.values()),
        "cases": cases,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
