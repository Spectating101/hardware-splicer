"""Product API for bounded exact-anchor bridge adapter synthesis."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .mechanical_brep_adapter import (
    BREP_ADAPTER_SCHEMA,
    MAX_ADAPTER_SPAN_MM,
    MAX_AXIS_ALIGNMENT_ERROR_DEG,
    MAX_CROSS_SECTION_MM,
    MIN_ADAPTER_SPAN_MM,
    MIN_CROSS_SECTION_MM,
    BrepAdapterCandidateReport,
    BrepAdapterParameters,
    synthesize_brep_bridge_adapter,
)
from .mechanical_brep_mating import BrepMatingAnchor
from .mechanical_brep_mesh_api import (
    RegisteredMechanicalBrepMeshSource,
    _registered_step_text,
    _resolve_registered_step_source,
)
from .mechanical_placement import DeclaredGeometryPlacement
from .project_store import ProjectNotFound, ProjectStore, ProjectStoreError


class MechanicalBrepAdapterSource(BaseModel):
    source_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content: str = Field(min_length=1)


class MechanicalBrepAdapterParent(BaseModel):
    source: MechanicalBrepAdapterSource
    placement: DeclaredGeometryPlacement
    anchor: BrepMatingAnchor


class MechanicalStoredBrepAdapterParent(BaseModel):
    source: RegisteredMechanicalBrepMeshSource
    placement: DeclaredGeometryPlacement
    anchor: BrepMatingAnchor


class MechanicalBrepAdapterRequest(BaseModel):
    project_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    first: MechanicalBrepAdapterParent
    second: MechanicalBrepAdapterParent
    parameters: BrepAdapterParameters = Field(default_factory=BrepAdapterParameters)
    timeout_s: float = Field(default=90.0, gt=0.0, le=120.0)


class MechanicalStoredBrepAdapterRequest(BaseModel):
    project_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    first: MechanicalStoredBrepAdapterParent
    second: MechanicalStoredBrepAdapterParent
    parameters: BrepAdapterParameters = Field(default_factory=BrepAdapterParameters)
    timeout_s: float = Field(default=90.0, gt=0.0, le=120.0)


def _authority_payload() -> Dict[str, Any]:
    return {
        "authority": "declared",
        "geometric_candidate_only": True,
        "mounting_method_resolved": False,
        "retention_verified": False,
        "material_resolved": False,
        "structural_analysis": False,
        "tolerance_stack_verified": False,
        "connector_mating_verified": False,
        "electrical_compatibility_verified": False,
        "whole_assembly_collision": False,
        "service_access_verified": False,
        "physical_measurement": False,
        "automatic_execution": False,
        "physical_action": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _payload(report: BrepAdapterCandidateReport) -> Dict[str, Any]:
    return {
        "ok": True,
        "brep_adapter_candidate": report.model_dump(mode="json"),
        "kernel_available": report.kernel_available,
        "exact_adapter_geometry_evaluated": report.status.value == "ready",
        "geometric_candidate_passed": report.geometric_candidate_passed,
        "generated_step_available": bool(report.generated_step_content),
        "generated_content_hash": report.generated_content_hash,
        "vertex_count": report.vertex_count,
        "triangle_count": report.triangle_count,
        "parent_raw_step_bytes_returned": False,
        **_authority_payload(),
    }


def _build(
    request: MechanicalBrepAdapterRequest | MechanicalStoredBrepAdapterRequest,
    *,
    first_content: str,
    second_content: str,
) -> BrepAdapterCandidateReport:
    return synthesize_brep_bridge_adapter(
        project_id=request.project_id,
        adapter_id=request.adapter_id,
        first_content=first_content,
        first_source_id=request.first.source.source_id,
        first_model_id=request.first.source.model_id,
        first_expected_content_hash=request.first.source.content_hash,
        first_placement=request.first.placement,
        first_anchor=request.first.anchor,
        second_content=second_content,
        second_source_id=request.second.source.source_id,
        second_model_id=request.second.source.model_id,
        second_expected_content_hash=request.second.source.content_hash,
        second_placement=request.second.placement,
        second_anchor=request.second.anchor,
        parameters=request.parameters,
        timeout_s=request.timeout_s,
    )


def create_mechanical_brep_adapter_router(project_store: ProjectStore | None = None) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(
        prefix="/v1/engineering/mechanical",
        tags=["engineering", "mechanical", "brep-adapter"],
    )

    @router.get("/geometry/brep/adapter/schema")
    def brep_adapter_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": BREP_ADAPTER_SCHEMA,
            "request_schema": MechanicalBrepAdapterRequest.model_json_schema(),
            "stored_request_schema": MechanicalStoredBrepAdapterRequest.model_json_schema(),
            "report_schema": BrepAdapterCandidateReport.model_json_schema(),
            "optional_kernel": "cadquery-isolated",
            "supported_families": ["bridge_block_v0"],
            "requires_two_ready_exact_surface_anchors": True,
            "requires_distinct_placed_objects": True,
            "requires_common_frame": True,
            "requires_planar_anchor_faces": True,
            "minimum_span_mm": MIN_ADAPTER_SPAN_MM,
            "maximum_span_mm": MAX_ADAPTER_SPAN_MM,
            "minimum_cross_section_mm": MIN_CROSS_SECTION_MM,
            "maximum_cross_section_mm": MAX_CROSS_SECTION_MM,
            "maximum_axis_alignment_error_deg": MAX_AXIS_ALIGNMENT_ERROR_DEG,
            "generated_step_export": True,
            "generated_mesh_preview": True,
            "exact_parent_contact_checked": True,
            "exact_parent_penetration_checked": True,
            "registered_source_materialization": "content_addressed_hash_reverified_server_side",
            "parent_raw_step_bytes_returned": False,
            **_authority_payload(),
        }

    @router.post("/geometry/brep/adapter/synthesize")
    def synthesize_adapter(request: MechanicalBrepAdapterRequest) -> Dict[str, Any]:
        try:
            report = _build(
                request,
                first_content=request.first.source.content,
                second_content=request.second.source.content,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_adapter_request", "message": str(exc)},
            ) from exc
        return _payload(report)

    @router.post("/geometry/brep/adapter/synthesize/stored")
    def synthesize_stored_adapter(request: MechanicalStoredBrepAdapterRequest) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(request.project_id)
            snapshot = envelope.get("snapshot")
            if not isinstance(snapshot, Mapping):
                raise ValueError("project snapshot is unavailable")
            first_descriptor = _resolve_registered_step_source(snapshot, request.first.source)
            second_descriptor = _resolve_registered_step_source(snapshot, request.second.source)
            first_content = _registered_step_text(store, request.project_id, first_descriptor)
            second_content = _registered_step_text(store, request.project_id, second_descriptor)
            report = _build(
                request,
                first_content=first_content,
                second_content=second_content,
            )
            if (
                report.first_content_hash != request.first.source.content_hash
                or report.second_content_hash != request.second.source.content_hash
            ):
                raise ValueError("stored STEP adapter parent hash disagrees with registered source identity")
            report = report.model_copy(
                update={
                    "metadata": {
                        **report.metadata,
                        "source_materialization": "registered_blobs_hash_reverified_server_side",
                        "registered_parent_raw_bytes_returned": False,
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
                detail={"type": "invalid_stored_brep_adapter_request", "message": str(exc)},
            ) from exc
        return {
            **_payload(report),
            "registered_sources_materialized": True,
            "registered_source_hashes_reverified": True,
            "raw_registered_parent_bytes_returned": False,
        }

    return router
