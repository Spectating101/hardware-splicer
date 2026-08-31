"""Durable workbench occurrence bindings for registered STEP source identities.

Content-addressed engineering sources are intentionally deduplicated by blob identity.
A machine workbench, however, may reuse one identical STEP source for multiple resource
occurrences. This module persists that occurrence mapping separately so source
deduplication never collapses workbench provenance.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .mechanical_brep_mesh_api import (
    RegisteredMechanicalBrepMeshSource,
    _resolve_registered_step_source,
)
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)
from .stored_source_parser import read_registered_source_bytes


WORKBENCH_STEP_BINDING_SCHEMA = "hardware_splicer.workbench_step_binding.v1"
WORKBENCH_STEP_BINDINGS_FIELD = "machineWorkbenchStepBindings"
WORKBENCH_PLACEMENTS_FIELD = "machineWorkbenchPlacements"
# Avoid an anchor-intent ↔ binding import cycle: anchor intents are downstream of the
# occurrence binding and are invalidated whenever that identity changes.
_WORKBENCH_ANCHOR_INTENTS_FIELD = "machineWorkbenchAnchorIntents"


class WorkbenchStepBindingApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterWorkbenchStepBindingRequest(WorkbenchStepBindingApiModel):
    expected_revision: int = Field(ge=1)
    candidate_id: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    entity_id: str = Field(min_length=1, max_length=240)
    source_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "workbench_step_binding_revision_conflict",
                "message": str(exc),
            },
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_workbench_step_binding", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "workbench_step_binding_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _binding_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("candidate_id") or ""), str(row.get("resource_id") or ""))


def _binding_payload(request: RegisterWorkbenchStepBindingRequest) -> Dict[str, Any]:
    return {
        "schema_version": WORKBENCH_STEP_BINDING_SCHEMA,
        "candidate_id": request.candidate_id,
        "resource_id": request.resource_id,
        "entity_id": request.entity_id,
        "source_id": request.source_id,
        "model_id": request.model_id,
        "content_hash": request.content_hash,
        "source_materialization": "registered_project",
        "source_binding_only": True,
        "physical_authority_unchanged": True,
        "automatic_authorization": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _invalidate_resource_dependencies(snapshot: Dict[str, Any], target_key: tuple[str, str]) -> tuple[bool, int]:
    placements = _rows(snapshot.get(WORKBENCH_PLACEMENTS_FIELD))
    retained_placements = [row for row in placements if _binding_key(row) != target_key]
    placement_invalidated = len(retained_placements) != len(placements)
    if placement_invalidated:
        snapshot[WORKBENCH_PLACEMENTS_FIELD] = retained_placements

    intents = _rows(snapshot.get(_WORKBENCH_ANCHOR_INTENTS_FIELD))
    retained_intents = [row for row in intents if _binding_key(row) != target_key]
    anchor_intents_invalidated = len(intents) - len(retained_intents)
    if intents or _WORKBENCH_ANCHOR_INTENTS_FIELD in snapshot:
        snapshot[_WORKBENCH_ANCHOR_INTENTS_FIELD] = retained_intents
    return placement_invalidated, anchor_intents_invalidated


def create_workbench_step_binding_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["machine-workbench", "engineering-source-provenance"])

    @router.get("/v1/engineering/workbench/step-bindings/schema")
    def workbench_step_binding_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": WORKBENCH_STEP_BINDING_SCHEMA,
            "request_schema": RegisterWorkbenchStepBindingRequest.model_json_schema(),
            "project_snapshot_field": WORKBENCH_STEP_BINDINGS_FIELD,
            "content_addressed_source_reuse_supported": True,
            "one_current_binding_per_candidate_resource": True,
            "same_source_may_back_multiple_resource_occurrences": True,
            "registered_source_hash_reverified_before_binding": True,
            "raw_registered_source_bytes_returned": False,
            "source_binding_only": True,
            "source_rebinding_invalidates_dependent_declared_placement": True,
            "source_rebinding_invalidates_dependent_anchor_intent": True,
            "physical_authority_unchanged": True,
            "automatic_authorization": False,
        }

    @router.post(
        "/v1/projects/{project_id}/workbench/step-bindings",
        status_code=status.HTTP_201_CREATED,
    )
    def register_workbench_step_binding(
        project_id: str,
        request: RegisterWorkbenchStepBindingRequest,
    ) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            reference = RegisteredMechanicalBrepMeshSource(
                source_id=request.source_id,
                model_id=request.model_id,
                content_hash=request.content_hash,
            )
            descriptor = _resolve_registered_step_source(snapshot, reference)
            # Binding provenance is durable only if the registered content-addressed
            # blob still matches the descriptor now. The bytes are never returned.
            read_registered_source_bytes(
                project_id,
                descriptor,
                project_root=store.root,
            )
            # The canonical stored STEP parser currently derives model identity from
            # the registered source identity. Refuse a synthetic workbench model id.
            if request.model_id != request.source_id:
                raise ValueError(
                    "durable workbench STEP binding model_id must equal the canonical registered source_id"
                )

            binding = _binding_payload(request)
            bindings = _rows(snapshot.get(WORKBENCH_STEP_BINDINGS_FIELD))
            target_key = _binding_key(binding)
            entity_collision = next(
                (
                    row
                    for row in bindings
                    if str(row.get("candidate_id") or "") == request.candidate_id
                    and str(row.get("entity_id") or "") == request.entity_id
                    and _binding_key(row) != target_key
                ),
                None,
            )
            if entity_collision is not None:
                raise ValueError(
                    f"entity {request.entity_id!r} is already bound to another resource in candidate {request.candidate_id!r}"
                )

            existing_index = next(
                (index for index, row in enumerate(bindings) if _binding_key(row) == target_key),
                None,
            )
            if existing_index is not None and bindings[existing_index] == binding:
                return {
                    "ok": True,
                    "registered": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "workbench_step_binding": binding,
                    "registered_source_hash_reverified": True,
                    "raw_registered_source_bytes_returned": False,
                    "dependent_placement_invalidated": False,
                    "anchor_intents_invalidated": 0,
                    "physical_authority_unchanged": True,
                }

            dependent_placement_invalidated = False
            anchor_intents_invalidated = 0
            if existing_index is None:
                bindings.append(binding)
            else:
                bindings[existing_index] = binding
                dependent_placement_invalidated, anchor_intents_invalidated = _invalidate_resource_dependencies(snapshot, target_key)
            snapshot[WORKBENCH_STEP_BINDINGS_FIELD] = bindings

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "workbench_step_binding",
                    "workbench_step_binding_schema": WORKBENCH_STEP_BINDING_SCHEMA,
                    "candidate_id": request.candidate_id,
                    "resource_id": request.resource_id,
                    "entity_id": request.entity_id,
                    "bound_source_id": request.source_id,
                    "bound_content_hash": request.content_hash,
                    "registered_source_hash_reverified": True,
                    "raw_registered_source_bytes_returned": False,
                    "source_binding_only": True,
                    "dependent_placement_invalidated": dependent_placement_invalidated,
                    "anchor_intents_invalidated": anchor_intents_invalidated,
                    "physical_authority_unchanged": True,
                    "automatic_authorization": False,
                },
            )
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "registered": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "workbench_step_binding": binding,
            "registered_source_hash_reverified": True,
            "raw_registered_source_bytes_returned": False,
            "dependent_placement_invalidated": dependent_placement_invalidated,
            "anchor_intents_invalidated": anchor_intents_invalidated,
            "physical_authority_unchanged": True,
        }

    return router
