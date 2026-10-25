"""Firmware must reference every microcontroller pin the design wires to a signal."""

from __future__ import annotations

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.firmware_coverage import assess_firmware_coverage

TWO_SERVOS = ["esp32-devkit", "sg90", "sg90", "usb-power-5v"]
HEARTBEAT = "void setup(){pinMode(LED_BUILTIN, OUTPUT);} void loop(){digitalWrite(LED_BUILTIN, 1);}"
SERVO_SKETCH = (
    "const int PAN_PIN = 15; const int TILT_PIN = 16; "
    "void setup(){ledcAttachPin(PAN_PIN,0); ledcAttachPin(TILT_PIN,1);}"
)


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


def test_the_project_package_carries_the_firmware_coverage_the_interface_reads(tmp_path, monkeypatch) -> None:
    result = _build_pan_tilt(tmp_path, monkeypatch)

    assert result["project_package"]["firmware_coverage"] == result["firmware_coverage"]


def _relay_pin_covered(source: str) -> bool:
    graph = _graph(["esp32-devkit", "relay-1ch-5v", "usb-power-5v"])
    assert "GPIO15" in {row["pin"] for row in assess_firmware_coverage(graph, "")["required_pins"]}
    pins = {row["pin"] for row in assess_firmware_coverage(graph, source)["uncovered_pins"]}
    return "GPIO15" not in pins


def test_a_number_that_is_not_used_as_a_pin_does_not_cover_the_pin() -> None:
    """The real servos-plus-relay sketch drove pins 15 and 17 and had `PWM_RES = 16`; the relay on 16 was never driven."""
    source = "const int PAN_PIN = 15; const int PWM_RES = 15; void setup(){ledcSetup(0, 50, PWM_RES);}"

    assert not _relay_pin_covered(source)


def test_a_constant_that_reaches_a_pin_function_covers_the_pin() -> None:
    assert _relay_pin_covered("const int RELAY = 15; void setup(){pinMode(RELAY, OUTPUT);}")
    assert _relay_pin_covered("#define RELAY 15\nvoid loop(){digitalWrite(RELAY, HIGH);}")
    assert _relay_pin_covered("void loop(){digitalWrite(15, HIGH);}")


def test_a_constant_that_is_declared_but_never_used_does_not_cover_the_pin() -> None:
    assert not _relay_pin_covered("const int RELAY_PIN = 15; void setup(){}")


def test_a_gpio_token_in_code_covers_the_pin_but_not_in_a_comment() -> None:
    assert _relay_pin_covered("void setup(){ pinMode(GPIO15, OUTPUT); }")
    assert not _relay_pin_covered("// relay on GPIO15\nvoid setup(){}")


def test_micropython_pin_construction_covers_the_pin() -> None:
    assert _relay_pin_covered("relay = Pin(15, Pin.OUT)\n")
    assert not _relay_pin_covered("# relay = Pin(15, Pin.OUT)\nrelay = None\n")


def test_servos_plus_a_relay_sketch_that_never_drives_the_relay_is_reported_as_a_gap() -> None:
    from hardware_splicer.firmware_scaffold import generate_firmware_scaffold

    graph = _graph(["esp32-devkit", "sg90", "sg90", "relay-1ch-5v", "usb-power-5v"])
    scaffold = generate_firmware_scaffold(build_id="generic_low_voltage_build", build_graph=graph)

    result = assess_firmware_coverage(graph, scaffold["source"])

    assert result["status"] == "gaps"
    assert [row["pin"] for row in result["uncovered_pins"]] == ["GPIO16"]
    assert result["uncovered_pins"][0]["drives"] == "relay-1ch-5v.IN"


def test_the_repos_own_dht22_sketch_passes_its_pin_to_a_constructor_and_covers_it() -> None:
    from hardware_splicer.firmware_scaffold import generate_firmware_scaffold

    graph = _graph(["esp32-devkit", "dht22", "usb-power-5v"])
    scaffold = generate_firmware_scaffold(build_id="sensor_logger", build_graph=graph)
    assert "DHT dht(DHT_PIN" in scaffold["source"]

    assert assess_firmware_coverage(graph, scaffold["source"])["status"] == "covers"


def test_a_constant_used_as_a_non_pin_argument_still_does_not_cover_a_pin() -> None:
    source = "constexpr int PWM_RES = 15;\nvoid setup(){ ledcSetup(0, 50, PWM_RES); }\nvoid writeUs(int channel, int us) {}"

    assert not _relay_pin_covered(source)


def test_a_build_that_fails_before_a_graph_exists_says_the_check_could_not_be_made(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from types import SimpleNamespace

    import hardware_splicer.project_intake as intake_module
    from hardware_splicer import load_project_intake

    for name in ("HARDWARE_SPLICER_OFFLINE_SALVAGE", "HARDWARE_SPLICER_OFFLINE_COMPOSE"):
        monkeypatch.setenv(name, "0")
    failed = SimpleNamespace(compile_result=None, error="compile failed", build_id="x", compile_casefile=None)
    monkeypatch.setattr(intake_module, "compile_scratch_build", lambda **_: failed)
    root = Path(__file__).resolve().parents[1]
    intake = load_project_intake(root / "examples" / "intakes" / "splice_physical_pan_tilt_loop.json")

    result = intake_module.splice_and_build_from_intake(intake, out_dir=tmp_path / "no_graph", export_gerber=False)

    assert not result["artifacts"].get("build_graph")
    assert result["firmware_coverage"]["status"] == "not_assessable"
    assert result["project_package"]["firmware_coverage"]["status"] == "not_assessable"
