"""Persist evidence-bounded pre-fabrication engineering plans without physical authority."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


PRE_FABRICATION_PLAN_SCHEMA = "hardware_splicer.pre_fabrication_plan.v1"

_GENERATED_PLAN_SURFACES = {
    "changeImpact",
    "currentStage",
    "engineeringAnalysis",
    "engineeringArtifactProjection",
    "engineeringExecutionPlan",
    "engineeringIdentityMap",
    "engineeringPlan",
    "engineeringReadiness",
    "engineeringSourceGraph",
    "engineeringStatus",
    "machineProject",
    "manufacturingClosure",
    "manufacturingProjection",
    "missingInfo",
    "mode",
    "operatorGuide",
    "orderedSteps",
    "projectId",
    "projectName",
    "robotTopology",
    "snapshot_schema_version",
    "sourceAdapter",
    "verificationBridge",
}

_AUTHORITY_TRUE_KEYS = {
    "fabrication_authorized",
    "firmware_flash_authorized",
    "flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "operational_authorized",
    "release_authorized",
    "physical_authority_granted",
    "fabrication_ready",
    "power_on_ready",
}


class ProjectPreFabricationPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectPreFabricationPlanRequest(ProjectPreFabricationPlanModel):
    expected_revision: int = Field(ge=1)
    assessment: Dict[str, Any]
    requirements: list[Dict[str, Any]] = Field(default_factory=list, max_length=512)
    architecture_candidates: list[Dict[str, Any]] = Field(default_factory=list, max_length=128)
    decisions: list[Dict[str, Any]] = Field(default_factory=list, max_length=256)
    actions: list[Dict[str, Any]] = Field(min_length=1, max_length=512)
    quarantine_generated_plan: bool = False
    quarantine_reason: str = ""


def _rows(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _assert_bounded_claims(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}"
            if key in _AUTHORITY_TRUE_KEYS and child is True:
                raise ValueError(f"bounded pre-fabrication plan may not set {child_path}=true")
            if key == "automatic_execution" and child not in (None, False):
                raise ValueError(f"bounded pre-fabrication plan may not enable {child_path}")
            if key == "authority_effect" and child not in (None, "none"):
                raise ValueError(f"bounded pre-fabrication plan requires {child_path}='none'")
            if key == "physical_correctness" and child not in (None, "UNPROVEN"):
                raise ValueError(f"bounded pre-fabrication plan requires {child_path}='UNPROVEN'")
            if key == "correct_engineering_architecture_asserted" and child not in (None, False):
                raise ValueError(
                    "bounded pre-fabrication plan may not assert a correct engineering architecture"
                )
            _assert_bounded_claims(child, path=child_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _assert_bounded_claims(child, path=f"{path}[{index}]")


def _referenced_source_ids(value: Any) -> set[str]:
    result: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for raw_key, child in node.items():
                key = str(raw_key)
                if key == "source_id" and isinstance(child, str) and child.strip():
                    result.add(child.strip())
                elif key == "source_ids" and isinstance(child, Sequence) and not isinstance(
                    child, (str, bytes, bytearray)
                ):
                    result.update(str(item).strip() for item in child if str(item).strip())
                walk(child)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in node:
                walk(child)

    walk(value)
    return result


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
        error_type = "invalid_project_id"
    elif isinstance(exc, ProjectNotFound):
        code = status.HTTP_404_NOT_FOUND
        error_type = "project_not_found"
    elif isinstance(exc, RevisionConflict):
        code = status.HTTP_409_CONFLICT
        error_type = "pre_fabrication_plan_revision_conflict"
    elif isinstance(exc, (TypeError, ValueError)):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
        error_type = "invalid_pre_fabrication_plan"
    elif isinstance(exc, CorruptProject):
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "corrupt_project"
    elif isinstance(exc, ProjectStoreError):
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "project_store_error"
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "pre_fabrication_plan_error"
    return HTTPException(status_code=code, detail={"type": error_type, "message": str(exc)})


def create_project_pre_fabrication_plan_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["project-engineering-plan"])

    @router.post(
        "/v1/projects/{project_id}/engineering/pre-fabrication-plan",
        summary=(
            "Persist a source-grounded bounded engineering plan when a full machine plan is "
            "unsupported or domain-incompatible; this operation never grants physical authority"
        ),
    )
    def save_pre_fabrication_plan(
        project_id: str,
        request: ProjectPreFabricationPlanRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            if request.quarantine_generated_plan and not request.quarantine_reason.strip():
                raise ValueError("quarantine_reason is required when quarantining a generated plan")

            proposed = {
                "assessment": request.assessment,
                "requirements": request.requirements,
                "architecture_candidates": request.architecture_candidates,
                "decisions": request.decisions,
                "actions": request.actions,
            }
            _assert_bounded_claims(proposed)
            for index, action in enumerate(request.actions, start=1):
                if not str(
                    action.get("action")
                    or action.get("title")
                    or action.get("description")
                    or ""
                ).strip():
                    raise ValueError(
                        f"actions[{index - 1}] requires action, title, or description"
                    )

            snapshot = deepcopy(dict(envelope["snapshot"]))
            known_source_ids = {
                str(row.get("source_id") or "").strip()
                for row in _rows(snapshot.get("engineeringSources"))
                if str(row.get("source_id") or "").strip()
            }
            unknown_source_ids = sorted(_referenced_source_ids(proposed) - known_source_ids)
            if unknown_source_ids:
                raise ValueError(
                    "pre-fabrication plan references unknown source_ids: "
                    + ", ".join(unknown_source_ids)
                )

            quarantined: Dict[str, Any] | None = None
            if request.quarantine_generated_plan:
                generated_plan = snapshot.get("engineeringPlan")
                quarantined = {
                    "source_revision": current_revision,
                    "reason": request.quarantine_reason.strip(),
                    "engineering_plan_sha256": (
                        _canonical_hash(generated_plan)
                        if isinstance(generated_plan, Mapping)
                        else None
                    ),
                    "authority_effect": "none",
                }
                for key in _GENERATED_PLAN_SURFACES:
                    snapshot.pop(key, None)

            plan = {
                "schema_version": PRE_FABRICATION_PLAN_SCHEMA,
                "project_id": project_id,
                "source_revision": current_revision,
                "assessment": deepcopy(request.assessment),
                "requirements": deepcopy(request.requirements),
                "architecture_candidates": deepcopy(request.architecture_candidates),
                "decisions": deepcopy(request.decisions),
                "actions": deepcopy(request.actions),
                "source_ids": sorted(_referenced_source_ids(proposed)),
                "quarantined_generated_plan": quarantined,
                "fabrication_ready": False,
                "power_on_ready": False,
                "physical_authority_granted": False,
                "physical_correctness": "UNPROVEN",
                "correct_engineering_architecture_asserted": False,
                "automatic_execution": False,
                "authority_effect": "none",
            }
            snapshot["preFabricationPlan"] = plan
            snapshot["engineeringBlockers"] = list(
                dict.fromkeys(
                    str(item)
                    for item in snapshot.get("engineeringBlockers") or []
                    if str(item)
                )
            )
            snapshot["engineering_readiness"] = {
                **(
                    dict(snapshot.get("engineering_readiness"))
                    if isinstance(snapshot.get("engineering_readiness"), Mapping)
                    else {}
                ),
                "evidence_complete": False,
                "fabrication_ready": False,
                "power_on_ready": False,
                "physical_authority_granted": False,
            }
            snapshot["engineering_status"] = "bounded_pre_fabrication_plan"
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "bounded_pre_fabrication_plan",
                    "pre_fabrication_plan_schema": PRE_FABRICATION_PLAN_SCHEMA,
                    "generated_plan_quarantined": bool(quarantined),
                    "physical_authority_unchanged": True,
                    "automatic_execution": False,
                },
            )
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "pre_fabrication_plan": plan,
            "engineering_blockers": snapshot["engineeringBlockers"],
            "authority_unchanged": True,
            "physical_authority_granted": False,
        }

    return router
