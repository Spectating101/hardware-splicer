"""Durable declared surface-anchor intent for project-bound machine workbench resources.

Only the source/placement-bound probe declaration is persisted. Kernel-derived face
identity, snapped point, normal, area, and snap result are deliberately recomputed from
the current registered STEP blob on project reopen rather than serialized as truth.
"""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Dict, Literal, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .mechanical_brep_anchor import MAX_SNAP_DISTANCE_MM
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
from .workbench_placement_api import WORKBENCH_PLACEMENTS_FIELD
from .workbench_step_binding_api import WORKBENCH_STEP_BINDINGS_FIELD


WORKBENCH_ANCHOR_INTENT_SCHEMA = "hardware_splicer.workbench_brep_anchor_intent.v1"
WORKBENCH_ANCHOR_INTENTS_FIELD = "machineWorkbenchAnchorIntents"


class WorkbenchAnchorIntentApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterWorkbenchAnchorIntentRequest(WorkbenchAnchorIntentApiModel):
    expected_revision: int = Field(ge=1)
    candidate_id: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    entity_id: str = Field(min_length=1, max_length=240)
    interface_id: str = Field(min_length=1, max_length=240)
    anchor_id: str = Field(min_length=1, max_length=320)
    source_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    placement_id: str = Field(min_length=1, max_length=240)
    target_frame: Literal["assembly"] = "assembly"
    translation_mm: tuple[float, float, float]
    rotation_deg_xyz: tuple[float, float, float]
    probe_point_mm: tuple[float, float, float]
    max_snap_distance_mm: float = Field(default=5.0, ge=0, le=MAX_SNAP_DISTANCE_MM)
    authority: Literal["declared"] = "declared"


class ClearWorkbenchAnchorIntentRequest(WorkbenchAnchorIntentApiModel):
    expected_revision: int = Field(ge=1)
    candidate_id: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    entity_id: str = Field(min_length=1, max_length=240)
    interface_id: str = Field(min_length=1, max_length=240)
    anchor_id: str = Field(min_length=1, max_length=320)
    source_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    placement_id: str = Field(min_length=1, max_length=240)


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
            detail={"type": "workbench_anchor_intent_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_workbench_anchor_intent", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "workbench_anchor_intent_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _resource_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("candidate_id") or ""), str(row.get("resource_id") or ""))


def _anchor_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("candidate_id") or ""),
        str(row.get("resource_id") or ""),
        str(row.get("anchor_id") or ""),
    )


def _source_identity(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("entity_id") or ""),
        str(row.get("source_id") or ""),
        str(row.get("model_id") or ""),
        str(row.get("content_hash") or ""),
    )


def _expected_source_identity(request: RegisterWorkbenchAnchorIntentRequest | ClearWorkbenchAnchorIntentRequest) -> tuple[str, str, str, str]:
    return (request.entity_id, request.source_id, request.model_id, request.content_hash)


def _finite_tuple(values: tuple[float, float, float], label: str) -> None:
    if not all(isfinite(float(value)) for value in values):
        raise ValueError(f"{label} must contain only finite numbers")


def _matching_binding(snapshot: Mapping[str, Any], request: RegisterWorkbenchAnchorIntentRequest | ClearWorkbenchAnchorIntentRequest) -> Dict[str, Any]:
    target_key = (request.candidate_id, request.resource_id)
    binding = next(
        (row for row in _rows(snapshot.get(WORKBENCH_STEP_BINDINGS_FIELD)) if _resource_key(row) == target_key),
        None,
    )
    if binding is None:
        raise ValueError("durable BREP anchor intent requires an existing workbench STEP occurrence binding")
    if _source_identity(binding) != _expected_source_identity(request):
        raise ValueError("workbench anchor intent source identity disagrees with the current resource binding")
    if binding.get("source_binding_only") is not True or binding.get("physical_authority_unchanged") is not True:
        raise ValueError("workbench STEP occurrence binding has an invalid authority contract")
    return binding


