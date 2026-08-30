"""Product API for bounded STEP identity and mechanical-fit reconciliation."""

from __future__ import annotations

from typing import Any, Dict, Mapping

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
from .project_store import ProjectNotFound, ProjectStore, ProjectStoreError
from .step_geometry import (
    DeclaredMountInterface,
    MechanicalGeometryReport,
    build_mechanical_geometry_report,
    parse_step_model,
)
from .stored_source_parser import read_registered_source_bytes


class MechanicalStepSource(BaseModel):
    source_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    model_id: str | None = None
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")


class RegisteredMechanicalStepSource(BaseModel):
    source_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    model_id: str = Field(min_length=1)


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
    minimum_clearance_mm: float | None = Field(default=None, ge=0.0)
    timeout_s: float = Field(default=60.0, gt=0.0, le=120.0)


class MechanicalStoredBrepInterferenceRequest(BaseModel):
    project_id: str = Field(min_length=1)
    first_source: RegisteredMechanicalStepSource
    second_source: RegisteredMechanicalStepSource
    first_placement: DeclaredGeometryPlacement
    second_placement: DeclaredGeometryPlacement
    minimum_clearance_mm: float | None = Field(default=None, ge=0.0)
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


def _brep_clearance_payload(
    report: BrepPairInterferenceReport,
    minimum_clearance_mm: float | None,
) -> Dict[str, Any]:
    if minimum_clearance_mm is None:
        return {
            "exact_minimum_clearance_evaluated": False,
            "minimum_clearance_requirement_mm": None,
            "minimum_clearance_passed": None,
            "minimum_clearance_message": None,
        }
    if (
        not report.exact_pair_interference_evaluated
        or report.exact_solid_interference is None
        or report.minimum_distance_mm is None
    ):
        return {
            "exact_minimum_clearance_evaluated": False,
            "minimum_clearance_requirement_mm": minimum_clearance_mm,
            "minimum_clearance_passed": None,
            "minimum_clearance_message": (
                f"Exact BREP minimum-clearance requirement {minimum_clearance_mm:.3f} mm remains UNKNOWN "
                "because pairwise kernel evidence is unavailable."
            ),
        }

    passed = (
        report.exact_solid_interference is False
        and report.minimum_distance_mm >= minimum_clearance_mm
    )
    if report.exact_solid_interference:
        message = (
            f"Exact BREP solids interfere by {float(report.intersection_volume_mm3 or 0.0):.3f} mm^3; "
            f"the {minimum_clearance_mm:.3f} mm minimum-clearance requirement fails."
        )
    elif passed:
        message = (
            f"Exact BREP minimum distance {report.minimum_distance_mm:.3f} mm meets the "
            f"{minimum_clearance_mm:.3f} mm requirement."
        )
    else:
        message = (
            f"Exact BREP minimum distance {report.minimum_distance_mm:.3f} mm is below the "
            f"{minimum_clearance_mm:.3f} mm requirement."
        )
    return {
        "exact_minimum_clearance_evaluated": True,
        "minimum_clearance_requirement_mm": minimum_clearance_mm,
        "minimum_clearance_passed": passed,
        "minimum_clearance_message": message,
    }


def _brep_payload(
    report: BrepPairInterferenceReport,
    minimum_clearance_mm: float | None = None,
) -> Dict[str, Any]:
    return {
        "ok": True,
        "brep_interference": report.model_dump(mode="json"),
        "kernel_available": report.kernel_available,
        "exact_pair_interference_evaluated": report.exact_pair_interference_evaluated,
        "exact_solid_interference": report.exact_solid_interference,
        "minimum_distance_mm": report.minimum_distance_mm,
        "intersection_volume_mm3": report.intersection_volume_mm3,
        **_brep_clearance_payload(report, minimum_clearance_mm),
        "aabb_fallback_used": False,
        "full_brep_collision": False,
        "connector_mating_verified": False,
        "cable_routing_verified": False,
        "service_access_verified": False,
        "structural_analysis": False,
        "physical_measurement": False,
        **_authority_payload(),
    }


def _source_hash(source: Mapping[str, Any]) -> str:
    return str(source.get("content_hash") or source.get("revision") or "")


