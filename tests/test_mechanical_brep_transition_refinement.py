from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.mechanical_brep_sweep import (
    BREP_ROTATION_CONVENTION,
    BREP_SWEEP_WORKER_SCHEMA,
)
from hardware_splicer.mechanical_brep_transition_refinement import (
    BREP_REFINEMENT_WORKER_SCHEMA,
    BrepRefinementStatus,
    BrepTransitionBoundaryKind,
    evaluate_step_brep_mating_path_refinement,
)


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.,0.,0.));
#2=CARTESIAN_POINT('',(10.,10.,10.));
ENDSEC;
END-ISO-10303-21;
"""


def _hash(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _placement(placement_id: str, object_id: str, model_id: str, x_mm: float) -> dict:
    return {
        "placement_id": placement_id,
        "object_id": object_id,
        "model_id": model_id,
        "target_frame": "assembly",
        "translation_mm": [x_mm, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _coarse_runner(moving_content, fixed_content, fixed_placement, moving_placements, timeout_s):
    assert timeout_s > 0
    assert [row.translation_mm[0] for row in moving_placements] == [30.0, 25.0, 20.0, 15.0, 10.0, 5.0]
    return {
        "schema_version": BREP_SWEEP_WORKER_SCHEMA,
        "ok": True,
        "kernel": "cadquery_occt",
        "cadquery_version": "2.8.0",
        "moving_content_hash": _hash(moving_content),
        "fixed_content_hash": _hash(fixed_content),
        "moving_shape_valid": True,
        "fixed_shape_valid": True,
        "moving_solid_count": 1,
        "fixed_solid_count": 1,
        "rotation_convention": BREP_ROTATION_CONVENTION,
        "samples": [
            {"sample_index": 0, "minimum_distance_mm": 20.0, "intersection_volume_mm3": 0.0},
            {"sample_index": 1, "minimum_distance_mm": 15.0, "intersection_volume_mm3": 0.0},
            {"sample_index": 2, "minimum_distance_mm": 10.0, "intersection_volume_mm3": 0.0},
            {"sample_index": 3, "minimum_distance_mm": 5.0, "intersection_volume_mm3": 0.0},
            {"sample_index": 4, "minimum_distance_mm": 0.0, "intersection_volume_mm3": 0.0},
            {"sample_index": 5, "minimum_distance_mm": 0.0, "intersection_volume_mm3": 500.0},
        ],
    }


def _refinement_runner(
    moving_content,
    fixed_content,
    moving_start,
    moving_end,
    fixed_placement,
    candidates,
    contact_distance_tolerance_mm,
    volume_tolerance_mm3,
    refinement_max_depth,
    refinement_fraction_tolerance,
    timeout_s,
):
    assert moving_start.translation_mm[0] == 30.0
    assert moving_end.translation_mm[0] == 5.0
    assert fixed_placement.translation_mm[0] == 0.0
    assert contact_distance_tolerance_mm >= 0
    assert volume_tolerance_mm3 >= 0
    assert refinement_max_depth == 8
    assert refinement_fraction_tolerance == pytest.approx(0.001)
    assert timeout_s > 0
    assert [candidate.kind for candidate in candidates] == [
        BrepTransitionBoundaryKind.CLEARANCE,
        BrepTransitionBoundaryKind.INTERFERENCE,
    ]
    assert [(candidate.lower_fraction, candidate.upper_fraction) for candidate in candidates] == [
        pytest.approx((0.6, 0.8)),
        pytest.approx((0.8, 1.0)),
    ]
    return {
        "schema_version": BREP_REFINEMENT_WORKER_SCHEMA,
        "ok": True,
        "kernel": "cadquery_occt",
        "cadquery_version": "2.8.0",
        "moving_content_hash": _hash(moving_content),
        "fixed_content_hash": _hash(fixed_content),
        "moving_shape_valid": True,
        "fixed_shape_valid": True,
        "moving_solid_count": 1,
        "fixed_solid_count": 1,
        "rotation_convention": BREP_ROTATION_CONVENTION,
        "evaluation_count": 20,
        "brackets": [
            {
                "boundary_index": 0,
                "kind": "clearance_boundary",
                "lower_fraction": 0.79921875,
                "upper_fraction": 0.8,
                "lower_state": "clear",
                "upper_state": "contact",
                "lower_minimum_distance_mm": 0.01953125,
                "upper_minimum_distance_mm": 0.0,
                "lower_intersection_volume_mm3": 0.0,
                "upper_intersection_volume_mm3": 0.0,
                "refinement_depth": 8,
                "evaluation_count": 10,
                "converged": True,
                "max_depth_reached": False,
            },
            {
                "boundary_index": 1,
                "kind": "interference_boundary",
                "lower_fraction": 0.8,
                "upper_fraction": 0.80078125,
                "lower_state": "contact",
                "upper_state": "interference",
                "lower_minimum_distance_mm": 0.0,
                "upper_minimum_distance_mm": 0.0,
                "lower_intersection_volume_mm3": 0.0,
                "upper_intersection_volume_mm3": 1.953125,
                "refinement_depth": 8,
                "evaluation_count": 10,
                "converged": True,
                "max_depth_reached": False,
            },
        ],
    }


def _evaluate(**overrides):
    values = {
        "project_id": "deck-001",
        "sweep_id": "refine-display",
        "moving_content": STEP,
        "moving_source_id": "display.step",
        "moving_model_id": "display-model",
        "moving_start_placement": _placement("display-start", "display-object", "display-model", 30.0),
        "moving_end_placement": _placement("display-end", "display-object", "display-model", 5.0),
        "fixed_content": STEP,
        "fixed_source_id": "board.step",
        "fixed_model_id": "board-model",
        "fixed_placement": _placement("board-fixed", "fixed-object", "board-model", 0.0),
        "sample_count": 6,
        "engagement_start_fraction": 0.8,
        "contact_distance_tolerance_mm": 0.001,
        "refinement_max_depth": 8,
        "refinement_fraction_tolerance": 0.001,
        "kernel_available": True,
        "coarse_runner": _coarse_runner,
        "refinement_runner": _refinement_runner,
    }
    values.update(overrides)
    return evaluate_step_brep_mating_path_refinement(**values)


def test_refinement_localizes_clearance_and_interference_predicate_changes() -> None:
    report = _evaluate()

    assert report.status == BrepRefinementStatus.READY
    assert report.refinement_candidate_count == 2
    assert report.refined_boundary_count == 2
    assert report.refinement_evaluated_pose_count == 20
    assert report.total_exact_pose_evaluations == 26
    assert [row.kind for row in report.brackets] == [
        BrepTransitionBoundaryKind.CLEARANCE,
        BrepTransitionBoundaryKind.INTERFERENCE,
    ]
    assert report.brackets[0].lower_state.value == "clear"
    assert report.brackets[0].upper_state.value == "contact"
    assert report.brackets[0].bracket_width_fraction == pytest.approx(0.00078125)
    assert report.brackets[0].bracket_width_mm == pytest.approx(0.01953125)
    assert report.brackets[1].lower_state.value == "contact"
    assert report.brackets[1].upper_state.value == "interference"
    assert report.metadata["transition_brackets_only"] is True
    assert report.metadata["unique_transition_pose_verified"] is False
    assert report.metadata["monotonicity_inside_bracket_verified"] is False
    assert report.metadata["continuous_path_verified"] is False
    assert report.metadata["continuous_collision_free_verified"] is False
    assert report.metadata["connector_mating_verified"] is False
    assert report.metadata["whole_assembly_collision"] is False
    assert report.metadata["fabrication_authorized"] is False


def test_direct_clear_to_interference_coarse_jump_creates_two_predicate_candidates() -> None:
    def coarse_direct(moving_content, fixed_content, fixed_placement, moving_placements, timeout_s):
        assert len(moving_placements) == 2
        return {
            "schema_version": BREP_SWEEP_WORKER_SCHEMA,
            "ok": True,
            "kernel": "cadquery_occt",
            "cadquery_version": "2.8.0",
            "moving_content_hash": _hash(moving_content),
            "fixed_content_hash": _hash(fixed_content),
            "moving_shape_valid": True,
            "fixed_shape_valid": True,
            "moving_solid_count": 1,
            "fixed_solid_count": 1,
            "rotation_convention": BREP_ROTATION_CONVENTION,
            "samples": [
                {"sample_index": 0, "minimum_distance_mm": 20.0, "intersection_volume_mm3": 0.0},
                {"sample_index": 1, "minimum_distance_mm": 0.0, "intersection_volume_mm3": 500.0},
            ],
        }

    seen = []

    def refinement_direct(*args):
        candidates = args[5]
        seen.extend((row.kind.value, row.lower_fraction, row.upper_fraction) for row in candidates)
        return {
            "schema_version": BREP_REFINEMENT_WORKER_SCHEMA,
            "ok": True,
            "kernel": "cadquery_occt",
            "cadquery_version": "2.8.0",
            "moving_content_hash": _hash(args[0]),
            "fixed_content_hash": _hash(args[1]),
            "moving_shape_valid": True,
            "fixed_shape_valid": True,
            "moving_solid_count": 1,
            "fixed_solid_count": 1,
            "rotation_convention": BREP_ROTATION_CONVENTION,
            "evaluation_count": 8,
            "brackets": [
                {
                    "boundary_index": 0,
                    "kind": "clearance_boundary",
                    "lower_fraction": 0.49,
                    "upper_fraction": 0.5,
                    "lower_state": "clear",
                    "upper_state": "contact",
                    "lower_minimum_distance_mm": 0.1,
                    "upper_minimum_distance_mm": 0.0,
                    "lower_intersection_volume_mm3": 0.0,
                    "upper_intersection_volume_mm3": 0.0,
                    "refinement_depth": 2,
                    "evaluation_count": 4,
                    "converged": True,
                    "max_depth_reached": False,
                },
                {
                    "boundary_index": 1,
                    "kind": "interference_boundary",
                    "lower_fraction": 0.5,
                    "upper_fraction": 0.51,
                    "lower_state": "contact",
                    "upper_state": "interference",
                    "lower_minimum_distance_mm": 0.0,
                    "upper_minimum_distance_mm": 0.0,
                    "lower_intersection_volume_mm3": 0.0,
                    "upper_intersection_volume_mm3": 0.1,
                    "refinement_depth": 2,
                    "evaluation_count": 4,
                    "converged": True,
                    "max_depth_reached": False,
                },
            ],
        }

    report = _evaluate(
        sample_count=2,
        coarse_runner=coarse_direct,
        refinement_runner=refinement_direct,
        refinement_fraction_tolerance=0.02,
    )
    assert report.status == BrepRefinementStatus.READY
    assert seen == [
        ("clearance_boundary", 0.0, 1.0),
        ("interference_boundary", 0.0, 1.0),
    ]


def test_refinement_fails_closed_on_worker_identity_mismatch() -> None:
    def mismatched(*args):
        payload = dict(_refinement_runner(*args))
        payload["moving_content_hash"] = f"sha256:{'f' * 64}"
        return payload

    report = _evaluate(refinement_runner=mismatched)
    assert report.status == BrepRefinementStatus.UNKNOWN
    assert report.refined_boundary_count == 0
    assert report.required_evidence[0]["field"] == "kernel_input_identity"
    assert report.metadata["continuous_path_verified"] is False


def test_real_cadquery_refinement_brackets_touch_and_interference_when_specialist_is_installed(tmp_path) -> None:
    cq = pytest.importorskip("cadquery", reason="optional cadquery-isolated specialist is not installed")
    step_path = tmp_path / "refine-box.step"
    cq.exporters.export(cq.Workplane("XY").box(10.0, 10.0, 10.0), str(step_path))
    content = step_path.read_text(encoding="utf-8")

    report = evaluate_step_brep_mating_path_refinement(
        project_id="brep-refine-live",
        sweep_id="approach-box",
        moving_content=content,
        moving_source_id="moving.step",
        moving_model_id="moving-model",
        moving_start_placement=_placement("moving-start", "moving-object", "moving-model", 30.0),
        moving_end_placement=_placement("moving-end", "moving-object", "moving-model", 5.0),
        fixed_content=content,
        fixed_source_id="fixed.step",
        fixed_model_id="fixed-model",
        fixed_placement=_placement("fixed", "fixed-object", "fixed-model", 0.0),
        sample_count=6,
        engagement_start_fraction=0.8,
        contact_distance_tolerance_mm=0.001,
        refinement_max_depth=10,
        refinement_fraction_tolerance=0.00025,
    )

    assert report.status == BrepRefinementStatus.READY
    assert report.refined_boundary_count == 2
    clearance, interference = report.brackets
    assert clearance.kind == BrepTransitionBoundaryKind.CLEARANCE
    assert clearance.lower_fraction < 0.8 <= clearance.upper_fraction + 1e-12
    assert clearance.bracket_width_fraction <= 0.00025 + 1e-12
    assert clearance.lower_state.value == "clear"
    assert clearance.upper_state.value == "contact"
    assert interference.kind == BrepTransitionBoundaryKind.INTERFERENCE
    assert interference.lower_fraction >= 0.8 - 1e-12
    assert interference.bracket_width_fraction <= 0.00025 + 1e-12
    assert interference.lower_state.value in {"contact", "clear"}
    assert interference.upper_state.value == "interference"
    assert report.metadata["continuous_path_verified"] is False