def _matching_placement(snapshot: Mapping[str, Any], request: RegisterWorkbenchAnchorIntentRequest | ClearWorkbenchAnchorIntentRequest) -> Dict[str, Any]:
    target_key = (request.candidate_id, request.resource_id)
    placement = next(
        (row for row in _rows(snapshot.get(WORKBENCH_PLACEMENTS_FIELD)) if _resource_key(row) == target_key),
        None,
    )
    if placement is None:
        raise ValueError("durable BREP anchor intent requires a current persisted declared placement")
    if _source_identity(placement) != _expected_source_identity(request):
        raise ValueError("workbench anchor intent source identity disagrees with the durable placement")
    if str(placement.get("placement_id") or "") != request.placement_id:
        raise ValueError("workbench anchor intent placement_id disagrees with the durable placement")
    if str(placement.get("target_frame") or "") != "assembly":
        raise ValueError("workbench anchor intent requires the durable assembly-frame placement")
    if isinstance(request, RegisterWorkbenchAnchorIntentRequest):
        if list(placement.get("translation_mm") or []) != list(request.translation_mm):
            raise ValueError("workbench anchor intent translation disagrees with the durable placement")
        if list(placement.get("rotation_deg_xyz") or []) != list(request.rotation_deg_xyz):
            raise ValueError("workbench anchor intent rotation disagrees with the durable placement")
    return placement


def _reverify_registered_source(project_id: str, snapshot: Mapping[str, Any], request: RegisterWorkbenchAnchorIntentRequest, store: ProjectStore) -> None:
    reference = RegisteredMechanicalBrepMeshSource(
        source_id=request.source_id,
        model_id=request.model_id,
        content_hash=request.content_hash,
    )
    descriptor = _resolve_registered_step_source(snapshot, reference)
    read_registered_source_bytes(project_id, descriptor, project_root=store.root)


