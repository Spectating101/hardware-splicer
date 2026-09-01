"""Bounded bridge-block synthesis over two exact, placed BREP surface anchors.

Adapter synthesis is deliberately narrower than general CAD authoring. The v0 family
accepts two distinct, common-frame, approximately opposed planar exact anchors and
asks an isolated CadQuery/OCCT worker to generate one bridge block between them.
The generated solid is then checked against both parent STEP solids for endpoint
contact and meaningful penetration.

A READY/PASS report means only that the generated solid satisfies the bounded
geometric contract against the supplied exact source/hash/pose identities. Mounting,
retention, material, strength, tolerance stack, manufacturing, and fabrication remain
unresolved and unauthorized.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .mechanical_brep import _diagnostic_suffix, _sanitized_environment, _terminate_process_tree
from .mechanical_brep_mating import BrepMatingAnchor
from .mechanical_placement import DeclaredGeometryPlacement
from .step_geometry import parse_step_model


BREP_ADAPTER_SCHEMA = "hardware_splicer.brep_adapter_candidate.v1"
BREP_ADAPTER_WORKER_SCHEMA = "hardware_splicer.cadquery_brep_adapter_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
ADAPTER_FAMILY = "bridge_block_v0"
MIN_ADAPTER_SPAN_MM = 0.5
MAX_ADAPTER_SPAN_MM = 2_000.0
MIN_CROSS_SECTION_MM = 0.5
MAX_CROSS_SECTION_MM = 250.0
MAX_AXIS_ALIGNMENT_ERROR_DEG = 30.0
MAX_CONTACT_TOLERANCE_MM = 1.0
MAX_PENETRATION_TOLERANCE_MM3 = 100.0
MAX_GENERATED_STEP_BYTES = 1_000_000
MAX_MESH_VERTICES = 5_000
MAX_MESH_TRIANGLES = 10_000
MAX_WORKER_RESPONSE_BYTES = 4 * 1024 * 1024
_DEFAULT_TIMEOUT_S = 90.0
_WORKER_PATH = Path(__file__).with_name("_cadquery_brep_adapter_worker.py")


class BrepAdapterStatus(str, Enum):
    READY = "ready"
    UNKNOWN = "unknown"


class BrepAdapterBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BrepAdapterParameters(BrepAdapterBase):
    family: Literal["bridge_block_v0"] = ADAPTER_FAMILY
    width_mm: float = Field(default=20.0, ge=MIN_CROSS_SECTION_MM, le=MAX_CROSS_SECTION_MM)
    thickness_mm: float = Field(default=4.0, ge=MIN_CROSS_SECTION_MM, le=MAX_CROSS_SECTION_MM)
    max_axis_alignment_error_deg: float = Field(default=10.0, ge=0.0, le=MAX_AXIS_ALIGNMENT_ERROR_DEG)
    contact_distance_tolerance_mm: float = Field(default=0.05, ge=0.0, le=MAX_CONTACT_TOLERANCE_MM)
    penetration_volume_tolerance_mm3: float = Field(default=0.001, ge=0.0, le=MAX_PENETRATION_TOLERANCE_MM3)
    tessellation_tolerance_mm: float = Field(default=0.5, ge=0.1, le=5.0)
    tessellation_angular_tolerance_rad: float = Field(default=0.1, ge=0.01, le=1.0)


class BrepAdapterCandidateReport(BrepAdapterBase):
    schema_version: str = BREP_ADAPTER_SCHEMA
    project_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    family: Literal["bridge_block_v0"] = ADAPTER_FAMILY
    frame_id: str = Field(min_length=1)
    first_anchor_id: str = Field(min_length=1)
    second_anchor_id: str = Field(min_length=1)
    first_object_id: str = Field(min_length=1)
    second_object_id: str = Field(min_length=1)
    first_source_id: str = Field(min_length=1)
    second_source_id: str = Field(min_length=1)
    first_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    second_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    first_placement_id: str = Field(min_length=1)
    second_placement_id: str = Field(min_length=1)
    status: BrepAdapterStatus
    kernel_available: bool
    kernel: str | None = None
    cadquery_version: str | None = None
    geometric_candidate_passed: bool | None = None
    adapter_axis: tuple[float, float, float] | None = None
    adapter_midpoint_mm: tuple[float, float, float] | None = None
    length_mm: float | None = Field(default=None, gt=0)
    width_mm: float = Field(gt=0)
    thickness_mm: float = Field(gt=0)
    volume_mm3: float | None = Field(default=None, gt=0)
    first_axis_alignment_error_deg: float | None = Field(default=None, ge=0, le=180)
    second_axis_alignment_error_deg: float | None = Field(default=None, ge=0, le=180)
    normal_opposition_error_deg: float | None = Field(default=None, ge=0, le=180)
    first_endpoint_error_mm: float | None = Field(default=None, ge=0)
    second_endpoint_error_mm: float | None = Field(default=None, ge=0)
    first_parent_minimum_distance_mm: float | None = Field(default=None, ge=0)
    second_parent_minimum_distance_mm: float | None = Field(default=None, ge=0)
    first_parent_intersection_volume_mm3: float | None = Field(default=None, ge=0)
    second_parent_intersection_volume_mm3: float | None = Field(default=None, ge=0)
    first_parent_contact_passed: bool | None = None
    second_parent_contact_passed: bool | None = None
    first_parent_penetration_passed: bool | None = None
    second_parent_penetration_passed: bool | None = None
    generated_source_id: str | None = None
    generated_model_id: str | None = None
    generated_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    generated_step_content: str | None = None
    generated_step_bytes: int | None = Field(default=None, ge=0, le=MAX_GENERATED_STEP_BYTES)
    bbox_minimum_mm: tuple[float, float, float] | None = None
    bbox_maximum_mm: tuple[float, float, float] | None = None
    vertex_count: int = Field(default=0, ge=0, le=MAX_MESH_VERTICES)
    triangle_count: int = Field(default=0, ge=0, le=MAX_MESH_TRIANGLES)
    vertices_mm: list[list[float]] = Field(default_factory=list)
    triangles: list[list[int]] = Field(default_factory=list)
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


Runner = Callable[..., Mapping[str, Any]]


def _cadquery_available() -> bool:
    try:
        return importlib.util.find_spec("cadquery") is not None
    except (ImportError, ValueError):
        return False


def _base_metadata() -> Dict[str, Any]:
    return {
        "specialist_capability": "cadquery-isolated",
        "scope": "two_anchor_bridge_block_geometric_candidate",
        "adapter_family": ADAPTER_FAMILY,
        "exact_anchor_inputs_required": True,
        "parent_source_hash_bound": True,
        "parent_pose_bound": True,
        "generated_geometry_exact_occt": True,
        "generated_step_export": True,
        "parent_pair_checks_exact_occt": True,
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
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _vector(values: tuple[float, float, float]) -> tuple[float, float, float]:
    row = tuple(float(value) for value in values)
    if len(row) != 3 or not all(math.isfinite(value) for value in row):
        raise ValueError("adapter vectors must contain three finite values")
    return row


def _sub(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(left[index] - right[index] for index in range(3))  # type: ignore[return-value]


def _scale(vector: tuple[float, float, float], scalar: float) -> tuple[float, float, float]:
    return tuple(value * scalar for value in vector)  # type: ignore[return-value]


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = _norm(vector)
    if length <= 1e-12:
        raise ValueError("adapter bridge axis must have non-zero length")
    return tuple(value / length for value in vector)  # type: ignore[return-value]


def _angle_deg(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    cosine = max(-1.0, min(1.0, _dot(_normalize(left), _normalize(right))))
    return math.degrees(math.acos(cosine))


def _unknown(
    *,
    project_id: str,
    adapter_id: str,
    first: BrepMatingAnchor,
    second: BrepMatingAnchor,
    parameters: BrepAdapterParameters,
    kernel_available: bool,
    reason: str,
    required_field: str,
    metadata: Mapping[str, Any] | None = None,
) -> BrepAdapterCandidateReport:
    return BrepAdapterCandidateReport(
        project_id=project_id,
        adapter_id=adapter_id,
        frame_id=first.frame_id,
        first_anchor_id=first.anchor_id,
        second_anchor_id=second.anchor_id,
        first_object_id=first.object_id,
        second_object_id=second.object_id,
        first_source_id=first.source_id,
        second_source_id=second.source_id,
        first_content_hash=first.content_hash,
        second_content_hash=second.content_hash,
        first_placement_id=first.placement_id,
        second_placement_id=second.placement_id,
        status=BrepAdapterStatus.UNKNOWN,
        kernel_available=kernel_available,
        width_mm=parameters.width_mm,
        thickness_mm=parameters.thickness_mm,
        required_evidence=[{"field": required_field, "reason": reason}],
        metadata={**_base_metadata(), **dict(metadata or {})},
    )


def _placement_payload(placement: DeclaredGeometryPlacement) -> Dict[str, Any]:
    return {
        "translation_mm": list(placement.translation_mm),
        "rotation_deg_xyz": list(placement.rotation_deg_xyz),
    }


def _validate_anchor_source_pose(
    *,
    anchor: BrepMatingAnchor,
    source_id: str,
    model_id: str,
    content_hash: str,
    placement: DeclaredGeometryPlacement,
    label: str,
) -> None:
    if anchor.source_id != source_id or anchor.model_id != model_id or anchor.content_hash != content_hash:
        raise ValueError(f"{label} exact anchor source identity disagrees with the supplied STEP source")
    if (
        anchor.object_id != placement.object_id
        or anchor.placement_id != placement.placement_id
        or anchor.frame_id != placement.target_frame
        or anchor.model_id != placement.model_id
    ):
        raise ValueError(f"{label} exact anchor pose identity disagrees with the supplied placement")


def _validated_triplet(payload: Mapping[str, Any], field: str) -> tuple[float, float, float]:
    raw = payload.get(field)
    if not isinstance(raw, list) or len(raw) != 3:
        raise ValueError(f"CadQuery adapter worker emitted malformed {field}")
    row = tuple(float(value) for value in raw)
    if not all(math.isfinite(value) for value in row):
        raise ValueError(f"CadQuery adapter worker emitted non-finite {field}")
    return row  # type: ignore[return-value]


def _validate_worker_payload(
    payload: Mapping[str, Any],
    *,
    first_hash: str,
    second_hash: str,
    parameters: BrepAdapterParameters,
) -> Dict[str, Any]:
    if payload.get("worker_schema") != BREP_ADAPTER_WORKER_SCHEMA:
        raise ValueError("CadQuery adapter worker schema is incompatible")
    if payload.get("first_input_content_hash") != first_hash or payload.get("second_input_content_hash") != second_hash:
        raise ValueError("CadQuery adapter worker parent hashes disagree with canonical source identity")
    if payload.get("rotation_convention") != ROTATION_CONVENTION:
        raise ValueError("CadQuery adapter worker rotation convention is incompatible")
    if payload.get("parent_placements_applied") is not True or payload.get("parent_shapes_valid") is not True:
        raise ValueError("CadQuery adapter worker did not validate placed parent geometry")
    if payload.get("adapter_family") != ADAPTER_FAMILY:
        raise ValueError("CadQuery adapter worker returned an unsupported adapter family")
    if payload.get("adapter_shape_valid") is not True or int(payload.get("adapter_solid_count", 0)) != 1:
        raise ValueError("CadQuery adapter worker did not produce one valid solid")

    generated_step = str(payload.get("generated_step_content") or "")
    generated_bytes = len(generated_step.encode("utf-8"))
    if not generated_step or generated_bytes > MAX_GENERATED_STEP_BYTES:
        raise ValueError("CadQuery adapter worker generated STEP violates bounded output size")
    generated_hash = f"sha256:{hashlib.sha256(generated_step.encode('utf-8')).hexdigest()}"
    if generated_hash != payload.get("generated_content_hash"):
        raise ValueError("generated adapter STEP hash disagrees with worker content")
    if int(payload.get("generated_step_bytes", -1)) != generated_bytes:
        raise ValueError("generated adapter STEP byte count disagrees with worker content")

    vertex_count = int(payload.get("vertex_count", -1))
    triangle_count = int(payload.get("triangle_count", -1))
    raw_vertices = payload.get("vertices_mm")
    raw_triangles = payload.get("triangles")
    if not isinstance(raw_vertices, list) or vertex_count != len(raw_vertices) or not (0 <= vertex_count <= MAX_MESH_VERTICES):
        raise ValueError("adapter worker vertex payload violates bounded mesh contract")
    if not isinstance(raw_triangles, list) or triangle_count != len(raw_triangles) or not (0 <= triangle_count <= MAX_MESH_TRIANGLES):
        raise ValueError("adapter worker triangle payload violates bounded mesh contract")
    vertices: list[list[float]] = []
    for raw in raw_vertices:
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError("adapter worker emitted malformed vertex")
        row = [float(value) for value in raw]
        if not all(math.isfinite(value) for value in row):
            raise ValueError("adapter worker emitted non-finite vertex")
        vertices.append(row)
    triangles: list[list[int]] = []
    for raw in raw_triangles:
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError("adapter worker emitted malformed triangle")
        row = [int(value) for value in raw]
        if any(value < 0 or value >= vertex_count for value in row):
            raise ValueError("adapter worker emitted out-of-range triangle index")
        triangles.append(row)

    numeric_fields = (
        "adapter_length_mm",
        "adapter_width_mm",
        "adapter_thickness_mm",
        "adapter_volume_mm3",
        "first_axis_alignment_error_deg",
        "second_axis_alignment_error_deg",
        "normal_opposition_error_deg",
        "first_endpoint_error_mm",
        "second_endpoint_error_mm",
        "first_parent_minimum_distance_mm",
        "second_parent_minimum_distance_mm",
        "first_parent_intersection_volume_mm3",
        "second_parent_intersection_volume_mm3",
    )
    numbers = {field: float(payload.get(field)) for field in numeric_fields}
    if not all(math.isfinite(value) and value >= 0 for value in numbers.values()):
        raise ValueError("adapter worker emitted invalid geometric metrics")
    if abs(numbers["adapter_width_mm"] - parameters.width_mm) > 1e-9 or abs(numbers["adapter_thickness_mm"] - parameters.thickness_mm) > 1e-9:
        raise ValueError("adapter worker cross-section disagrees with requested parameters")

    return {
        **numbers,
        "adapter_axis": _validated_triplet(payload, "adapter_axis"),
        "adapter_midpoint_mm": _validated_triplet(payload, "adapter_midpoint_mm"),
        "bbox_minimum_mm": _validated_triplet(payload, "bbox_minimum_mm"),
        "bbox_maximum_mm": _validated_triplet(payload, "bbox_maximum_mm"),
        "generated_step_content": generated_step,
        "generated_content_hash": generated_hash,
        "generated_step_bytes": generated_bytes,
        "vertices_mm": vertices,
        "triangles": triangles,
        "vertex_count": vertex_count,
        "triangle_count": triangle_count,
        "first_parent_contact_passed": bool(payload.get("first_parent_contact_passed")),
        "second_parent_contact_passed": bool(payload.get("second_parent_contact_passed")),
        "first_parent_penetration_passed": bool(payload.get("first_parent_penetration_passed")),
        "second_parent_penetration_passed": bool(payload.get("second_parent_penetration_passed")),
        "geometric_candidate_passed": bool(payload.get("geometric_candidate_passed")),
    }


def synthesize_brep_bridge_adapter(
    *,
    project_id: str,
    adapter_id: str,
    first_content: str,
    first_source_id: str,
    first_model_id: str,
    first_expected_content_hash: str,
    first_placement: DeclaredGeometryPlacement | Mapping[str, Any],
    first_anchor: BrepMatingAnchor | Mapping[str, Any],
    second_content: str,
    second_source_id: str,
    second_model_id: str,
    second_expected_content_hash: str,
    second_placement: DeclaredGeometryPlacement | Mapping[str, Any],
    second_anchor: BrepMatingAnchor | Mapping[str, Any],
    parameters: BrepAdapterParameters | Mapping[str, Any] | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    kernel_available: bool | None = None,
    runner: Runner | None = None,
) -> BrepAdapterCandidateReport:
    if not project_id.strip() or not adapter_id.strip():
        raise ValueError("project_id and adapter_id are required")
    if timeout_s <= 0 or timeout_s > 120:
        raise ValueError("timeout_s must be greater than zero and at most 120 seconds")

    resolved_parameters = parameters if isinstance(parameters, BrepAdapterParameters) else BrepAdapterParameters.model_validate(parameters or {})
    first = first_anchor if isinstance(first_anchor, BrepMatingAnchor) else BrepMatingAnchor.model_validate(first_anchor)
    second = second_anchor if isinstance(second_anchor, BrepMatingAnchor) else BrepMatingAnchor.model_validate(second_anchor)
    first_pose = first_placement if isinstance(first_placement, DeclaredGeometryPlacement) else DeclaredGeometryPlacement.model_validate(first_placement)
    second_pose = second_placement if isinstance(second_placement, DeclaredGeometryPlacement) else DeclaredGeometryPlacement.model_validate(second_placement)

    first_model = parse_step_model(first_content, source_id=first_source_id, model_id=first_model_id)
    second_model = parse_step_model(second_content, source_id=second_source_id, model_id=second_model_id)
    if first_model.content_hash != first_expected_content_hash:
        raise ValueError("first inline STEP content no longer matches its expected canonical content_hash")
    if second_model.content_hash != second_expected_content_hash:
        raise ValueError("second inline STEP content no longer matches its expected canonical content_hash")
    _validate_anchor_source_pose(anchor=first, source_id=first_source_id, model_id=first_model_id, content_hash=first_expected_content_hash, placement=first_pose, label="first")
    _validate_anchor_source_pose(anchor=second, source_id=second_source_id, model_id=second_model_id, content_hash=second_expected_content_hash, placement=second_pose, label="second")

    if first.anchor_id == second.anchor_id or first.object_id == second.object_id:
        raise ValueError("adapter synthesis requires two distinct exact anchors on two distinct placed objects")
    if first.frame_id != second.frame_id:
        return _unknown(
            project_id=project_id,
            adapter_id=adapter_id,
            first=first,
            second=second,
            parameters=resolved_parameters,
            kernel_available=bool(kernel_available),
            reason=f"anchor frames differ: {first.frame_id!r} vs {second.frame_id!r}",
            required_field="common_frame",
        )
    if first.face_geom_type.upper() != "PLANE" or second.face_geom_type.upper() != "PLANE":
        return _unknown(
            project_id=project_id,
            adapter_id=adapter_id,
            first=first,
            second=second,
            parameters=resolved_parameters,
            kernel_available=bool(kernel_available),
            reason="bridge_block_v0 only supports exact planar anchor faces",
            required_field="opposed_planar_anchor_faces",
        )

    first_point = _vector(first.anchor_point_mm)
    second_point = _vector(second.anchor_point_mm)
    axis = _normalize(_sub(second_point, first_point))
    span = _norm(_sub(second_point, first_point))
    if not (MIN_ADAPTER_SPAN_MM <= span <= MAX_ADAPTER_SPAN_MM):
        return _unknown(
            project_id=project_id,
            adapter_id=adapter_id,
            first=first,
            second=second,
            parameters=resolved_parameters,
            kernel_available=bool(kernel_available),
            reason=f"anchor separation {span:.3f} mm is outside bridge_block_v0 range {MIN_ADAPTER_SPAN_MM}..{MAX_ADAPTER_SPAN_MM} mm",
            required_field="supported_adapter_span",
        )
    first_axis_error = _angle_deg(_vector(first.outward_normal), axis)
    second_axis_error = _angle_deg(_vector(second.outward_normal), _scale(axis, -1.0))
    if first_axis_error > resolved_parameters.max_axis_alignment_error_deg + 1e-12 or second_axis_error > resolved_parameters.max_axis_alignment_error_deg + 1e-12:
        return _unknown(
            project_id=project_id,
            adapter_id=adapter_id,
            first=first,
            second=second,
            parameters=resolved_parameters,
            kernel_available=bool(kernel_available),
            reason=(
                "exact planar anchor normals are not sufficiently opposed along the bridge axis: "
                f"{first_axis_error:.3f}° / {second_axis_error:.3f}°"
            ),
            required_field="bridge_axis_aligned_planar_anchors",
            metadata={"first_axis_alignment_error_deg": first_axis_error, "second_axis_alignment_error_deg": second_axis_error},
        )

    available = _cadquery_available() if kernel_available is None else bool(kernel_available)
    if not available:
        return _unknown(
            project_id=project_id,
            adapter_id=adapter_id,
            first=first,
            second=second,
            parameters=resolved_parameters,
            kernel_available=False,
            reason="optional cadquery-isolated specialist is not available in this runtime",
            required_field="cadquery-isolated",
        )

    selected_runner = runner or _run_isolated_worker
    try:
        payload = dict(selected_runner(
            first_content,
            first_expected_content_hash,
            _placement_payload(first_pose),
            first.model_dump(mode="json"),
            second_content,
            second_expected_content_hash,
            _placement_payload(second_pose),
            second.model_dump(mode="json"),
            resolved_parameters.model_dump(mode="json"),
            timeout_s,
        ))
        if payload.get("ok") is not True:
            raise ValueError("CadQuery adapter worker did not report success")
        fields = _validate_worker_payload(
            payload,
            first_hash=first_expected_content_hash,
            second_hash=second_expected_content_hash,
            parameters=resolved_parameters,
        )
        response_bytes = len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        if response_bytes > MAX_WORKER_RESPONSE_BYTES:
            raise ValueError("CadQuery adapter worker response exceeds bounded output size")
    except (OSError, RuntimeError, TimeoutError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        return _unknown(
            project_id=project_id,
            adapter_id=adapter_id,
            first=first,
            second=second,
            parameters=resolved_parameters,
            kernel_available=True,
            reason=f"isolated CadQuery BREP adapter worker failed: {type(exc).__name__}: {exc}",
            required_field="valid_brep_adapter_candidate",
            metadata={"worker_error_type": type(exc).__name__},
        )

    required_evidence: list[Dict[str, Any]] = [
        {"field": "mounting_method", "reason": "bridge geometry does not establish fastening or retention"},
        {"field": "material", "reason": "generated geometry has no material authority"},
        {"field": "structural_analysis", "reason": "loads, stress, fatigue and safety factor are not evaluated"},
        {"field": "fabrication_review", "reason": "geometric candidate is not fabrication authorization"},
    ]
    if not fields["geometric_candidate_passed"]:
        required_evidence.insert(0, {
            "field": "exact_parent_clearance",
            "reason": "generated bridge did not simultaneously satisfy bounded exact parent contact/penetration checks",
        })

    return BrepAdapterCandidateReport(
        project_id=project_id,
        adapter_id=adapter_id,
        frame_id=first.frame_id,
        first_anchor_id=first.anchor_id,
        second_anchor_id=second.anchor_id,
        first_object_id=first.object_id,
        second_object_id=second.object_id,
        first_source_id=first.source_id,
        second_source_id=second.source_id,
        first_content_hash=first.content_hash,
        second_content_hash=second.content_hash,
        first_placement_id=first.placement_id,
        second_placement_id=second.placement_id,
        status=BrepAdapterStatus.READY,
        kernel_available=True,
        kernel=str(payload.get("kernel") or "cadquery_occt"),
        cadquery_version=str(payload.get("cadquery_version")) if payload.get("cadquery_version") else None,
        geometric_candidate_passed=fields["geometric_candidate_passed"],
        adapter_axis=fields["adapter_axis"],
        adapter_midpoint_mm=fields["adapter_midpoint_mm"],
        length_mm=fields["adapter_length_mm"],
        width_mm=fields["adapter_width_mm"],
        thickness_mm=fields["adapter_thickness_mm"],
        volume_mm3=fields["adapter_volume_mm3"],
        first_axis_alignment_error_deg=fields["first_axis_alignment_error_deg"],
        second_axis_alignment_error_deg=fields["second_axis_alignment_error_deg"],
        normal_opposition_error_deg=fields["normal_opposition_error_deg"],
        first_endpoint_error_mm=fields["first_endpoint_error_mm"],
        second_endpoint_error_mm=fields["second_endpoint_error_mm"],
        first_parent_minimum_distance_mm=fields["first_parent_minimum_distance_mm"],
        second_parent_minimum_distance_mm=fields["second_parent_minimum_distance_mm"],
        first_parent_intersection_volume_mm3=fields["first_parent_intersection_volume_mm3"],
        second_parent_intersection_volume_mm3=fields["second_parent_intersection_volume_mm3"],
        first_parent_contact_passed=fields["first_parent_contact_passed"],
        second_parent_contact_passed=fields["second_parent_contact_passed"],
        first_parent_penetration_passed=fields["first_parent_penetration_passed"],
        second_parent_penetration_passed=fields["second_parent_penetration_passed"],
        generated_source_id=f"generated://adapter/{adapter_id}.step",
        generated_model_id=adapter_id,
        generated_content_hash=fields["generated_content_hash"],
        generated_step_content=fields["generated_step_content"],
        generated_step_bytes=fields["generated_step_bytes"],
        bbox_minimum_mm=fields["bbox_minimum_mm"],
        bbox_maximum_mm=fields["bbox_maximum_mm"],
        vertex_count=fields["vertex_count"],
        triangle_count=fields["triangle_count"],
        vertices_mm=fields["vertices_mm"],
        triangles=fields["triangles"],
        required_evidence=required_evidence,
        metadata={
            **_base_metadata(),
            "worker_isolated": True,
            "worker_schema": BREP_ADAPTER_WORKER_SCHEMA,
            "worker_response_bytes": response_bytes,
            "geometric_candidate_only": True,
            "exact_parent_contact_checked": True,
            "exact_parent_penetration_checked": True,
            "generated_content_hash_reverified": True,
        },
    )


def _run_isolated_worker(
    first_content: str,
    first_expected_content_hash: str,
    first_placement: Mapping[str, Any],
    first_anchor: Mapping[str, Any],
    second_content: str,
    second_expected_content_hash: str,
    second_placement: Mapping[str, Any],
    second_anchor: Mapping[str, Any],
    parameters: Mapping[str, Any],
    timeout_s: float,
) -> Mapping[str, Any]:
    if not _WORKER_PATH.is_file():
        raise RuntimeError(f"CadQuery BREP adapter worker is missing: {_WORKER_PATH}")

    with tempfile.TemporaryDirectory(prefix="hardware-splicer-brep-adapter-") as temp_dir:
        root = Path(temp_dir)
        first_path = root / "first.step"
        second_path = root / "second.step"
        input_path = root / "request.json"
        first_path.write_text(first_content, encoding="utf-8")
        second_path.write_text(second_content, encoding="utf-8")
        input_path.write_text(
            json.dumps({
                "first_step_path": str(first_path),
                "first_expected_content_hash": first_expected_content_hash,
                "first_placement": dict(first_placement),
                "first_anchor": dict(first_anchor),
                "second_step_path": str(second_path),
                "second_expected_content_hash": second_expected_content_hash,
                "second_placement": dict(second_placement),
                "second_anchor": dict(second_anchor),
                "width_mm": float(parameters["width_mm"]),
                "thickness_mm": float(parameters["thickness_mm"]),
                "max_axis_alignment_error_deg": float(parameters["max_axis_alignment_error_deg"]),
                "contact_distance_tolerance_mm": float(parameters["contact_distance_tolerance_mm"]),
                "penetration_volume_tolerance_mm3": float(parameters["penetration_volume_tolerance_mm3"]),
                "tessellation_tolerance_mm": float(parameters["tessellation_tolerance_mm"]),
                "tessellation_angular_tolerance_rad": float(parameters["tessellation_angular_tolerance_rad"]),
            }),
            encoding="utf-8",
        )
        kwargs: dict[str, object] = {
            "args": [sys.executable, "-I", str(_WORKER_PATH), str(input_path)],
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "env": _sanitized_environment(),
            "cwd": str(root),
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(**kwargs)  # type: ignore[arg-type]
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            stdout, stderr = process.communicate()
            raise TimeoutError(
                f"CadQuery BREP adapter worker exceeded {timeout_s:.3f}s; process tree terminated"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
        if process.returncode != 0:
            raise RuntimeError(
                f"CadQuery BREP adapter worker failed with exit code {process.returncode}"
                + _diagnostic_suffix(stdout, stderr)
            )
        if len((stdout or "").encode("utf-8")) > MAX_WORKER_RESPONSE_BYTES:
            raise RuntimeError("CadQuery BREP adapter worker stdout exceeds bounded output size")
        try:
            return json.loads((stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "CadQuery BREP adapter worker returned no valid structured result"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
