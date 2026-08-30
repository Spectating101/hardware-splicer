"""Adaptive exact-BREP transition brackets for a sampled mating path.

This module preserves the existing coarse sampled mating-path report, detects adjacent
samples whose geometry predicates differ, and adaptively bisects only those intervals
with the isolated CadQuery/OCCT specialist. Returned brackets localize a predicate
change but deliberately do not claim a unique contact pose, monotonicity inside the
interval, continuous-path clearance, connector mating, or whole-assembly validity.
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

from .mechanical_brep_sweep import (
    BREP_KERNEL,
    BREP_ROTATION_CONVENTION,
    BREP_SWEEP_WORKER_SCHEMA,
    BrepMatingPathSweepReport,
    BrepSweepSample,
    BrepSweepSampleState,
    evaluate_step_brep_mating_path,
)
from .mechanical_placement import DeclaredGeometryPlacement


BREP_REFINEMENT_SCHEMA = "hardware_splicer.brep_mating_path_refinement.v1"
BREP_REFINEMENT_WORKER_SCHEMA = "hardware_splicer.cadquery_brep_transition_refinement_worker.v1"
MIN_REFINEMENT_DEPTH = 1
MAX_REFINEMENT_DEPTH = 12
DEFAULT_REFINEMENT_DEPTH = 8
MIN_REFINEMENT_FRACTION_TOLERANCE = 1e-6
MAX_REFINEMENT_FRACTION_TOLERANCE = 0.25
DEFAULT_REFINEMENT_FRACTION_TOLERANCE = 1e-3
_DEFAULT_TIMEOUT_S = 120.0
_DEFAULT_VOLUME_TOLERANCE_MM3 = 1e-9
_MAX_DIAGNOSTIC_CHARS = 4000
_WORKER_PATH = Path(__file__).with_name("_cadquery_brep_transition_refinement_worker.py")
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


class BrepRefinementStatus(str, Enum):
    READY = "ready"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class BrepTransitionBoundaryKind(str, Enum):
    CLEARANCE = "clearance_boundary"
    INTERFERENCE = "interference_boundary"


class BrepRefinementBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BrepTransitionCandidate(BrepRefinementBase):
    kind: BrepTransitionBoundaryKind
    lower_sample_index: int = Field(ge=0)
    upper_sample_index: int = Field(ge=1)
    lower_fraction: float = Field(ge=0.0, le=1.0)
    upper_fraction: float = Field(ge=0.0, le=1.0)
    lower_state: BrepSweepSampleState
    upper_state: BrepSweepSampleState


class BrepTransitionBracket(BrepRefinementBase):
    boundary_index: int = Field(ge=0)
    kind: BrepTransitionBoundaryKind
    lower_fraction: float = Field(ge=0.0, le=1.0)
    upper_fraction: float = Field(ge=0.0, le=1.0)
    lower_path_distance_mm: float = Field(ge=0.0)
    upper_path_distance_mm: float = Field(ge=0.0)
    bracket_width_fraction: float = Field(ge=0.0)
    bracket_width_mm: float = Field(ge=0.0)
    lower_state: BrepSweepSampleState
    upper_state: BrepSweepSampleState
    lower_minimum_distance_mm: float = Field(ge=0.0)
    upper_minimum_distance_mm: float = Field(ge=0.0)
    lower_intersection_volume_mm3: float = Field(ge=0.0)
    upper_intersection_volume_mm3: float = Field(ge=0.0)
    refinement_depth: int = Field(ge=0)
    evaluation_count: int = Field(ge=2)
    converged: bool
    max_depth_reached: bool


class BrepMatingPathRefinementReport(BrepRefinementBase):
    schema_version: str = BREP_REFINEMENT_SCHEMA
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
    status: BrepRefinementStatus
    kernel_available: bool
    kernel: str | None = None
    cadquery_version: str | None = None
    path_length_mm: float = Field(ge=0.0)
    coarse_sample_count: int = Field(ge=2)
    coarse_evaluated_sample_count: int = Field(ge=0)
    refinement_candidate_count: int = Field(ge=0)
    refined_boundary_count: int = Field(ge=0)
    refinement_evaluated_pose_count: int = Field(ge=0)
    total_exact_pose_evaluations: int = Field(ge=0)
    refinement_max_depth: int = Field(ge=MIN_REFINEMENT_DEPTH, le=MAX_REFINEMENT_DEPTH)
    refinement_fraction_tolerance: float = Field(
        ge=MIN_REFINEMENT_FRACTION_TOLERANCE,
        le=MAX_REFINEMENT_FRACTION_TOLERANCE,
    )
    coarse_report: BrepMatingPathSweepReport
    candidates: list[BrepTransitionCandidate] = Field(default_factory=list)
    brackets: list[BrepTransitionBracket] = Field(default_factory=list)
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


CoarseRunner = Callable[
    [str, str, DeclaredGeometryPlacement, Sequence[DeclaredGeometryPlacement], float],
    Mapping[str, Any],
]
RefinementRunner = Callable[
    [
        str,
        str,
        DeclaredGeometryPlacement,
        DeclaredGeometryPlacement,
        DeclaredGeometryPlacement,
        Sequence[BrepTransitionCandidate],
        float,
        float,
        int,
        float,
        float,
    ],
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
        "scope": "pairwise_adaptive_sample_transition_refinement",
        "rotation_convention": BREP_ROTATION_CONVENTION,
        "translation_only_path": True,
        "adaptive_refinement": True,
        "transition_brackets_only": True,
        "unique_transition_pose_verified": False,
        "monotonicity_inside_bracket_verified": False,
        "continuous_path_verified": False,
        "continuous_collision_free_verified": False,
        "aabb_fallback_used": False,
        "connector_mating_verified": False,
        "whole_assembly_collision": False,
        "physical_measurement": False,
        "manufacturing_authorized": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def _predicate(kind: BrepTransitionBoundaryKind, state: BrepSweepSampleState) -> bool:
    if kind == BrepTransitionBoundaryKind.CLEARANCE:
        return state == BrepSweepSampleState.CLEAR
    return state == BrepSweepSampleState.INTERFERENCE


def _transition_candidates(samples: Sequence[BrepSweepSample]) -> list[BrepTransitionCandidate]:
    candidates: list[BrepTransitionCandidate] = []
    for lower, upper in zip(samples, samples[1:]):
        for kind in (BrepTransitionBoundaryKind.CLEARANCE, BrepTransitionBoundaryKind.INTERFERENCE):
            if _predicate(kind, lower.state) == _predicate(kind, upper.state):
                continue
            candidates.append(
                BrepTransitionCandidate(
                    kind=kind,
                    lower_sample_index=lower.sample_index,
                    upper_sample_index=upper.sample_index,
                    lower_fraction=lower.fraction,
                    upper_fraction=upper.fraction,
                    lower_state=lower.state,
                    upper_state=upper.state,
                )
            )
    return candidates


def _unknown_report(
    *,
    coarse: BrepMatingPathSweepReport,
    candidates: Sequence[BrepTransitionCandidate],
    refinement_max_depth: int,
    refinement_fraction_tolerance: float,
    reason: str,
    required_field: str,
    kernel_available: bool,
    metadata: Mapping[str, Any] | None = None,
) -> BrepMatingPathRefinementReport:
    return BrepMatingPathRefinementReport(
        project_id=coarse.project_id,
        sweep_id=coarse.sweep_id,
        moving_source_id=coarse.moving_source_id,
        fixed_source_id=coarse.fixed_source_id,
        moving_model_id=coarse.moving_model_id,
        fixed_model_id=coarse.fixed_model_id,
        moving_content_hash=coarse.moving_content_hash,
        fixed_content_hash=coarse.fixed_content_hash,
        moving_object_id=coarse.moving_object_id,
        fixed_object_id=coarse.fixed_object_id,
        frame_id=coarse.frame_id,
        status=BrepRefinementStatus.UNKNOWN,
        kernel_available=kernel_available,
        kernel=coarse.kernel,
        cadquery_version=coarse.cadquery_version,
        path_length_mm=coarse.path_length_mm,
        coarse_sample_count=coarse.sample_count,
        coarse_evaluated_sample_count=coarse.evaluated_sample_count,
        refinement_candidate_count=len(candidates),
        refined_boundary_count=0,
        refinement_evaluated_pose_count=0,
        total_exact_pose_evaluations=coarse.evaluated_sample_count,
        refinement_max_depth=refinement_max_depth,
        refinement_fraction_tolerance=refinement_fraction_tolerance,
        coarse_report=coarse,
        candidates=list(candidates),
        required_evidence=[{"field": required_field, "reason": reason}],
        metadata={**_base_metadata(), **dict(metadata or {})},
    )


def evaluate_step_brep_mating_path_refinement(
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
    contact_distance_tolerance_mm: float = 1e-6,
    refinement_max_depth: int = DEFAULT_REFINEMENT_DEPTH,
    refinement_fraction_tolerance: float = DEFAULT_REFINEMENT_FRACTION_TOLERANCE,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    volume_tolerance_mm3: float = _DEFAULT_VOLUME_TOLERANCE_MM3,
    kernel_available: bool | None = None,
    coarse_runner: CoarseRunner | None = None,
    refinement_runner: RefinementRunner | None = None,
) -> BrepMatingPathRefinementReport:
    """Refine exact-BREP predicate transitions without promoting continuous authority."""

    if not MIN_REFINEMENT_DEPTH <= int(refinement_max_depth) <= MAX_REFINEMENT_DEPTH:
        raise ValueError(
            f"refinement_max_depth must be between {MIN_REFINEMENT_DEPTH} and {MAX_REFINEMENT_DEPTH}"
        )
    refinement_max_depth = int(refinement_max_depth)
    if not math.isfinite(refinement_fraction_tolerance) or not (
        MIN_REFINEMENT_FRACTION_TOLERANCE
        <= refinement_fraction_tolerance
        <= MAX_REFINEMENT_FRACTION_TOLERANCE
    ):
        raise ValueError(
            "refinement_fraction_tolerance must be finite and between "
            f"{MIN_REFINEMENT_FRACTION_TOLERANCE} and {MAX_REFINEMENT_FRACTION_TOLERANCE}"
        )
    if timeout_s <= 0:
        raise ValueError("timeout_s must be greater than zero")

    coarse = evaluate_step_brep_mating_path(
        project_id=project_id,
        sweep_id=sweep_id,
        moving_content=moving_content,
        moving_source_id=moving_source_id,
        moving_model_id=moving_model_id,
        moving_start_placement=moving_start_placement,
        moving_end_placement=moving_end_placement,
        fixed_content=fixed_content,
        fixed_source_id=fixed_source_id,
        fixed_model_id=fixed_model_id,
        fixed_placement=fixed_placement,
        sample_count=sample_count,
        engagement_start_fraction=engagement_start_fraction,
        contact_distance_tolerance_mm=contact_distance_tolerance_mm,
        timeout_s=timeout_s,
        volume_tolerance_mm3=volume_tolerance_mm3,
        kernel_available=kernel_available,
        runner=coarse_runner,
    )
    candidates = _transition_candidates(coarse.samples) if coarse.status.value == "ready" else []
    if coarse.status.value != "ready":
        return _unknown_report(
            coarse=coarse,
            candidates=candidates,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            reason="coarse exact-BREP mating-path evidence is not ready, so transition refinement cannot run",
            required_field="ready_coarse_brep_mating_path",
            kernel_available=coarse.kernel_available,
        )

    if not candidates:
        return BrepMatingPathRefinementReport(
            project_id=coarse.project_id,
            sweep_id=coarse.sweep_id,
            moving_source_id=coarse.moving_source_id,
            fixed_source_id=coarse.fixed_source_id,
            moving_model_id=coarse.moving_model_id,
            fixed_model_id=coarse.fixed_model_id,
            moving_content_hash=coarse.moving_content_hash,
            fixed_content_hash=coarse.fixed_content_hash,
            moving_object_id=coarse.moving_object_id,
            fixed_object_id=coarse.fixed_object_id,
            frame_id=coarse.frame_id,
            status=BrepRefinementStatus.NOT_REQUIRED,
            kernel_available=coarse.kernel_available,
            kernel=coarse.kernel,
            cadquery_version=coarse.cadquery_version,
            path_length_mm=coarse.path_length_mm,
            coarse_sample_count=coarse.sample_count,
            coarse_evaluated_sample_count=coarse.evaluated_sample_count,
            refinement_candidate_count=0,
            refined_boundary_count=0,
            refinement_evaluated_pose_count=0,
            total_exact_pose_evaluations=coarse.evaluated_sample_count,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            coarse_report=coarse,
            metadata={
                **_base_metadata(),
                "refinement_required": False,
                "reason": "no adjacent coarse samples change clearance/interference predicates",
            },
        )

    available = _cadquery_available() if kernel_available is None else bool(kernel_available)
    if not available:
        return _unknown_report(
            coarse=coarse,
            candidates=candidates,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            reason="optional cadquery-isolated specialist is not available for adaptive transition refinement",
            required_field="cadquery-isolated",
            kernel_available=False,
        )

    moving_start = (
        moving_start_placement
        if isinstance(moving_start_placement, DeclaredGeometryPlacement)
        else DeclaredGeometryPlacement.model_validate(moving_start_placement)
    )
    moving_end = (
        moving_end_placement
        if isinstance(moving_end_placement, DeclaredGeometryPlacement)
        else DeclaredGeometryPlacement.model_validate(moving_end_placement)
    )
    fixed_pose = (
        fixed_placement
        if isinstance(fixed_placement, DeclaredGeometryPlacement)
        else DeclaredGeometryPlacement.model_validate(fixed_placement)
    )

    selected_runner = refinement_runner or _run_isolated_worker
    try:
        payload = dict(
            selected_runner(
                moving_content,
                fixed_content,
                moving_start,
                moving_end,
                fixed_pose,
                candidates,
                contact_distance_tolerance_mm,
                volume_tolerance_mm3,
                refinement_max_depth,
                refinement_fraction_tolerance,
                timeout_s,
            )
        )
    except (OSError, RuntimeError, TimeoutError, ValueError, subprocess.SubprocessError) as exc:
        return _unknown_report(
            coarse=coarse,
            candidates=candidates,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            reason=f"isolated CadQuery transition refinement worker failed: {type(exc).__name__}: {exc}",
            required_field="valid_brep_transition_refinement_result",
            kernel_available=True,
            metadata={"worker_error_type": type(exc).__name__},
        )

    contract_error: tuple[str, str] | None = None
    if payload.get("ok") is not True:
        contract_error = (
            "valid_brep_transition_refinement_result",
            "isolated CadQuery transition refinement worker did not report success",
        )
    elif payload.get("schema_version") != BREP_REFINEMENT_WORKER_SCHEMA:
        contract_error = (
            "compatible_brep_transition_refinement_worker",
            f"CadQuery transition refinement worker schema must be {BREP_REFINEMENT_WORKER_SCHEMA!r}",
        )
    elif payload.get("kernel") != BREP_KERNEL:
        contract_error = (
            "compatible_brep_transition_refinement_worker",
            f"CadQuery transition refinement worker kernel identity must be {BREP_KERNEL!r}",
        )
    elif payload.get("rotation_convention") != BREP_ROTATION_CONVENTION:
        contract_error = (
            "compatible_brep_transition_refinement_worker",
            "CadQuery transition refinement placement convention disagrees with HS placement convention",
        )
    elif (
        payload.get("moving_content_hash") != coarse.moving_content_hash
        or payload.get("fixed_content_hash") != coarse.fixed_content_hash
    ):
        contract_error = (
            "kernel_input_identity",
            "CadQuery transition refinement worker input hashes disagree with canonical STEP identities",
        )
    elif payload.get("moving_shape_valid") is not True or payload.get("fixed_shape_valid") is not True:
        contract_error = ("valid_step_brep", "CadQuery/OCCT reports an invalid imported BREP shape")
    if contract_error is not None:
        return _unknown_report(
            coarse=coarse,
            candidates=candidates,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            reason=contract_error[1],
            required_field=contract_error[0],
            kernel_available=True,
            metadata={
                "worker_schema": payload.get("schema_version"),
                "worker_kernel": payload.get("kernel"),
                "worker_rotation_convention": payload.get("rotation_convention"),
            },
        )

    try:
        moving_solid_count = int(payload["moving_solid_count"])
        fixed_solid_count = int(payload["fixed_solid_count"])
        evaluation_count = int(payload["evaluation_count"])
    except (KeyError, TypeError, ValueError):
        moving_solid_count = 0
        fixed_solid_count = 0
        evaluation_count = -1
    if moving_solid_count <= 0 or fixed_solid_count <= 0:
        return _unknown_report(
            coarse=coarse,
            candidates=candidates,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            reason="adaptive mating-path refinement requires at least one imported solid in each STEP source",
            required_field="solid_step_brep",
            kernel_available=True,
        )
    if evaluation_count < 2 * len(candidates):
        return _unknown_report(
            coarse=coarse,
            candidates=candidates,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            reason="CadQuery transition refinement worker returned an impossible exact evaluation count",
            required_field="complete_brep_transition_refinement",
            kernel_available=True,
        )

    worker_brackets = payload.get("brackets")
    if not isinstance(worker_brackets, list) or len(worker_brackets) != len(candidates):
        return _unknown_report(
            coarse=coarse,
            candidates=candidates,
            refinement_max_depth=refinement_max_depth,
            refinement_fraction_tolerance=refinement_fraction_tolerance,
            reason="CadQuery transition refinement worker returned incomplete transition brackets",
            required_field="complete_brep_transition_refinement",
            kernel_available=True,
        )

    brackets: list[BrepTransitionBracket] = []
    for index, (candidate, row) in enumerate(zip(candidates, worker_brackets)):
        if not isinstance(row, Mapping) or int(row.get("boundary_index", -1)) != index:
            return _unknown_report(
                coarse=coarse,
                candidates=candidates,
                refinement_max_depth=refinement_max_depth,
                refinement_fraction_tolerance=refinement_fraction_tolerance,
                reason="CadQuery transition refinement bracket identities are incomplete or out of order",
                required_field="complete_brep_transition_refinement",
                kernel_available=True,
            )
        try:
            kind = BrepTransitionBoundaryKind(str(row["kind"]))
            lower_fraction = float(row["lower_fraction"])
            upper_fraction = float(row["upper_fraction"])
            lower_state = BrepSweepSampleState(str(row["lower_state"]))
            upper_state = BrepSweepSampleState(str(row["upper_state"]))
            lower_distance = float(row["lower_minimum_distance_mm"])
            upper_distance = float(row["upper_minimum_distance_mm"])
            lower_volume = float(row["lower_intersection_volume_mm3"])
            upper_volume = float(row["upper_intersection_volume_mm3"])
            depth = int(row["refinement_depth"])
            bracket_evaluations = int(row["evaluation_count"])
        except (KeyError, TypeError, ValueError) as exc:
            return _unknown_report(
                coarse=coarse,
                candidates=candidates,
                refinement_max_depth=refinement_max_depth,
                refinement_fraction_tolerance=refinement_fraction_tolerance,
                reason=f"CadQuery transition refinement bracket metrics are invalid: {exc}",
                required_field="valid_brep_transition_refinement_result",
                kernel_available=True,
            )
        if kind != candidate.kind:
            return _unknown_report(
                coarse=coarse,
                candidates=candidates,
                refinement_max_depth=refinement_max_depth,
                refinement_fraction_tolerance=refinement_fraction_tolerance,
                reason="CadQuery transition refinement bracket kind disagrees with the detected coarse boundary",
                required_field="complete_brep_transition_refinement",
                kernel_available=True,
            )
        if not (
            candidate.lower_fraction - 1e-12 <= lower_fraction < upper_fraction <= candidate.upper_fraction + 1e-12
        ):
            return _unknown_report(
                coarse=coarse,
                candidates=candidates,
                refinement_max_depth=refinement_max_depth,
                refinement_fraction_tolerance=refinement_fraction_tolerance,
                reason="CadQuery transition refinement escaped its originating coarse sample interval",
                required_field="bounded_brep_transition_refinement",
                kernel_available=True,
            )
        if _predicate(kind, lower_state) == _predicate(kind, upper_state):
            return _unknown_report(
                coarse=coarse,
                candidates=candidates,
                refinement_max_depth=refinement_max_depth,
                refinement_fraction_tolerance=refinement_fraction_tolerance,
                reason="CadQuery transition refinement no longer brackets the declared predicate change",
                required_field="bounded_brep_transition_refinement",
                kernel_available=True,
            )
        if not all(
            math.isfinite(value) and value >= 0.0
            for value in (lower_distance, upper_distance, lower_volume, upper_volume)
        ):
            return _unknown_report(
                coarse=coarse,
                candidates=candidates,
                refinement_max_depth=refinement_max_depth,
                refinement_fraction_tolerance=refinement_fraction_tolerance,
                reason="CadQuery transition refinement returned non-finite or negative exact metrics",
                required_field="valid_brep_transition_refinement_result",
                kernel_available=True,
            )
        width_fraction = upper_fraction - lower_fraction
        brackets.append(
            BrepTransitionBracket(
                boundary_index=index,
                kind=kind,
                lower_fraction=lower_fraction,
                upper_fraction=upper_fraction,
                lower_path_distance_mm=coarse.path_length_mm * lower_fraction,
                upper_path_distance_mm=coarse.path_length_mm * upper_fraction,
                bracket_width_fraction=width_fraction,
                bracket_width_mm=coarse.path_length_mm * width_fraction,
                lower_state=lower_state,
                upper_state=upper_state,
                lower_minimum_distance_mm=lower_distance,
                upper_minimum_distance_mm=upper_distance,
                lower_intersection_volume_mm3=lower_volume,
                upper_intersection_volume_mm3=upper_volume,
                refinement_depth=depth,
                evaluation_count=bracket_evaluations,
                converged=bool(row.get("converged")),
                max_depth_reached=bool(row.get("max_depth_reached")),
            )
        )

    return BrepMatingPathRefinementReport(
        project_id=coarse.project_id,
        sweep_id=coarse.sweep_id,
        moving_source_id=coarse.moving_source_id,
        fixed_source_id=coarse.fixed_source_id,
        moving_model_id=coarse.moving_model_id,
        fixed_model_id=coarse.fixed_model_id,
        moving_content_hash=coarse.moving_content_hash,
        fixed_content_hash=coarse.fixed_content_hash,
        moving_object_id=coarse.moving_object_id,
        fixed_object_id=coarse.fixed_object_id,
        frame_id=coarse.frame_id,
        status=BrepRefinementStatus.READY,
        kernel_available=True,
        kernel=BREP_KERNEL,
        cadquery_version=(str(payload["cadquery_version"]) if payload.get("cadquery_version") else coarse.cadquery_version),
        path_length_mm=coarse.path_length_mm,
        coarse_sample_count=coarse.sample_count,
        coarse_evaluated_sample_count=coarse.evaluated_sample_count,
        refinement_candidate_count=len(candidates),
        refined_boundary_count=len(brackets),
        refinement_evaluated_pose_count=evaluation_count,
        total_exact_pose_evaluations=coarse.evaluated_sample_count + evaluation_count,
        refinement_max_depth=refinement_max_depth,
        refinement_fraction_tolerance=refinement_fraction_tolerance,
        coarse_report=coarse,
        candidates=candidates,
        brackets=brackets,
        metadata={
            **_base_metadata(),
            "worker_isolated": True,
            "worker_schema": BREP_REFINEMENT_WORKER_SCHEMA,
            "kernel_input_hash_reverified": True,
            "moving_solid_count": moving_solid_count,
            "fixed_solid_count": fixed_solid_count,
            "coarse_worker_schema": BREP_SWEEP_WORKER_SCHEMA,
            "refinement_required": True,
            "brackets_localize_boolean_predicate_change_only": True,
        },
    )


def _run_isolated_worker(
    moving_content: str,
    fixed_content: str,
    moving_start: DeclaredGeometryPlacement,
    moving_end: DeclaredGeometryPlacement,
    fixed_placement: DeclaredGeometryPlacement,
    candidates: Sequence[BrepTransitionCandidate],
    contact_distance_tolerance_mm: float,
    volume_tolerance_mm3: float,
    refinement_max_depth: int,
    refinement_fraction_tolerance: float,
    timeout_s: float,
) -> Mapping[str, Any]:
    if not _WORKER_PATH.is_file():
        raise RuntimeError(f"CadQuery BREP transition refinement worker is missing: {_WORKER_PATH}")

    with tempfile.TemporaryDirectory(prefix="hardware-splicer-brep-transition-refine-") as temp_dir:
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
                    "moving_start_placement": {
                        "translation_mm": list(moving_start.translation_mm),
                        "rotation_deg_xyz": list(moving_start.rotation_deg_xyz),
                    },
                    "moving_end_placement": {
                        "translation_mm": list(moving_end.translation_mm),
                        "rotation_deg_xyz": list(moving_end.rotation_deg_xyz),
                    },
                    "fixed_placement": {
                        "translation_mm": list(fixed_placement.translation_mm),
                        "rotation_deg_xyz": list(fixed_placement.rotation_deg_xyz),
                    },
                    "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
                    "contact_distance_tolerance_mm": contact_distance_tolerance_mm,
                    "intersection_volume_tolerance_mm3": volume_tolerance_mm3,
                    "refinement_max_depth": refinement_max_depth,
                    "refinement_fraction_tolerance": refinement_fraction_tolerance,
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
                f"CadQuery BREP transition refinement worker exceeded {timeout_s:.3f}s; process tree terminated"
                + _diagnostic_suffix(stdout, stderr)
            ) from exc
        if process.returncode != 0:
            raise RuntimeError(
                f"CadQuery BREP transition refinement worker failed with exit code {process.returncode}"
                + _diagnostic_suffix(stdout, stderr)
            )
        try:
            return json.loads((stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "CadQuery BREP transition refinement worker returned no valid structured result"
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
