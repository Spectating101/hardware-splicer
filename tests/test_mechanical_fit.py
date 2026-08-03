from __future__ import annotations

import pytest

from hardware_splicer.mechanical_fit import (
    ClearanceBox,
    FastenerStack,
    build_mechanical_fit_report,
)
from hardware_splicer.step_geometry import build_mechanical_geometry_report, parse_step_model


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


def _geometry(*, right_normal=None):
    right_normal = right_normal or [0.0, 0.0, -1.0]
    models = [
        parse_step_model(STEP, source_id="left.step", model_id="left"),
        parse_step_model(STEP, source_id="right.step", model_id="right"),
    ]
    mounts = [
        {
            "interface_id": "left-mount",
            "part_id": "left-part",
            "cad_model_id": "left",
            "mount_type": "flat_flange",
            "mates_with": "right-mount",
            "datum_frame": "left-frame",
            "origin_mm": [10.0, 10.0, 5.0],
            "normal": [0.0, 0.0, 1.0],
            "hole_pattern": {
                "count": 4,
                "spacing_x_mm": 40.0,
                "spacing_y_mm": 20.0,
                "hole_diameter_mm": 3.2,
            },
            "fastener_spec": "M3",
        },
        {
            "interface_id": "right-mount",
            "part_id": "right-part",
            "cad_model_id": "right",
            "mount_type": "flat_flange",
            "mates_with": "left-mount",
            "datum_frame": "right-frame",
            "origin_mm": [10.0, 10.0, 5.0],
            "normal": right_normal,
            "hole_pattern": {
                "count": 4,
                "spacing_x_mm": 40.0,
                "spacing_y_mm": 20.0,
                "hole_diameter_mm": 3.2,
            },
            "fastener_spec": "M3",
        },
    ]
    return build_mechanical_geometry_report(
        project_id="fit-project",
        models=models,
        mounts=mounts,
    )


def test_opposed_normals_clearance_and_fastener_stack_pass() -> None:
    report = build_mechanical_fit_report(
        _geometry(),
        clearance_boxes=[
            {
                "object_id": "moving-arm",
                "frame_id": "assembly",
                "minimum_mm": [0.0, 0.0, 0.0],
                "maximum_mm": [10.0, 10.0, 10.0],
                "state": "deployed",
            },
            {
                "object_id": "enclosure",
                "frame_id": "assembly",
                "minimum_mm": [15.0, 0.0, 0.0],
                "maximum_mm": [30.0, 20.0, 20.0],
                "state": "deployed",
            },
        ],
        clearance_requirements=[
            {
                "requirement_id": "arm-enclosure",
                "first_object_id": "moving-arm",
                "second_object_id": "enclosure",
                "minimum_clearance_mm": 3.0,
                "applicable_states": ["deployed"],
            }
        ],
        fastener_stacks=[
            {
                "stack_id": "mount-m3",
                "fastener_spec": "M3x12",
                "fastener_length_mm": 12.0,
                "clamped_thicknesses_mm": [3.0, 4.0],
                "non_thread_allowance_mm": 1.0,
                "required_thread_engagement_mm": 3.0,
                "maximum_thread_protrusion_mm": 2.0,
                "target_ids": ["left-mount", "right-mount"],
            }
        ],
    )

    assert report.status == "candidate"
    assert report.blocking_checks == []
    orientation = next(row for row in report.checks if row.category == "mount_orientation")
    clearance = next(row for row in report.checks if row.category == "aabb_clearance")
    fastener = next(row for row in report.checks if row.category == "fastener_stack")
    assert orientation.status.value == "pass"
    assert orientation.metadata["anti_parallel_deviation_deg"] == 0.0
    assert clearance.status.value == "pass"
    assert clearance.metadata["clearance_mm"] == 5.0
    assert fastener.status.value == "pass"
    assert fastener.metadata["calculated_thread_engagement_mm"] == 4.0
    assert report.metadata["full_brep_collision"] is False
    assert report.metadata["thread_strength_verified"] is False
    assert report.metadata["fabrication_authorized"] is False


def test_parallel_mating_normals_fail_orientation() -> None:
    report = build_mechanical_fit_report(
        _geometry(right_normal=[0.0, 0.0, 1.0]),
    )

    orientation = next(row for row in report.checks if row.category == "mount_orientation")
    assert orientation.status.value == "fail"
    assert orientation.metadata["anti_parallel_deviation_deg"] == 180.0
    assert report.status == "blocked"


