from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.mechanical_brep_adapter import (
    BREP_ADAPTER_WORKER_SCHEMA,
    BrepAdapterStatus,
    synthesize_brep_bridge_adapter,
)


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(-5.0,-5.0,-5.0));
#4=CARTESIAN_POINT('',(5.0,5.0,5.0));
ENDSEC;
END-ISO-10303-21;
"""


def _hash(content: str = STEP) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _placement(*, side: str, x: float) -> dict:
    return {
        "placement_id": f"place-{side}",
        "object_id": f"cmp-{side}",
        "model_id": side,
        "target_frame": "assembly",
        "translation_mm": [x, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _anchor(*, side: str, point: list[float], normal: list[float], geom: str = "PLANE") -> dict:
    return {
        "anchor_id": f"anchor-{side}",
        "interface_id": f"if-{side}",
        "object_id": f"cmp-{side}",
        "source_id": f"{side}.step",
        "model_id": side,
        "content_hash": _hash(),
        "placement_id": f"place-{side}",
        "frame_id": "assembly",
        "anchor_point_mm": point,
        "outward_normal": normal,
        "face_index": 1,
        "face_geom_type": geom,
        "authority": "declared",
        "status": "ready",
        "kernel_surface_snap": True,
        "connector_mating_verified": False,
        "physical_measurement": False,
        "fabrication_authorized": False,
    }


def _generated_step() -> str:
    return "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=PRODUCT('adapter','Adapter','',());\nENDSEC;\nEND-ISO-10303-21;\n"


def _worker_payload(*, geometric_pass: bool = True) -> dict:
    step = _generated_step()
    return {
        "ok": True,
        "worker_schema": BREP_ADAPTER_WORKER_SCHEMA,
        "kernel": "cadquery_occt",
        "cadquery_version": "test",
        "rotation_convention": "Rz*Ry*Rx; canonical STEP XYZ",
        "first_input_content_hash": _hash(),
        "second_input_content_hash": _hash(),
        "parent_placements_applied": True,
        "parent_shapes_valid": True,
        "adapter_family": "bridge_block_v0",
        "adapter_shape_valid": True,
        "adapter_solid_count": 1,
        "adapter_axis": [1.0, 0.0, 0.0],
        "adapter_midpoint_mm": [10.0, 0.0, 0.0],
        "adapter_length_mm": 10.0,
        "adapter_width_mm": 4.0,
        "adapter_thickness_mm": 4.0,
        "adapter_volume_mm3": 160.0,
        "first_axis_alignment_error_deg": 0.0,
        "second_axis_alignment_error_deg": 0.0,
        "normal_opposition_error_deg": 0.0,
        "first_endpoint_error_mm": 0.0,
        "second_endpoint_error_mm": 0.0,
        "first_parent_minimum_distance_mm": 0.0,
        "second_parent_minimum_distance_mm": 0.0,
        "first_parent_intersection_volume_mm3": 0.0 if geometric_pass else 2.0,
        "second_parent_intersection_volume_mm3": 0.0,
        "first_parent_contact_passed": True,
        "second_parent_contact_passed": True,
        "first_parent_penetration_passed": geometric_pass,
        "second_parent_penetration_passed": True,
        "geometric_candidate_passed": geometric_pass,
        "generated_step_content": step,
        "generated_content_hash": f"sha256:{hashlib.sha256(step.encode('utf-8')).hexdigest()}",
        "generated_step_bytes": len(step.encode("utf-8")),
        "bbox_minimum_mm": [5.0, -2.0, -2.0],
        "bbox_maximum_mm": [15.0, 2.0, 2.0],
        "vertex_count": 8,
        "triangle_count": 12,
        "vertices_mm": [
            [5.0, -2.0, -2.0], [5.0, 2.0, -2.0], [5.0, 2.0, 2.0], [5.0, -2.0, 2.0],
            [15.0, -2.0, -2.0], [15.0, 2.0, -2.0], [15.0, 2.0, 2.0], [15.0, -2.0, 2.0],
        ],
        "triangles": [
            [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
            [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
            [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0],
        ],
        "tessellation_tolerance_mm": 0.5,
        "tessellation_angular_tolerance_rad": 0.1,
    }


def _call(**overrides):
    values = {
        "project_id": "adapter-test",
        "adapter_id": "adapter-a-b",
        "first_content": STEP,
        "first_source_id": "left.step",
        "first_model_id": "left",
        "first_expected_content_hash": _hash(),
        "first_placement": _placement(side="left", x=0.0),
        "first_anchor": _anchor(side="left", point=[5.0, 0.0, 0.0], normal=[1.0, 0.0, 0.0]),
        "second_content": STEP,
        "second_source_id": "right.step",
        "second_model_id": "right",
        "second_expected_content_hash": _hash(),
        "second_placement": _placement(side="right", x=20.0),
        "second_anchor": _anchor(side="right", point=[15.0, 0.0, 0.0], normal=[-1.0, 0.0, 0.0]),
        "parameters": {"width_mm": 4.0, "thickness_mm": 4.0},
        "kernel_available": True,
        "runner": lambda *_args: _worker_payload(),
    }
    values.update(overrides)
    return synthesize_brep_bridge_adapter(**values)


def test_bridge_adapter_requires_planar_exact_anchor_faces() -> None:
    report = _call(
        first_anchor=_anchor(
            side="left",
            point=[5.0, 0.0, 0.0],
            normal=[1.0, 0.0, 0.0],
            geom="CYLINDER",
        ),
        runner=lambda *_args: (_ for _ in ()).throw(AssertionError("worker must not run")),
    )

    assert report.status == BrepAdapterStatus.UNKNOWN
    assert report.required_evidence[0]["field"] == "opposed_planar_anchor_faces"
    assert report.metadata["fabrication_authorized"] is False


def test_bridge_adapter_rejects_stale_anchor_pose_before_worker() -> None:
    stale = _anchor(side="left", point=[5.0, 0.0, 0.0], normal=[1.0, 0.0, 0.0])
    stale["placement_id"] = "stale-placement"

    with pytest.raises(ValueError, match="pose identity"):
        _call(
            first_anchor=stale,
            runner=lambda *_args: (_ for _ in ()).throw(AssertionError("worker must not run")),
        )


def test_bridge_adapter_refuses_misaligned_planar_family_without_kernel_execution() -> None:
    report = _call(
        first_anchor=_anchor(side="left", point=[5.0, 0.0, 0.0], normal=[0.0, 1.0, 0.0]),
        runner=lambda *_args: (_ for _ in ()).throw(AssertionError("worker must not run")),
    )

    assert report.status == BrepAdapterStatus.UNKNOWN
    assert report.required_evidence[0]["field"] == "bridge_axis_aligned_planar_anchors"


def test_valid_bridge_candidate_is_hash_pose_anchor_and_authority_bound() -> None:
    def runner(*args):
        first_content, first_hash, first_pose, first_anchor, second_content, second_hash, second_pose, second_anchor, parameters, _timeout = args
        assert first_content == STEP and second_content == STEP
        assert first_hash == _hash() and second_hash == _hash()
        assert first_pose["translation_mm"] == [0.0, 0.0, 0.0]
        assert second_pose["translation_mm"] == [20.0, 0.0, 0.0]
        assert first_anchor["anchor_id"] == "anchor-left"
        assert second_anchor["anchor_id"] == "anchor-right"
        assert parameters["width_mm"] == 4.0
        assert parameters["thickness_mm"] == 4.0
        return _worker_payload()

    report = _call(runner=runner)

    assert report.status == BrepAdapterStatus.READY
    assert report.geometric_candidate_passed is True
    assert report.adapter_axis == pytest.approx((1.0, 0.0, 0.0))
    assert report.length_mm == pytest.approx(10.0)
    assert report.generated_content_hash == f"sha256:{hashlib.sha256(_generated_step().encode('utf-8')).hexdigest()}"
    assert report.vertex_count == 8
    assert report.triangle_count == 12
    assert report.first_parent_contact_passed is True
    assert report.second_parent_contact_passed is True
    assert report.metadata["generated_geometry_exact_occt"] is True
    assert report.metadata["mounting_method_resolved"] is False
    assert report.metadata["structural_analysis"] is False
    assert report.metadata["fabrication_authorized"] is False
    assert {row["field"] for row in report.required_evidence} >= {
        "mounting_method", "material", "structural_analysis", "fabrication_review"
    }


def test_exact_parent_penetration_can_reject_generated_candidate_without_promoting_authority() -> None:
    report = _call(runner=lambda *_args: _worker_payload(geometric_pass=False))

    assert report.status == BrepAdapterStatus.READY
    assert report.geometric_candidate_passed is False
    assert report.first_parent_penetration_passed is False
    assert report.required_evidence[0]["field"] == "exact_parent_clearance"
    assert report.metadata["fabrication_authorized"] is False


def test_missing_optional_kernel_keeps_adapter_unknown() -> None:
    report = _call(
        kernel_available=False,
        runner=lambda *_args: (_ for _ in ()).throw(AssertionError("worker must not run")),
    )

    assert report.status == BrepAdapterStatus.UNKNOWN
    assert report.kernel_available is False
    assert report.required_evidence[0]["field"] == "cadquery-isolated"


def test_real_cadquery_bridge_spans_two_separated_box_faces(tmp_path) -> None:
    cq = pytest.importorskip("cadquery", reason="optional cadquery-isolated specialist is not installed")
    step_path = tmp_path / "box.step"
    cq.exporters.export(cq.Workplane("XY").box(10.0, 10.0, 10.0), str(step_path))
    content = step_path.read_text(encoding="utf-8")
    content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

    def anchor(side: str, source_id: str, model_id: str, placement_id: str, object_id: str, point, normal):
        return {
            "anchor_id": f"anchor-{side}",
            "interface_id": f"if-{side}",
            "object_id": object_id,
            "source_id": source_id,
            "model_id": model_id,
            "content_hash": content_hash,
            "placement_id": placement_id,
            "frame_id": "assembly",
            "anchor_point_mm": point,
            "outward_normal": normal,
            "face_index": 1,
            "face_geom_type": "PLANE",
            "authority": "declared",
            "status": "ready",
            "kernel_surface_snap": True,
            "connector_mating_verified": False,
            "physical_measurement": False,
            "fabrication_authorized": False,
        }

    report = synthesize_brep_bridge_adapter(
        project_id="adapter-real",
        adapter_id="bridge-real",
        first_content=content,
        first_source_id="left-box.step",
        first_model_id="left-box",
        first_expected_content_hash=content_hash,
        first_placement={
            "placement_id": "place-left-real",
            "object_id": "left-real",
            "model_id": "left-box",
            "target_frame": "assembly",
            "translation_mm": [0.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
            "authority": "declared",
        },
        first_anchor=anchor("left", "left-box.step", "left-box", "place-left-real", "left-real", [5.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
        second_content=content,
        second_source_id="right-box.step",
        second_model_id="right-box",
        second_expected_content_hash=content_hash,
        second_placement={
            "placement_id": "place-right-real",
            "object_id": "right-real",
            "model_id": "right-box",
            "target_frame": "assembly",
            "translation_mm": [20.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
            "authority": "declared",
        },
        second_anchor=anchor("right", "right-box.step", "right-box", "place-right-real", "right-real", [15.0, 0.0, 0.0], [-1.0, 0.0, 0.0]),
        parameters={"width_mm": 4.0, "thickness_mm": 4.0},
        kernel_available=True,
    )

    assert report.status == BrepAdapterStatus.READY
    assert report.kernel == "cadquery_occt"
    assert report.geometric_candidate_passed is True
    assert report.length_mm == pytest.approx(10.0, abs=1e-6)
    assert report.volume_mm3 == pytest.approx(160.0, rel=1e-5)
    assert report.first_parent_minimum_distance_mm == pytest.approx(0.0, abs=1e-6)
    assert report.second_parent_minimum_distance_mm == pytest.approx(0.0, abs=1e-6)
    assert report.first_parent_intersection_volume_mm3 == pytest.approx(0.0, abs=1e-7)
    assert report.second_parent_intersection_volume_mm3 == pytest.approx(0.0, abs=1e-7)
    assert report.generated_step_content and "ISO-10303-21" in report.generated_step_content
    assert report.vertex_count > 0
    assert report.triangle_count > 0
