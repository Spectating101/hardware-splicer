"""Bench capture vision assist — camera → draft template (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.api import create_app
from hardware_splicer.bench_capture_vision import assist_bench_capture_vision
from hardware_splicer.sdk import bench_capture_vision_assist
from hardware_splicer.splice_bench import open_bench_session

ROOT = Path(__file__).resolve().parents[1]
DONOR_FIXTURE = ROOT / "examples" / "fixtures" / "splice_donor_rc_motor_board.json"


def _minimal_build(tmp_path: Path) -> Path:
    donor = json.loads(DONOR_FIXTURE.read_text(encoding="utf-8"))
    root = tmp_path / "build"
    intake = {
        "project_name": "vision_assist_unit",
        "circuit": {"boards": [{"board_id": "donor_rc_car_ctrl", "functional_salvage": donor}]},
    }
    splice_plan = {"splice_plan": {"required_measurements": ["Measure VMOTOR at J_LOGIC"]}}
    root.mkdir(parents=True, exist_ok=True)
    (root / "PROJECT_INTAKE.json").write_text(json.dumps(intake, indent=2), encoding="utf-8")
    (root / "SPLICE_PLAN.json").write_text(json.dumps(splice_plan, indent=2), encoding="utf-8")
    open_bench_session(root)
    return root


def _fake_jpeg(path: Path) -> None:
    path.write_bytes(b"\xff\xd8\xff\xd8fake-jpeg-for-bench-vision")


def test_bench_capture_vision_assist_offline_draft(tmp_path: Path) -> None:
    root = _minimal_build(tmp_path)
    photo = tmp_path / "donor_bench.jpg"
    _fake_jpeg(photo)
    before = open_bench_session(root)
    open_before = before.get("open_gate_count")

    result = assist_bench_capture_vision(
        root,
        attachments=[{"kind": "image", "path": str(photo)}],
        live=False,
        operator_id="repair_cafe_01",
    )
    assert result.get("ok") is True
    draft_path = Path(result["draft_path"])
    assert draft_path.is_file()
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["schema_version"] == "bench_topology_capture.v1"
    assert draft.get("vision_assisted") is True
    assert draft["policy"]["vision_alone_is_not_evidence"] is True
    assert all(row.get("status") == "open" for row in draft.get("measurements") or [])
    assert any(row.get("vision_assist") for row in draft.get("measurements") or [])
    assert any(art.get("uri") for art in draft.get("artifacts") or [])

    after = open_bench_session(root)
    assert after.get("open_gate_count") == open_before
    assert after.get("power_on_authorized") is not True
    assert (root / "BENCH_CAPTURE_VISION_REPORT.json").is_file()


def test_bench_capture_vision_assist_inline_base64(tmp_path: Path) -> None:
    root = _minimal_build(tmp_path)
    import base64

    tiny = base64.b64encode(b"\xff\xd8\xff\xd8inline").decode("ascii")
    result = bench_capture_vision_assist(
        root,
        attachments=[{"kind": "image", "image_base64": tiny, "filename": "inline.jpg"}],
    )
    assert result.get("ok") is True
    assert Path(result["draft_path"]).is_file()


def test_bench_capture_vision_assist_requires_images(tmp_path: Path) -> None:
    root = _minimal_build(tmp_path)
    with pytest.raises(ValueError, match="no_bench_images_resolved"):
        assist_bench_capture_vision(root, attachments=[])


def test_bench_capture_vision_assist_http(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    root = _minimal_build(tmp_path)
    photo = tmp_path / "http_bench.jpg"
    _fake_jpeg(photo)
    client = TestClient(create_app())
    response = client.post(
        "/v1/splice-bench/vision-assist",
        json={
            "build_dir": str(root),
            "attachments": [{"kind": "image", "path": str(photo)}],
            "operator_id": "http_operator",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("ok") is True
    assert payload.get("policy", {}).get("vision_alone_is_not_evidence") is True
    assert payload.get("policy", {}).get("gates_unchanged") is True
