from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.mechanical_brep_mesh import (
    BREP_MESH_WORKER_SCHEMA,
    MAX_MESH_TRIANGLES,
    BrepMeshStatus,
    build_step_brep_render_mesh,
)


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(10.0,10.0,10.0));
ENDSEC;
END-ISO-10303-21;
"""


def _hash(content: str = STEP) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def test_missing_optional_kernel_keeps_render_mesh_unknown() -> None:
    report = build_step_brep_render_mesh(
        project_id="mesh-test",
        content=STEP,
        source_id="fixture.step",
        model_id="fixture",
        expected_content_hash=_hash(),
        kernel_available=False,
    )

    assert report.status == BrepMeshStatus.UNKNOWN
    assert report.kernel_available is False
    assert report.vertex_count == 0
    assert report.triangle_count == 0
    assert report.required_evidence[0]["field"] == "cadquery-isolated"
    assert report.metadata["render_evidence_only"] is True
    assert report.metadata["fabrication_authorized"] is False


def test_inline_mesh_rejects_hash_mismatch_before_kernel_execution() -> None:
    with pytest.raises(ValueError, match="expected canonical content_hash"):
        build_step_brep_render_mesh(
            project_id="mesh-test",
            content=STEP.replace("(10.0,10.0,10.0)", "(11.0,10.0,10.0)"),
            source_id="fixture.step",
            model_id="fixture",
            expected_content_hash=_hash(),
            kernel_available=True,
            runner=lambda *_args: (_ for _ in ()).throw(AssertionError("worker must not run")),
        )


def test_valid_worker_mesh_is_bounded_and_render_only() -> None:
    def runner(_content, expected_hash, tolerance, angular, _timeout):
        return {
            "ok": True,
            "worker_schema": BREP_MESH_WORKER_SCHEMA,
            "kernel": "cadquery_occt",
            "cadquery_version": "test",
            "input_content_hash": expected_hash,
            "shape_valid": True,
            "solid_count": 1,
            "vertex_count": 4,
            "triangle_count": 2,
            "vertices_mm": [
                [0.0, 0.0, 0.0],
                [10.0, 0.0, 0.0],
                [0.0, 10.0, 0.0],
                [0.0, 0.0, 10.0],
            ],
            "triangles": [[0, 1, 2], [0, 1, 3]],
            "tolerance_mm": tolerance,
            "angular_tolerance_rad": angular,
        }

    report = build_step_brep_render_mesh(
        project_id="mesh-test",
        content=STEP,
        source_id="fixture.step",
        model_id="fixture",
        expected_content_hash=_hash(),
        kernel_available=True,
        runner=runner,
    )

    assert report.status == BrepMeshStatus.READY
    assert report.vertex_count == 4
    assert report.triangle_count == 2
    assert report.vertices_mm[3] == [0.0, 0.0, 10.0]
    assert report.triangles[1] == [0, 1, 3]
    assert report.metadata["worker_input_hash_reverified"] is True
    assert report.metadata["full_assembly_collision"] is False
    assert report.metadata["physical_measurement"] is False


def test_worker_claim_over_triangle_limit_fails_closed_without_materializing_large_payload() -> None:
    def runner(_content, expected_hash, tolerance, angular, _timeout):
        return {
            "ok": True,
            "worker_schema": BREP_MESH_WORKER_SCHEMA,
            "input_content_hash": expected_hash,
            "shape_valid": True,
            "solid_count": 1,
            "vertex_count": 0,
            "triangle_count": MAX_MESH_TRIANGLES + 1,
            "vertices_mm": [],
            "triangles": [],
            "tolerance_mm": tolerance,
            "angular_tolerance_rad": angular,
        }

    report = build_step_brep_render_mesh(
        project_id="mesh-test",
        content=STEP,
        source_id="fixture.step",
        model_id="fixture",
        expected_content_hash=_hash(),
        kernel_available=True,
        runner=runner,
    )

    assert report.status == BrepMeshStatus.UNKNOWN
    assert report.required_evidence[0]["field"] == "valid_brep_render_mesh"
    assert "triangle count exceeds bounded contract" in report.required_evidence[0]["reason"]


def test_real_cadquery_tessellation_when_optional_specialist_is_installed(tmp_path) -> None:
    cq = pytest.importorskip("cadquery", reason="optional cadquery-isolated specialist is not installed")
    step_path = tmp_path / "box.step"
    cq.exporters.export(cq.Workplane("XY").box(10.0, 8.0, 6.0), str(step_path))
    content = step_path.read_text(encoding="utf-8")

    report = build_step_brep_render_mesh(
        project_id="mesh-real",
        content=content,
        source_id="box.step",
        model_id="box",
        expected_content_hash=_hash(content),
        tolerance_mm=0.5,
        angular_tolerance_rad=0.1,
        kernel_available=True,
    )

    assert report.status == BrepMeshStatus.READY
    assert report.kernel == "cadquery_occt"
    assert report.shape_valid is True
    assert report.solid_count == 1
    assert report.vertex_count > 0
    assert report.triangle_count > 0
    assert len(report.vertices_mm) == report.vertex_count
    assert len(report.triangles) == report.triangle_count
    assert report.content_hash == _hash(content)
