"""Product API for hash-bound, placed STEP BREP surface anchors."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .mechanical_brep_anchor import (
    BREP_ANCHOR_SCHEMA,
    MAX_SNAP_DISTANCE_MM,
    BrepSurfaceAnchorReport,
    build_step_brep_surface_anchor,
)
from .mechanical_brep_mesh_api import (
    RegisteredMechanicalBrepMeshSource,
    _registered_step_text,
    _resolve_registered_step_source,
)
from .mechanical_placement import DeclaredGeometryPlacement
from .project_store import ProjectNotFound, ProjectStore, ProjectStoreError


class MechanicalBrepAnchorSource(BaseModel):
    source_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content: str = Field(min_length=1)


class MechanicalBrepSurfaceAnchorRequest(BaseModel):
    project_id: str = Field(min_length=1)
    anchor_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    source: MechanicalBrepAnchorSource
    placement: DeclaredGeometryPlacement
    probe_point_mm: tuple[float, float, float]
    max_snap_distance_mm: float = Field(default=5.0, ge=0, le=MAX_SNAP_DISTANCE_MM)
    timeout_s: float = Field(default=60.0, gt=0, le=120.0)


class MechanicalStoredBrepSurfaceAnchorRequest(BaseModel):
    project_id: str = Field(min_length=1)
    anchor_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    source: RegisteredMechanicalBrepMeshSource
    placement: DeclaredGeometryPlacement
    probe_point_mm: tuple[float, float, float]
    max_snap_distance_mm: float = Field(default=5.0, ge=0, le=MAX_SNAP_DISTANCE_MM)
    timeout_s: float = Field(default=60.0, gt=0, le=120.0)


def _authority_payload() -> Dict[str, Any]:
    return {
        "authority": "declared",
        "connector_mating_verified": False,
        "fit_verified": False,
        "full_assembly_collision": False,
        "service_access_verified": False,
        "structural_analysis": False,
        "physical_measurement": False,
        "automatic_execution": False,
        "physical_action": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _anchor_payload(report: BrepSurfaceAnchorReport) -> Dict[str, Any]:
    return {
        "ok": True,
        "brep_surface_anchor": report.model_dump(mode="json"),
        "kernel_available": report.kernel_available,
        "exact_brep_surface_anchor_evaluated": report.status.value == "ready",
        "interface_binding_declared": True,
        "raw_step_bytes_returned": False,
        **_authority_payload(),
    }


def _build(
    request: MechanicalBrepSurfaceAnchorRequest | MechanicalStoredBrepSurfaceAnchorRequest,
    *,
    content: str,
) -> BrepSurfaceAnchorReport:
    return build_step_brep_surface_anchor(
        project_id=request.project_id,
        anchor_id=request.anchor_id,
        interface_id=request.interface_id,
        content=content,
        source_id=request.source.source_id,
        model_id=request.source.model_id,
        expected_content_hash=request.source.content_hash,
        placement=request.placement,
        probe_point_mm=list(request.probe_point_mm),
        max_snap_distance_mm=request.max_snap_distance_mm,
        timeout_s=request.timeout_s,
    )


def create_mechanical_brep_anchor_router(project_store: ProjectStore | None = None) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(
        prefix="/v1/engineering/mechanical",
        tags=["engineering", "mechanical", "brep-anchor"],
    )

    @router.get("/geometry/brep/anchor/schema")
    def brep_anchor_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": BREP_ANCHOR_SCHEMA,
            "request_schema": MechanicalBrepSurfaceAnchorRequest.model_json_schema(),
            "stored_request_schema": MechanicalStoredBrepSurfaceAnchorRequest.model_json_schema(),
            "report_schema": BrepSurfaceAnchorReport.model_json_schema(),
            "optional_kernel": "cadquery-isolated",
            "maximum_snap_distance_mm": MAX_SNAP_DISTANCE_MM,
            "hash_bound_source_required": True,
            "declared_placement_required": True,
            "kernel_surface_snap": True,
            "interface_binding_declared": True,
            "registered_source_materialization": "content_addressed_hash_reverified_server_side",
            "raw_step_bytes_returned": False,
            **_authority_payload(),
        }

    @router.post("/geometry/brep/anchor")
    def build_brep_anchor(request: MechanicalBrepSurfaceAnchorRequest) -> Dict[str, Any]:
        try:
            report = _build(request, content=request.source.content)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_surface_anchor_request", "message": str(exc)},
            ) from exc
        return _anchor_payload(report)

    @router.post("/geometry/brep/anchor/stored")
    def build_stored_brep_anchor(request: MechanicalStoredBrepSurfaceAnchorRequest) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(request.project_id)
            snapshot = envelope.get("snapshot")
            if not isinstance(snapshot, Mapping):
                raise ValueError("project snapshot is unavailable")
            descriptor = _resolve_registered_step_source(snapshot, request.source)
            content = _registered_step_text(store, request.project_id, descriptor)
            report = _build(request, content=content)
            if report.content_hash != request.source.content_hash:
                raise ValueError(
                    "stored STEP anchor canonical hash disagrees with the registered source identity"
                )
            report = report.model_copy(
                update={
                    "metadata": {
                        **report.metadata,
                        "source_materialization": "registered_blob_hash_reverified_server_side",
                        "registered_raw_bytes_returned": False,
                    }
                }
            )
        except ProjectNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"type": "project_not_found", "message": str(exc)},
            ) from exc
        except ProjectStoreError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"type": "project_store_error", "message": str(exc)},
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_stored_brep_surface_anchor_request", "message": str(exc)},
            ) from exc
        return {
            **_anchor_payload(report),
            "registered_source_materialized": True,
            "registered_source_hash_reverified": True,
            "raw_registered_source_bytes_returned": False,
        }

    return router
