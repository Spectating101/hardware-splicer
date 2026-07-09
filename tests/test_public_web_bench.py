"""Public-web DMM photo → bench capture (cold-run provenance)."""

from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.public_web_bench import (
    analyze_public_dmm_photo,
    build_public_web_capture,
    list_public_bench_photos,
    map_public_capture_to_open_gates,
    run_public_web_bench_on_build,
)
from hardware_splicer.splice_bench import open_bench_session

ROOT = Path(__file__).resolve().parents[1]
DONOR_FIXTURE = ROOT / "examples" / "fixtures" / "splice_donor_rc_motor_board.json"


def _minimal_build(tmp_path: Path) -> Path:
    donor = json.loads(DONOR_FIXTURE.read_text(encoding="utf-8"))
    root = tmp_path / "build"
    intake = {
        "project_name": "public_web_bench_unit",
        "circuit": {"boards": [{"board_id": "donor_rc_car_ctrl", "functional_salvage": donor}]},
    }
    splice_plan = {
        "splice_plan": {
            "required_measurements": [
                "Measure VMOTOR at J_LOGIC",
                "Confirm continuity on motor harness",
            ]
        }
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "PROJECT_INTAKE.json").write_text(json.dumps(intake, indent=2), encoding="utf-8")
    (root / "SPLICE_PLAN.json").write_text(json.dumps(splice_plan, indent=2), encoding="utf-8")
    open_bench_session(root)
    return root


def test_list_public_bench_photos():
    photos = list_public_bench_photos()
    assert photos
    assert any(p.name == "dmm_testing_5v.jpg" for p in photos)


def test_pinned_public_photo_reading():
    photo = ROOT / "tests" / "data" / "golden" / "public_bench" / "dmm_testing_5v.jpg"
    assert photo.is_file()
    analysis = analyze_public_dmm_photo(photo, live=False)
    assert analysis.get("pinned") is True
    assert analysis["parsed"]["value"] == 5.52
    assert analysis["parsed"]["unit"] == "V"


def test_public_web_bench_closes_gates(tmp_path: Path) -> None:
    root = _minimal_build(tmp_path)
    before = open_bench_session(root)
    assert before.get("power_on_authorized") is not True
    report = run_public_web_bench_on_build(root, live=False, submit=True, max_photos=2)
    assert report.get("passed") is True
    assert report.get("policy", {}).get("public_web_is_not_this_board") is True
    assert (root / "PUBLIC_WEB_BENCH_CAPTURE.json").is_file()
    after = open_bench_session(root)
    assert after.get("power_on_authorized") is True


def test_map_public_capture_assigns_gate_ids():
    capture = build_public_web_capture(
        photo_analyses=[
            {
                "image_name": "dmm_testing_5v.jpg",
                "image_path": "x.jpg",
                "parsed": {
                    "value": 5.52,
                    "unit": "V",
                    "kind": "voltage",
                    "status_for_pass": "pass",
                    "pin_note": "5.52V",
                },
            }
        ]
    )
    template = {
        "measurements": [
            {"gate_id": "vmotor", "kind": "voltage", "target": "VMOTOR", "status": "open"},
            {"gate_id": "gnd", "kind": "continuity", "target": "GND", "status": "open"},
        ]
    }
    mapped = map_public_capture_to_open_gates(capture, template)
    ids = {row["gate_id"] for row in mapped["measurements"]}
    assert "vmotor" in ids
