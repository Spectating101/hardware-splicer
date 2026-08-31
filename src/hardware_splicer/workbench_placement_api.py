"""Durable declared placement intent for project-bound machine workbench resources.

Only source-bound declared transform intent is persisted. Derived AABBs, BREP meshes,
anchors, collision results, and physical authority are deliberately recomputed rather
than serialized as durable truth.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Literal, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

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
from .workbench_step_binding_api import WORKBENCH_STEP_BINDINGS_FIELD


WORKBENCH_PLACEMENT_SCHEMA = "hardware_splicer.workbench_declared_placement.v1"
WORKBENCH_PLACEMENTS_FIELD = "machineWorkbenchPlacements"
# Keep this dependency field literal here to avoid a placement ↔ anchor-intent import
# cycle. Anchor intents are children of a source-bound durable placement.
_WORKBENCH_ANCHOR_INTENTS_FIELD = "machineWorkbenchAnchorIntents"


class WorkbenchPlacementApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterWorkbenchPlacementRequest(WorkbenchPlacementApiModel):
    expected_revision: int = Field(ge=1)
    candidate_id: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    entity_id: str = Field(min_length=1, max_length=240)
    source_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    placement_id: str = Field(min_length=1, max_length=240)
    target_frame: Literal["assembly"] = "assembly"
    translation_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    rotation_deg_xyz: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    authority: Literal["declared"] = "declared"


class ClearWorkbenchPlacementRequest(WorkbenchPlacementApiModel):
    expected_revision: int = Field(ge=1)
    candidate_id: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    entity_id: str = Field(min_length=1, max_length=240)
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
            detail={"type": "workbench_placement_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_workbench_placement", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "workbench_placement_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("candidate_id") or ""), str(row.get("resource_id") or ""))


def _source_identity(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("entity_id") or ""),
        str(row.get("source_id") or ""),
        str(row.get("model_id") or ""),
        str(row.get("content_hash") or ""),
    )


def _expected_source_identity(request: RegisterWorkbenchPlacementRequest | ClearWorkbenchPlacementRequest) -> tuple[str, str, str, str]:
    return (request.entity_id, request.source_id, request.model_id, request.content_hash)


def _matching_binding(snapshot: Mapping[str, Any], request: RegisterWorkbenchPlacementRequest | ClearWorkbenchPlacementRequest) -> Dict[str, Any]:
    target_key = (request.candidate_id, request.resource_id)
    binding = next(
        (row for row in _rows(snapshot.get(WORKBENCH_STEP_BINDINGS_FIELD)) if _key(row) == target_key),
        None,
    )
    if binding is None:
        raise ValueError("durable declared placement requires an existing workbench STEP occurrence binding")
    if _source_identity(binding) != _expected_source_identity(request):
        raise ValueError("workbench placement source identity disagrees with the current resource binding")
    if binding.get("source_binding_only") is not True or binding.get("physical_authority_unchanged") is not True:
        raise ValueError("workbench STEP occurrence binding has an invalid authority contract")
    return binding


def _reverify_registered_source(project_id: str, snapshot: Mapping[str, Any], request: RegisterWorkbenchPlacementRequest, store: ProjectStore) -> None:
    reference = RegisteredMechanicalBrepMeshSource(
        source_id=request.source_id,
        model_id=request.model_id,
        content_hash=request.content_hash,
    )
    descriptor = _resolve_registered_step_source(snapshot, reference)
    read_registered_source_bytes(project_id, descriptor, project_root=store.root)


def _payload(request: RegisterWorkbenchPlacementRequest) -> Dict[str, Any]:
    return {
        "schema_version": WORKBENCH_PLACEMENT_SCHEMA,
        "candidate_id": request.candidate_id,
        "resource_id": request.resource_id,
        "entity_id": request.entity_id,
        "source_id": request.source_id,
        "model_id": request.model_id,
        "content_hash": request.content_hash,
        "placement_id": request.placement_id,
        "target_frame": request.target_frame,
        "translation_mm": list(request.translation_mm),
        "rotation_deg_xyz": list(request.rotation_deg_xyz),
        "authority": "declared",
        "source_binding_required": True,
        "registered_source_hash_reverified": True,
        "derived_geometry_persisted": False,
        "physical_authority_unchanged": True,
        "automatic_authorization": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _invalidate_anchor_intents(snapshot: Dict[str, Any], target_key: tuple[str, str]) -> int:
    intents = _rows(snapshot.get(_WORKBENCH_ANCHOR_INTENTS_FIELD))
    retained = [row for row in intents if _key(row) != target_key]
    removed = len(intents) - len(retained)
    if intents or _WORKBENCH_ANCHOR_INTENTS_FIELD in snapshot:
        snapshot[_WORKBENCH_ANCHOR_INTENTS_FIELD] = retained
    return removed


def create_workbench_placement_router(project_store: ProjectStore | None = None) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["machine-workbench", "engineering-source-provenance"])

    @router.get("/v1/engineering/workbench/placements/schema")
    def workbench_placement_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": WORKBENCH_PLACEMENT_SCHEMA,
            "register_request_schema": RegisterWorkbenchPlacementRequest.model_json_schema(),
            "clear_request_schema": ClearWorkbenchPlacementRequest.model_json_schema(),
            "project_snapshot_field": WORKBENCH_PLACEMENTS_FIELD,
            "registered_source_binding_required": True,
            "registered_source_hash_reverified_before_write": True,
            "finite_transform_values_required": True,
            "declared_transform_only": True,
            "derived_aabb_persisted": False,
            "brep_mesh_persisted": False,
            "surface_anchor_persisted": False,
            "anchor_intent_invalidated_on_pose_change": True,
            "physical_authority_unchanged": True,
            "automatic_authorization": False,
        }

    @router.post(
        "/v1/projects/{project_id}/workbench/placements",
        status_code=status.HTTP_201_CREATED,
    )
    def register_workbench_placement(project_id: str, request: RegisterWorkbenchPlacementRequest) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            _matching_binding(snapshot, request)
            _reverify_registered_source(project_id, snapshot, request, store)

            placement = _payload(request)
            placements = _rows(snapshot.get(WORKBENCH_PLACEMENTS_FIELD))
            target_key = _key(placement)
            existing_index = next(
                (index for index, row in enumerate(placements) if _key(row) == target_key),
                None,
            )
            if existing_index is not None and placements[existing_index] == placement:
                return {
                    "ok": True,
                    "registered": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "workbench_placement": placement,
                    "registered_source_hash_reverified": True,
                    "derived_geometry_persisted": False,
                    "anchor_intents_invalidated": 0,
                    "physical_authority_unchanged": True,
                }
            anchor_intents_invalidated = _invalidate_anchor_intents(snapshot, target_key)
            if existing_index is None:
                placements.append(placement)
            else:
                placements[existing_index] = placement
            snapshot[WORKBENCH_PLACEMENTS_FIELD] = placements

            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "workbench_declared_placement",
                    "workbench_placement_schema": WORKBENCH_PLACEMENT_SCHEMA,
                    "candidate_id": request.candidate_id,
                    "resource_id": request.resource_id,
                    "entity_id": request.entity_id,
                    "bound_source_id": request.source_id,
                    "bound_content_hash": request.content_hash,
                    "declared_transform_only": True,
                    "registered_source_hash_reverified": True,
                    "derived_geometry_persisted": False,
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
            "workbench_placement": placement,
            "registered_source_hash_reverified": True,
            "derived_geometry_persisted": False,
            "anchor_intents_invalidated": anchor_intents_invalidated,
            "physical_authority_unchanged": True,
        }

    @router.post("/v1/projects/{project_id}/workbench/placements/clear")
    def clear_workbench_placement(project_id: str, request: ClearWorkbenchPlacementRequest) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, expected {request.expected_revision}"
                )
            snapshot = deepcopy(envelope["snapshot"])
            _matching_binding(snapshot, request)
            placements = _rows(snapshot.get(WORKBENCH_PLACEMENTS_FIELD))
            target_key = (request.candidate_id, request.resource_id)
            existing = next((row for row in placements if _key(row) == target_key), None)
            if existing is None:
                return {
                    "ok": True,
                    "cleared": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "anchor_intents_invalidated": 0,
                    "physical_authority_unchanged": True,
                }
            if (
                _source_identity(existing) != _expected_source_identity(request)
                or str(existing.get("placement_id") or "") != request.placement_id
            ):
                raise ValueError("stale workbench placement clear does not match the current durable placement identity")
            snapshot[WORKBENCH_PLACEMENTS_FIELD] = [row for row in placements if _key(row) != target_key]
            anchor_intents_invalidated = _invalidate_anchor_intents(snapshot, target_key)
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "workbench_declared_placement_clear",
                    "workbench_placement_schema": WORKBENCH_PLACEMENT_SCHEMA,
                    "candidate_id": request.candidate_id,
                    "resource_id": request.resource_id,
                    "entity_id": request.entity_id,
                    "anchor_intents_invalidated": anchor_intents_invalidated,
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
            "anchor_intents_invalidated": anchor_intents_invalidated,
            "physical_authority_unchanged": True,
        }

    return router
