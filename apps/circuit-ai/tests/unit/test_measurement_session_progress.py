from src.api.v1 import main as main_module
from src.intelligence.measurement_session_progress import build_measurement_session_progress


def _board_evidence():
    return {
        "schema_version": "board_evidence.v1",
        "components": [{"id": "u1", "label": "CH340C USB serial bridge IC", "kind": "integrated_circuit"}],
        "markings": [{"id": "m1", "marking": "CH340C"}],
        "connectors": [
            {"id": "usb_c", "label": "USB-C connector", "kind": "connector"},
            {"id": "uart_header", "label": "UART header", "kind": "header"},
        ],
        "damage": [],
        "salvage_candidates": [{"id": "s1", "label": "UART debug header reuse"}],
    }


def _base_payload(**extra):
    payload = {
        "goal": "reuse this CH340C board as a USB serial debug adapter",
        "device_hint": "CH340C serial adapter",
        "board_evidence": _board_evidence(),
        "required_capabilities": ["usb_serial", "connector"],
        "strategy_mode": "constrained",
        "target_authority_level": "production_repair",
        "constraints": {"current_limit_a": 0.5},
        "use_reference_catalog": False,
    }
    payload.update(extra)
    return payload


def _capture(measurements):
    return {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "bench-progress-001",
        "operator_id": "operator-1",
        "recorded_at": "2026-06-02T07:00:00Z",
        "instruments": [
            {"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"},
            {"instrument_id": "bench_supply_01", "instrument_type": "current_limited_supply", "calibration_status": "valid"},
            {"instrument_id": "thermal_probe_01", "instrument_type": "thermal_probe", "calibration_status": "valid"},
        ],
        "artifacts": [
            {"kind": "photo", "uri": "session://progress/pinout"},
            {"kind": "measurement_log", "uri": "session://progress/log"},
        ],
        "connectors": [
            {
                "ref": "J1",
                "label": "bench verified CH340C UART header",
                "pins": [
                    {"pin": "1", "net": "DTR", "role": "dtr", "status": "verified"},
                    {"pin": "2", "net": "RXI", "role": "rxi", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "3", "net": "TXO", "role": "txo", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "4", "net": "VCC", "role": "vcc", "voltage": 3.3, "status": "verified"},
                    {"pin": "5", "net": "CTS", "role": "cts", "status": "verified"},
                    {"pin": "6", "net": "GND", "role": "gnd", "status": "verified"},
                ],
            }
        ],
        "measurements": measurements,
    }


def _complete_measurements():
    return [
        {"kind": "resistance", "target": "power to ground no-short", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "connector ground to exposed ground", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "voltage", "target": "input voltage and polarity", "value": 3.3, "unit": "V", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "current", "target": "current draw under current-limited supply", "value": 0.12, "unit": "A", "status": "pass", "instrument_id": "bench_supply_01"},
        {"kind": "thermal", "target": "thermal behavior after first power", "value": "normal", "status": "pass", "instrument_id": "thermal_probe_01"},
        {"kind": "voltage", "target": "logic high voltage", "value": 3.3, "unit": "V", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "UART Header (uart_header) pin-1/orientation confirmation", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "UART Header (uart_header) ground reference continuity: 6:GND", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "voltage", "target": "UART Header (uart_header) supply voltage and polarity: 4:VCC", "value": 3.3, "unit": "V", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "resistance", "target": "UART Header (uart_header) supply-to-ground no-short: 4:VCC vs 6:GND", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "voltage", "target": "UART Header (uart_header) logic voltage domain: 2:RXI, 3:TXO", "value": 3.3, "unit": "V", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "UART Header (uart_header) signal pin continuity map: 2:RXI, 3:TXO", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "USB-C Connector (usb_c) pin-1/orientation confirmation", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "resistance", "target": "USB-C Connector (usb_c) supply-to-ground no-short: VBUS:VBUS vs GND:GND", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "voltage", "target": "USB-C Connector (usb_c) supply voltage and polarity: VBUS:VBUS", "value": 5.0, "unit": "V", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "USB-C Connector (usb_c) ground reference continuity: GND:GND", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "USB-C Connector (usb_c) USB data pair protection/path confirmation: D+:USB_DP, D-:USB_DM", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
        {"kind": "continuity", "target": "USB-C Connector (usb_c) high-speed/shield reference check: D+:USB_DP, D-:USB_DM", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
    ]


def test_measurement_session_starts_waiting_with_template_and_next_prompt():
    progress = build_measurement_session_progress(_base_payload(), include_authority_closure=False)

    assert progress["status"] == "waiting_for_measurements"
    assert progress["progress"]["closed_count"] == 0
    assert progress["progress"]["open_count"] > 0
    assert progress["next_measurement"]["kind"] == "resistance"
    assert progress["draft_bench_topology_capture"]["connectors"]


def test_measurement_session_tracks_partial_capture_without_authority_ready():
    partial = _complete_measurements()[:3]
    progress = build_measurement_session_progress(
        _base_payload(bench_topology_capture=_capture(partial)),
        include_authority_closure=True,
    )

    assert progress["status"] == "measurement_in_progress"
    assert progress["progress"]["closed_count"] == 3
    assert progress["progress"]["open_count"] > 0
    assert progress["progress"]["authority_packet_ready"] is False
    assert progress["authority_closure"]["capture_integrity"]["verdict"] == "measurement_capture_incomplete"


def test_measurement_session_marks_authority_packet_ready_before_optional_template_exhaustion():
    progress = build_measurement_session_progress(
        _base_payload(bench_topology_capture=_capture(_complete_measurements())),
        include_authority_closure=True,
    )

    assert progress["status"] == "authority_packet_ready"
    assert progress["progress"]["authority_packet_ready"] is True
    assert progress["progress"]["closed_count"] >= 5
    assert progress["next_measurement"]["action_id"] == "submit_authority_closure"
    assert progress["authority_closure"]["authority_after"]["can"]["use_measured_pinout"] is True


def test_measurement_session_api_returns_progress_metadata():
    response = main_module.hardware_measurement_session_progress(
        _base_payload(bench_topology_capture=_capture(_complete_measurements()[:2])),
        include_authority_closure=False,
        current_user={"user_id": "operator-1"},
    )

    assert response["metadata"]["user_id"] == "operator-1"
    assert response["metadata"]["status"] == "measurement_in_progress"
    assert response["metadata"]["open_count"] > 0
    assert response["metadata"]["next_action_id"].startswith("record_")
