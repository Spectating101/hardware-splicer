"""When HS composes a design itself (no agent), it applies the repair that needs no person, and says so."""

from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.pcb.safety_rules import analyze_build


def _codes(graph: dict, level: str = "error") -> list[str]:
    return [w.get("code") or w["id"] for w in analyze_build(graph) if w["level"] == level]


def test_two_identical_sensors_are_composed_onto_two_buses_and_the_note_says_why() -> None:
    result = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"])

    assert [n["moduleId"] for n in result["graph"]["nodes"]].count("bme280") == 2
    assert "i2c_address_clash" not in _codes(result["graph"])
    assert any("second I2C bus" in note and "0x77" in note for note in result["notes"])


def test_asking_for_no_repair_returns_the_raw_wiring_with_the_clash_visible() -> None:
    raw = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "usb-power-5v"], auto_repair=False)

    assert "i2c_address_clash" in _codes(raw["graph"])


def test_a_design_with_nothing_to_repair_is_wired_exactly_as_before() -> None:
    for ids in (["esp32-devkit", "bme280", "usb-power-5v"], ["esp32-devkit", "bme280", "bh1750", "usb-power-5v"]):
        raw = compose_build_graph_from_module_ids(ids, auto_repair=False)
        repaired = compose_build_graph_from_module_ids(ids)

        assert repaired["graph"] == raw["graph"], ids
        assert not any("I2C" in note for note in repaired["notes"])


def test_a_third_identical_sensor_cannot_get_a_third_bus_so_the_clash_is_left_standing() -> None:
    graph = compose_build_graph_from_module_ids(["esp32-devkit", "bme280", "bme280", "bme280", "usb-power-5v"])["graph"]
    clash = [w for w in analyze_build(graph) if w.get("code") == "i2c_address_clash"]

    assert len(clash) == 1 and clash[0]["level"] == "error"
    assert [r["kind"] for r in clash[0]["repairs"]] == ["strap_alternate_address"]


def test_a_controller_without_a_second_bus_is_left_with_the_error_not_silently_changed() -> None:
    graph = compose_build_graph_from_module_ids(["arduino-nano", "ds3231_rtc", "ds3231_rtc", "usb-power-5v"])["graph"]

    assert "i2c_address_clash" in _codes(graph)


def test_the_intake_build_for_two_identical_sensors_is_electrically_clean_and_firmware_gap_is_reported(tmp_path, monkeypatch) -> None:
    from hardware_splicer import load_project_intake
    from hardware_splicer.project_intake import splice_and_build_from_intake

    for name in ("HARDWARE_SPLICER_OFFLINE_SALVAGE", "HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        monkeypatch.setenv(name, "0")
    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "splice_physical_pan_tilt_loop.json")
    intake["available_parts"] = [
        {"name": "ESP32 DevKit", "module_id": "esp32-devkit", "type": "microcontroller", "condition": "salvaged"},
        {"name": "BME280 one", "module_id": "bme280", "type": "sensor", "condition": "salvaged"},
        {"name": "BME280 two", "module_id": "bme280", "type": "sensor", "condition": "salvaged"},
        {"name": "USB 5V power bank", "module_id": "usb-power-5v", "type": "power_source", "condition": "salvaged"},
    ]
    intake["goal"] = "Read temperature in two places with two BME280 sensors on an ESP32."

    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "two_bme", export_gerber=False)

    gate = json.loads((tmp_path / "two_bme" / "build_compilation" / "DESIGN_QUALITY_GATE.json").read_text())
    assert gate["request_fidelity"]["status"] == "matches"
    assert not [i for i in gate["summary"]["electrical_issues"] if i.get("code") == "i2c_address_clash"]
    assert result["firmware_coverage"]["status"] == "gaps", "firmware does not start the second bus, and HS says so"


def _build(tmp_path, monkeypatch, module_ids: list[str], name: str):
    from hardware_splicer import load_project_intake
    from hardware_splicer.project_intake import splice_and_build_from_intake

    for env in ("HARDWARE_SPLICER_OFFLINE_SALVAGE", "HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        monkeypatch.setenv(env, "0")
    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "splice_physical_pan_tilt_loop.json")
    intake["available_parts"] = [
        {"name": f"{mid} {i}", "module_id": mid, "type": "part", "condition": "salvaged"} for i, mid in enumerate(module_ids)
    ]
    intake["goal"] = f"Build a board with exactly these parts: {', '.join(module_ids)}."
    result = splice_and_build_from_intake(intake, out_dir=tmp_path / name, export_gerber=False)
    gate = json.loads((tmp_path / name / "build_compilation" / "DESIGN_QUALITY_GATE.json").read_text())
    graph = json.loads(Path(result["artifacts"]["build_graph"]).read_text())
    return result, gate, graph


def test_a_clash_no_repair_can_fix_is_reported_not_hidden_by_quietly_dropping_a_device(tmp_path, monkeypatch) -> None:
    """The retry loop used to delete the duplicate devices until the safety check passed."""
    _result, gate, graph = _build(
        tmp_path, monkeypatch, ["esp32-devkit", "bme280", "bme280", "bme280", "usb-power-5v"], "three_bme"
    )

    assert [n["moduleId"] for n in graph["nodes"]].count("bme280") == 3
    assert gate["request_fidelity"]["status"] == "matches"
    assert gate["build_ready"] is False
    assert any("0x77" in blocker and "cannot both work" in blocker for blocker in gate["blockers"])
    assert [f["code"] for f in gate["repairable_findings"]] == ["i2c_address_clash"]


def test_two_clock_chips_on_a_board_with_one_bus_keep_both_and_say_there_is_no_automatic_repair(tmp_path, monkeypatch) -> None:
    _result, gate, graph = _build(tmp_path, monkeypatch, ["arduino-nano", "ds3231_rtc", "ds3231_rtc", "usb-power-5v"], "two_rtc")

    assert [n["moduleId"] for n in graph["nodes"]].count("ds3231_rtc") == 2
    assert gate["build_ready"] is False
    assert any("no automatic repair" in blocker for blocker in gate["blockers"])
