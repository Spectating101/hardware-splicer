"""Audit contract for vendor-model-backed SPI simulation executions.

The contract deliberately does not run IBIS or Verilog itself. It defines what a future engine
must prove to earn *modeled* verification credit and prevents engine output from promoting
physical authority.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_model_execution_audit.v2"
RESULT_SCHEMA_VERSION = "hardware_splicer.spi_model_execution_result.v1"

_REQUIRED_CHECKS: dict[str, set[str]] = {
    "ibis-nominal-3v3-to-1v8": {
        "logic_high_margin",
        "logic_low_margin",
        "overshoot_absolute_maximum",
        "undershoot_absolute_minimum",
        "settling_before_sample",
    },
    "ibis-low-dut-rail-corner": {
        "logic_high_margin",
        "logic_low_margin",
        "overshoot_absolute_maximum",
        "undershoot_absolute_minimum",
        "settling_before_sample",
    },
    "ibis-high-dut-rail-corner": {
        "logic_high_margin",
        "logic_low_margin",
        "overshoot_absolute_maximum",
        "undershoot_absolute_minimum",
        "settling_before_sample",
    },
    "ibis-dut-rail-absent": {
        "translator_output_high_impedance",
        "dut_domain_not_driven",
    },
    "verilog-jedec-id-read-9f": {
        "command_9f_accepted",
        "jedec_id_response_observed",
        "no_write_or_erase_side_effect",
    },
}


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "")
    if not text.startswith("sha256:") or len(text) != 71:
        return False
    try:
        int(text[7:], 16)
    except ValueError:
        return False
    return True


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def required_checks_for_execution(execution_id: str) -> set[str]:
    return set(_REQUIRED_CHECKS.get(str(execution_id), set()))


def seal_spi_model_execution_result(
    campaign: Mapping[str, Any],
    *,
    execution_id: str,
    engine_name: str,
    engine_version: str,
    exit_code: int,
    raw_output: bytes,
    model_hashes: Mapping[str, str],
    checks: Iterable[Mapping[str, Any]],
    metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the HS-owned result envelope around one engine execution.

    The wrapper computes raw-output identity and hard-codes the authority boundary. Engines may
    supply check data and metrics, but they cannot choose readiness or physical-authority fields.
    """

    if not isinstance(raw_output, (bytes, bytearray)):
        raise TypeError("raw_output must be bytes")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "execution_id": str(execution_id),
        "target_candidate_id": campaign.get("target_candidate_id"),
        "engine": {"name": str(engine_name), "version": str(engine_version)},
        "exit_code": int(exit_code),
        "raw_output_sha256": _sha256_bytes(bytes(raw_output)),
        "model_hashes": dict(model_hashes),
        "checks": [deepcopy(dict(row)) for row in checks],
        "metrics": deepcopy(dict(metrics or {})),
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def audit_spi_model_execution_result(
    campaign: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit one engine result against a ready campaign and frozen execution contract."""

    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    campaign_ready = campaign.get("status") == "ready_for_model_execution" and campaign.get(
        "execution_ready"
    ) is True
    checks["campaign_ready"] = campaign_ready

    schema_ok = result.get("schema_version") == RESULT_SCHEMA_VERSION
    checks["result_schema"] = schema_ok

    candidate_id = str(campaign.get("target_candidate_id") or "")
    checks["candidate_binding"] = bool(candidate_id) and result.get("target_candidate_id") == candidate_id

    execution_id = str(result.get("execution_id") or "")
    planned = {
        str(row.get("execution_id")): row
        for row in campaign.get("planned_executions", [])
        if isinstance(row, Mapping)
    }
    execution_known = execution_id in planned and execution_id in _REQUIRED_CHECKS
    checks["execution_binding"] = execution_known

    engine = result.get("engine") if isinstance(result.get("engine"), Mapping) else {}
    checks["engine_identity"] = bool(str(engine.get("name") or "").strip()) and bool(
        str(engine.get("version") or "").strip()
    )

    checks["successful_process_exit"] = result.get("exit_code") == 0
    checks["raw_output_identity"] = _valid_sha256(result.get("raw_output_sha256"))

    required_models = set(planned.get(execution_id, {}).get("required_models", [])) if execution_known else set()
    supplied_hashes = result.get("model_hashes") if isinstance(result.get("model_hashes"), Mapping) else {}
    campaign_models = campaign.get("model_captures") if isinstance(campaign.get("model_captures"), Mapping) else {}
    model_binding_errors: list[str] = []
    for model_id in sorted(required_models):
        expected = campaign_models.get(model_id, {}).get("capture_sha256") if isinstance(campaign_models.get(model_id), Mapping) else None
        actual = supplied_hashes.get(model_id)
        if not _valid_sha256(expected) or actual != expected:
            model_binding_errors.append(model_id)
    checks["model_hash_binding"] = not model_binding_errors and bool(required_models)
    details["model_hash_binding_errors"] = model_binding_errors

    rows = result.get("checks") if isinstance(result.get("checks"), list) else []
    check_rows: dict[str, Mapping[str, Any]] = {}
    malformed_rows: list[int] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            malformed_rows.append(index)
            continue
        check_id = str(row.get("check_id") or "")
        status = row.get("status")
        if not check_id or status not in {"pass", "fail"} or check_id in check_rows:
            malformed_rows.append(index)
            continue
        check_rows[check_id] = row

    required_checks = required_checks_for_execution(execution_id)
    missing_checks = sorted(required_checks - set(check_rows))
    failed_required_checks = sorted(
        check_id
        for check_id in required_checks
        if check_id in check_rows and check_rows[check_id].get("status") != "pass"
    )
    reported_failed_checks = sorted(
        check_id for check_id, row in check_rows.items() if row.get("status") == "fail"
    )
    missing_required_evidence = sorted(
        check_id
        for check_id in required_checks
        if check_id in check_rows
        and (
            not isinstance(check_rows[check_id].get("evidence"), Mapping)
            or not bool(check_rows[check_id].get("evidence"))
        )
    )

    checks["machine_readable_checks"] = not malformed_rows and bool(rows)
    checks["required_checks_present"] = execution_known and not missing_checks
    checks["required_checks_pass"] = execution_known and not missing_checks and not failed_required_checks
    checks["required_check_evidence"] = execution_known and not missing_checks and not missing_required_evidence
    checks["no_reported_failures"] = not reported_failed_checks
    details["malformed_check_rows"] = malformed_rows
    details["missing_required_checks"] = missing_checks
    details["failed_required_checks"] = failed_required_checks
    details["reported_failed_checks"] = reported_failed_checks
    details["missing_required_evidence"] = missing_required_evidence

    numeric_metrics = result.get("metrics") if isinstance(result.get("metrics"), Mapping) else {}
    nonfinite_metrics = sorted(
        str(key)
        for key, value in numeric_metrics.items()
        if isinstance(value, (int, float)) and not _finite_number(value)
    )
    checks["finite_numeric_metrics"] = not nonfinite_metrics
    details["nonfinite_numeric_metrics"] = nonfinite_metrics

    authority_safe = (
        result.get("modeled_evidence_only") is True
        and result.get("measured_evidence_present") is False
        and result.get("physical_correctness") == "UNPROVEN"
        and result.get("fabrication_ready") is False
        and result.get("power_on_ready") is False
        and result.get("physical_authority_granted") is False
        and result.get("authority_effect") == "none"
    )
    checks["authority_boundary"] = authority_safe

    audit_pass = all(checks.values())
    if not campaign_ready:
        status = "rejected_campaign_not_ready"
    elif not audit_pass:
        status = "rejected_contract"
    else:
        status = "accepted_modeled_result"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "audit_pass": audit_pass,
        "execution_id": execution_id,
        "target_candidate_id": candidate_id or None,
        "checks": checks,
        "details": details,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
