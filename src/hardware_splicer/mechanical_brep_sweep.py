"""Bounded sampled mating-path evidence over exact STEP BREP geometry.

This module evaluates a declared translation-only path for one moving STEP member
against one fixed STEP member using the isolated CadQuery/OCCT specialist. Exact BREP
metrics are produced at each requested sample. The result is intentionally *sampled*
path evidence: it never claims continuous-path closure between samples, connector
mating, whole-assembly collision closure, physical measurement, or fabrication
readiness.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .engineering_source_ingestion import MAX_ENGINEERING_SOURCE_BYTES
from .mechanical_placement import DeclaredGeometryPlacement
from .step_geometry import StepModelSummary, parse_step_model


BREP_SWEEP_SCHEMA = "hardware_splicer.brep_mating_path_sweep.v1"
BREP_SWEEP_WORKER_SCHEMA = "hardware_splicer.cadquery_brep_sweep_worker.v1"
BREP_KERNEL = "cadquery_occt"
BREP_ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
MIN_SWEEP_SAMPLES = 2
MAX_SWEEP_SAMPLES = 33
_DEFAULT_TIMEOUT_S = 120.0
_DEFAULT_CONTACT_TOLERANCE_MM = 1e-6
_VOLUME_TOLERANCE_MM3 = 1e-9
_ROTATION_MATCH_TOLERANCE_DEG = 1e-9
_PATH_EPS_MM = 1e-12
_MAX_DIAGNOSTIC_CHARS = 4000
_WORKER_PATH = Path(__file__).with_name("_cadquery_brep_sweep_worker.py")
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


class BrepSweepStatus(str, Enum):
    READY = "ready"
    UNKNOWN = "unknown"


class BrepSweepSampleState(str, Enum):
    CLEAR = "clear"
    CONTACT = "contact"
    INTERFERENCE = "interference"
    UNKNOWN = "unknown"


class BrepSweepPhase(str, Enum):
    APPROACH = "approach"
    ENGAGEMENT = "engagement"


class BrepSweepBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BrepSweepSample(BrepSweepBase):
    sample_index: int = Field(ge=0)
    fraction: float = Field(ge=0.0, le=1.0)
    path_distance_mm: float = Field(ge=0.0)
    phase: BrepSweepPhase
    moving_translation_mm: tuple[float, float, float]
    state: BrepSweepSampleState
    exact_kernel_evaluated: bool
    minimum_distance_mm: float | None = Field(default=None, ge=0.0)
    intersection_volume_mm3: float | None = Field(default=None, ge=0.0)
    exact_solid_interference: bool | None = None


class BrepMatingPathSweepReport(BrepSweepBase):
    schema_version: str = BREP_SWEEP_SCHEMA
    project_id: str = Field(min_length=1)
    sweep_id: str = Field(min_length=1)
    moving_source_id: str = Field(min_length=1)
    fixed_source_id: str = Field(min_length=1)
    moving_model_id: str = Field(min_length=1)
    fixed_model_id: str = Field(min_length=1)
    moving_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    fixed_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    moving_object_id: str = Field(min_length=1)
    fixed_object_id: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    status: BrepSweepStatus
    kernel_available: bool
    kernel: str | None = None
    cadquery_version: str | None = None
    sample_count: int = Field(ge=MIN_SWEEP_SAMPLES, le=MAX_SWEEP_SAMPLES)
    evaluated_sample_count: int = Field(ge=0)
    path_length_mm: float = Field(ge=0.0)
    engagement_start_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    contact_distance_tolerance_mm: float = Field(ge=0.0)
    sampled_path_interference_free: bool | None = None
    approach_interference_free: bool | None = None
    engagement_region_evaluated: bool = False
    engagement_region_interference_free: bool | None = None
    first_contact_sample_index: int | None = Field(default=None, ge=0)
    first_contact_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    first_contact_path_distance_mm: float | None = Field(default=None, ge=0.0)
    first_interference_sample_index: int | None = Field(default=None, ge=0)
    first_interference_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    first_interference_path_distance_mm: float | None = Field(default=None, ge=0.0)
    samples: list[BrepSweepSample] = Field(default_factory=list)
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


Runner = Callable[
    [str, str, DeclaredGeometryPlacement, Sequence[DeclaredGeometryPlacement], float],
    Mapping[str, Any],
]


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
        "scope": "pairwise_sampled_translation_mating_path",
        "rotation_convention": BREP_ROTATION_CONVENTION,
        "translation_only_path": True,
        "sampled_path_only": True,
        "continuous_path_verified": False,
        "continuous_collision_free_verified": False,
        "aabb_fallback_used": False,
        "connector_mating_verified": False,
        "protocol_compatibility_verified": False,
        "pin_compatibility_verified": False,
        "retention_verified": False,
        "whole_assembly_collision": False,
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


def _placement(value: DeclaredGeometryPlacement | Mapping[str, Any]) -> DeclaredGeometryPlacement:
    return value if isinstance(value, DeclaredGeometryPlacement) else DeclaredGeometryPlacement.model_validate(value)


def _validate_path(
    *,
    moving_model: StepModelSummary,
    fixed_model: StepModelSummary,
    moving_start: DeclaredGeometryPlacement,
    moving_end: DeclaredGeometryPlacement,
    fixed: DeclaredGeometryPlacement,
) -> tuple[tuple[float, float, float], float]:
    if moving_start.model_id != moving_model.model_id or moving_end.model_id != moving_model.model_id:
        raise ValueError("moving path placements must target the imported moving STEP model")
    if fixed.model_id != fixed_model.model_id:
        raise ValueError("fixed placement must target the imported fixed STEP model")
    if moving_start.object_id != moving_end.object_id:
        raise ValueError("moving path start/end must target the same object_id")
    if moving_start.object_id == fixed.object_id:
        raise ValueError("mating-path sweep requires distinct moving and fixed objects")
    if moving_start.target_frame != moving_end.target_frame or moving_start.target_frame != fixed.target_frame:
        raise ValueError("moving start, moving end, and fixed placement must share one target frame")
    if any(
        abs(float(start) - float(end)) > _ROTATION_MATCH_TOLERANCE_DEG
        for start, end in zip(moving_start.rotation_deg_xyz, moving_end.rotation_deg_xyz)
    ):
        raise ValueError(
            "current exact mating-path sweep is translation-only; moving start/end rotations must match"
        )
    vector = tuple(
        float(moving_end.translation_mm[index]) - float(moving_start.translation_mm[index])
        for index in range(3)
    )
    length = math.sqrt(sum(value * value for value in vector))
    if length <= _PATH_EPS_MM:
        raise ValueError("mating-path sweep requires a non-zero declared translation path")
    return vector, length


def _interpolated_placements(
    start: DeclaredGeometryPlacement,
    end: DeclaredGeometryPlacement,
    sample_count: int,
) -> list[DeclaredGeometryPlacement]:
    rows: list[DeclaredGeometryPlacement] = []
    for index in range(sample_count):
        fraction = index / (sample_count - 1)
        translation = [
            float(start.translation_mm[axis])
            + fraction * (float(end.translation_mm[axis]) - float(start.translation_mm[axis]))
            for axis in range(3)
        ]
        rows.append(
            start.model_copy(
                update={
                    "placement_id": f"{start.placement_id}:sweep:{index}",
                    "translation_mm": translation,
                    "metadata": {
                        **start.metadata,
                        "sweep_sample_index": index,
                        "sweep_fraction": fraction,
                    },
                }
            )
        )
    return rows


def _unknown_report(
    *,
    project_id: str,
    sweep_id: str,
    moving: StepModelSummary,
    fixed: StepModelSummary,
    moving_start: DeclaredGeometryPlacement,
    fixed_placement: DeclaredGeometryPlacement,
    sample_count: int,
    path_length_mm: float,
    engagement_start_fraction: float | None,
    contact_distance_tolerance_mm: float,
    kernel_available: bool,
    reason: str,
    required_field: str,
    metadata: Mapping[str, Any] | None = None,
) -> BrepMatingPathSweepReport:
    return BrepMatingPathSweepReport(
        project_id=project_id,
        sweep_id=sweep_id,
        moving_source_id=moving.source_id,
        fixed_source_id=fixed.source_id,
        moving_model_id=moving.model_id,
        fixed_model_id=fixed.model_id,
        moving_content_hash=moving.content_hash,
        fixed_content_hash=fixed.content_hash,
        moving_object_id=moving_start.object_id,
        fixed_object_id=fixed_placement.object_id,
        frame_id=moving_start.target_frame,
        status=BrepSweepStatus.UNKNOWN,
        kernel_available=kernel_available,
        sample_count=sample_count,
        evaluated_sample_count=0,
        path_length_mm=path_length_mm,
        engagement_start_fraction=engagement_start_fraction,
        contact_distance_tolerance_mm=contact_distance_tolerance_mm,
        required_evidence=[{"field": required_field, "reason": reason}],
        metadata={**_base_metadata(), **dict(metadata or {})},
    )


def evaluate_step_brep_mating_path(
    *,
    project_id: str,
    sweep_id: str,
    moving_content: str,
    moving_source_id: str,
    moving_model_id: str | None,
    moving_start_placement: DeclaredGeometryPlacement | Mapping[str, Any],
    moving_end_placement: DeclaredGeometryPlacement | Mapping[str, Any],
    fixed_content: str,
    fixed_source_id: str,
    fixed_model_id: str | None,
    fixed_placement: DeclaredGeometryPlacement | Mapping[str, Any],
    sample_count: int = 9,
    engagement_start_fraction: float | None = None,
    contact_distance_tolerance_mm: float = _DEFAULT_CONTACT_TOLERANCE_MM,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    volume_tolerance_mm3: float = _VOLUME_TOLERANCE_MM3,
    kernel_available: bool | None = None,
    runner: Runner | None = None,
) -> BrepMatingPathSweepReport:
    """Evaluate exact BREP evidence at bounded samples along one declared translation path."""

    if not project_id.strip() or not sweep_id.strip():
        raise ValueError("project_id and sweep_id are required")
    if not MIN_SWEEP_SAMPLES <= int(sample_count) <= MAX_SWEEP_SAMPLES:
        raise ValueError(f"sample_count must be between {MIN_SWEEP_SAMPLES} and {MAX_SWEEP_SAMPLES}")
    sample_count = int(sample_count)
    if timeout_s <= 0:
        raise ValueError("timeout_s must be greater than zero")
    if contact_distance_tolerance_mm < 0 or not math.isfinite(contact_distance_tolerance_mm):
        raise ValueError("contact_distance_tolerance_mm must be finite and non-negative")
    if volume_tolerance_mm3 < 0 or not math.isfinite(volume_tolerance_mm3):
        raise ValueError("volume_tolerance_mm3 must be finite and non-negative")
    if engagement_start_fraction is not None and not 0.0 <= engagement_start_fraction <= 1.0:
        raise ValueError("engagement_start_fraction must be between zero and one")

    moving = _source_model(moving_content, moving_source_id, moving_model_id)
    fixed = _source_model(fixed_content, fixed_source_id, fixed_model_id)
    moving_start = _placement(moving_start_placement)
    moving_end = _placement(moving_end_placement)
    fixed_pose = _placement(fixed_placement)
    _, path_length = _validate_path(
        moving_model=moving,
        fixed_model=fixed,
        moving_start=moving_start,
        moving_end=moving_end,
        fixed=fixed_pose,
    )
    moving_samples = _interpolated_placements(moving_start, moving_end, sample_count)

    available = _cadquery_available() if kernel_available is None else bool(kernel_available)
    if not available:
        return _unknown_report(
            project_id=project_id,
            sweep_id=sweep_id,
            moving=moving,
            fixed=fixed,
            moving_start=moving_start,
            fixed_placement=fixed_pose,
            sample_count=sample_count,
            path_length_mm=path_length,
            engagement_start_fraction=engagement_start_fraction,
            contact_distance_tolerance_mm=contact_distance_tolerance_mm,
            kernel_available=False,
            reason="optional cadquery-isolated specialist is not available in this runtime",
            required_field="cadquery-isolated",
        )

    selected_runner = runner or _run_isolated_worker
    try:
        payload = dict(selected_runner(moving_content, fixed_content, fixed_pose, moving_samples, timeout_s))
    except (OSError, RuntimeError, TimeoutError, ValueError, subprocess.SubprocessError) as exc:
        return _unknown_report(
            project_id=project_id,
            sweep_id=sweep_id,
            moving=moving,
            fixed=fixed,
            moving_start=moving_start,
            fixed_placement=fixed_pose,
            sample_count=sample_count,
            path_length_mm=path_length,
            engagement_start_fraction=engagement_start_fraction,
            contact_distance_tolerance_mm=contact_distance_tolerance_mm,
            kernel_available=True,
            reason=f"isolated CadQuery BREP sweep worker failed: {type(exc).__name__}: {exc}",
            required_field="valid_brep_sweep_kernel_result",
            metadata={"worker_error_type": type(exc).__name__},
        )

    contract_error: tuple[str, str] | None = None
    if payload.get("ok") is not True:
        contract_error = ("valid_brep_sweep_kernel_result", "isolated CadQuery BREP sweep worker did not report success")
    elif payload.get("schema_version") != BREP_SWEEP_WORKER_SCHEMA:
        contract_error = ("compatible_brep_sweep_worker", f"CadQuery sweep worker schema must be {BREP_SWEEP_WORKER_SCHEMA!r}")
    elif payload.get("kernel") != BREP_KERNEL:
        contract_error = ("compatible_brep_sweep_worker", f"CadQuery sweep worker kernel identity must be {BREP_KERNEL!r}")
    elif payload.get("rotation_convention") != BREP_ROTATION_CONVENTION:
        contract_error = ("compatible_brep_sweep_worker", "CadQuery sweep worker placement convention disagrees with HS placement convention")
    elif payload.get("moving_content_hash") != moving.content_hash or payload.get("fixed_content_hash") != fixed.content_hash:
        contract_error = ("kernel_input_identity", "CadQuery sweep worker input hashes disagree with canonical STEP identities")
    elif payload.get("moving_shape_valid") is not True or payload.get("fixed_shape_valid") is not True:
        contract_error = ("valid_step_brep", "CadQuery/OCCT reports an invalid imported BREP shape")
    if contract_error is not None:
        return _unknown_report(
            project_id=project_id,
            sweep_id=sweep_id,
            moving=moving,
            fixed=fixed,
            moving_start=moving_start,
            fixed_placement=fixed_pose,
            sample_count=sample_count,
            path_length_mm=path_length,
            engagement_start_fraction=engagement_start_fraction,
            contact_distance_tolerance_mm=contact_distance_tolerance_mm,
            kernel_available=True,
            reason=contract_error[1],
            required_field=contract_error[0],
            metadata={
                "worker_schema": payload.get("schema_version"),
                "worker_kernel": payload.get("kernel"),
                "worker_rotation_convention": payload.get("rotation_convention"),
            },
        )

    try:
        moving_solid_count = int(payload["moving_solid_count"])
        fixed_solid_count = int(payload["fixed_solid_count"])
    except (KeyError, TypeError, ValueError):
        moving_solid_count = 0
        fixed_solid_count = 0
    if moving_solid_count <= 0 or fixed_solid_count <= 0:
        return _unknown_report(
            project_id=project_id,
            sweep_id=sweep_id,
            moving=moving,
            fixed=fixed,
            moving_start=moving_start,
            fixed_placement=fixed_pose,
            sample_count=sample_count,
            path_length_mm=path_length,
            engagement_start_fraction=engagement_start_fraction,
            contact_distance_tolerance_mm=contact_distance_tolerance_mm,
            kernel_available=True,
            reason="exact mating-path evidence requires at least one imported solid in each STEP source",
            required_field="solid_step_brep",
        )

    worker_samples = payload.get("samples")
    if not isinstance(worker_samples, list) or len(worker_samples) != sample_count:
        return _unknown_report(
            project_id=project_id,
            sweep_id=sweep_id,
            moving=moving,
            fixed=fixed,
            moving_start=moving_start,
            fixed_placement=fixed_pose,
            sample_count=sample_count,
            path_length_mm=path_length,
            engagement_start_fraction=engagement_start_fraction,
            contact_distance_tolerance_mm=contact_distance_tolerance_mm,
            kernel_available=True,
            reason="CadQuery sweep worker returned the wrong number of bounded samples",
            required_field="complete_brep_sweep_samples",
        )

    samples: list[BrepSweepSample] = []
    for index, (worker_row, placement) in enumerate(zip(worker_samples, moving_samples)):
        if not isinstance(worker_row, Mapping) or worker_row.get("sample_index") != index:
            return _unknown_report(
                project_id=project_id,
                sweep_id=sweep_id,
                moving=moving,
                fixed=fixed,
                moving_start=moving_start,
                fixed_placement=fixed_pose,
                sample_count=sample_count,
                path_length_mm=path_length,
                engagement_start_fraction=engagement_start_fraction,
                contact_distance_tolerance_mm=contact_distance_tolerance_mm,
                kernel_available=True,
                reason="CadQuery sweep worker sample identities are incomplete or out of order",
                required_field="complete_brep_sweep_samples",
            )
        try:
            distance = float(worker_row["minimum_distance_mm"])
            volume = float(worker_row["intersection_volume_mm3"])
        except (KeyError, TypeError, ValueError):
            distance = math.nan
            volume = math.nan
        if not all(math.isfinite(value) and value >= 0.0 for value in (distance, volume)):
            return _unknown_report(
                project_id=project_id,
                sweep_id=sweep_id,
                moving=moving,
                fixed=fixed,
                moving_start=moving_start,
                fixed_placement=fixed_pose,
                sample_count=sample_count,
                path_length_mm=path_length,
                engagement_start_fraction=engagement_start_fraction,
                contact_distance_tolerance_mm=contact_distance_tolerance_mm,
                kernel_available=True,
                reason="CadQuery sweep worker returned non-finite or negative sample metrics",
                required_field="valid_brep_sweep_kernel_result",
            )
        interference = volume > volume_tolerance_mm3
        if interference:
            state = BrepSweepSampleState.INTERFERENCE
        elif distance <= contact_distance_tolerance_mm + 1e-12:
            state = BrepSweepSampleState.CONTACT
        else:
            state = BrepSweepSampleState.CLEAR
        fraction = index / (sample_count - 1)
        phase = (
            BrepSweepPhase.ENGAGEMENT
            if engagement_start_fraction is not None and fraction >= engagement_start_fraction - 1e-12
            else BrepSweepPhase.APPROACH
        )
        samples.append(
            BrepSweepSample(
                sample_index=index,
                fraction=fraction,
                path_distance_mm=path_length * fraction,
                phase=phase,
                moving_translation_mm=tuple(float(value) for value in placement.translation_mm),
                state=state,
                exact_kernel_evaluated=True,
                minimum_distance_mm=distance,
                intersection_volume_mm3=volume,
                exact_solid_interference=interference,
            )
        )

    first_contact = next((sample for sample in samples if sample.state == BrepSweepSampleState.CONTACT), None)
    first_interference = next((sample for sample in samples if sample.state == BrepSweepSampleState.INTERFERENCE), None)
    approach_samples = [sample for sample in samples if sample.phase == BrepSweepPhase.APPROACH]
    engagement_samples = [sample for sample in samples if sample.phase == BrepSweepPhase.ENGAGEMENT]
    sampled_clear = all(sample.state != BrepSweepSampleState.INTERFERENCE for sample in samples)
    approach_clear = all(sample.state != BrepSweepSampleState.INTERFERENCE for sample in approach_samples)
    engagement_evaluated = engagement_start_fraction is not None and bool(engagement_samples)
    engagement_clear = (
        all(sample.state != BrepSweepSampleState.INTERFERENCE for sample in engagement_samples)
        if engagement_evaluated
        else None
    )

    return BrepMatingPathSweepReport(
        project_id=project_id,
        sweep_id=sweep_id,
        moving_source_id=moving.source_id,
        fixed_source_id=fixed.source_id,
        moving_model_id=moving.model_id,
        fixed_model_id=fixed.model_id,
        moving_content_hash=moving.content_hash,
        fixed_content_hash=fixed.content_hash,
        moving_object_id=moving_start.object_id,
        fixed_object_id=fixed_pose.object_id,
        frame_id=moving_start.target_frame,
        status=BrepSweepStatus.READY,
        kernel_available=True,
        kernel=BREP_KERNEL,
        cadquery_version=(str(payload["cadquery_version"]) if payload.get("cadquery_version") else None),
        sample_count=sample_count,
        evaluated_sample_count=len(samples),
        path_length_mm=path_length,
        engagement_start_fraction=engagement_start_fraction,
        contact_distance_tolerance_mm=contact_distance_tolerance_mm,
        sampled_path_interference_free=sampled_clear,
        approach_interference_free=approach_clear,
        engagement_region_evaluated=engagement_evaluated,
        engagement_region_interference_free=engagement_clear,
        first_contact_sample_index=first_contact.sample_index if first_contact else None,
        first_contact_fraction=first_contact.fraction if first_contact else None,
        first_contact_path_distance_mm=first_contact.path_distance_mm if first_contact else None,
        first_interference_sample_index=first_interference.sample_index if first_interference else None,
        first_interference_fraction=first_interference.fraction if first_interference else None,
        first_interference_path_distance_mm=first_interference.path_distance_mm if first_interference else None,
        samples=samples,
        metadata={
            **_base_metadata(),
            "worker_isolated": True,
            "worker_schema": BREP_SWEEP_WORKER_SCHEMA,
            "kernel_input_hash_reverified": True,
            "moving_solid_count": moving_solid_count,
            "fixed_solid_count": fixed_solid_count,
            "intersection_volume_tolerance_mm3": volume_tolerance_mm3,
            "first_contact_is_sampled_event_only": True,
            "first_interference_is_sampled_event_only": True,
        },
    )


def _run_isolated_worker(
    moving_content: str,
    fixed_content: str,
    fixed_placement: DeclaredGeometryPlacement,
    moving_placements: Sequence[DeclaredGeometryPlacement],
    timeout_s: float,
) -> Mapping[str, Any]:
    if not _WORKER_PATH.is_file():
        raise RuntimeError(f"CadQuery BREP sweep worker is missing: {_WORKER_PATH}")

    with tempfile.TemporaryDirectory(prefix="hardware-splicer-brep-sweep-") as temp_dir:
        root = Path(temp_dir)
        moving_path = root / "moving.step"
        fixed_path = root / "fixed.step"
        input_path = root / "request.json"
        moving_path.write_text(moving_content, encoding="utf-8")
        fixed_path.write_text(fixed_content, encoding="utf-8")
        input_path.write_text(
            json.dumps(
                {
                    "moving_step_path": str(moving_path),
                    "fixed_step_path": str(fixed_path),
                    "fixed_placement": {
                        "translation_mm": list(fixed_placement.translation_mm),
                        "rotation_deg_xyz": list(fixed_placement.rotation_deg_xyz),
                    },
                    "moving_placements": [
                        {
                            "translation_mm": list(placement.translation_mm),
                            "rotation_deg_xyz": list(placement.rotation_deg_xyz),
                        }
                        for placement in moving_placements
                    ],
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
                f"CadQuery BREP sweep worker exceeded {timeout_s:.3f}s; process tree terminated"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
        if process.returncode != 0:
            raise RuntimeError(
                f"CadQuery BREP sweep worker failed with exit code {process.returncode}"
                + _diagnostic_suffix(stdout, stderr)
            )
        try:
            return json.loads((stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "CadQuery BREP sweep worker returned no valid structured result"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc


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
