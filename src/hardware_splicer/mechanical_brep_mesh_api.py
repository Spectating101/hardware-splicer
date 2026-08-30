"""Product API for bounded renderable STEP tessellation evidence."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .mechanical_brep_mesh import (
    BREP_MESH_SCHEMA,
    MAX_ANGULAR_TOLERANCE_RAD,
    MAX_MESH_TRIANGLES,
    MAX_MESH_VERTICES,
    MAX_TOLERANCE_MM,
    MIN_ANGULAR_TOLERANCE_RAD,
    MIN_TOLERANCE_MM,
    BrepRenderMeshReport,
    build_step_brep_render_mesh,
)
from .mechanical_placement import DeclaredGeometryPlacement


class MechanicalBrepMeshSource(BaseModel):
    source_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    model_id: str | None = None
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")


class MechanicalBrepMeshRequest(BaseModel):
    project_id: str = Field(min_length=1)
    source: MechanicalBrepMeshSource
    placement: DeclaredGeometryPlacement | None = None
    tolerance_mm: float = Field(default=0.5, ge=MIN_TOLERANCE_MM, le=MAX_TOLERANCE_MM)
    angular_tolerance_rad: float = Field(
        default=0.1,
        ge=MIN_ANGULAR_TOLERANCE_RAD,
        le=MAX_ANGULAR_TOLERANCE_RAD,
    )
    timeout_s: float = Field(default=60.0, gt=0.0, le=120.0)


def _authority_payload() -> Dict[str, Any]:
    return {
        "automatic_execution": False,
        "physical_action": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def create_mechanical_brep_mesh_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/mechanical",
        tags=["engineering", "mechanical", "brep-mesh"],
    )

    @router.get("/geometry/brep/mesh/schema")
    def brep_mesh_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": BREP_MESH_SCHEMA,
            "request_schema": MechanicalBrepMeshRequest.model_json_schema(),
            "report_schema": BrepRenderMeshReport.model_json_schema(),
            "optional_kernel": "cadquery-isolated",
            "minimum_tolerance_mm": MIN_TOLERANCE_MM,
            "maximum_tolerance_mm": MAX_TOLERANCE_MM,
            "minimum_angular_tolerance_rad": MIN_ANGULAR_TOLERANCE_RAD,
            "maximum_angular_tolerance_rad": MAX_ANGULAR_TOLERANCE_RAD,
            "maximum_vertices": MAX_MESH_VERTICES,
            "maximum_triangles": MAX_MESH_TRIANGLES,
            "hash_bound_inline_source_supported": True,
            "declared_placement_supported": True,
            "placement_transform_convention": "Rz*Ry*Rx; canonical STEP XYZ",
            "raw_step_bytes_returned": False,
            "render_evidence_only": True,
            "full_assembly_collision": False,
            "structural_analysis": False,
            "physical_measurement": False,
            **_authority_payload(),
        }

    @router.post("/geometry/brep/mesh")
    def build_brep_mesh(request: MechanicalBrepMeshRequest) -> Dict[str, Any]:
        try:
            report = build_step_brep_render_mesh(
                project_id=request.project_id,
                content=request.source.content,
                source_id=request.source.source_id,
                model_id=request.source.model_id,
                expected_content_hash=request.source.content_hash,
                placement=request.placement,
                tolerance_mm=request.tolerance_mm,
                angular_tolerance_rad=request.angular_tolerance_rad,
                timeout_s=request.timeout_s,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_mesh_request", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "brep_mesh": report.model_dump(mode="json"),
            "kernel_available": report.kernel_available,
            "exact_brep_mesh_evaluated": report.status.value == "ready",
            "declared_placement_applied": report.metadata.get("declared_placement_applied") is True,
            "vertex_count": report.vertex_count,
            "triangle_count": report.triangle_count,
            "raw_step_bytes_returned": False,
            "render_evidence_only": True,
            "full_assembly_collision": False,
            "connector_mating_verified": False,
            "cable_routing_verified": False,
            "service_access_verified": False,
            "structural_analysis": False,
            "physical_measurement": False,
            **_authority_payload(),
        }

    return router
