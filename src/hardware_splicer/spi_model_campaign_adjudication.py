"""Adjudicate the complete preregistered SPI vendor-model execution campaign.

Individual engine runs are insufficient for campaign-level credit.  This layer requires one
accepted, correctly bound result for every preregistered execution and rejects duplicates,
missing cases, foreign cases, failed checks, or authority-boundary violations.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .spi_model_execution_contract import audit_spi_model_execution_result

SCHEMA_VERSION = "hardware_splicer.spi_model_campaign_adjudication.v1"


def adjudicate_spi_model_campaign(
    campaign: Mapping[str, Any],
    results: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a fail-closed campaign verdict over sealed per-execution results."""

    planned_rows = [
        row for row in campaign.get("planned_executions", []) if isinstance(row, Mapping)
    ]
    planned_ids = [str(row.get("execution_id") or "") for row in planned_rows]
    planned_set = {execution_id for execution_id in planned_ids if execution_id}
    campaign_ready = (
        campaign.get("status") == "ready_for_model_execution"
        and campaign.get("execution_ready") is True
        and bool(planned_set)
        and len(planned_set) == len(planned_ids)
    )

    by_execution: dict[str, list[Mapping[str, Any]]] = {}
    malformed_indices: list[int] = []
    foreign_execution_ids: list[str] = []
    for index, result in enumerate(results):
        if not isinstance(result, Mapping):
            malformed_indices.append(index)
            continue
        execution_id = str(result.get("execution_id") or "")
        if not execution_id:
            malformed_indices.append(index)
            continue
        if execution_id not in planned_set:
            foreign_execution_ids.append(execution_id)
        by_execution.setdefault(execution_id, []).append(result)

    duplicate_execution_ids = sorted(
        execution_id for execution_id, rows in by_execution.items() if len(rows) != 1
    )
    missing_execution_ids = sorted(planned_set - set(by_execution))

    execution_audits: dict[str, Any] = {}
    rejected_execution_ids: list[str] = []
    for execution_id in sorted(planned_set):
        rows = by_execution.get(execution_id, [])
        if len(rows) != 1:
            continue
        audit = audit_spi_model_execution_result(campaign, rows[0])
        execution_audits[execution_id] = audit
        if audit.get("audit_pass") is not True or audit.get("status") != "accepted_modeled_result":
            rejected_execution_ids.append(execution_id)

    checks = {
        "campaign_ready": campaign_ready,
        "result_rows_well_formed": not malformed_indices,
        "no_foreign_executions": not foreign_execution_ids,
        "exactly_one_result_per_execution": not duplicate_execution_ids and not missing_execution_ids,
        "all_execution_audits_pass": (
            len(execution_audits) == len(planned_set) and not rejected_execution_ids
        ),
    }
    campaign_pass = all(checks.values())

    if not campaign_ready:
        status = "rejected_campaign_not_ready"
    elif campaign_pass:
        status = "passed_modeled_campaign"
    else:
        status = "rejected_incomplete_or_failed_campaign"

    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign.get("campaign_id"),
        "target_candidate_id": campaign.get("target_candidate_id"),
        "status": status,
        "campaign_pass": campaign_pass,
        "checks": checks,
        "planned_execution_ids": sorted(planned_set),
        "received_execution_ids": sorted(by_execution),
        "missing_execution_ids": missing_execution_ids,
        "duplicate_execution_ids": duplicate_execution_ids,
        "foreign_execution_ids": sorted(set(foreign_execution_ids)),
        "malformed_result_indices": malformed_indices,
        "rejected_execution_ids": sorted(rejected_execution_ids),
        "execution_audits": execution_audits,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaims": [
            "A passed modeled campaign is not measured bench evidence.",
            "A passed modeled campaign does not identify the user's physical DUT.",
            "A passed modeled campaign does not establish fabrication or power-on readiness.",
            "A passed modeled campaign does not grant physical authority.",
        ],
    }
