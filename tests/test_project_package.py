"""Tests for Blueprint-shaped project package generation."""

from __future__ import annotations

from pathlib import Path

from hardware_splicer.intent_clarifier import analyze_intent_clarifications, apply_clarification_answers
from hardware_splicer.project_package import build_project_package, render_project_page_md, write_project_package_artifacts
from hardware_splicer.sdk import clarify_hardware_intent, synthesize_circuit


def test_clarifier_flags_vague_goal() -> None:
    report = analyze_intent_clarifications({"goal": "make a gadget"})
    assert report["needs_clarification"] is True
    assert len(report["questions"]) >= 3


def test_clarifier_records_answers_without_inventing_engineering_facts() -> None:
    enriched = apply_clarification_answers(
        {
            "goal": "make a gadget",
            "clarification_answers": {
                "power_source": "battery",
                "controller": "ESP32",
                "load_type": "pump motor",
            },
        }
    )

    # User prose is preserved as declared evidence. The clarifier must not invent
    # voltages, currents, load classes, or a particular catalog part.
    assert "supply_rails" not in enriched
    assert "allowed_modules" not in enriched
    assert "load_requirements" not in enriched
    observations = {
        row["question_id"]: row for row in enriched["clarification_observations"]
    }
    assert observations["power_source"]["answer"] == "battery"
    assert observations["controller"]["answer"] == "ESP32"
    assert observations["load_type"]["answer"] == "pump motor"
    assert all(row["authority"] == "declared" for row in observations.values())
    assert all(row["interpretation_status"] == "unresolved" for row in observations.values())

    report = analyze_intent_clarifications(
        {
            "goal": "make a gadget",
            "clarification_answers": {"power_source": "battery"},
        }
    )
    assert report["needs_clarification"] is False
    assert report["semantic_interpretation_required"] is True
    assert report["enriched_intent"]["clarification_observations"][0]["answer"] == "battery"


def test_synthesis_package_blocked(tmp_path: Path) -> None:
    result = synthesize_circuit(
        {
            "goal": "design a low noise analog audio preamplifier from discrete transistors",
            "supply_rails": [{"name": "+12V", "voltage_v": 12.0, "max_current_a": 0.25}],
        },
        out_dir=tmp_path,
        compile_build=False,
    )
    package = result["project_package"]
    assert package["gates"]["verdict"] == "BLOCKED"
    assert (tmp_path / "PROJECT_PAGE.md").is_file()
    assert (tmp_path / "ASSEMBLY_GUIDE.md").is_file()


def test_synthesis_package_compile(tmp_path: Path) -> None:
    result = synthesize_circuit(
        {
            "goal": "build an ESP32 controlled 5V pump driver",
            "supply_rails": [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}],
            "load_requirements": [{"name": "pump", "type": "dc_motor", "voltage_v": 5.0, "current_a": 0.45}],
            "signal_requirements": [{"name": "pump_enable", "type": "pwm", "voltage_v": 3.3}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit", "mosfet-irlz44n", "water_pump_5v"],
            "required_evidence": ["flyback_or_driver_protection"],
        },
        out_dir=tmp_path,
        export_gerber=False,
    )
    assert (tmp_path / "PROJECT_PACKAGE.json").is_file()
    page = (tmp_path / "PROJECT_PAGE.md").read_text(encoding="utf-8")
    assert "## BOM" in page
    assert "## GATES" in page
    assert result["project_package"]["bom"]["line_count"] >= 1


def test_render_project_page_from_package() -> None:
    package = build_project_package(
        ".",
        result={
            "ok": False,
            "goal": "test goal",
            "project_name": "demo",
            "candidate": {"result": "blocked", "missing_evidence": ["load_current_estimate"]},
        },
        source="unit",
    )
    md = render_project_page_md(package)
    assert "demo" in md
    assert "GATES" in md


def test_sdk_clarify_wrapper() -> None:
    report = clarify_hardware_intent({"goal": "LED thing"})
    assert "questions" in report
