"""A goal that names a part, or a mains voltage, must reach the gate, not only the picked catalog list.

Probe on main: "read a thermistor, switch a 230 V 300 W PTC heater with an SSR" compiled to an Arduino
Nano, a 5 V relay and USB power (no thermistor, no SSR) and the gate said build_ready with no blockers.
"""

from __future__ import annotations

import json

import pytest

from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.request_fidelity import (
    assess_goal_fidelity,
    assess_request_fidelity,
    detect_high_voltage_goal,
)

HEATER_GOAL = (
    "3D printer enclosure heater controller: read a thermistor, switch a 230 V 300 W PTC heater "
    "with an SSR to hold 45 C, with over-temperature cutoff"
)

CLEAN_BOARD = {
    "build_graph_compiled": True,
    "electrical_safety_pass": True,
    "drc_pass": True,
    "build_ready": True,
    "bom_ready": True,
    "gerber_ready": True,
    "fabrication_ready": True,
}


def _graph(*module_ids: str) -> dict:
    return {"nodes": [{"id": f"n{i}", "moduleId": m} for i, m in enumerate(module_ids, 1)]}


@pytest.mark.parametrize(
    "text",
    [
        HEATER_GOAL,
        "switch a 110 V lamp",
        "relay for 120 VAC load",
        "controls the mains heater",
        "240V kettle controller",
        "mains-powered fan",
        "switch a 150 V DC bus",
        "run from the 230VAC outlet",
        "3 kV spark gap",
    ],
)
def test_mains_or_high_voltage_goals_are_detected(text: str) -> None:
    assert detect_high_voltage_goal(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "ESP32 logger with BME280 on 3.3V and a 5 V USB supply",
        "12 V pump driven from a 24 V DC rail",
        "48 V DC telecom bus monitor",
        "no mains connection, battery only, 3V3 logic",
        "ESP32 with 3V3 sensors",
        "",
    ],
)
def test_low_voltage_goals_are_not_flagged(text: str) -> None:
    assert detect_high_voltage_goal(text) is None


def test_goal_fidelity_names_the_thermistor_and_ssr_the_design_lacks() -> None:
    result = assess_goal_fidelity(HEATER_GOAL, _graph("arduino-nano", "relay-1ch-5v", "usb-power-5v"))

    labels = [row["label"] for row in result["named_parts_missing"]]
    assert labels == ["thermistor", "solid-state relay (SSR)"]
    assert result["high_voltage"] is not None


def test_a_named_part_that_is_in_the_design_is_not_reported() -> None:
    result = assess_goal_fidelity(
        "ESP32 logger with BME280 and a microSD card", _graph("esp32-devkit", "bme280", "sd_card_module")
    )

    assert result["named_parts_missing"] == []


def test_a_negated_part_is_not_required() -> None:
    result = assess_goal_fidelity("ESP32 sensor node, no microSD, without a thermistor", _graph("esp32-devkit"))

    assert result["named_parts_missing"] == []


def test_request_fidelity_is_a_mismatch_when_the_goal_names_a_part_the_design_lacks() -> None:
    result = assess_request_fidelity([], _graph("esp32-devkit", "bme280"), goal="ESP32 logger with a microSD card")

    assert result["status"] == "mismatch"
    assert [r["label"] for r in result["goal_named_parts_missing"]] == ["microSD card"]


def test_gate_blocks_on_a_named_part_the_design_lacks() -> None:
    fidelity = assess_request_fidelity([], _graph("esp32-devkit", "bme280"), goal="ESP32 logger with a microSD card")

    gate = build_design_quality_gate(CLEAN_BOARD, request_fidelity=fidelity)

    assert gate["build_ready"] is False
    assert any("microSD card" in b and "leaves out" in b for b in gate["blockers"])


def test_gate_treats_mains_as_out_of_scope_and_needing_a_person_even_when_every_part_is_present() -> None:
    graph = _graph("esp32-devkit", "thermistor", "ssr")
    fidelity = assess_request_fidelity([], graph, goal=HEATER_GOAL)

    gate = build_design_quality_gate(CLEAN_BOARD, request_fidelity=fidelity)

    assert gate["build_ready"] is False
    assert gate["fabrication_ready"] is False
    assert gate["requires_person"] is True
    assert any("mains" in b.lower() or "high voltage" in b.lower() for b in gate["blockers"])


def test_gate_without_a_goal_is_unchanged() -> None:
    gate = build_design_quality_gate(CLEAN_BOARD, request_fidelity=assess_request_fidelity([], _graph("esp32-devkit")))

    assert gate["build_ready"] is True


def test_the_heater_brief_through_splice_and_build_is_blocked(tmp_path) -> None:
    from hardware_splicer.project_intake import splice_and_build_from_intake

    intake = {
        "project_name": "probe_enclosure_heater",
        "goal": HEATER_GOAL,
        "salvage_mode": False,
        "available_parts": [],
        "constraints": {"strategy_mode": "open"},
    }

    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "heater", export_gerber=False)

    gate = json.loads((tmp_path / "heater" / "build_compilation" / "DESIGN_QUALITY_GATE.json").read_text())
    assert gate["build_ready"] is False
    assert gate["requires_person"] is True
    assert any("230" in b or "mains" in b.lower() for b in gate["blockers"])
    assert any("thermistor" in b for b in gate["blockers"])
    assert any("SSR" in b for b in gate["blockers"])
    assert result["design_quality_gate"]["build_ready"] is False


def test_compose_phrase_that_asks_for_a_microsd_card_is_not_build_ready_when_the_card_is_dropped(tmp_path) -> None:
    """Probe on main: the phrase picker dropped the card, ERC/DRC were clean, and compose said build_ready."""
    from hardware_splicer.compose_dispatch import compose_dispatch

    result = compose_dispatch(
        out_dir=tmp_path / "logger",
        phrase="ESP32 environmental sensor logger with I2C BME280 and microSD card",
        export_gerber=False,
    )

    assert "sd_card_module" not in result["module_ids"]
    gate = result["design_quality_gate"]
    assert gate["build_ready"] is False
    assert result["ok"] is False
    assert any("microSD card" in b and "leaves out" in b for b in gate["blockers"])
    assert gate["request_fidelity"]["status"] == "mismatch"


def test_compose_phrase_without_a_named_missing_part_is_unaffected(tmp_path) -> None:
    from hardware_splicer.compose_dispatch import compose_dispatch

    result = compose_dispatch(
        out_dir=tmp_path / "plain",
        phrase="ESP32 environmental sensor logger with I2C BME280",
        export_gerber=False,
    )

    assert not any("leaves out" in b for b in result["design_quality_gate"]["blockers"])
