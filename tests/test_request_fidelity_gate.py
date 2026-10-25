"""A design that leaves out a requested part must not be reported as build ready."""

from __future__ import annotations

from hardware_splicer.design_quality import build_design_quality_gate

CLEAN_BOARD = {
    "build_graph_compiled": True,
    "electrical_safety_pass": True,
    "drc_pass": True,
    "build_ready": True,
    "bom_ready": True,
    "gerber_ready": True,
    "fabrication_ready": True,
}

MISMATCH = {
    "status": "mismatch",
    "missing_parts": [
        {"module_id": "sg90", "names": ["SG90 pan servo", "SG90 tilt servo"], "requested": 2, "in_design": 1}
    ],
}


def test_callers_that_pass_no_request_comparison_get_the_same_gate_as_before() -> None:
    gate = build_design_quality_gate(CLEAN_BOARD)

    assert gate["build_ready"] is True
    assert "request_fidelity" not in gate


def test_a_clean_board_missing_a_requested_part_is_not_build_ready_and_the_blocker_names_it() -> None:
    gate = build_design_quality_gate(CLEAN_BOARD, request_fidelity=MISMATCH)

    assert gate["build_ready"] is False
    assert gate["fabrication_ready"] is False
    [blocker] = [text for text in gate["blockers"] if "sg90" in text]
    assert "requested 2" in blocker and "design has 1" in blocker
    assert "SG90 tilt servo" in blocker
    assert gate["request_fidelity"]["status"] == "mismatch"


def test_a_comparison_that_could_not_be_made_is_recorded_but_does_not_block() -> None:
    unknown = {"status": "not_assessable", "missing_parts": []}
    gate = build_design_quality_gate(CLEAN_BOARD, request_fidelity=unknown)

    assert gate["build_ready"] is True
    assert gate["request_fidelity"]["status"] == "not_assessable"


def test_a_matching_comparison_does_not_block() -> None:
    gate = build_design_quality_gate(
        CLEAN_BOARD, request_fidelity={"status": "matches", "missing_parts": []}
    )

    assert gate["build_ready"] is True
    assert gate["request_fidelity"]["status"] == "matches"


def test_the_pan_tilt_demo_request_is_not_build_ready_because_the_second_servo_was_dropped(tmp_path) -> None:
    import json
    from pathlib import Path

    from hardware_splicer import load_project_intake
    from hardware_splicer.project_intake import splice_and_build_from_intake

    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "splice_physical_pan_tilt_loop.json")

    splice_and_build_from_intake(intake, out_dir=tmp_path / "pan_tilt", export_gerber=False)

    gate = json.loads((tmp_path / "pan_tilt" / "build_compilation" / "DESIGN_QUALITY_GATE.json").read_text())
    assert gate["request_fidelity"]["status"] == "mismatch"
    assert gate["build_ready"] is False
    assert any("sg90" in blocker and "requested 2" in blocker for blocker in gate["blockers"])


def test_the_pan_tilt_demo_builds_both_servos_and_matches_the_request(tmp_path, monkeypatch) -> None:
    import json

    # The shared test setup forces the offline catalog route, which builds one fixed servo
    # whatever the request says. The demo and the product use the composing route.
    for name in ("HARDWARE_SPLICER_OFFLINE_SALVAGE", "HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        monkeypatch.setenv(name, "0")
    from pathlib import Path

    from hardware_splicer import load_project_intake
    from hardware_splicer.project_intake import splice_and_build_from_intake

    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "splice_physical_pan_tilt_loop.json")

    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "pan_tilt_fixed", export_gerber=False)

    graph = json.loads(Path(result["artifacts"]["build_graph"]).read_text())
    assert [n["moduleId"] for n in graph["nodes"]].count("sg90") == 2
    gate = json.loads((tmp_path / "pan_tilt_fixed" / "build_compilation" / "DESIGN_QUALITY_GATE.json").read_text())
    assert gate["request_fidelity"]["status"] == "matches"


def test_a_warning_blocker_says_what_the_warning_is_not_only_how_many() -> None:
    quality = {
        **CLEAN_BOARD,
        "electrical_warnings": 1,
        "electrical_issues": [
            {"level": "warn", "message": "ESP32 DevKit has no power connection yet.", "node_id": "n1"},
            {"level": "info", "message": "I2C bus: confirm 4.7k pull-ups to VCC exist."},
        ],
    }

    gate = build_design_quality_gate(quality)

    assert gate["build_ready"] is False
    assert "Electrical safety has 1 warning(s) — resolve before fabrication." in gate["blockers"]
    assert "ESP32 DevKit has no power connection yet." in gate["blockers"]
    assert not any("pull-ups" in blocker for blocker in gate["blockers"]), "notes are not blockers"


def test_the_blocker_for_an_unknown_part_id_says_so_and_names_the_likely_id() -> None:
    mismatch = {
        "status": "mismatch",
        "missing_parts": [
            {"module_id": "usb-5v", "names": ["USB supply"], "requested": 1, "in_design": 0, "unknown_module_id": True, "did_you_mean": ["usb-power-5v"]}
        ],
    }
    gate = build_design_quality_gate(CLEAN_BOARD, request_fidelity=mismatch)
    [blocker] = gate["blockers"]

    assert "usb-5v" in blocker and "not a part id HS knows" in blocker and "usb-power-5v" in blocker


def test_the_blocker_for_an_unknown_id_with_no_suggestion_points_at_the_catalog() -> None:
    mismatch = {
        "status": "mismatch",
        "missing_parts": [
            {"module_id": "zzz", "names": ["x"], "requested": 1, "in_design": 0, "unknown_module_id": True, "did_you_mean": []}
        ],
    }
    [blocker] = build_design_quality_gate(CLEAN_BOARD, request_fidelity=mismatch)["blockers"]

    assert "module catalog" in blocker
