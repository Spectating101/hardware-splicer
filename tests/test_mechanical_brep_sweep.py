from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.mechanical_brep_sweep import (
    BREP_ROTATION_CONVENTION,
    BREP_SWEEP_WORKER_SCHEMA,
    BrepSweepSampleState,
    evaluate_step_brep_mating_path,
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


def _runner(moving_content, fixed_content, fixed_placement, moving_placements, timeout_s):
    assert timeout_s > 0
    assert fixed_placement.object_id == "fixed-object"
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


def _evaluate(**overrides):
    values = {
        "project_id": "deck-001",
        "sweep_id": "sweep-display",
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
        "kernel_available": True,
        "runner": _runner,
    }
    values.update(overrides)
    return evaluate_step_brep_mating_path(**values)


def test_sampled_sweep_distinguishes_approach_contact_engagement_and_interference() -> None:
    report = _evaluate()

    assert report.status.value == "ready"
    assert report.kernel_available is True
    assert report.evaluated_sample_count == 6
    assert report.path_length_mm == pytest.approx(25.0)
    assert [sample.state for sample in report.samples] == [
        BrepSweepSampleState.CLEAR,
        BrepSweepSampleState.CLEAR,
        BrepSweepSampleState.CLEAR,
        BrepSweepSampleState.CLEAR,
        BrepSweepSampleState.CONTACT,
        BrepSweepSampleState.INTERFERENCE,
    ]
    assert report.first_contact_sample_index == 4
    assert report.first_contact_fraction == pytest.approx(0.8)
    assert report.first_contact_path_distance_mm == pytest.approx(20.0)
    assert report.first_interference_sample_index == 5
    assert report.first_interference_path_distance_mm == pytest.approx(25.0)
    assert report.approach_interference_free is True
    assert report.engagement_region_evaluated is True
    assert report.engagement_region_interference_free is False
    assert report.sampled_path_interference_free is False
    assert report.metadata["continuous_path_verified"] is False
    assert report.metadata["continuous_collision_free_verified"] is False
    assert report.metadata["connector_mating_verified"] is False
    assert report.metadata["whole_assembly_collision"] is False
    assert report.metadata["fabrication_authorized"] is False


def test_sampled_sweep_fails_closed_on_worker_source_identity_mismatch() -> None:
    def mismatched(*args):
        payload = dict(_runner(*args))
        payload["moving_content_hash"] = f"sha256:{'f' * 64}"
        return payload

    report = _evaluate(runner=mismatched)
    assert report.status.value == "unknown"
    assert report.evaluated_sample_count == 0
    assert report.sampled_path_interference_free is None
    assert report.required_evidence[0]["field"] == "kernel_input_identity"
    assert report.metadata["continuous_path_verified"] is False


def test_sampled_sweep_rejects_rotating_or_zero_length_path() -> None:
    rotating_end = _placement("display-end", "display-object", "display-model", 5.0)
    rotating_end["rotation_deg_xyz"] = [0.0, 0.0, 5.0]
    with pytest.raises(ValueError, match="translation-only"):
        _evaluate(moving_end_placement=rotating_end)

    with pytest.raises(ValueError, match="non-zero"):
        _evaluate(
            moving_end_placement=_placement("display-end", "display-object", "display-model", 30.0)
        )


def test_real_cadquery_sweep_finds_touch_then_overlap_when_specialist_is_installed(tmp_path) -> None:
    cq = pytest.importorskip("cadquery", reason="optional cadquery-isolated specialist is not installed")
    step_path = tmp_path / "sweep-box.step"
    cq.exporters.export(cq.Workplane("XY").box(10.0, 10.0, 10.0), str(step_path))
    content = step_path.read_text(encoding="utf-8")

    report = evaluate_step_brep_mating_path(
        project_id="brep-sweep-live",
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
    )

    assert report.status.value == "ready"
    assert report.kernel == "cadquery_occt"
    assert report.first_contact_sample_index == 4
    assert report.samples[4].minimum_distance_mm == pytest.approx(0.0, abs=1e-6)
    assert report.samples[4].intersection_volume_mm3 == pytest.approx(0.0, abs=1e-6)
    assert report.samples[5].state == BrepSweepSampleState.INTERFERENCE
    assert report.samples[5].intersection_volume_mm3 == pytest.approx(500.0, rel=1e-6, abs=1e-6)
    assert report.sampled_path_interference_free is False
    assert report.metadata["continuous_path_verified"] is False
