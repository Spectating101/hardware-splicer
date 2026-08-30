"""Bounded renderable STEP tessellation evidence via isolated CadQuery/OCCT.

This module provides one deliberately narrow bridge from canonical STEP identity to a
renderable triangle mesh. The result is visual/geometry evidence only: it does not
establish physical measurement, connector mating, structural safety, fabrication
readiness, or whole-assembly collision freedom.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .mechanical_brep import _diagnostic_suffix, _sanitized_environment, _terminate_process_tree
from .mechanical_placement import DeclaredGeometryPlacement
from .step_geometry import StepModelSummary, parse_step_model


BREP_MESH_SCHEMA = "hardware_splicer.brep_render_mesh.v1"
BREP_MESH_WORKER_SCHEMA = "hardware_splicer.cadquery_brep_mesh_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
MIN_TOLERANCE_MM = 0.1
MAX_TOLERANCE_MM = 5.0
MIN_ANGULAR_TOLERANCE_RAD = 0.01
MAX_ANGULAR_TOLERANCE_RAD = 1.0
MAX_MESH_VERTICES = 25_000
MAX_MESH_TRIANGLES = 50_000
MAX_MESH_RESPONSE_BYTES = 8 * 1024 * 1024
_DEFAULT_TIMEOUT_S = 60.0
_WORKER_PATH = Path(__file__).with_name("_cadquery_brep_mesh_worker.py")


class BrepMeshStatus(str, Enum):
    READY = "ready"
    UNKNOWN = "unknown"


class BrepMeshBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BrepRenderMeshReport(BrepMeshBase):
    schema_version: str = BREP_MESH_SCHEMA
    project_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    frame_id: str | None = None
    placement_id: str | None = None
    status: BrepMeshStatus
    kernel_available: bool
    kernel: str | None = None
    cadquery_version: str | None = None
    shape_valid: bool | None = None
    solid_count: int | None = Field(default=None, ge=0)
    vertex_count: int = Field(default=0, ge=0, le=MAX_MESH_VERTICES)
    triangle_count: int = Field(default=0, ge=0, le=MAX_MESH_TRIANGLES)
    vertices_mm: list[list[float]] = Field(default_factory=list)
    triangles: list[list[int]] = Field(default_factory=list)
    tolerance_mm: float = Field(ge=MIN_TOLERANCE_MM, le=MAX_TOLERANCE_MM)
    angular_tolerance_rad: float = Field(
        ge=MIN_ANGULAR_TOLERANCE_RAD,
        le=MAX_ANGULAR_TOLERANCE_RAD,
    )
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


Runner = Callable[
    [str, str, Mapping[str, Any], float, float, float],
    Mapping[str, Any],
]


def _cadquery_available() -> bool:
    try:
        return importlib.util.find_spec("cadquery") is not None
    except (ImportError, ValueError):
        return False


def _base_metadata() -> Dict[str, Any]:
    return {
        "specialist_capability": "cadquery-isolated",
        "scope": "single_step_placed_render_tessellation",
        "render_evidence_only": True,
        "exact_brep_mesh_source": True,
        "rotation_convention": ROTATION_CONVENTION,
        "full_assembly_collision": False,
        "connector_mating_verified": False,
        "cable_routing_verified": False,
        "service_access_verified": False,
        "structural_analysis": False,
        "physical_measurement": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _placement_payload(
    model: StepModelSummary,
    placement: DeclaredGeometryPlacement | Mapping[str, Any] | None,
) -> tuple[DeclaredGeometryPlacement | None, Dict[str, Any]]:
    if placement is None:
        return None, {
            "translation_mm": [0.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
        }
    resolved = (
        placement
        if isinstance(placement, DeclaredGeometryPlacement)
        else DeclaredGeometryPlacement.model_validate(placement)
    )
    if resolved.model_id != model.model_id:
        raise ValueError(
            f"mesh placement targets model {resolved.model_id!r}, not imported STEP model {model.model_id!r}"
        )
    return resolved, {
        "translation_mm": list(resolved.translation_mm),
        "rotation_deg_xyz": list(resolved.rotation_deg_xyz),
    }


def _unknown(
    *,
    project_id: str,
    model: StepModelSummary,
    placement: DeclaredGeometryPlacement | None,
    tolerance_mm: float,
    angular_tolerance_rad: float,
    kernel_available: bool,
    reason: str,
    required_field: str,
    metadata: Mapping[str, Any] | None = None,
) -> BrepRenderMeshReport:
    return BrepRenderMeshReport(
        project_id=project_id,
        source_id=model.source_id,
        model_id=model.model_id,
        content_hash=model.content_hash,
        frame_id=placement.target_frame if placement else None,
        placement_id=placement.placement_id if placement else None,
        status=BrepMeshStatus.UNKNOWN,
        kernel_available=kernel_available,
        tolerance_mm=tolerance_mm,
        angular_tolerance_rad=angular_tolerance_rad,
        required_evidence=[{"field": required_field, "reason": reason}],
        metadata={
            **_base_metadata(),
            "declared_placement_applied": placement is not None,
            **dict(metadata or {}),
        },
    )


def _validate_mesh_payload(
    payload: Mapping[str, Any],
    *,
    expected_hash: str,
) -> tuple[list[list[float]], list[list[int]], int, int]:
    if payload.get("worker_schema") != BREP_MESH_WORKER_SCHEMA:
        raise ValueError("CadQuery mesh worker schema is incompatible")
    if payload.get("input_content_hash") != expected_hash:
        raise ValueError("CadQuery mesh worker input hash disagrees with canonical STEP identity")
    if payload.get("rotation_convention") != ROTATION_CONVENTION:
        raise ValueError("CadQuery mesh worker rotation convention is incompatible")
    if payload.get("placement_applied") is not True:
        raise ValueError("CadQuery mesh worker did not confirm placement application")
    if payload.get("shape_valid") is not True:
        raise ValueError("CadQuery mesh worker did not validate the imported shape")

    solid_count = int(payload.get("solid_count", 0))
    if solid_count <= 0:
        raise ValueError("CadQuery mesh worker reported no imported solids")
    vertex_count = int(payload.get("vertex_count", -1))
    triangle_count = int(payload.get("triangle_count", -1))
    if vertex_count < 0 or vertex_count > MAX_MESH_VERTICES:
        raise ValueError("CadQuery mesh worker vertex count exceeds bounded contract")
    if triangle_count < 0 or triangle_count > MAX_MESH_TRIANGLES:
        raise ValueError("CadQuery mesh worker triangle count exceeds bounded contract")

    raw_vertices = payload.get("vertices_mm")
    raw_triangles = payload.get("triangles")
    if not isinstance(raw_vertices, list) or len(raw_vertices) != vertex_count:
        raise ValueError("CadQuery mesh worker vertex payload disagrees with vertex_count")
    if not isinstance(raw_triangles, list) or len(raw_triangles) != triangle_count:
        raise ValueError("CadQuery mesh worker triangle payload disagrees with triangle_count")

    vertices: list[list[float]] = []
    for raw in raw_vertices:
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError("CadQuery mesh worker emitted a malformed vertex")
        row = [float(value) for value in raw]
        if not all(math.isfinite(value) for value in row):
            raise ValueError("CadQuery mesh worker emitted a non-finite vertex")
        vertices.append(row)

    triangles: list[list[int]] = []
    for raw in raw_triangles:
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError("CadQuery mesh worker emitted a malformed triangle")
        row = [int(value) for value in raw]
        if any(value < 0 or value >= vertex_count for value in row):
            raise ValueError("CadQuery mesh worker emitted an out-of-range triangle index")
        triangles.append(row)
    return vertices, triangles, solid_count, len(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )


def build_step_brep_render_mesh(
    *,
    project_id: str,
    content: str,
    source_id: str,
    model_id: str | None = None,
    expected_content_hash: str | None = None,
    placement: DeclaredGeometryPlacement | Mapping[str, Any] | None = None,
    tolerance_mm: float = 0.5,
    angular_tolerance_rad: float = 0.1,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    kernel_available: bool | None = None,
    runner: Runner | None = None,
) -> BrepRenderMeshReport:
    if not (MIN_TOLERANCE_MM <= tolerance_mm <= MAX_TOLERANCE_MM):
        raise ValueError(
            f"tolerance_mm must be between {MIN_TOLERANCE_MM} and {MAX_TOLERANCE_MM}"
        )
    if not (
        MIN_ANGULAR_TOLERANCE_RAD
        <= angular_tolerance_rad
        <= MAX_ANGULAR_TOLERANCE_RAD
    ):
        raise ValueError(
            "angular_tolerance_rad is outside the bounded tessellation range"
        )
    if timeout_s <= 0 or timeout_s > 120:
        raise ValueError("timeout_s must be greater than zero and at most 120 seconds")

    model = parse_step_model(content, source_id=source_id, model_id=model_id)
    if expected_content_hash is not None and expected_content_hash != model.content_hash:
        raise ValueError("inline STEP content no longer matches its expected canonical content_hash")
    resolved_placement, placement_payload = _placement_payload(model, placement)

    available = _cadquery_available() if kernel_available is None else bool(kernel_available)
    if not available:
        return _unknown(
            project_id=project_id,
            model=model,
            placement=resolved_placement,
            tolerance_mm=tolerance_mm,
            angular_tolerance_rad=angular_tolerance_rad,
            kernel_available=False,
            reason="optional cadquery-isolated specialist is not available in this runtime",
            required_field="cadquery-isolated",
        )

    selected_runner = runner or _run_isolated_worker
    try:
        payload = dict(
            selected_runner(
                content,
                model.content_hash,
                placement_payload,
                tolerance_mm,
                angular_tolerance_rad,
                timeout_s,
            )
        )
        if payload.get("ok") is not True:
            raise ValueError("CadQuery mesh worker did not report success")
        vertices, triangles, solid_count, response_bytes = _validate_mesh_payload(
            payload,
            expected_hash=model.content_hash,
        )
        if response_bytes > MAX_MESH_RESPONSE_BYTES:
            raise ValueError("CadQuery mesh worker response exceeds bounded output size")
    except (OSError, RuntimeError, TimeoutError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        return _unknown(
            project_id=project_id,
            model=model,
            placement=resolved_placement,
            tolerance_mm=tolerance_mm,
            angular_tolerance_rad=angular_tolerance_rad,
            kernel_available=True,
            reason=f"isolated CadQuery BREP mesh worker failed: {type(exc).__name__}: {exc}",
            required_field="valid_brep_render_mesh",
            metadata={"worker_error_type": type(exc).__name__},
        )

    return BrepRenderMeshReport(
        project_id=project_id,
        source_id=model.source_id,
        model_id=model.model_id,
        content_hash=model.content_hash,
        frame_id=resolved_placement.target_frame if resolved_placement else None,
        placement_id=resolved_placement.placement_id if resolved_placement else None,
        status=BrepMeshStatus.READY,
        kernel_available=True,
        kernel=str(payload.get("kernel") or "cadquery_occt"),
        cadquery_version=(
            str(payload["cadquery_version"])
            if payload.get("cadquery_version")
            else None
        ),
        shape_valid=True,
        solid_count=solid_count,
        vertex_count=len(vertices),
        triangle_count=len(triangles),
        vertices_mm=vertices,
        triangles=triangles,
        tolerance_mm=tolerance_mm,
        angular_tolerance_rad=angular_tolerance_rad,
        metadata={
            **_base_metadata(),
            "worker_isolated": True,
            "worker_schema": BREP_MESH_WORKER_SCHEMA,
            "worker_input_hash_reverified": True,
            "declared_placement_applied": resolved_placement is not None,
            "mesh_response_bytes": response_bytes,
            "vertex_limit": MAX_MESH_VERTICES,
            "triangle_limit": MAX_MESH_TRIANGLES,
        },
    )


def _run_isolated_worker(
    content: str,
    expected_content_hash: str,
    placement: Mapping[str, Any],
    tolerance_mm: float,
    angular_tolerance_rad: float,
    timeout_s: float,
) -> Mapping[str, Any]:
    if not _WORKER_PATH.is_file():
        raise RuntimeError(f"CadQuery BREP mesh worker is missing: {_WORKER_PATH}")

    with tempfile.TemporaryDirectory(prefix="hardware-splicer-brep-mesh-") as temp_dir:
        root = Path(temp_dir)
        step_path = root / "source.step"
        input_path = root / "request.json"
        step_path.write_text(content, encoding="utf-8")
        input_path.write_text(
            json.dumps(
                {
                    "step_path": str(step_path),
                    "expected_content_hash": expected_content_hash,
                    "placement": dict(placement),
                    "tolerance_mm": tolerance_mm,
                    "angular_tolerance_rad": angular_tolerance_rad,
                }
            ),
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
                f"CadQuery BREP mesh worker exceeded {timeout_s:.3f}s; process tree terminated"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
        if process.returncode != 0:
            raise RuntimeError(
                f"CadQuery BREP mesh worker failed with exit code {process.returncode}"
                + _diagnostic_suffix(stdout, stderr)
            )
        if len((stdout or "").encode("utf-8")) > MAX_MESH_RESPONSE_BYTES:
            raise RuntimeError("CadQuery BREP mesh worker stdout exceeds bounded output size")
        try:
            return json.loads((stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "CadQuery BREP mesh worker returned no valid structured result"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
