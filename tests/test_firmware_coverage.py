"""Firmware must reference every microcontroller pin the design wires to a signal."""

from __future__ import annotations

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.firmware_coverage import assess_firmware_coverage

TWO_SERVOS = ["esp32-devkit", "sg90", "sg90", "usb-power-5v"]
HEARTBEAT = "void setup(){pinMode(LED_BUILTIN, OUTPUT);} void loop(){digitalWrite(LED_BUILTIN, 1);}"
SERVO_SKETCH = "const int PAN_PIN = 15; const int TILT_PIN = 16; void setup(){ledcAttachPin(PAN_PIN,0);}"


def _graph(module_ids: list[str]) -> dict:
    return compose_build_graph_from_module_ids(module_ids)["graph"]


def test_a_heartbeat_sketch_does_not_cover_two_wired_servos() -> None:
    result = assess_firmware_coverage(_graph(TWO_SERVOS), HEARTBEAT)

    assert result["status"] == "gaps"
    assert sorted(row["pin"] for row in result["uncovered_pins"]) == ["GPIO15", "GPIO16"]
    assert {row["drives"] for row in result["uncovered_pins"]} == {"sg90.SIG"}


def test_a_sketch_that_names_both_pins_covers_them() -> None:
    result = assess_firmware_coverage(_graph(TWO_SERVOS), SERVO_SKETCH)

    assert result["status"] == "covers"
    assert result["uncovered_pins"] == []


def test_a_pin_number_inside_another_number_is_not_a_reference() -> None:
    result = assess_firmware_coverage(_graph(TWO_SERVOS), "const int A = 115; const int B = 160;")

    assert result["status"] == "gaps"


def test_bus_pins_are_not_expected_in_the_source_because_the_default_bus_hides_them() -> None:
    graph = _graph(["esp32-devkit", "bme280", "usb-power-5v"])
    result = assess_firmware_coverage(graph, "void setup(){Wire.begin();}")

    assert result["required_pins"] == []
    assert result["status"] == "not_assessable"


def test_a_pin_the_board_data_calls_uart_is_required_when_a_servo_is_wired_to_it() -> None:
    result = assess_firmware_coverage(_graph(TWO_SERVOS), HEARTBEAT)

    assert "GPIO16" in {row["pin"] for row in result["required_pins"]}


def test_no_firmware_or_no_graph_is_not_assessable_never_covers() -> None:
    assert assess_firmware_coverage(_graph(TWO_SERVOS), None)["status"] == "not_assessable"
    assert assess_firmware_coverage(None, HEARTBEAT)["status"] == "not_assessable"


def test_a_design_with_no_signal_pins_has_nothing_to_cover() -> None:
    assert assess_firmware_coverage(_graph(["esp32-devkit", "usb-power-5v"]), HEARTBEAT)["status"] == "not_assessable"


def test_the_result_says_it_only_checks_that_pins_are_named() -> None:
    result = assess_firmware_coverage(_graph(TWO_SERVOS), SERVO_SKETCH)

    assert result["schema_version"] == "hardware_splicer.firmware_coverage.v1"
    assert "compile" in result["claim_boundary"] and "behave" in result["claim_boundary"]


def _build_pan_tilt(tmp_path, monkeypatch):
    from pathlib import Path

    from hardware_splicer import load_project_intake
    from hardware_splicer.project_intake import splice_and_build_from_intake

    # Use the composing route the product uses; the shared test setup forces the offline catalog route.
    for name in ("HARDWARE_SPLICER_OFFLINE_SALVAGE", "HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        monkeypatch.setenv(name, "0")
    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "splice_physical_pan_tilt_loop.json")
    return splice_and_build_from_intake(intake, out_dir=tmp_path / "pan_tilt", export_gerber=False)


def test_the_intake_build_reports_that_the_firmware_covers_the_wired_servos(tmp_path, monkeypatch) -> None:
    import json

    result = _build_pan_tilt(tmp_path, monkeypatch)

    assert result["firmware_coverage"]["status"] == "covers"
    saved = json.loads((tmp_path / "pan_tilt" / "firmware" / "FIRMWARE_COVERAGE.json").read_text())
    assert saved["status"] == "covers"


def test_the_intake_build_reports_the_gap_when_the_firmware_ignores_the_servos(tmp_path, monkeypatch) -> None:
    import hardware_splicer.firmware_scaffold as scaffold

    real = scaffold.generate_firmware_scaffold

    def heartbeat_only(*, build_id, build_graph):
        payload = dict(real(build_id=build_id, build_graph=build_graph))
        payload["source"] = HEARTBEAT
        return payload

    monkeypatch.setattr(scaffold, "generate_firmware_scaffold", heartbeat_only)

    result = _build_pan_tilt(tmp_path, monkeypatch)

    assert result["firmware_coverage"]["status"] == "gaps"
    assert sorted(row["pin"] for row in result["firmware_coverage"]["uncovered_pins"]) == ["GPIO15", "GPIO16"]
