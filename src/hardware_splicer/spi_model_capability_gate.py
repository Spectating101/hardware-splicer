"""Apply model-semantic capability evidence to SPI campaign input readiness.

PR #93's campaign planner answers whether required model *inputs* are present for each
preregistered execution. Once real vendor bytes are acquired, this projection adds a second,
stricter question: can those exact model semantics support the checks the execution is expected
to prove? Input readiness is preserved rather than rewritten.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_model_capability_gate.v1"


def _audit_map(audits: Iterable[Mapping[str, Any]] | None) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for audit in audits or []:
        if isinstance(audit, Mapping):
            model_id = str(audit.get("model_id") or "")
            if model_id:
                rows[model_id] = audit
    return rows


def apply_spi_model_capability_gate(
    campaign: Mapping[str, Any],
    audits: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a fail-closed semantic-readiness projection over a campaign plan."""

    audit_by_model = _audit_map(audits)
    rows: dict[str, Any] = {}

    for execution in campaign.get("planned_executions", []):
        if not isinstance(execution, Mapping):
            continue
        execution_id = str(execution.get("execution_id") or "")
        input_ready = execution.get("execution_ready") is True
        semantic_ready = input_ready
        blockers: list[str] = []

        if execution_id == "ibis-dut-rail-absent":
            txu_audit = audit_by_model.get("txu0304-ibis-scem787")
            semantic_ready = bool(
                input_ready
                and isinstance(txu_audit, Mapping)
                and txu_audit.get("rail_absent_isolation_claim_supported") is True
            )
            if input_ready and not semantic_ready:
                blockers.append(
                    "Captured TXU0304 IBIS data does not execute the VCC-disconnect/OE state transition required for rail-absent isolation credit."
                )

        rows[execution_id] = {
            "input_ready": input_ready,
            "semantic_capability_ready": semantic_ready,
            "effective_execution_ready": bool(input_ready and semantic_ready),
            "capability_blockers": blockers,
        }

    effective_ready = sorted(
        execution_id
        for execution_id, row in rows.items()
        if row["effective_execution_ready"]
    )
    effective_blocked = sorted(set(rows) - set(effective_ready))
    full_ready = bool(rows) and len(effective_ready) == len(rows)
    any_ready = bool(effective_ready)
    accepted_capture_count = sum(
        bool(row.get("accepted_capture"))
        for row in campaign.get("model_captures", {}).values()
        if isinstance(row, Mapping)
    ) if isinstance(campaign.get("model_captures"), Mapping) else 0

    if full_ready:
        status = "ready_for_capability_gated_model_execution"
    elif any_ready:
        status = "partial_capability_gated_model_execution_ready"
    elif accepted_capture_count:
        status = "captured_models_no_semantically_executable_case"
    else:
        status = "model_capture_required"

    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign.get("campaign_id"),
        "target_candidate_id": campaign.get("target_candidate_id"),
        "input_campaign_status": campaign.get("status"),
        "status": status,
        "accepted_capture_count": accepted_capture_count,
        "execution_readiness": deepcopy(rows),
        "ready_execution_ids": effective_ready,
        "blocked_execution_ids": effective_blocked,
        "any_execution_ready": any_ready,
        "execution_ready": full_ready,
        "model_execution_result_count": len(campaign.get("simulation_results", []))
        if isinstance(campaign.get("simulation_results"), list)
        else 0,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaims": [
            "Capture/input readiness is not semantic execution readiness.",
            "A vendor model may be genuine yet still lack semantics required by a preregistered check.",
            "Capability-gated execution readiness is not a passing model result.",
            "Modeled evidence is not measured physical evidence.",
        ],
    }