def _require_inline_source_hashes(
    request: MechanicalBrepInterferenceRequest,
    report: BrepPairInterferenceReport,
) -> None:
    if (
        request.first_source.content_hash is not None
        and report.first_content_hash != request.first_source.content_hash
    ):
        raise ValueError("first inline STEP content no longer matches its expected canonical content_hash")
    if (
        request.second_source.content_hash is not None
        and report.second_content_hash != request.second_source.content_hash
    ):
        raise ValueError("second inline STEP content no longer matches its expected canonical content_hash")


def _resolve_registered_step_source(
    snapshot: Mapping[str, Any],
    reference: RegisteredMechanicalStepSource,
) -> Mapping[str, Any]:
    sources = snapshot.get("engineeringSources")
    if not isinstance(sources, list):
        raise ValueError("project snapshot contains no registered engineering sources")
    matches = [
        row
        for row in sources
        if isinstance(row, Mapping)
        and str(row.get("source_id") or "") == reference.source_id
        and _source_hash(row) == reference.content_hash
    ]
    if len(matches) != 1:
        raise ValueError(
            f"registered STEP source {reference.source_id!r} at {reference.content_hash!r} was not found exactly once"
        )
    source = matches[0]
    metadata = source.get("metadata")
    parser_route = str(metadata.get("parser_route") or "") if isinstance(metadata, Mapping) else ""
    if parser_route != "step_geometry":
        raise ValueError(
            f"registered source {reference.source_id!r} is not classified for bounded STEP geometry"
        )
    return source


def _registered_step_text(
    store: ProjectStore,
    project_id: str,
    source: Mapping[str, Any],
) -> str:
    content = read_registered_source_bytes(
        project_id,
        source,
        project_root=store.root,
    )
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("registered STEP source must be UTF-8/ASCII text for the canonical STEP parser") from exc


def create_mechanical_router(project_store: ProjectStore | None = None) -> APIRouter:
    store = project_store or ProjectStore()
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
            "stored_brep_pair_interference_request_schema": MechanicalStoredBrepInterferenceRequest.model_json_schema(),
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
            "exact_pair_brep_minimum_clearance_when_kernel_available": True,
            "inline_brep_expected_content_hash_supported": True,
            "registered_source_brep_materialization": "content_addressed_hash_reverified_server_side",
            "raw_registered_source_bytes_returned": False,
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
            _require_inline_source_hashes(request, report)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_brep_interference_request", "message": str(exc)},
            ) from exc
        return _brep_payload(report, request.minimum_clearance_mm)

    @router.post("/geometry/brep/interference/stored")
    def check_stored_brep_interference(request: MechanicalStoredBrepInterferenceRequest) -> Dict[str, Any]:
        try:
            envelope = store.load_latest_with_recovery(request.project_id)
            snapshot = envelope.get("snapshot")
            if not isinstance(snapshot, Mapping):
                raise ValueError("project snapshot is unavailable")
            first_descriptor = _resolve_registered_step_source(snapshot, request.first_source)
            second_descriptor = _resolve_registered_step_source(snapshot, request.second_source)
            first_content = _registered_step_text(store, request.project_id, first_descriptor)
            second_content = _registered_step_text(store, request.project_id, second_descriptor)
            report = check_step_brep_interference(
                project_id=request.project_id,
                first_content=first_content,
                first_source_id=request.first_source.source_id,
                first_model_id=request.first_source.model_id,
                first_placement=request.first_placement,
                second_content=second_content,
                second_source_id=request.second_source.source_id,
                second_model_id=request.second_source.model_id,
                second_placement=request.second_placement,
                timeout_s=request.timeout_s,
            )
            if report.first_content_hash != request.first_source.content_hash:
                raise ValueError("first stored STEP canonical hash disagrees with the registered source identity")
            if report.second_content_hash != request.second_source.content_hash:
                raise ValueError("second stored STEP canonical hash disagrees with the registered source identity")
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
                detail={"type": "invalid_stored_brep_interference_request", "message": str(exc)},
            ) from exc
        return {
            **_brep_payload(report, request.minimum_clearance_mm),
            "registered_source_materialized": True,
            "registered_source_hash_reverified": True,
            "raw_registered_source_bytes_returned": False,
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