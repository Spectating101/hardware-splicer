"""Canonical physical-capability source routing and bounded engineering operator contracts.

This layer sits above individual EDA/design primitives. It decides which source strategy
is worth engineering investigation and binds delegated operator work to one project/revision.

Nothing in this module grants fabrication, power-on, field, sale, or release authority.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


SOURCE_ROUTE_SCHEMA = "hardware_splicer.capability_source_decision.v1"
OPERATOR_JOB_SCHEMA = "hardware_splicer.engineering_operator_job.v1"
OPERATOR_RECEIPT_SCHEMA = "hardware_splicer.engineering_operator_receipt.v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SourceMode(str, Enum):
    NEW_BUILD = "NEW_BUILD"
    MODIFY_EXISTING = "MODIFY_EXISTING"
    MODULE_REUSE = "MODULE_REUSE"
    DONOR_RETROFIT = "DONOR_RETROFIT"
    HYBRID = "HYBRID"


class SourceCandidate(StrictModel):
    candidate_id: str = Field(min_length=1)
    mode: SourceMode
    description: str = Field(min_length=1)
    requirement_coverage_fraction: float = Field(ge=0.0, le=1.0)
    estimated_effective_cogs: float = Field(gt=0.0)
    currency: str = Field(min_length=1)
    engineering_risk_1_to_5: int = Field(ge=1, le=5)
    hazard_burden_1_to_5: int = Field(ge=1, le=5)
    evidence_ids: list[str] = Field(default_factory=list)
    identity_resolved: bool = False
    supply_depth_verified: bool = False
    usable_yield_measured: bool = False
    exact_existing_artifact_available: bool = False
    unresolved: list[str] = Field(default_factory=list)


class SourceDecisionRequest(StrictModel):
    requirement_id: str = Field(min_length=1)
    candidates: list[SourceCandidate] = Field(min_length=1)
    minimum_requirement_coverage_fraction: float = Field(default=0.90, ge=0.0, le=1.0)
    maximum_engineering_risk: int = Field(default=4, ge=1, le=5)
    maximum_hazard_burden: int = Field(default=3, ge=1, le=5)


class OperatorTaskKind(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    SCHEMATIC = "SCHEMATIC"
    PCB_LAYOUT = "PCB_LAYOUT"
    SIMULATION = "SIMULATION"
    DESIGN_REVIEW = "DESIGN_REVIEW"
    MECHANICAL = "MECHANICAL"
    DOCUMENTATION = "DOCUMENTATION"
    OTHER = "OTHER"


class OperatorJobRequest(StrictModel):
    project_id: str = Field(min_length=1)
    project_revision: str = Field(min_length=1)
    task_kind: OperatorTaskKind
    operator_name: str = Field(min_length=1)
    operator_version: str | None = None
    input_artifacts: list[Dict[str, Any]] = Field(min_length=1)
    requested_outputs: list[str] = Field(min_length=1)
    constraints: Dict[str, Any] = Field(default_factory=dict)


class OperatorReceiptRequest(StrictModel):
    job: Dict[str, Any]
    receipt: Dict[str, Any]


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _candidate_checks(candidate: SourceCandidate, request: SourceDecisionRequest) -> dict[str, bool]:
    donor_like = candidate.mode in {
        SourceMode.MODULE_REUSE,
        SourceMode.DONOR_RETROFIT,
        SourceMode.HYBRID,
    }
    existing_like = donor_like or candidate.mode == SourceMode.MODIFY_EXISTING
    return {
        "coverage": candidate.requirement_coverage_fraction
        >= request.minimum_requirement_coverage_fraction,
        "engineering_risk": candidate.engineering_risk_1_to_5
        <= request.maximum_engineering_risk,
        "hazard_burden": candidate.hazard_burden_1_to_5
        <= request.maximum_hazard_burden,
        "evidence_present": bool(candidate.evidence_ids),
        "identity_resolved": (not existing_like) or candidate.identity_resolved,
        "existing_artifact_available": (not existing_like)
        or candidate.exact_existing_artifact_available,
        "supply_depth": (not donor_like) or candidate.supply_depth_verified,
        "yield_evidence": (not donor_like) or candidate.usable_yield_measured,
        "unresolved_clear": not candidate.unresolved,
    }


def evaluate_source_routes(request: SourceDecisionRequest | Mapping[str, Any]) -> dict[str, Any]:
    req = (
        request
        if isinstance(request, SourceDecisionRequest)
        else SourceDecisionRequest.model_validate(request)
    )
    rows: list[dict[str, Any]] = []
    for candidate in req.candidates:
        checks = _candidate_checks(candidate, req)
        blockers = [name for name, ok in checks.items() if not ok]
        eligible = not blockers
        # Score is only for ordering engineering investigations, never physical authority.
        score = (
            candidate.requirement_coverage_fraction * 100.0
            - candidate.engineering_risk_1_to_5 * 5.0
            - candidate.hazard_burden_1_to_5 * 7.0
            - len(blockers) * 25.0
        )
        rows.append(
            {
                **candidate.model_dump(mode="json"),
                "checks": checks,
                "blockers": blockers,
                "engineering_investigation_eligible": eligible,
                "investigation_score": round(score, 4),
            }
        )

    eligible_rows = [row for row in rows if row["engineering_investigation_eligible"]]
    selected = None
    if eligible_rows:
        lowest_cogs = min(float(row["estimated_effective_cogs"]) for row in eligible_rows)
        for row in eligible_rows:
            cogs = float(row["estimated_effective_cogs"])
            # Economic efficiency matters only after evidence/risk eligibility.
            row["economic_index"] = round(lowest_cogs / cogs, 6)
            row["selection_score"] = round(
                float(row["investigation_score"]) + row["economic_index"] * 20.0,
                4,
            )
        selected = max(
            eligible_rows,
            key=lambda row: (
                float(row["selection_score"]),
                -float(row["estimated_effective_cogs"]),
                str(row["candidate_id"]),
            ),
        )
    for row in rows:
        row.setdefault("economic_index", None)
        row.setdefault("selection_score", None)

    return {
        "schema": SOURCE_ROUTE_SCHEMA,
        "requirement_id": req.requirement_id,
        "decision": "ADVANCE_ENGINEERING_INVESTIGATION" if selected else "HOLD_FOR_EVIDENCE",
        "selected_candidate_id": selected["candidate_id"] if selected else None,
        "selected_mode": selected["mode"] if selected else None,
        "candidates": rows,
        "authority": {
            "engineering_investigation_authorized": bool(selected),
            "donor_purchase_authorized": False,
            "disassembly_authorized": False,
            "fabrication_authorized": False,
            "power_on_authorized": False,
            "release_authorized": False,
        },
        "boundary": (
            "Selection ranks evidence-qualified source strategies for engineering investigation only. "
            "It does not establish physical correctness, supplier availability beyond supplied evidence, "
            "fabrication authority, product-market fit, or commercial superiority."
        ),
    }


def prepare_operator_job(request: OperatorJobRequest | Mapping[str, Any]) -> dict[str, Any]:
    req = (
        request
        if isinstance(request, OperatorJobRequest)
        else OperatorJobRequest.model_validate(request)
    )
    body = {
        "schema": OPERATOR_JOB_SCHEMA,
        "project_id": req.project_id,
        "project_revision": req.project_revision,
        "task_kind": req.task_kind.value,
        "operator": {
            "name": req.operator_name,
            "version": req.operator_version,
        },
        "input_artifacts": req.input_artifacts,
        "requested_outputs": req.requested_outputs,
        "constraints": req.constraints,
        "authority": {
            "proposal_generation": True,
            "artifact_generation": True,
            "network_or_external_tool_use": "operator_specific",
            "fabrication": False,
            "power_on": False,
            "flash": False,
            "motion": False,
            "release": False,
        },
        "boundary": (
            "The operator may propose or generate bounded engineering artifacts. Hardware-Splicer "
            "must independently ingest/identify/verify outputs before they can affect release state."
        ),
    }
    body["job_id"] = _sha256(body)
    return body


def validate_operator_receipt(
    request: OperatorReceiptRequest | Mapping[str, Any],
) -> dict[str, Any]:
    req = (
        request
        if isinstance(request, OperatorReceiptRequest)
        else OperatorReceiptRequest.model_validate(request)
    )
    job = dict(req.job)
    receipt = dict(req.receipt)
    if job.get("schema") != OPERATOR_JOB_SCHEMA:
        raise ValueError("unsupported operator job schema")
    expected_job_id = _sha256({k: v for k, v in job.items() if k != "job_id"})
    errors: list[str] = []
    if job.get("job_id") != expected_job_id:
        errors.append("job_hash_mismatch")
    if receipt.get("job_id") != job.get("job_id"):
        errors.append("receipt_job_id_mismatch")
    if receipt.get("project_id") != job.get("project_id"):
        errors.append("receipt_project_id_mismatch")
    if receipt.get("project_revision") != job.get("project_revision"):
        errors.append("receipt_project_revision_mismatch")
    if receipt.get("status") != "completed":
        errors.append("operator_not_completed")

    outputs = receipt.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append("operator_outputs_missing")
        outputs = []
    for index, output in enumerate(outputs):
        if not isinstance(output, Mapping):
            errors.append(f"output_{index}_invalid")
            continue
        digest = str(output.get("sha256") or "")
        if not digest.startswith("sha256:") or len(digest) != 71:
            errors.append(f"output_{index}_sha256_missing_or_invalid")

    accepted = not errors
    return {
        "schema": OPERATOR_RECEIPT_SCHEMA,
        "job_id": job.get("job_id"),
        "project_id": job.get("project_id"),
        "project_revision": job.get("project_revision"),
        "operator": job.get("operator"),
        "task_kind": job.get("task_kind"),
        "status": "ACCEPTED_FOR_HS_INGESTION" if accepted else "REJECTED",
        "errors": errors,
        "outputs": outputs if accepted else [],
        "authority": {
            "artifact_ingestion_allowed": accepted,
            "engineering_truth_automatically_updated": False,
            "fabrication_authorized": False,
            "power_on_authorized": False,
            "release_authorized": False,
        },
        "boundary": (
            "An accepted operator receipt proves bounded job/identity/hash consistency only. "
            "It does not prove the engineering output correct and does not grant physical authority."
        ),
    }