def _payload(request: RegisterWorkbenchAnchorIntentRequest) -> Dict[str, Any]:
    return {
        "schema_version": WORKBENCH_ANCHOR_INTENT_SCHEMA,
        "candidate_id": request.candidate_id,
        "resource_id": request.resource_id,
        "entity_id": request.entity_id,
        "interface_id": request.interface_id,
        "anchor_id": request.anchor_id,
        "source_id": request.source_id,
        "model_id": request.model_id,
        "content_hash": request.content_hash,
        "placement_id": request.placement_id,
        "target_frame": "assembly",
        "translation_mm": list(request.translation_mm),
        "rotation_deg_xyz": list(request.rotation_deg_xyz),
        "probe_point_mm": list(request.probe_point_mm),
        "max_snap_distance_mm": request.max_snap_distance_mm,
        "authority": "declared",
        "source_binding_required": True,
        "durable_placement_required": True,
        "registered_source_hash_reverified": True,
        "kernel_result_persisted": False,
        "face_identity_persisted": False,
        "anchor_point_persisted": False,
        "surface_normal_persisted": False,
        "requires_occt_resnap_on_reopen": True,
        "physical_authority_unchanged": True,
        "connector_mating_verified": False,
        "physical_measurement": False,
        "automatic_authorization": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def create_workbench_anchor_intent_router(project_store: ProjectStore | None = None) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["machine-workbench", "engineering-source-provenance"])

    @router.get("/v1/engineering/workbench/anchor-intents/schema")
    def workbench_anchor_intent_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": WORKBENCH_ANCHOR_INTENT_SCHEMA,
            "register_request_schema": RegisterWorkbenchAnchorIntentRequest.model_json_schema(),
            "clear_request_schema": ClearWorkbenchAnchorIntentRequest.model_json_schema(),
            "project_snapshot_field": WORKBENCH_ANCHOR_INTENTS_FIELD,
            "registered_source_binding_required": True,
            "durable_placement_required": True,
            "registered_source_hash_reverified_before_write": True,
            "probe_intent_only": True,
            "kernel_result_persisted": False,
            "face_identity_persisted": False,
            "surface_normal_persisted": False,
            "requires_occt_resnap_on_reopen": True,
            "physical_authority_unchanged": True,
            "automatic_authorization": False,
        }

    @router.post(
        "/v1/projects/{project_id}/workbench/anchor-intents",
        status_code=status.HTTP_201_CREATED,
    )
    def register_workbench_anchor_intent(project_id: str, request: RegisterWorkbenchAnchorIntentRequest) -> Dict[str, Any]:
        try:
            _finite_tuple(request.translation_mm, "translation_mm")
            _finite_tuple(request.rotation_deg_xyz, "rotation_deg_xyz")
            _finite_tuple(request.probe_point_mm, "probe_point_mm")
            if not isfinite(float(request.max_snap_distance_mm)):
                raise ValueError("max_snap_distance_mm must be finite")

            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            _matching_binding(snapshot, request)
            _matching_placement(snapshot, request)
            _reverify_registered_source(project_id, snapshot, request, store)

            intent = _payload(request)
            intents = _rows(snapshot.get(WORKBENCH_ANCHOR_INTENTS_FIELD))
            target_key = _anchor_key(intent)
            existing_index = next(
                (index for index, row in enumerate(intents) if _anchor_key(row) == target_key),
                None,
            )
            if existing_index is not None and intents[existing_index] == intent:
                return {
                    "ok": True,
                    "registered": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "workbench_anchor_intent": intent,
                    "registered_source_hash_reverified": True,
                    "kernel_result_persisted": False,
                    "physical_authority_unchanged": True,
                }
            if existing_index is None:
                intents.append(intent)
            else:
                intents[existing_index] = intent
            snapshot[WORKBENCH_ANCHOR_INTENTS_FIELD] = intents

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "workbench_brep_anchor_intent",
                    "workbench_anchor_intent_schema": WORKBENCH_ANCHOR_INTENT_SCHEMA,
                    "candidate_id": request.candidate_id,
                    "resource_id": request.resource_id,
                    "entity_id": request.entity_id,
                    "interface_id": request.interface_id,
                    "anchor_id": request.anchor_id,
                    "bound_source_id": request.source_id,
                    "bound_content_hash": request.content_hash,
                    "placement_id": request.placement_id,
                    "registered_source_hash_reverified": True,
                    "probe_intent_only": True,
                    "kernel_result_persisted": False,
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
            "workbench_anchor_intent": intent,
            "registered_source_hash_reverified": True,
            "kernel_result_persisted": False,
            "physical_authority_unchanged": True,
        }

    @router.post("/v1/projects/{project_id}/workbench/anchor-intents/clear")
    def clear_workbench_anchor_intent(project_id: str, request: ClearWorkbenchAnchorIntentRequest) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            _matching_binding(snapshot, request)
            _matching_placement(snapshot, request)
            intents = _rows(snapshot.get(WORKBENCH_ANCHOR_INTENTS_FIELD))
            target_key = (request.candidate_id, request.resource_id, request.anchor_id)
            existing = next((row for row in intents if _anchor_key(row) == target_key), None)
            if existing is None:
                return {
                    "ok": True,
                    "cleared": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "physical_authority_unchanged": True,
                }
            if (
                _source_identity(existing) != _expected_source_identity(request)
                or str(existing.get("placement_id") or "") != request.placement_id
                or str(existing.get("interface_id") or "") != request.interface_id
            ):
                raise ValueError("stale workbench anchor-intent clear does not match the current durable intent identity")
            snapshot[WORKBENCH_ANCHOR_INTENTS_FIELD] = [row for row in intents if _anchor_key(row) != target_key]
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "workbench_brep_anchor_intent_clear",
                    "workbench_anchor_intent_schema": WORKBENCH_ANCHOR_INTENT_SCHEMA,
                    "candidate_id": request.candidate_id,
                    "resource_id": request.resource_id,
                    "entity_id": request.entity_id,
                    "interface_id": request.interface_id,
                    "anchor_id": request.anchor_id,
                    "physical_authority_unchanged": True,
                    "automatic_authorization": False,
                },
            )
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "cleared": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "physical_authority_unchanged": True,
        }

    return router
