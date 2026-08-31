"""Product API for pairwise geometric mating evaluation over exact BREP anchors."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .mechanical_brep_mating import (
    BREP_MATING_SCHEMA,
    BrepAnchorMatingReport,
    BrepMatingAnchor,
    BrepMatingRequirements,
    evaluate_brep_anchor_mating,
)


class MechanicalBrepAnchorMatingRequest(BaseModel):
    project_id: str = Field(min_length=1)
    mating_id: str = Field(min_length=1)
    first_anchor: BrepMatingAnchor
    second_anchor: BrepMatingAnchor
    requirements: BrepMatingRequirements = Field(default_factory=BrepMatingRequirements)


def _authority_payload() -> Dict[str, Any]:
    return {
        "authority": "declared",
        "geometric_mating_only": True,
        "connector_mating_verified": False,
        "protocol_compatibility_verified": False,
        "pin_compatibility_verified": False,
        "retention_verified": False,
        "swept_engagement_collision": False,
        "whole_assembly_collision": False,
        "physical_measurement": False,
        "automatic_execution": False,
        "physical_action": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _payload(report: BrepAnchorMatingReport) -> Dict[str, Any]:
    return {
        "ok": True,
        "brep_anchor_mating": report.model_dump(mode="json"),
        "mating_geometry_evaluated": report.status.value == "ready",
        "geometric_mating_passed": report.geometric_mating_passed,
        "common_frame": report.metadata.get("common_frame") is True,
        **_authority_payload(),
    }


def create_mechanical_brep_mating_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/mechanical",
        tags=["engineering", "mechanical", "brep-mating"],
    )

    @router.get("/geometry/brep/mating/schema")
    def brep_mating_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": BREP_MATING_SCHEMA,
            "request_schema": MechanicalBrepAnchorMatingRequest.model_json_schema(),
            "report_schema": BrepAnchorMatingReport.model_json_schema(),
            "requires_ready_exact_surface_anchors": True,
            "same_interface_required": True,
            "common_frame_required": True,
            "normal_opposition_evaluated": True,
            "axial_offset_evaluated": True,
            "lateral_offset_evaluated": True,
            "coaxiality_requires_declared_axis": True,
            "engagement_depth_kernel_inferred": False,
            "declared_engagement_requirement_supported": True,
            **_authority_payload(),
        }

    @router.post("/geometry/brep/mating")
    def evaluate_mating(request: MechanicalBrepAnchorMatingRequest) -> Dict[str, Any]:
        try:
            report = evaluate_brep_anchor_mating(
                project_id=request.project_id,
                mating_id=request.mating_id,
                first=request.first_anchor,
                second=request.second_anchor,
                requirements=request.requirements,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_anchor_mating_request", "message": str(exc)},
            ) from exc
        return _payload(report)

    return router