def test_overlapping_aabbs_report_negative_clearance() -> None:
    report = build_mechanical_fit_report(
        _geometry(),
        clearance_boxes=[
            {
                "object_id": "moving-arm",
                "frame_id": "assembly",
                "minimum_mm": [0.0, 0.0, 0.0],
                "maximum_mm": [10.0, 10.0, 10.0],
            },
            {
                "object_id": "enclosure",
                "frame_id": "assembly",
                "minimum_mm": [8.0, 2.0, 2.0],
                "maximum_mm": [20.0, 20.0, 20.0],
            },
        ],
        clearance_requirements=[
            {
                "requirement_id": "arm-enclosure",
                "first_object_id": "moving-arm",
                "second_object_id": "enclosure",
                "minimum_clearance_mm": 1.0,
            }
        ],
    )

    clearance = next(row for row in report.checks if row.category == "aabb_clearance")
    assert clearance.status.value == "fail"
    assert clearance.metadata["overlap"] is True
    assert clearance.metadata["clearance_mm"] == -2.0
    assert report.status == "blocked"


def test_different_frames_or_missing_operating_state_remain_unknown() -> None:
    different_frames = build_mechanical_fit_report(
        _geometry(),
        clearance_boxes=[
            {
                "object_id": "moving-arm",
                "frame_id": "arm",
                "minimum_mm": [0.0, 0.0, 0.0],
                "maximum_mm": [10.0, 10.0, 10.0],
            },
            {
                "object_id": "enclosure",
                "frame_id": "base",
                "minimum_mm": [15.0, 0.0, 0.0],
                "maximum_mm": [30.0, 20.0, 20.0],
            },
        ],
        clearance_requirements=[
            {
                "requirement_id": "different-frames",
                "first_object_id": "moving-arm",
                "second_object_id": "enclosure",
            }
        ],
    )
    wrong_state = build_mechanical_fit_report(
        _geometry(),
        clearance_boxes=[
            {
                "object_id": "moving-arm",
                "frame_id": "assembly",
                "minimum_mm": [0.0, 0.0, 0.0],
                "maximum_mm": [10.0, 10.0, 10.0],
                "state": "stowed",
            },
            {
                "object_id": "enclosure",
                "frame_id": "assembly",
                "minimum_mm": [15.0, 0.0, 0.0],
                "maximum_mm": [30.0, 20.0, 20.0],
                "state": "deployed",
            },
        ],
        clearance_requirements=[
            {
                "requirement_id": "state-envelope",
                "first_object_id": "moving-arm",
                "second_object_id": "enclosure",
                "applicable_states": ["deployed"],
            }
        ],
    )

    frame_check = next(row for row in different_frames.checks if row.category == "aabb_clearance")
    state_check = next(row for row in wrong_state.checks if row.category == "aabb_clearance")
    assert frame_check.status.value == "unknown"
    assert frame_check.unresolved_fields == ["relative_transform"]
    assert state_check.status.value == "unknown"
    assert state_check.unresolved_fields == ["applicable_state_envelope"]


def test_short_fastener_and_excessive_protrusion_fail() -> None:
    short = build_mechanical_fit_report(
        _geometry(),
        fastener_stacks=[
            {
                "stack_id": "short",
                "fastener_spec": "M3x8",
                "fastener_length_mm": 8.0,
                "clamped_thicknesses_mm": [3.0, 3.0],
                "non_thread_allowance_mm": 1.0,
                "required_thread_engagement_mm": 3.0,
            }
        ],
    )
    long = build_mechanical_fit_report(
        _geometry(),
        fastener_stacks=[
            {
                "stack_id": "long",
                "fastener_spec": "M3x20",
                "fastener_length_mm": 20.0,
                "clamped_thicknesses_mm": [3.0, 3.0],
                "required_thread_engagement_mm": 3.0,
                "maximum_thread_protrusion_mm": 2.0,
            }
        ],
    )

    short_check = next(row for row in short.checks if row.category == "fastener_stack")
    long_check = next(row for row in long.checks if row.category == "fastener_stack")
    assert short_check.status.value == "fail"
    assert "thread engagement" in short_check.message
    assert long_check.status.value == "fail"
    assert "thread protrusion" in long_check.message


def test_invalid_clearance_box_and_fastener_thickness_are_rejected() -> None:
    with pytest.raises(ValueError, match="minimum must not exceed maximum"):
        ClearanceBox(
            object_id="invalid",
            frame_id="frame",
            minimum_mm=[10.0, 0.0, 0.0],
            maximum_mm=[0.0, 1.0, 1.0],
        )
    with pytest.raises(ValueError, match="thicknesses must be positive"):
        FastenerStack(
            stack_id="invalid",
            fastener_spec="M3",
            fastener_length_mm=10.0,
            clamped_thicknesses_mm=[3.0, 0.0],
            required_thread_engagement_mm=2.0,
        )
