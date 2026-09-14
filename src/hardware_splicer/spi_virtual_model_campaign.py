"""Plan the vendor-model-backed SPI verification campaign without fabricating results."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .spi_power_budget import evaluate_spi_power_budget
from .spi_timing_budget import evaluate_spi_timing_budget
from .spi_virtual_target import build_grounded_virtual_spi_target
from .spi_virtual_verification import apply_spi_fault, verify_spi_virtual_candidate

SCHEMA_VERSION = "hardware_splicer.spi_virtual_model_campaign.v5"
_CAPTURE_SCHEMA_VERSION = "hardware_splicer.vendor_model_capture.v1"

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


def _capture_acceptable(
    capture: Mapping[str, Any] | None,
    *,
    expected_model_kind: str,
) -> bool:
    if not isinstance(capture, Mapping):
        return False
    digest = str(capture.get("sha256") or "")
    size = capture.get("size_bytes")
    recognized_count = capture.get("recognized_expected_model_file_count")
    return (
        capture.get("schema_version") == _CAPTURE_SCHEMA_VERSION
        and capture.get("expected_model_kind") == expected_model_kind
        and isinstance(recognized_count, int)
        and not isinstance(recognized_count, bool)
        and recognized_count > 0
        and str(capture.get("capture_status") or "") == "captured_hashed_unreviewed"
        and digest.startswith("sha256:")
        and len(digest) == 71
        and isinstance(size, int)
        and not isinstance(size, bool)
        and size > 0
        and capture.get("modeled_evidence_only") is True
        and capture.get("measured_evidence_present") is False
        and capture.get("physical_correctness") == "UNPROVEN"
        and capture.get("authority_effect") == "none"
        and capture.get("physical_authority_granted") is False
    )


def build_spi_virtual_model_campaign(
    captures: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one reproducible campaign plan and readiness decision.

    Static verification, spec timing/power budgets, and adversarial checks can run immediately.
    Model executions are admitted *per preregistered case*: an execution may run when its own
    required model captures are present and the shared deterministic preconditions are safe.
    Missing Winbond bytes therefore cannot manufacture a full campaign pass, but they also do
    not prevent a TXU-only isolation case from earning modeled credit once the TXU capture is
    valid. Full campaign readiness still requires every preregistered model and execution.
    """

    target = build_grounded_virtual_spi_target()
    static_result = verify_spi_virtual_candidate(target)
    timing_budget = evaluate_spi_timing_budget()
    power_budget = evaluate_spi_power_budget()
    capture_by_id = _capture_map(captures)

    model_rows: dict[str, Any] = {}
    for model in target["vendor_model_registry"]["models"]:
        model_id = model["model_id"]
        expected_kind = str(model["model_kind"])
        captured = capture_by_id.get(model_id)
        accepted = _capture_acceptable(captured, expected_model_kind=expected_kind)
        model_rows[model_id] = {
            "required": model_id in _REQUIRED_MODEL_IDS,
            "model_kind": expected_kind,
            "component": model["component"],
            "accepted_capture": accepted,
            "capture_sha256": captured.get("sha256") if accepted else None,
            "capture_size_bytes": captured.get("size_bytes") if accepted else None,
            "recognized_expected_model_file_count": (
                captured.get("recognized_expected_model_file_count") if accepted else 0
            ),
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

    planned_executions: list[dict[str, Any]] = [
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

    static_has_no_failures = static_result["counts"]["fail"] == 0
    timing_known_terms_safe = not str(timing_budget["status"]).startswith("failed")
    power_known_terms_safe = not str(power_budget["status"]).startswith("failed")
    fault_detection_ready = all(row["detected"] for row in adversarial_cases.values())
    shared_preconditions_ready = (
        static_has_no_failures
        and timing_known_terms_safe
        and power_known_terms_safe
        and fault_detection_ready
    )

    execution_readiness: dict[str, Any] = {}
    enriched_executions: list[dict[str, Any]] = []
    for execution in planned_executions:
        required_models = list(execution["required_models"])
        missing_for_execution = sorted(
            model_id
            for model_id in required_models
            if not model_rows.get(model_id, {}).get("accepted_capture")
        )
        execution_ready = shared_preconditions_ready and not missing_for_execution
        enriched = {
            **execution,
            "model_capture_ready": not missing_for_execution,
            "missing_required_model_ids": missing_for_execution,
            "execution_ready": execution_ready,
        }
        enriched_executions.append(enriched)
        execution_readiness[execution["execution_id"]] = {
            "execution_ready": execution_ready,
            "model_capture_ready": not missing_for_execution,
            "missing_required_model_ids": missing_for_execution,
            "shared_preconditions_ready": shared_preconditions_ready,
        }

    ready_execution_ids = sorted(
        execution_id
        for execution_id, row in execution_readiness.items()
        if row["execution_ready"]
    )
    blocked_execution_ids = sorted(set(execution_readiness) - set(ready_execution_ids))
    model_capture_ready = not missing_models
    full_execution_ready = bool(enriched_executions) and len(ready_execution_ids) == len(
        enriched_executions
    )
    any_execution_ready = bool(ready_execution_ids)

    if full_execution_ready:
        status = "ready_for_model_execution"
    elif any_execution_ready:
        status = "partial_model_execution_ready"
    elif shared_preconditions_ready and missing_models:
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
        "spec_timing_budget": timing_budget,
        "timing_known_terms_safe": timing_known_terms_safe,
        "timing_fully_closed": timing_budget["status"] == "passed_modeled_timing",
        "spec_power_budget": power_budget,
        "power_known_terms_safe": power_known_terms_safe,
        "power_fully_closed": power_budget["status"] == "passed_modeled_power_budget",
        "adversarial_fault_detection": adversarial_cases,
        "fault_detection_ready": fault_detection_ready,
        "shared_preconditions_ready": shared_preconditions_ready,
        "planned_executions": enriched_executions,
        "execution_readiness": execution_readiness,
        "ready_execution_ids": ready_execution_ids,
        "blocked_execution_ids": blocked_execution_ids,
        "any_execution_ready": any_execution_ready,
        "execution_ready": full_execution_ready,
        "simulation_results": [],
        "model_inference_used": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaims": [
            "Execution readiness is case-specific; partial readiness is not full campaign readiness.",
            "No execution receives model-backed credit without immutable required model captures.",
            "Spec-level residual timing margin is not a validated timing path.",
            "Regulator capacity without a worst-case DUT load is not a validated rail budget.",
            "A ready execution is not a passing simulation execution.",
            "A passed modeled campaign is not measured physical evidence.",
        ],
    }
