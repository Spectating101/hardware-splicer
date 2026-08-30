"""Product API for bounded sampled and adaptively refined exact-BREP mating-path evidence."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .mechanical_brep_sweep import (
    BREP_SWEEP_SCHEMA,
    MAX_SWEEP_SAMPLES,
    MIN_SWEEP_SAMPLES,
    BrepMatingPathSweepReport,
    evaluate_step_brep_mating_path,
)
from .mechanical_brep_transition_refinement import (
    BREP_REFINEMENT_SCHEMA,
    DEFAULT_REFINEMENT_DEPTH,
    DEFAULT_REFINEMENT_FRACTION_TOLERANCE,
    MAX_REFINEMENT_DEPTH,
    MAX_REFINEMENT_FRACTION_TOLERANCE,
    MIN_REFINEMENT_DEPTH,
    MIN_REFINEMENT_FRACTION_TOLERANCE,
    BrepMatingPathRefinementReport,
    evaluate_step_brep_mating_path_refinement,
)
from .mechanical_placement import DeclaredGeometryPlacement


class MechanicalBrepSweepStepSource(BaseModel):
    source_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    model_id: str | None = None
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")


class MechanicalBrepMatingPathRequest(BaseModel):
    project_id: str = Field(min_length=1)
    sweep_id: str = Field(min_length=1)
    moving_source: MechanicalBrepSweepStepSource
    fixed_source: MechanicalBrepSweepStepSource
    moving_start_placement: DeclaredGeometryPlacement
    moving_end_placement: DeclaredGeometryPlacement
    fixed_placement: DeclaredGeometryPlacement
    sample_count: int = Field(default=9, ge=MIN_SWEEP_SAMPLES, le=MAX_SWEEP_SAMPLES)
    engagement_start_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    contact_distance_tolerance_mm: float = Field(default=1e-6, ge=0.0, le=100.0)
    timeout_s: float = Field(default=120.0, gt=0.0, le=180.0)


class MechanicalBrepMatingPathRefinementRequest(MechanicalBrepMatingPathRequest):
    refinement_max_depth: int = Field(
        default=DEFAULT_REFINEMENT_DEPTH,
        ge=MIN_REFINEMENT_DEPTH,
        le=MAX_REFINEMENT_DEPTH,
    )
    refinement_fraction_tolerance: float = Field(
        default=DEFAULT_REFINEMENT_FRACTION_TOLERANCE,
        ge=MIN_REFINEMENT_FRACTION_TOLERANCE,
        le=MAX_REFINEMENT_FRACTION_TOLERANCE,
    )


def _authority_payload() -> Dict[str, Any]:
    return {
        "authority": "declared",
        "sampled_path_only": True,
        "continuous_path_verified": False,
        "continuous_collision_free_verified": False,
        "connector_mating_verified": False,
        "protocol_compatibility_verified": False,
        "pin_compatibility_verified": False,
        "retention_verified": False,
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


def _require_expected_hashes(
    request: MechanicalBrepMatingPathRequest,
    report: BrepMatingPathSweepReport | BrepMatingPathRefinementReport,
) -> None:
    if (
        request.moving_source.content_hash is not None
        and report.moving_content_hash != request.moving_source.content_hash
    ):
        raise ValueError("moving inline STEP content no longer matches its expected canonical content_hash")
    if (
        request.fixed_source.content_hash is not None
        and report.fixed_content_hash != request.fixed_source.content_hash
    ):
        raise ValueError("fixed inline STEP content no longer matches its expected canonical content_hash")


def _payload(report: BrepMatingPathSweepReport) -> Dict[str, Any]:
    return {
        "ok": True,
        # Absent sampled events remain absent rather than JSON null. That prevents UI
        # number coercion from manufacturing a fictitious sample zero for "not observed".
        "brep_mating_path": report.model_dump(mode="json", exclude_none=True),
        "kernel_available": report.kernel_available,
        "sampled_path_evaluated": report.status.value == "ready",
        "sampled_path_interference_free": report.sampled_path_interference_free,
        "approach_interference_free": report.approach_interference_free,
        "engagement_region_evaluated": report.engagement_region_evaluated,
        "engagement_region_interference_free": report.engagement_region_interference_free,
        "first_contact_sample_index": report.first_contact_sample_index,
        "first_interference_sample_index": report.first_interference_sample_index,
        "aabb_fallback_used": False,
        **_authority_payload(),
    }


def _refinement_payload(report: BrepMatingPathRefinementReport) -> Dict[str, Any]:
    return {
        "ok": True,
        "brep_mating_path_refinement": report.model_dump(mode="json", exclude_none=True),
        "kernel_available": report.kernel_available,
        "adaptive_transition_refinement": True,
        "transition_brackets_only": True,
        "unique_transition_pose_verified": False,
        "monotonicity_inside_bracket_verified": False,
        "refinement_evaluated": report.status.value in {"ready", "not_required"},
        "refinement_required": report.refinement_candidate_count > 0,
        "refined_boundary_count": report.refined_boundary_count,
        "refinement_evaluated_pose_count": report.refinement_evaluated_pose_count,
        "total_exact_pose_evaluations": report.total_exact_pose_evaluations,
        "aabb_fallback_used": False,
        **_authority_payload(),
    }


def create_mechanical_brep_sweep_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/mechanical",
        tags=["engineering", "mechanical", "brep-mating-path"],
    )

    @router.get("/geometry/brep/mating-path/schema")
    def brep_mating_path_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": BREP_SWEEP_SCHEMA,
            "request_schema": MechanicalBrepMatingPathRequest.model_json_schema(),
            "report_schema": BrepMatingPathSweepReport.model_json_schema(),
            "translation_only_path": True,
            "bounded_sample_count": {"minimum": MIN_SWEEP_SAMPLES, "maximum": MAX_SWEEP_SAMPLES},
            "exact_brep_per_sample": True,
            "contact_event_is_sampled_only": True,
            "interference_event_is_sampled_only": True,
            "declared_engagement_region_supported": True,
            **_authority_payload(),
        }

    @router.get("/geometry/brep/mating-path/refine/schema")
    def brep_mating_path_refinement_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": BREP_REFINEMENT_SCHEMA,
            "request_schema": MechanicalBrepMatingPathRefinementRequest.model_json_schema(),
            "report_schema": BrepMatingPathRefinementReport.model_json_schema(),
            "adaptive_transition_refinement": True,
            "transition_brackets_only": True,
            "refined_predicates": ["clearance_boundary", "interference_boundary"],
            "bounded_refinement_depth": {
                "minimum": MIN_REFINEMENT_DEPTH,
                "maximum": MAX_REFINEMENT_DEPTH,
            },
            "bounded_fraction_tolerance": {
                "minimum": MIN_REFINEMENT_FRACTION_TOLERANCE,
                "maximum": MAX_REFINEMENT_FRACTION_TOLERANCE,
            },
            "unique_transition_pose_verified": False,
            "monotonicity_inside_bracket_verified": False,
            **_authority_payload(),
        }

    @router.post("/geometry/brep/mating-path")
    def evaluate_mating_path(request: MechanicalBrepMatingPathRequest) -> Dict[str, Any]:
        try:
            report = evaluate_step_brep_mating_path(
                project_id=request.project_id,
                sweep_id=request.sweep_id,
                moving_content=request.moving_source.content,
                moving_source_id=request.moving_source.source_id,
                moving_model_id=request.moving_source.model_id,
                moving_start_placement=request.moving_start_placement,
                moving_end_placement=request.moving_end_placement,
                fixed_content=request.fixed_source.content,
                fixed_source_id=request.fixed_source.source_id,
                fixed_model_id=request.fixed_source.model_id,
                fixed_placement=request.fixed_placement,
                sample_count=request.sample_count,
                engagement_start_fraction=request.engagement_start_fraction,
                contact_distance_tolerance_mm=request.contact_distance_tolerance_mm,
                timeout_s=request.timeout_s,
            )
            _require_expected_hashes(request, report)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_mating_path_request", "message": str(exc)},
            ) from exc
        return _payload(report)

    @router.post("/geometry/brep/mating-path/refine")
    def refine_mating_path(request: MechanicalBrepMatingPathRefinementRequest) -> Dict[str, Any]:
        try:
            report = evaluate_step_brep_mating_path_refinement(
                project_id=request.project_id,
                sweep_id=request.sweep_id,
                moving_content=request.moving_source.content,
                moving_source_id=request.moving_source.source_id,
                moving_model_id=request.moving_source.model_id,
                moving_start_placement=request.moving_start_placement,
                moving_end_placement=request.moving_end_placement,
                fixed_content=request.fixed_source.content,
                fixed_source_id=request.fixed_source.source_id,
                fixed_model_id=request.fixed_source.model_id,
                fixed_placement=request.fixed_placement,
                sample_count=request.sample_count,
                engagement_start_fraction=request.engagement_start_fraction,
                contact_distance_tolerance_mm=request.contact_distance_tolerance_mm,
                refinement_max_depth=request.refinement_max_depth,
                refinement_fraction_tolerance=request.refinement_fraction_tolerance,
                timeout_s=request.timeout_s,
            )
            _require_expected_hashes(request, report)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_mating_path_refinement_request", "message": str(exc)},
            ) from exc
        return _refinement_payload(report)

    return router
