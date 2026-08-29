"""Product API for bounded STEP identity and mechanical-fit reconciliation."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .mechanical_access import DeclaredInterfaceAccess, build_declared_access_box
from .mechanical_brep import BrepPairInterferenceReport, check_step_brep_interference
from .mechanical_fit import (
    ClearanceBox,
    ClearanceRequirement,
    FastenerStack,
    MechanicalFitReport,
    build_mechanical_fit_report,
)
from .mechanical_fit_plan_update import apply_mechanical_fit_to_plan
from .mechanical_geometry_plan_update import apply_mechanical_geometry_to_plan
from .mechanical_placement import DeclaredGeometryPlacement, build_declared_placement_box
from .step_geometry import (
    DeclaredMountInterface,
    MechanicalGeometryReport,
    build_mechanical_geometry_report,
    parse_step_model,
)


class MechanicalStepSource(BaseModel):
    source_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    model_id: str | None = None


class MechanicalGeometryParseRequest(BaseModel):
    project_id: str = Field(min_length=1)
    sources: list[MechanicalStepSource] = Field(min_length=1)
    mounts: list[DeclaredMountInterface] = Field(default_factory=list)


class MechanicalGeometryPlaceRequest(BaseModel):
    geometry: MechanicalGeometryReport
    placements: list[DeclaredGeometryPlacement] = Field(min_length=1)


class MechanicalBrepInterferenceRequest(BaseModel):
    project_id: str = Field(min_length=1)
    first_source: MechanicalStepSource
    second_source: MechanicalStepSource
    first_placement: DeclaredGeometryPlacement
    second_placement: DeclaredGeometryPlacement
    timeout_s: float = Field(default=60.0, gt=0.0, le=120.0)


class MechanicalInterfaceAccessRequest(BaseModel):
    object_box: ClearanceBox
    access: DeclaredInterfaceAccess


class MechanicalGeometryApplyRequest(BaseModel):
    plan: Dict[str, Any]
    report: MechanicalGeometryReport


class MechanicalFitCheckRequest(BaseModel):
    geometry: MechanicalGeometryReport
    clearance_boxes: list[ClearanceBox] = Field(default_factory=list)
    clearance_requirements: list[ClearanceRequirement] = Field(default_factory=list)
    fastener_stacks: list[FastenerStack] = Field(default_factory=list)
    normal_tolerance_deg: float = Field(default=5.0, ge=0.0, le=90.0)


class MechanicalFitApplyRequest(BaseModel):
    plan: Dict[str, Any]
    report: MechanicalFitReport


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


def create_mechanical_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/mechanical",
        tags=["engineering", "mechanical"],
    )

    @router.get("/schema")
    def mechanical_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "geometry_parse_request_schema": MechanicalGeometryParseRequest.model_json_schema(),
            "geometry_place_request_schema": MechanicalGeometryPlaceRequest.model_json_schema(),
            "brep_pair_interference_request_schema": MechanicalBrepInterferenceRequest.model_json_schema(),
            "interface_access_request_schema": MechanicalInterfaceAccessRequest.model_json_schema(),
            "geometry_report_schema": MechanicalGeometryReport.model_json_schema(),
            "placement_schema": DeclaredGeometryPlacement.model_json_schema(),
            "brep_pair_interference_report_schema": BrepPairInterferenceReport.model_json_schema(),
            "interface_access_schema": DeclaredInterfaceAccess.model_json_schema(),
            "fit_report_schema": MechanicalFitReport.model_json_schema(),
            "fit_check_request_schema": MechanicalFitCheckRequest.model_json_schema(),
            "geometry_apply_request_schema": MechanicalGeometryApplyRequest.model_json_schema(),
            "fit_apply_request_schema": MechanicalFitApplyRequest.model_json_schema(),
            "step_point_envelope_only": True,
            "declared_rigid_placement_only": True,
            "declared_interface_access_only": True,
            "optional_brep_kernel": "cadquery-isolated",
            "exact_pair_brep_interference_when_kernel_available": True,
            "full_brep_collision": False,
            "structural_analysis": False,
            "thread_strength_verified": False,
            **_authority_payload(),
        }

    @router.post("/geometry/parse")
    def parse_geometry(request: MechanicalGeometryParseRequest) -> Dict[str, Any]:
        try:
            models = [
                parse_step_model(
                    source.content,
                    source_id=source.source_id,
                    model_id=source.model_id,
                )
                for source in request.sources
            ]
            report = build_mechanical_geometry_report(
                project_id=request.project_id,
                models=models,
                mounts=request.mounts,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_step_geometry", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "mechanical_geometry": report.model_dump(mode="json"),
            "model_count": len(report.models),
            "blocking_check_count": len(report.blocking_checks),
            "step_point_envelope_only": True,
            "full_brep_collision": False,
            "mass_properties_verified": False,
            **_authority_payload(),
        }

    @router.post("/geometry/place")
    def place_geometry(request: MechanicalGeometryPlaceRequest) -> Dict[str, Any]:
        models = {model.model_id: model for model in request.geometry.models}
        try:
            boxes = []
            for placement in request.placements:
                model = models.get(placement.model_id)
                if model is None:
                    raise ValueError(
                        f"placement {placement.placement_id!r} references unknown STEP model {placement.model_id!r}"
                    )
                boxes.append(build_declared_placement_box(model, placement))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_mechanical_placement", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "clearance_boxes": [box.model_dump(mode="json") for box in boxes],
            "placement_count": len(boxes),
            "declared_rigid_placement_only": True,
            "aabb_only": True,
            "full_brep_collision": False,
            "physical_measurement": False,
            **_authority_payload(),
        }

    @router.post("/geometry/brep/interference")
    def check_brep_interference(request: MechanicalBrepInterferenceRequest) -> Dict[str, Any]:
        try:
            report = check_step_brep_interference(
                project_id=request.project_id,
                first_content=request.first_source.content,
                first_source_id=request.first_source.source_id,
                first_model_id=request.first_source.model_id,
                first_placement=request.first_placement,
                second_content=request.second_source.content,
                second_source_id=request.second_source.source_id,
                second_model_id=request.second_source.model_id,
                second_placement=request.second_placement,
                timeout_s=request.timeout_s,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_interference_request", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "brep_interference": report.model_dump(mode="json"),
            "kernel_available": report.kernel_available,
            "exact_pair_interference_evaluated": report.exact_pair_interference_evaluated,
            "exact_solid_interference": report.exact_solid_interference,
            "minimum_distance_mm": report.minimum_distance_mm,
            "intersection_volume_mm3": report.intersection_volume_mm3,
            "aabb_fallback_used": False,
            "full_brep_collision": False,
            "connector_mating_verified": False,
            "cable_routing_verified": False,
            "service_access_verified": False,
            "structural_analysis": False,
            "physical_measurement": False,
            **_authority_payload(),
        }

    @router.post("/interfaces/access-envelope")
    def build_interface_access(request: MechanicalInterfaceAccessRequest) -> Dict[str, Any]:
        try:
            access_box = build_declared_access_box(request.object_box, request.access)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_interface_access", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "access_box": access_box.model_dump(mode="json"),
            "declared_interface_access_only": True,
            "aabb_only": True,
            "cable_routing_verified": False,
            "connector_mating_verified": False,
            "service_access_verified": False,
            "full_brep_collision": False,
            "physical_measurement": False,
            **_authority_payload(),
        }

    @router.post("/geometry/apply")
    def apply_geometry(request: MechanicalGeometryApplyRequest) -> Dict[str, Any]:
        try:
            plan = apply_mechanical_geometry_to_plan(request.plan, request.report)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_mechanical_geometry", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "plan": plan,
            "mechanical_geometry": plan.get("mechanical_geometry"),
            "engineering_status": plan.get("engineering_status"),
            "engineering_readiness": plan.get("engineering_readiness"),
            **_authority_payload(),
        }

    @router.post("/fit/check")
    def check_fit(request: MechanicalFitCheckRequest) -> Dict[str, Any]:
        try:
            report = build_mechanical_fit_report(
                request.geometry,
                clearance_boxes=request.clearance_boxes,
                clearance_requirements=request.clearance_requirements,
                fastener_stacks=request.fastener_stacks,
                normal_tolerance_deg=request.normal_tolerance_deg,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_mechanical_fit", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "mechanical_fit": report.model_dump(mode="json"),
            "blocking_check_count": len(report.blocking_checks),
            "full_brep_collision": False,
            "structural_analysis": False,
            "thread_strength_verified": False,
            **_authority_payload(),
        }

    @router.post("/fit/apply")
    def apply_fit(request: MechanicalFitApplyRequest) -> Dict[str, Any]:
        try:
            plan = apply_mechanical_fit_to_plan(request.plan, request.report)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_mechanical_fit", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "plan": plan,
            "mechanical_fit": plan.get("mechanical_fit"),
            "manufacturing_closure": plan.get("manufacturing_closure"),
            "engineering_status": plan.get("engineering_status"),
            "engineering_readiness": plan.get("engineering_readiness"),
            **_authority_payload(),
        }

    return router
