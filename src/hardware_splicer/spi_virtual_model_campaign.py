"""Plan the vendor-model-backed SPI verification campaign without fabricating results."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .spi_virtual_target import build_grounded_virtual_spi_target
from .spi_virtual_verification import apply_spi_fault, verify_spi_virtual_candidate

SCHEMA_VERSION = "hardware_splicer.spi_virtual_model_campaign.v1"

_REQUIRED_MODEL_IDS = {
    "txu0304-ibis-scem787",
    "w25q128jwsiq-ibis-da03-aag072",
    "w25q128jw-q-verilog-da02-aag072",
}


def _capture_map(captures: Iterable[Mapping[str, Any]] | None) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for capture in captures or []:
        if not isinstance(capture, Mapping):
            continue
        model_id = str(capture.get("model_id") or "")
        if model_id:
            rows[model_id] = capture
    return rows


def _capture_acceptable(capture: Mapping[str, Any] | None) -> bool:
    if not isinstance(capture, Mapping):
        return False
    digest = str(capture.get("sha256") or "")
    size = capture.get("size_bytes")
    return (
        str(capture.get("capture_status") or "") == "captured_hashed_unreviewed"
        and digest.startswith("sha256:")
        and len(digest) == 71
        and isinstance(size, int)
        and not isinstance(size, bool)
        and size > 0
        and capture.get("authority_effect") == "none"
        and capture.get("physical_authority_granted") is False
    )


def build_spi_virtual_model_campaign(
    captures: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one reproducible campaign plan and readiness decision.

    This planner never substitutes synthetic simulator output for missing manufacturer-model
    bytes.  Static verification and adversarial checks can run immediately; IBIS/Verilog
    execution remains blocked until every required model has a valid capture manifest.
    """

    target = build_grounded_virtual_spi_target()
    static_result = verify_spi_virtual_candidate(target)
    capture_by_id = _capture_map(captures)

    model_rows: dict[str, Any] = {}
    for model in target["vendor_model_registry"]["models"]:
        model_id = model["model_id"]
        captured = capture_by_id.get(model_id)
        accepted = _capture_acceptable(captured)
        model_rows[model_id] = {
            "required": model_id in _REQUIRED_MODEL_IDS,
            "model_kind": model["model_kind"],
            "component": model["component"],
            "accepted_capture": accepted,
            "capture_sha256": captured.get("sha256") if accepted else None,
            "capture_size_bytes": captured.get("size_bytes") if accepted else None,
            "landing_url": model["landing_url"],
            "download_url": model.get("download_url"),
        }

    missing_models = sorted(
        model_id
        for model_id in _REQUIRED_MODEL_IDS
        if not model_rows.get(model_id, {}).get("accepted_capture")
    )

    adversarial_cases: dict[str, Any] = {}
    for fault_id in ("direct_3v3_drive", "reversed_miso", "grouped_direction_translator"):
        result = verify_spi_virtual_candidate(apply_spi_fault(target, fault_id))
        adversarial_cases[fault_id] = {
            "verification_status": result["verification_status"],
            "fail_count": result["counts"]["fail"],
            "detected": result["verification_status"] == "failed",
        }

    planned_executions = [
        {
            "execution_id": "ibis-nominal-3v3-to-1v8",
            "engine_class": "IBIS signal-integrity",
            "required_models": ["txu0304-ibis-scem787", "w25q128jwsiq-ibis-da03-aag072"],
            "conditions": {"vcca_v": 3.3, "vccb_v": 1.8, "spi_clock_hz": 5_000_000},
            "credit": "modeled_only",
        },
        {
            "execution_id": "ibis-low-dut-rail-corner",
            "engine_class": "IBIS signal-integrity",
            "required_models": ["txu0304-ibis-scem787", "w25q128jwsiq-ibis-da03-aag072"],
            "conditions": {"vcca_v": 3.3, "vccb_v": 1.773, "spi_clock_hz": 5_000_000},
            "credit": "modeled_only",
        },
        {
            "execution_id": "ibis-high-dut-rail-corner",
            "engine_class": "IBIS signal-integrity",
            "required_models": ["txu0304-ibis-scem787", "w25q128jwsiq-ibis-da03-aag072"],
            "conditions": {"vcca_v": 3.3, "vccb_v": 1.827, "spi_clock_hz": 5_000_000},
            "credit": "modeled_only",
        },
        {
            "execution_id": "ibis-dut-rail-absent",
            "engine_class": "IBIS/isolation boundary",
            "required_models": ["txu0304-ibis-scem787"],
            "conditions": {"vcca_v": 3.3, "vccb_v": 0.0, "oe_expected": "disabled_or_high_z"},
            "credit": "modeled_only",
        },
        {
            "execution_id": "verilog-jedec-id-read-9f",
            "engine_class": "Verilog protocol behavior",
            "required_models": ["w25q128jw-q-verilog-da02-aag072"],
            "conditions": {"command_hex": "9F", "mode": "read_only", "spi_clock_hz": 5_000_000},
            "credit": "modeled_only",
        },
    ]

    model_capture_ready = not missing_models
    static_has_no_failures = static_result["counts"]["fail"] == 0
    fault_detection_ready = all(row["detected"] for row in adversarial_cases.values())
    execution_ready = model_capture_ready and static_has_no_failures and fault_detection_ready

    if execution_ready:
        status = "ready_for_model_execution"
    elif missing_models:
        status = "model_capture_required"
    else:
        status = "blocked"

    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": "hs-spi-vendor-model-campaign-v1",
        "status": status,
        "target_candidate_id": target["candidate_id"],
        "model_capture_ready": model_capture_ready,
        "missing_required_model_ids": missing_models,
        "model_captures": model_rows,
        "static_verification": {
            "verification_status": static_result["verification_status"],
            "static_verification_pass": static_result["static_verification_pass"],
            "counts": static_result["counts"],
        },
        "adversarial_fault_detection": adversarial_cases,
        "fault_detection_ready": fault_detection_ready,
        "planned_executions": planned_executions,
        "execution_ready": execution_ready,
        "simulation_results": [],
        "model_inference_used": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaims": [
            "No IBIS or Verilog execution is claimed until immutable vendor-model bytes are captured.",
            "A ready campaign is not a passing simulation campaign.",
            "A passing simulation campaign is not measured physical evidence.",
        ],
    }
