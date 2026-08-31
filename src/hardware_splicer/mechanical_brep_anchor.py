"""Placed STEP BREP surface-anchor evidence via isolated CadQuery/OCCT.

A surface anchor binds an explicitly selected assembly-frame probe to the nearest
surface on the exact imported STEP BREP and records the kernel-derived point and
normal. It is declared geometric interface evidence only: no connector mating,
measurement truth, fit, fabrication, structural, or physical authority is inferred.
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


BREP_ANCHOR_SCHEMA = "hardware_splicer.brep_surface_anchor.v1"
BREP_ANCHOR_WORKER_SCHEMA = "hardware_splicer.cadquery_brep_anchor_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
MAX_SNAP_DISTANCE_MM = 100.0
MAX_ANCHOR_RESPONSE_BYTES = 128 * 1024
_DEFAULT_TIMEOUT_S = 60.0
_WORKER_PATH = Path(__file__).with_name("_cadquery_brep_anchor_worker.py")


class BrepAnchorStatus(str, Enum):
    READY = "ready"
    UNKNOWN = "unknown"


class BrepAnchorBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BrepSurfaceAnchorReport(BrepAnchorBase):
    schema_version: str = BREP_ANCHOR_SCHEMA
    project_id: str = Field(min_length=1)
    anchor_id: str = Field(min_length=1)
    interface_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    object_id: str = Field(min_length=1)
    placement_id: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    status: BrepAnchorStatus
    kernel_available: bool
    kernel: str | None = None
    cadquery_version: str | None = None
    probe_point_mm: list[float] = Field(min_length=3, max_length=3)
    anchor_point_mm: list[float] | None = Field(default=None, min_length=3, max_length=3)
    outward_normal: list[float] | None = Field(default=None, min_length=3, max_length=3)
    snap_distance_mm: float | None = Field(default=None, ge=0)
    max_snap_distance_mm: float = Field(ge=0, le=MAX_SNAP_DISTANCE_MM)
    face_index: int | None = Field(default=None, ge=0)
    face_count: int | None = Field(default=None, ge=0)
    face_geom_type: str | None = None
    face_area_mm2: float | None = Field(default=None, gt=0)
    face_center_mm: list[float] | None = Field(default=None, min_length=3, max_length=3)
    solid_count: int | None = Field(default=None, ge=0)
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


Runner = Callable[
    [str, str, Mapping[str, Any], list[float], float, float],
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
        "scope": "single_placed_step_surface_anchor",
        "authority": "declared",
        "kernel_surface_snap": True,
        "interface_binding_declared": True,
        "rotation_convention": ROTATION_CONVENTION,
        "connector_mating_verified": False,
        "fit_verified": False,
        "full_assembly_collision": False,
        "service_access_verified": False,
        "structural_analysis": False,
        "physical_measurement": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _finite_triplet(value: list[float] | tuple[float, float, float], field: str) -> list[float]:
    row = [float(item) for item in value]
    if len(row) != 3 or not all(math.isfinite(item) for item in row):
        raise ValueError(f"{field} must contain exactly three finite values")
    return row


def _placement_payload(
    model: StepModelSummary,
    placement: DeclaredGeometryPlacement | Mapping[str, Any],
) -> tuple[DeclaredGeometryPlacement, Dict[str, Any]]:
    resolved = (
        placement
        if isinstance(placement, DeclaredGeometryPlacement)
        else DeclaredGeometryPlacement.model_validate(placement)
    )
    if resolved.model_id != model.model_id:
        raise ValueError(
            f"anchor placement targets model {resolved.model_id!r}, not imported STEP model {model.model_id!r}"
        )
    return resolved, {
        "translation_mm": list(resolved.translation_mm),
        "rotation_deg_xyz": list(resolved.rotation_deg_xyz),
    }


def _unknown(
    *,
    project_id: str,
    anchor_id: str,
    interface_id: str,
    model: StepModelSummary,
    placement: DeclaredGeometryPlacement,
    probe_point_mm: list[float],
    max_snap_distance_mm: float,
    kernel_available: bool,
    reason: str,
    required_field: str,
    metadata: Mapping[str, Any] | None = None,
) -> BrepSurfaceAnchorReport:
    return BrepSurfaceAnchorReport(
        project_id=project_id,
        anchor_id=anchor_id,
        interface_id=interface_id,
        source_id=model.source_id,
        model_id=model.model_id,
        content_hash=model.content_hash,
        object_id=placement.object_id,
        placement_id=placement.placement_id,
        frame_id=placement.target_frame,
        status=BrepAnchorStatus.UNKNOWN,
        kernel_available=kernel_available,
        probe_point_mm=probe_point_mm,
        max_snap_distance_mm=max_snap_distance_mm,
        required_evidence=[{"field": required_field, "reason": reason}],
        metadata={**_base_metadata(), **dict(metadata or {})},
    )


def _validate_payload(
    payload: Mapping[str, Any],
    *,
    expected_hash: str,
    expected_probe: list[float],
    max_snap_distance_mm: float,
) -> Dict[str, Any]:
    if payload.get("worker_schema") != BREP_ANCHOR_WORKER_SCHEMA:
        raise ValueError("CadQuery anchor worker schema is incompatible")
    if payload.get("input_content_hash") != expected_hash:
        raise ValueError("CadQuery anchor worker input hash disagrees with canonical STEP identity")
    if payload.get("rotation_convention") != ROTATION_CONVENTION:
        raise ValueError("CadQuery anchor worker rotation convention is incompatible")
    if payload.get("placement_applied") is not True:
        raise ValueError("CadQuery anchor worker did not confirm placement application")
    if payload.get("shape_valid") is not True:
        raise ValueError("CadQuery anchor worker did not validate the imported shape")

    probe = _finite_triplet(list(payload.get("probe_point_mm") or []), "worker probe_point_mm")
    if any(abs(probe[index] - expected_probe[index]) > 1e-9 for index in range(3)):
        raise ValueError("CadQuery anchor worker probe identity disagrees with request")
    anchor = _finite_triplet(list(payload.get("anchor_point_mm") or []), "worker anchor_point_mm")
    normal = _finite_triplet(list(payload.get("outward_normal") or []), "worker outward_normal")
    normal_length = math.sqrt(sum(value * value for value in normal))
    if abs(normal_length - 1.0) > 1e-5:
        raise ValueError("CadQuery anchor worker normal is not unit length")

    snap_distance = float(payload.get("snap_distance_mm"))
    if not math.isfinite(snap_distance) or snap_distance < 0 or snap_distance > max_snap_distance_mm + 1e-9:
        raise ValueError("CadQuery anchor worker snap distance violates the bounded request")
    face_index = int(payload.get("face_index", -1))
    face_count = int(payload.get("face_count", -1))
    if face_index < 0 or face_count <= face_index:
        raise ValueError("CadQuery anchor worker face identity is invalid")
    face_area = float(payload.get("face_area_mm2"))
    if not math.isfinite(face_area) or face_area <= 0:
        raise ValueError("CadQuery anchor worker face area is invalid")
    face_center = _finite_triplet(list(payload.get("face_center_mm") or []), "worker face_center_mm")
    solid_count = int(payload.get("solid_count", 0))
    if solid_count <= 0:
        raise ValueError("CadQuery anchor worker reported no imported solids")

    return {
        "anchor_point_mm": anchor,
        "outward_normal": normal,
        "snap_distance_mm": snap_distance,
        "face_index": face_index,
        "face_count": face_count,
        "face_geom_type": str(payload.get("face_geom_type") or "unknown"),
        "face_area_mm2": face_area,
        "face_center_mm": face_center,
        "solid_count": solid_count,
    }


def build_step_brep_surface_anchor(
    *,
    project_id: str,
    anchor_id: str,
    interface_id: str,
    content: str,
    source_id: str,
    model_id: str,
    expected_content_hash: str,
    placement: DeclaredGeometryPlacement | Mapping[str, Any],
    probe_point_mm: list[float] | tuple[float, float, float],
    max_snap_distance_mm: float = 5.0,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    kernel_available: bool | None = None,
    runner: Runner | None = None,
) -> BrepSurfaceAnchorReport:
    if not anchor_id.strip() or not interface_id.strip():
        raise ValueError("anchor_id and interface_id are required")
    if not math.isfinite(max_snap_distance_mm) or not (0 <= max_snap_distance_mm <= MAX_SNAP_DISTANCE_MM):
        raise ValueError(
            f"max_snap_distance_mm must be between 0 and {MAX_SNAP_DISTANCE_MM}"
        )
    if timeout_s <= 0 or timeout_s > 120:
        raise ValueError("timeout_s must be greater than zero and at most 120 seconds")

    model = parse_step_model(content, source_id=source_id, model_id=model_id)
    if expected_content_hash != model.content_hash:
        raise ValueError("inline STEP content no longer matches its expected canonical content_hash")
    resolved_placement, placement_payload = _placement_payload(model, placement)
    probe = _finite_triplet(list(probe_point_mm), "probe_point_mm")

    available = _cadquery_available() if kernel_available is None else bool(kernel_available)
    if not available:
        return _unknown(
            project_id=project_id,
            anchor_id=anchor_id,
            interface_id=interface_id,
            model=model,
            placement=resolved_placement,
            probe_point_mm=probe,
            max_snap_distance_mm=max_snap_distance_mm,
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
                probe,
                max_snap_distance_mm,
                timeout_s,
            )
        )
        if payload.get("ok") is not True:
            raise ValueError("CadQuery anchor worker did not report success")
        fields = _validate_payload(
            payload,
            expected_hash=model.content_hash,
            expected_probe=probe,
            max_snap_distance_mm=max_snap_distance_mm,
        )
        response_bytes = len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        if response_bytes > MAX_ANCHOR_RESPONSE_BYTES:
            raise ValueError("CadQuery anchor worker response exceeds bounded output size")
    except (OSError, RuntimeError, TimeoutError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        return _unknown(
            project_id=project_id,
            anchor_id=anchor_id,
            interface_id=interface_id,
            model=model,
            placement=resolved_placement,
            probe_point_mm=probe,
            max_snap_distance_mm=max_snap_distance_mm,
            kernel_available=True,
            reason=f"isolated CadQuery BREP anchor worker failed: {type(exc).__name__}: {exc}",
            required_field="valid_brep_surface_anchor",
            metadata={"worker_error_type": type(exc).__name__},
        )

    return BrepSurfaceAnchorReport(
        project_id=project_id,
        anchor_id=anchor_id,
        interface_id=interface_id,
        source_id=model.source_id,
        model_id=model.model_id,
        content_hash=model.content_hash,
        object_id=resolved_placement.object_id,
        placement_id=resolved_placement.placement_id,
        frame_id=resolved_placement.target_frame,
        status=BrepAnchorStatus.READY,
        kernel_available=True,
        kernel=str(payload.get("kernel") or "cadquery_occt"),
        cadquery_version=str(payload.get("cadquery_version")) if payload.get("cadquery_version") else None,
        probe_point_mm=probe,
        max_snap_distance_mm=max_snap_distance_mm,
        **fields,
        metadata={
            **_base_metadata(),
            "worker_isolated": True,
            "worker_schema": BREP_ANCHOR_WORKER_SCHEMA,
            "worker_input_hash_reverified": True,
            "worker_response_bytes": response_bytes,
            "face_identity_scoped_to_content_hash": True,
        },
    )


def _run_isolated_worker(
    content: str,
    expected_content_hash: str,
    placement: Mapping[str, Any],
    probe_point_mm: list[float],
    max_snap_distance_mm: float,
    timeout_s: float,
) -> Mapping[str, Any]:
    if not _WORKER_PATH.is_file():
        raise RuntimeError(f"CadQuery BREP anchor worker is missing: {_WORKER_PATH}")

    with tempfile.TemporaryDirectory(prefix="hardware-splicer-brep-anchor-") as temp_dir:
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
                    "probe_point_mm": probe_point_mm,
                    "max_snap_distance_mm": max_snap_distance_mm,
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
                f"CadQuery BREP anchor worker exceeded {timeout_s:.3f}s; process tree terminated"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
        if process.returncode != 0:
            raise RuntimeError(
                f"CadQuery BREP anchor worker failed with exit code {process.returncode}"
                + _diagnostic_suffix(stdout, stderr)
            )
        if len((stdout or "").encode("utf-8")) > MAX_ANCHOR_RESPONSE_BYTES:
            raise RuntimeError("CadQuery BREP anchor worker stdout exceeds bounded output size")
        try:
            return json.loads((stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "CadQuery BREP anchor worker returned no valid structured result"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
