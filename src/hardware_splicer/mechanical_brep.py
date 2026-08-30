"""Optional exact STEP BREP pair-interference evidence via CadQuery/OCCT.

The existing mechanical path intentionally remains AABB/declared-envelope based.
This module is a narrow opt-in bridge to the already-declared ``cadquery-isolated``
specialist. It may establish pairwise solid interference and minimum shape distance
for two explicitly placed STEP sources. It does not establish connector mating,
cable routing, service ergonomics, structural safety, fabrication readiness, or any
physical authorization.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
from enum import Enum
from math import isfinite
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .engineering_source_ingestion import MAX_ENGINEERING_SOURCE_BYTES
from .mechanical_placement import DeclaredGeometryPlacement
from .step_geometry import StepModelSummary, parse_step_model


BREP_INTERFERENCE_SCHEMA = "hardware_splicer.brep_pair_interference.v1"
BREP_WORKER_SCHEMA = "hardware_splicer.cadquery_brep_worker.v1"
BREP_KERNEL = "cadquery_occt"
BREP_ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
_DEFAULT_TIMEOUT_S = 60.0
_MAX_DIAGNOSTIC_CHARS = 4000
_VOLUME_TOLERANCE_MM3 = 1e-9
_WORKER_PATH = Path(__file__).with_name("_cadquery_brep_worker.py")
_ALLOWED_ENV_KEYS = {
    "HOME",
    "PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
}


class BrepStatus(str, Enum):
    CLEAR = "clear"
    INTERFERENCE = "interference"
    UNKNOWN = "unknown"


class BrepBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BrepPairInterferenceReport(BrepBase):
    schema_version: str = BREP_INTERFERENCE_SCHEMA
    project_id: str = Field(min_length=1)
    first_source_id: str = Field(min_length=1)
    second_source_id: str = Field(min_length=1)
    first_model_id: str = Field(min_length=1)
    second_model_id: str = Field(min_length=1)
    first_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    second_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    frame_id: str | None = None
    status: BrepStatus
    kernel_available: bool
    kernel: str | None = None
    cadquery_version: str | None = None
    first_shape_valid: bool | None = None
    second_shape_valid: bool | None = None
    first_solid_count: int | None = Field(default=None, ge=0)
    second_solid_count: int | None = Field(default=None, ge=0)
    minimum_distance_mm: float | None = Field(default=None, ge=0.0)
    intersection_volume_mm3: float | None = Field(default=None, ge=0.0)
    exact_solid_interference: bool | None = None
    exact_pair_interference_evaluated: bool = False
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


Runner = Callable[[str, str, DeclaredGeometryPlacement, DeclaredGeometryPlacement, float], Mapping[str, Any]]


def _cadquery_available() -> bool:
    try:
        return importlib.util.find_spec("cadquery") is not None
    except (ImportError, ValueError):
        return False


def _source_model(content: str, source_id: str, model_id: str | None) -> StepModelSummary:
    size_bytes = len(content.encode("utf-8"))
    if size_bytes > MAX_ENGINEERING_SOURCE_BYTES:
        raise ValueError(
            f"STEP source {source_id!r} is {size_bytes} bytes; exact BREP input is bounded to "
            f"{MAX_ENGINEERING_SOURCE_BYTES} bytes"
        )
    return parse_step_model(content, source_id=source_id, model_id=model_id)


def _base_metadata() -> Dict[str, Any]:
    return {
        "specialist_capability": "cadquery-isolated",
        "scope": "pairwise_static_step_solid_interference_and_minimum_distance",
        "rotation_convention": BREP_ROTATION_CONVENTION,
        "aabb_fallback_used": False,
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


def _unknown_report(
    *,
    project_id: str,
    first: StepModelSummary,
    second: StepModelSummary,
    frame_id: str | None,
    kernel_available: bool,
    reason: str,
    required_field: str,
    metadata: Mapping[str, Any] | None = None,
) -> BrepPairInterferenceReport:
    return BrepPairInterferenceReport(
        project_id=project_id,
        first_source_id=first.source_id,
        second_source_id=second.source_id,
        first_model_id=first.model_id,
        second_model_id=second.model_id,
        first_content_hash=first.content_hash,
        second_content_hash=second.content_hash,
        frame_id=frame_id,
        status=BrepStatus.UNKNOWN,
        kernel_available=kernel_available,
        required_evidence=[
            {
                "field": required_field,
                "reason": reason,
            }
        ],
        metadata={**_base_metadata(), **dict(metadata or {})},
    )


def _worker_contract_failure(
    *,
    project_id: str,
    first: StepModelSummary,
    second: StepModelSummary,
    frame_id: str,
    reason: str,
    required_field: str = "valid_brep_kernel_result",
    payload: Mapping[str, Any] | None = None,
) -> BrepPairInterferenceReport:
    worker = payload or {}
    return _unknown_report(
        project_id=project_id,
        first=first,
        second=second,
        frame_id=frame_id,
        kernel_available=True,
        reason=reason,
        required_field=required_field,
        metadata={
            "worker_schema": worker.get("schema_version"),
            "worker_kernel": worker.get("kernel"),
            "worker_rotation_convention": worker.get("rotation_convention"),
        },
    )


def check_step_brep_interference(
    *,
    project_id: str,
    first_content: str,
    first_source_id: str,
    first_model_id: str | None,
    first_placement: DeclaredGeometryPlacement | Mapping[str, Any],
    second_content: str,
    second_source_id: str,
    second_model_id: str | None,
    second_placement: DeclaredGeometryPlacement | Mapping[str, Any],
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    volume_tolerance_mm3: float = _VOLUME_TOLERANCE_MM3,
    kernel_available: bool | None = None,
    runner: Runner | None = None,
) -> BrepPairInterferenceReport:
    """Evaluate one exact placed-STEP pair when the optional kernel is available.

    ``UNKNOWN`` is returned rather than silently falling back to AABB evidence when
    CadQuery/OCCT is absent, the two placements do not share a frame, imported solids
    are invalid, or the isolated worker fails.
    """

    if timeout_s <= 0:
        raise ValueError("timeout_s must be greater than zero")
    if volume_tolerance_mm3 < 0:
        raise ValueError("volume_tolerance_mm3 must be non-negative")

    first = _source_model(first_content, first_source_id, first_model_id)
    second = _source_model(second_content, second_source_id, second_model_id)
    first_pose = (
        first_placement
        if isinstance(first_placement, DeclaredGeometryPlacement)
        else DeclaredGeometryPlacement.model_validate(first_placement)
    )
    second_pose = (
        second_placement
        if isinstance(second_placement, DeclaredGeometryPlacement)
        else DeclaredGeometryPlacement.model_validate(second_placement)
    )
    if first_pose.model_id != first.model_id:
        raise ValueError(
            f"first placement targets model {first_pose.model_id!r}, not imported STEP model {first.model_id!r}"
        )
    if second_pose.model_id != second.model_id:
        raise ValueError(
            f"second placement targets model {second_pose.model_id!r}, not imported STEP model {second.model_id!r}"
        )

    available = _cadquery_available() if kernel_available is None else bool(kernel_available)
    if first_pose.target_frame != second_pose.target_frame:
        return _unknown_report(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=None,
            kernel_available=available,
            reason=(
                f"placements use different frames {first_pose.target_frame!r} and {second_pose.target_frame!r}; "
                "an explicit relative transform is required"
            ),
            required_field="relative_transform",
        )
    frame_id = first_pose.target_frame
    if not available:
        return _unknown_report(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            kernel_available=False,
            reason="optional cadquery-isolated specialist is not available in this runtime",
            required_field="cadquery-isolated",
        )

    selected_runner = runner or _run_isolated_worker
    try:
        payload = dict(selected_runner(first_content, second_content, first_pose, second_pose, timeout_s))
    except (OSError, RuntimeError, TimeoutError, ValueError, subprocess.SubprocessError) as exc:
        return _unknown_report(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            kernel_available=True,
            reason=f"isolated CadQuery BREP worker failed: {type(exc).__name__}: {exc}",
            required_field="valid_brep_kernel_result",
            metadata={"worker_error_type": type(exc).__name__},
        )

    if payload.get("ok") is not True:
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason="isolated CadQuery BREP worker did not report success",
            payload=payload,
        )
    if payload.get("schema_version") != BREP_WORKER_SCHEMA:
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason=f"CadQuery worker schema must be {BREP_WORKER_SCHEMA!r}",
            required_field="compatible_brep_worker",
            payload=payload,
        )
    if payload.get("kernel") != BREP_KERNEL:
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason=f"CadQuery worker kernel identity must be {BREP_KERNEL!r}",
            required_field="compatible_brep_worker",
            payload=payload,
        )
    if payload.get("rotation_convention") != BREP_ROTATION_CONVENTION:
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason="CadQuery worker placement convention disagrees with the declared HS placement convention",
            required_field="compatible_brep_worker",
            payload=payload,
        )
    if payload.get("first_content_hash") != first.content_hash or payload.get("second_content_hash") != second.content_hash:
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason="CadQuery worker input hashes disagree with the canonical STEP identities",
            required_field="kernel_input_identity",
            payload=payload,
        )

    first_valid = payload.get("first_shape_valid") is True
    second_valid = payload.get("second_shape_valid") is True
    if not first_valid or not second_valid:
        invalid = []
        if not first_valid:
            invalid.append(first.source_id)
        if not second_valid:
            invalid.append(second.source_id)
        return _unknown_report(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            kernel_available=True,
            reason=f"CadQuery/OCCT reports invalid imported BREP shape(s): {', '.join(invalid)}",
            required_field="valid_step_brep",
            metadata={
                "kernel": payload.get("kernel"),
                "cadquery_version": payload.get("cadquery_version"),
                "first_shape_valid": first_valid,
                "second_shape_valid": second_valid,
                "worker_schema": payload.get("schema_version"),
            },
        )

    try:
        first_solid_count = int(payload["first_solid_count"])
        second_solid_count = int(payload["second_solid_count"])
    except (KeyError, TypeError, ValueError):
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason="CadQuery/OCCT result omitted valid solid counts",
            required_field="solid_step_brep",
            payload=payload,
        )
    if first_solid_count <= 0 or second_solid_count <= 0:
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason="exact solid interference requires at least one imported solid in each STEP source",
            required_field="solid_step_brep",
            payload=payload,
        )

    try:
        minimum_distance_mm = float(payload["minimum_distance_mm"])
        intersection_volume_mm3 = float(payload["intersection_volume_mm3"])
    except (KeyError, TypeError, ValueError):
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason="CadQuery/OCCT result omitted numeric BREP evidence",
            payload=payload,
        )
    if not all(isfinite(value) and value >= 0.0 for value in (minimum_distance_mm, intersection_volume_mm3)):
        return _worker_contract_failure(
            project_id=project_id,
            first=first,
            second=second,
            frame_id=frame_id,
            reason="CadQuery/OCCT returned non-finite or negative BREP metrics",
            payload=payload,
        )

    interference = intersection_volume_mm3 > volume_tolerance_mm3
    return BrepPairInterferenceReport(
        project_id=project_id,
        first_source_id=first.source_id,
        second_source_id=second.source_id,
        first_model_id=first.model_id,
        second_model_id=second.model_id,
        first_content_hash=first.content_hash,
        second_content_hash=second.content_hash,
        frame_id=frame_id,
        status=BrepStatus.INTERFERENCE if interference else BrepStatus.CLEAR,
        kernel_available=True,
        kernel=BREP_KERNEL,
        cadquery_version=(str(payload["cadquery_version"]) if payload.get("cadquery_version") else None),
        first_shape_valid=True,
        second_shape_valid=True,
        first_solid_count=first_solid_count,
        second_solid_count=second_solid_count,
        minimum_distance_mm=minimum_distance_mm,
        intersection_volume_mm3=intersection_volume_mm3,
        exact_solid_interference=interference,
        exact_pair_interference_evaluated=True,
        metadata={
            **_base_metadata(),
            "touching_or_intersecting_distance": minimum_distance_mm <= 1e-12,
            "intersection_volume_tolerance_mm3": volume_tolerance_mm3,
            "worker_isolated": True,
            "worker_schema": BREP_WORKER_SCHEMA,
            "kernel_input_hash_reverified": True,
            "solid_brep_required": True,
        },
    )


def _run_isolated_worker(
    first_content: str,
    second_content: str,
    first_placement: DeclaredGeometryPlacement,
    second_placement: DeclaredGeometryPlacement,
    timeout_s: float,
) -> Mapping[str, Any]:
    if not _WORKER_PATH.is_file():
        raise RuntimeError(f"CadQuery BREP worker is missing: {_WORKER_PATH}")

    with tempfile.TemporaryDirectory(prefix="hardware-splicer-brep-") as temp_dir:
        root = Path(temp_dir)
        first_path = root / "first.step"
        second_path = root / "second.step"
        input_path = root / "request.json"
        first_path.write_text(first_content, encoding="utf-8")
        second_path.write_text(second_content, encoding="utf-8")
        input_path.write_text(
            json.dumps(
                {
                    "first_step_path": str(first_path),
                    "second_step_path": str(second_path),
                    "first_placement": {
                        "translation_mm": list(first_placement.translation_mm),
                        "rotation_deg_xyz": list(first_placement.rotation_deg_xyz),
                    },
                    "second_placement": {
                        "translation_mm": list(second_placement.translation_mm),
                        "rotation_deg_xyz": list(second_placement.rotation_deg_xyz),
                    },
                }
            ),
            encoding="utf-8",
        )
        process = _start_worker(input_path, root)
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            stdout, stderr = process.communicate()
            raise TimeoutError(
                f"CadQuery BREP worker exceeded {timeout_s:.3f}s; process tree terminated"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
        if process.returncode != 0:
            raise RuntimeError(
                f"CadQuery BREP worker failed with exit code {process.returncode}"
                + _diagnostic_suffix(stdout, stderr)
            )
        try:
            payload = json.loads((stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "CadQuery BREP worker returned no valid structured result"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
        return payload


def _sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    current = source or os.environ
    environment = {key: value for key, value in current.items() if key in _ALLOWED_ENV_KEYS}
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["HARDWARE_SPLICER_CAD_WORKER"] = "1"
    return environment


def _start_worker(input_path: Path, cwd: Path) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {
        "args": [sys.executable, "-I", str(_WORKER_PATH), str(input_path)],
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "env": _sanitized_environment(),
        "cwd": str(cwd),
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(**kwargs)  # type: ignore[arg-type]


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _diagnostic_suffix(stdout: str | None, stderr: str | None) -> str:
    details = []
    if stderr and stderr.strip():
        details.append(f"stderr={stderr.strip()[-_MAX_DIAGNOSTIC_CHARS:]!r}")
    if stdout and stdout.strip():
        details.append(f"stdout={stdout.strip()[-_MAX_DIAGNOSTIC_CHARS:]!r}")
    return f" ({'; '.join(details)})" if details else ""