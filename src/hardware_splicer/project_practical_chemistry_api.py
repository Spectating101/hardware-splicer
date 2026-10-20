"""Revision-pinned practical chemistry assessments staged in existing HS workflow.

Read-only preview: load project, validate component identity, compute a bounded
chemistry result, and produce the *candidate snapshot* expected by the existing
project review API. Review, acceptance, release and physical gates are NOT bypassed.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .chemical_api import PracticalChemistryAssessmentRequest
from .finding_ledger import replace_producer_findings
from .machine_project import MachineProject
from .practical_chemistry import assess_practical_chemistry
from .project_api import _project_error
from .project_store import ProjectStore, RevisionConflict

PROJECT_PRACTICAL_CHEMISTRY_SCHEMA = "hardware_splicer.project_practical_chemistry.v1"
CHEMISTRY_FINDINGS_PRODUCER = "practical_chemistry_assessment"
SNAPSHOT_KEY = "practicalChemistryAssessments"


class ProjectPracticalChemistryPreviewRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    component_id: str = Field(min_length=1, max_length=128)
    assessment: PracticalChemistryAssessmentRequest


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _validate_retained_assessment(row: dict[str, Any], project_id: str) -> None:
    if row.get("schema_version") != PROJECT_PRACTICAL_CHEMISTRY_SCHEMA:
        raise ValueError("Stored chemistry row is not a recognized schema")
    if row.get("project_id") != project_id:
        raise ValueError("Stored chemistry row has another project identity")
    inputs = row.get("input_request")
    report = row.get("assessment")
    if not isinstance(inputs, dict) or not isinstance(report, dict):
        raise ValueError("Stored chemistry assessment lacks its hashed original inputs")
    payload = {
        "project_id": row.get("project_id"),
        "project_revision": row.get("project_revision"),
        "component_id": row.get("component_id"),
        "inputs": inputs,
        "result": report,
    }
    current_hash = sha256(_canonical(payload)).hexdigest()
    if row.get("report_sha256") != f"sha256:{current_hash}" or (
        row.get("assessment_id") != f"practical-chemistry-{current_hash[:20]}"
    ):
        raise ValueError("Stored practical chemistry assessment fails content integrity")


def _record_findings(component_id: str, assessment: Dict[str, Any],
                     assessment_id: str) -> list[dict[str, Any]]:
    def finding(kind: str, reason: str, *, detail: str) -> dict[str, Any]:
        return {
            "category": kind,
            "object_id": component_id,
            "text": f"Practical chemistry {reason}: {detail}"[:1000],
            "provenance": {
                "kind": "deterministic",
                "basis": (
                    "Computed HS practical chemistry source-scoped screening; "
                    "manufacturer statements, real physical conditions and "
                    "user assertions are NOT independently attested."
                ),
                "source_ref": assessment_id,
                "authority_ceiling": "observed",
            },
        }
    findings = [
        finding(
            "release_blocker",
            "requires independent physical and source validation",
            detail=(
                "Catalog claims and matching scores are not specimen compatibility, "
                "production qualification or safe-to-operate authorization."
            ),
        ),
    ]
    for reason in assessment["global_blockers"]:
        findings.append(finding("object_blocker", reason,
                                detail="Reported project repair input requires triage before work."))
    for candidate in assessment["approaches"]:
        if candidate["status"] == "blocked":
            for blocker in candidate["hard_blockers"]:
                findings.append(finding(
                    "object_blocker", blocker,
                    detail=f"Method {candidate['approach_id']} is not eligible.",
                ))
        elif candidate["status"] == "research_required":
            findings.append(finding(
                "object_blocker", "research evidence missing",
                detail=(f"Method {candidate['approach_id']}: "
                        + ", ".join(candidate["conditions_to_research_before_trial"][:3])),
            ))
    # Duplicate global blockers are de-duplicated, without clipping relevant
    # source evidence from the full retained assessment report.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in findings:
        unique[(item["category"], item["text"])] = item
    return list(unique.values())


def preview_project_practical_chemistry(
    *, project_id: str, store: ProjectStore,
    expected_revision: int, component_id: str,
    assessment: PracticalChemistryAssessmentRequest,
) -> dict[str, Any]:
    envelope = store.load_latest_with_recovery(project_id)
    if int(envelope["revision"]) != expected_revision:
        raise RevisionConflict(
            f"Expected project revision {expected_revision}, actual {envelope['revision']}"
        )
    snapshot = envelope["snapshot"]
    if snapshot.get("projectId") not in (None, project_id):
        raise ValueError("Project snapshot identity does not match requested project")
    raw_machine = snapshot.get("machineProject") or snapshot.get("machine_project")
    if not isinstance(raw_machine, dict):
        raise ValueError("Project lacks canonical MachineProject")
    machine = MachineProject.model_validate(raw_machine)
    if machine.project_id != project_id:
        raise ValueError("MachineProject identity does not match project")
    components = [row for row in machine.components if row.component_id == component_id]
    if len(components) != 1:
        raise ValueError("Selected component is absent or ambiguous in canonical MachineProject")
    part = components[0]
    if part.domain.value not in {"electrical", "mechanical", "chemical", "assembly"}:
        raise ValueError("Component domain cannot support practical materials assessment")

    declared = part.metadata.get("material_family")
    if declared is not None and str(declared) != assessment.primary_material:
        raise ValueError("Requested material contradicts component declared material identity")

    args = assessment.model_dump(mode="json")
    quotes = {
        key: val.model_dump(exclude_none=True)
        for key, val in assessment.cost_quotes.items()
    }
    args["cost_quotes"] = quotes
    report = assess_practical_chemistry(**args)
    body_for_hash = {
        "project_id": project_id, "project_revision": expected_revision,
        "component_id": component_id, "inputs": args, "result": report,
    }
    report_hash = sha256(_canonical(body_for_hash)).hexdigest()
    assessment_id = f"practical-chemistry-{report_hash[:20]}"
    report_row = {
        "schema_version": PROJECT_PRACTICAL_CHEMISTRY_SCHEMA,
        "assessment_id": assessment_id,
        "project_id": project_id,
        "project_revision": expected_revision,
        "component_id": component_id,
        "component_domain": part.domain.value,
        "input_material_source": "caller_asserted_with_component_consistency_check",
        "material_grade_independently_verified": False,
        "manufacturer_source_revision_verified": False,
        "report_sha256": f"sha256:{report_hash}",
        "input_request": args,
        "assessment": report,
    }
    old_rows = snapshot.get(SNAPSHOT_KEY, [])
    if not isinstance(old_rows, list):
        raise ValueError("Existing practical chemistry assessment state is malformed")
    for row in old_rows:
        if not isinstance(row, dict):
            raise ValueError("Stored practical chemistry assessment row is malformed")
        _validate_retained_assessment(row, project_id)
    remaining = [
        row for row in old_rows if isinstance(row, dict)
        and row.get("component_id") != component_id
    ]
    if len(remaining) != len(old_rows) - sum(
        isinstance(row, dict) and row.get("component_id") == component_id for row in old_rows
    ):
        raise ValueError("Existing practical chemistry state includes invalid rows")
    candidate = dict(snapshot)
    candidate[SNAPSHOT_KEY] = remaining + [report_row]
    # On a repeated review, re-record all retained component blockers as
    # unverified, never silently clear a different component's blockers.
    findings: list[dict[str, Any]] = []
    for row in candidate[SNAPSHOT_KEY]:
        _validate_retained_assessment(row, project_id)
        findings.extend(_record_findings(
            row["component_id"], row["assessment"], row["assessment_id"]
        ))
    candidate = replace_producer_findings(
        candidate, CHEMISTRY_FINDINGS_PRODUCER,
        assessment_id, findings,
    )
    return {
        "schema_version": PROJECT_PRACTICAL_CHEMISTRY_SCHEMA,
        "project_id": project_id,
        "base_revision": expected_revision,
        "component_id": component_id,
        "assessment_id": assessment_id,
        "assessment": report,
        "proposed_findings_count": len(findings),
        "candidate_snapshot": candidate,
        "next_review_api": f"/v1/projects/{project_id}/reviews",
        "next_review_request": {
            "base_revision": expected_revision,
            "candidate_snapshot": candidate,
            "created_by": "practical_chemistry_agent",
            "note": "Proposed source-scoped chemical/material evaluation; physical use NOT authorized",
        },
        "project_store_mutated": False,
        "human_review_required": True,
        "review_actor_identity_attested_by_chemistry": False,
        "findings_enforce_global_release_gate": False,
        "physical_action_authorized": False,
        "release_authorized": False,
    }


def create_project_practical_chemistry_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["practical-chemistry", "projects"])

    @router.post("/{project_id}/chemistry/practical/preview")
    def project_practical_chemistry_preview(
        project_id: str, request: ProjectPracticalChemistryPreviewRequest,
    ) -> dict[str, Any]:
        try:
            return preview_project_practical_chemistry(
                store=store, project_id=project_id,
                expected_revision=request.expected_revision,
                component_id=request.component_id, assessment=request.assessment,
            )
        except Exception as exc:
            raise _project_error(exc) from exc

    return router
