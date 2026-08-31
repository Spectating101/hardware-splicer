from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.mechanical_brep_anchor import (
    BREP_ANCHOR_WORKER_SCHEMA,
    BrepAnchorStatus,
    build_step_brep_surface_anchor,
)


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(-5.0,-4.0,-3.0));
#4=CARTESIAN_POINT('',(5.0,4.0,3.0));
ENDSEC;
END-ISO-10303-21;
"""


def _hash(content: str = STEP) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _placement(model_id: str = "fixture") -> dict:
    return {
        "placement_id": "place-fixture",
        "object_id": "cmp-fixture",
        "model_id": model_id,
        "target_frame": "assembly",
        "translation_mm": [20.0, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _worker_payload(expected_hash: str, probe: list[float]) -> dict:
    return {
        "ok": True,
        "worker_schema": BREP_ANCHOR_WORKER_SCHEMA,
        "kernel": "cadquery_occt",
        "cadquery_version": "test",
        "input_content_hash": expected_hash,
        "rotation_convention": "Rz*Ry*Rx; canonical STEP XYZ",
        "placement_applied": True,
        "shape_valid": True,
        "solid_count": 1,
        "face_count": 6,
        "face_index": 1,
        "face_geom_type": "PLANE",
        "face_area_mm2": 48.0,
        "face_center_mm": [25.0, 0.0, 0.0],
        "probe_point_mm": probe,
        "anchor_point_mm": [25.0, 0.0, 0.0],
        "outward_normal": [1.0, 0.0, 0.0],
        "snap_distance_mm": 0.1,
        "max_snap_distance_mm": 1.0,
    }


def test_missing_optional_kernel_keeps_surface_anchor_unknown() -> None:
    report = build_step_brep_surface_anchor(
        project_id="anchor-test",
        anchor_id="anchor-usb",
        interface_id="if-usb",
        content=STEP,
        source_id="fixture.step",
        model_id="fixture",
        expected_content_hash=_hash(),
        placement=_placement(),
        probe_point_mm=[25.1, 0.0, 0.0],
        max_snap_distance_mm=1.0,
        kernel_available=False,
    )

    assert report.status == BrepAnchorStatus.UNKNOWN
    assert report.kernel_available is False
    assert report.anchor_point_mm is None
    assert report.required_evidence[0]["field"] == "cadquery-isolated"
    assert report.metadata["connector_mating_verified"] is False
    assert report.metadata["fabrication_authorized"] is False


def test_anchor_rejects_hash_mismatch_before_kernel_execution() -> None:
    with pytest.raises(ValueError, match="expected canonical content_hash"):
        build_step_brep_surface_anchor(
            project_id="anchor-test",
            anchor_id="anchor-usb",
            interface_id="if-usb",
            content=STEP.replace("(5.0,4.0,3.0)", "(6.0,4.0,3.0)"),
            source_id="fixture.step",
            model_id="fixture",
            expected_content_hash=_hash(),
            placement=_placement(),
            probe_point_mm=[25.1, 0.0, 0.0],
            max_snap_distance_mm=1.0,
            kernel_available=True,
            runner=lambda *_args: (_ for _ in ()).throw(AssertionError("worker must not run")),
        )


def test_anchor_rejects_placement_model_identity_mismatch_before_worker() -> None:
    with pytest.raises(ValueError, match="anchor placement targets model 'wrong'"):
        build_step_brep_surface_anchor(
            project_id="anchor-test",
            anchor_id="anchor-usb",
            interface_id="if-usb",
            content=STEP,
            source_id="fixture.step",
            model_id="fixture",
            expected_content_hash=_hash(),
            placement=_placement("wrong"),
            probe_point_mm=[25.1, 0.0, 0.0],
            kernel_available=True,
            runner=lambda *_args: (_ for _ in ()).throw(AssertionError("worker must not run")),
        )


def test_valid_worker_surface_anchor_is_hash_pose_and_interface_bound() -> None:
    probe = [25.1, 0.0, 0.0]

    def runner(_content, expected_hash, placement, worker_probe, max_snap, _timeout):
        assert placement == {
            "translation_mm": [20.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
        }
        assert worker_probe == probe
        assert max_snap == 1.0
        return _worker_payload(expected_hash, worker_probe)

    report = build_step_brep_surface_anchor(
        project_id="anchor-test",
        anchor_id="anchor-usb",
        interface_id="if-usb",
        content=STEP,
        source_id="fixture.step",
        model_id="fixture",
        expected_content_hash=_hash(),
        placement=_placement(),
        probe_point_mm=probe,
        max_snap_distance_mm=1.0,
        kernel_available=True,
        runner=runner,
    )

    assert report.status == BrepAnchorStatus.READY
    assert report.interface_id == "if-usb"
    assert report.object_id == "cmp-fixture"
    assert report.placement_id == "place-fixture"
    assert report.frame_id == "assembly"
    assert report.anchor_point_mm == [25.0, 0.0, 0.0]
    assert report.outward_normal == [1.0, 0.0, 0.0]
    assert report.snap_distance_mm == pytest.approx(0.1)
    assert report.face_geom_type == "PLANE"
    assert report.metadata["face_identity_scoped_to_content_hash"] is True
    assert report.metadata["connector_mating_verified"] is False
    assert report.metadata["physical_measurement"] is False


def test_invalid_worker_normal_fails_closed() -> None:
    def runner(_content, expected_hash, _placement, probe, _max_snap, _timeout):
        payload = _worker_payload(expected_hash, probe)
        payload["outward_normal"] = [2.0, 0.0, 0.0]
        return payload

    report = build_step_brep_surface_anchor(
        project_id="anchor-test",
        anchor_id="anchor-usb",
        interface_id="if-usb",
        content=STEP,
        source_id="fixture.step",
        model_id="fixture",
        expected_content_hash=_hash(),
        placement=_placement(),
        probe_point_mm=[25.1, 0.0, 0.0],
        max_snap_distance_mm=1.0,
        kernel_available=True,
        runner=runner,
    )

    assert report.status == BrepAnchorStatus.UNKNOWN
    assert report.required_evidence[0]["field"] == "valid_brep_surface_anchor"
    assert "normal is not unit length" in report.required_evidence[0]["reason"]


def test_real_cadquery_surface_anchor_snaps_to_translated_box_face(tmp_path) -> None:
    cq = pytest.importorskip("cadquery", reason="optional cadquery-isolated specialist is not installed")
    step_path = tmp_path / "box.step"
    cq.exporters.export(cq.Workplane("XY").box(10.0, 8.0, 6.0), str(step_path))
    content = step_path.read_text(encoding="utf-8")

    report = build_step_brep_surface_anchor(
        project_id="anchor-real",
        anchor_id="anchor-plus-x",
        interface_id="if-plus-x",
        content=content,
        source_id="box.step",
        model_id="box",
        expected_content_hash=_hash(content),
        placement={
            "placement_id": "place-box",
            "object_id": "box-object",
            "model_id": "box",
            "target_frame": "assembly",
            "translation_mm": [20.0, 0.0, 0.0],
            "rotation_deg_xyz": [0.0, 0.0, 0.0],
            "authority": "declared",
        },
        probe_point_mm=[25.1, 0.0, 0.0],
        max_snap_distance_mm=1.0,
        kernel_available=True,
    )

    assert report.status == BrepAnchorStatus.READY
    assert report.kernel == "cadquery_occt"
    assert report.anchor_point_mm == pytest.approx([25.0, 0.0, 0.0], abs=1e-5)
    assert report.outward_normal == pytest.approx([1.0, 0.0, 0.0], abs=1e-5)
    assert report.snap_distance_mm == pytest.approx(0.1, abs=1e-5)
    assert report.face_geom_type.upper() == "PLANE"
    assert report.face_area_mm2 == pytest.approx(48.0, rel=1e-5)
