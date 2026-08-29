from __future__ import annotations

import pytest

from hardware_splicer.mechanical_brep import (
    BrepStatus,
    _sanitized_environment,
    check_step_brep_interference,
)


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(100.0,50.0,10.0));
ENDSEC;
END-ISO-10303-21;
"""


def _placement(placement_id: str, object_id: str, model_id: str, *, frame: str = "assembly") -> dict:
    return {
        "placement_id": placement_id,
        "object_id": object_id,
        "model_id": model_id,
        "target_frame": frame,
        "translation_mm": [0.0, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _check(*, kernel_available: bool, runner, second_frame: str = "assembly"):
    return check_step_brep_interference(
        project_id="brep-test",
        first_content=STEP,
        first_source_id="left.step",
        first_model_id="left",
        first_placement=_placement("place-left", "left-part", "left"),
        second_content=STEP,
        second_source_id="right.step",
        second_model_id="right",
        second_placement=_placement("place-right", "right-part", "right", frame=second_frame),
        kernel_available=kernel_available,
        runner=runner,
    )


def test_missing_optional_kernel_fails_closed_without_aabb_fallback() -> None:
    def should_not_run(*_args):
        raise AssertionError("worker must not run when the optional kernel is unavailable")

    report = _check(kernel_available=False, runner=should_not_run)

    assert report.status == BrepStatus.UNKNOWN
    assert report.kernel_available is False
    assert report.exact_pair_interference_evaluated is False
    assert report.exact_solid_interference is None
    assert report.minimum_distance_mm is None
    assert report.intersection_volume_mm3 is None
    assert report.required_evidence[0]["field"] == "cadquery-isolated"
    assert report.metadata["aabb_fallback_used"] is False
    assert report.metadata["fabrication_authorized"] is False
    assert report.metadata["service_access_verified"] is False


def test_frame_mismatch_fails_closed_before_kernel_execution() -> None:
    def should_not_run(*_args):
        raise AssertionError("worker must not run without an explicit common frame")

    report = _check(kernel_available=True, runner=should_not_run, second_frame="display-frame")

    assert report.status == BrepStatus.UNKNOWN
    assert report.frame_id is None
    assert report.required_evidence[0]["field"] == "relative_transform"
    assert report.exact_pair_interference_evaluated is False


def test_valid_kernel_result_reports_exact_solid_interference_without_authority() -> None:
    def runner(*_args):
        return {
            "ok": True,
            "kernel": "cadquery_occt",
            "cadquery_version": "test",
            "first_shape_valid": True,
            "second_shape_valid": True,
            "first_solid_count": 1,
            "second_solid_count": 2,
            "minimum_distance_mm": 0.0,
            "intersection_volume_mm3": 12.5,
        }

    report = _check(kernel_available=True, runner=runner)

    assert report.status == BrepStatus.INTERFERENCE
    assert report.kernel_available is True
    assert report.kernel == "cadquery_occt"
    assert report.exact_pair_interference_evaluated is True
    assert report.exact_solid_interference is True
    assert report.intersection_volume_mm3 == 12.5
    assert report.minimum_distance_mm == 0.0
    assert report.first_content_hash.startswith("sha256:")
    assert report.second_content_hash.startswith("sha256:")
    assert report.metadata["aabb_fallback_used"] is False
    assert report.metadata["connector_mating_verified"] is False
    assert report.metadata["cable_routing_verified"] is False
    assert report.metadata["service_access_verified"] is False
    assert report.metadata["fabrication_authorized"] is False


def test_valid_kernel_result_can_report_clear_pair_and_exact_shape_distance() -> None:
    def runner(*_args):
        return {
            "ok": True,
            "kernel": "cadquery_occt",
            "first_shape_valid": True,
            "second_shape_valid": True,
            "first_solid_count": 1,
            "second_solid_count": 1,
            "minimum_distance_mm": 5.0,
            "intersection_volume_mm3": 0.0,
        }

    report = _check(kernel_available=True, runner=runner)

    assert report.status == BrepStatus.CLEAR
    assert report.exact_pair_interference_evaluated is True
    assert report.exact_solid_interference is False
    assert report.minimum_distance_mm == 5.0
    assert report.intersection_volume_mm3 == 0.0
    assert report.metadata["touching_or_intersecting_distance"] is False
    assert report.metadata["release_authorized"] is False


def test_invalid_imported_brep_remains_unknown_even_if_worker_returns_numbers() -> None:
    def runner(*_args):
        return {
            "ok": True,
            "kernel": "cadquery_occt",
            "first_shape_valid": False,
            "second_shape_valid": True,
            "minimum_distance_mm": 0.0,
            "intersection_volume_mm3": 50.0,
        }

    report = _check(kernel_available=True, runner=runner)

    assert report.status == BrepStatus.UNKNOWN
    assert report.exact_pair_interference_evaluated is False
    assert report.exact_solid_interference is None
    assert report.required_evidence[0]["field"] == "valid_step_brep"
    assert report.metadata["first_shape_valid"] is False


def test_worker_environment_does_not_inherit_provider_secrets() -> None:
    environment = _sanitized_environment(
        {
            "PATH": "/usr/bin",
            "HOME": "/tmp/home",
            "OPENAI_API_KEY": "secret-openai",
            "ANTHROPIC_API_KEY": "secret-anthropic",
            "AWS_SECRET_ACCESS_KEY": "secret-aws",
        }
    )

    assert environment["PATH"] == "/usr/bin"
    assert environment["HOME"] == "/tmp/home"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["HARDWARE_SPLICER_CAD_WORKER"] == "1"
    assert "OPENAI_API_KEY" not in environment
    assert "ANTHROPIC_API_KEY" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment


def test_real_cadquery_worker_when_optional_specialist_is_installed(tmp_path) -> None:
    cq = pytest.importorskip("cadquery", reason="optional cadquery-isolated specialist is not installed")
    step_path = tmp_path / "box.step"
    cq.exporters.export(cq.Workplane("XY").box(10.0, 10.0, 10.0), str(step_path))
    step_content = step_path.read_text(encoding="utf-8")

    overlapping = check_step_brep_interference(
        project_id="brep-real",
        first_content=step_content,
        first_source_id="left-box.step",
        first_model_id="left-box",
        first_placement=_placement("place-left-box", "left-box-object", "left-box"),
        second_content=step_content,
        second_source_id="right-box.step",
        second_model_id="right-box",
        second_placement={
            **_placement("place-right-box", "right-box-object", "right-box"),
            "translation_mm": [5.0, 0.0, 0.0],
        },
        kernel_available=True,
    )

    assert overlapping.status == BrepStatus.INTERFERENCE
    assert overlapping.exact_pair_interference_evaluated is True
    assert overlapping.exact_solid_interference is True
    assert overlapping.minimum_distance_mm == pytest.approx(0.0, abs=1e-9)
    assert overlapping.intersection_volume_mm3 == pytest.approx(500.0, rel=1e-6, abs=1e-6)
    assert overlapping.metadata["worker_isolated"] is True

    separated = check_step_brep_interference(
        project_id="brep-real",
        first_content=step_content,
        first_source_id="left-box.step",
        first_model_id="left-box",
        first_placement=_placement("place-left-box", "left-box-object", "left-box"),
        second_content=step_content,
        second_source_id="right-box.step",
        second_model_id="right-box",
        second_placement={
            **_placement("place-right-box", "right-box-object", "right-box"),
            "translation_mm": [20.0, 0.0, 0.0],
        },
        kernel_available=True,
    )

    assert separated.status == BrepStatus.CLEAR
    assert separated.exact_pair_interference_evaluated is True
    assert separated.exact_solid_interference is False
    assert separated.minimum_distance_mm == pytest.approx(10.0, rel=1e-6, abs=1e-6)
    assert separated.intersection_volume_mm3 == pytest.approx(0.0, abs=1e-9)
