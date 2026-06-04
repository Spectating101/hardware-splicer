from src.intelligence.production_casefile import build_production_casefile


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


def _bench_capture():
    return {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "bench-ch340c-001",
        "operator_id": "operator-1",
        "recorded_at": "2026-05-26T04:00:00Z",
        "instruments": [
            {"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"},
            {"instrument_id": "bench_supply_01", "instrument_type": "current_limited_supply", "calibration_status": "valid"},
            {"instrument_id": "thermal_probe_01", "instrument_type": "thermal_probe", "calibration_status": "valid"},
        ],
        "artifacts": [
            {"kind": "photo", "uri": "session://bench/ch340c/pinout-photo"},
            {"kind": "measurement_log", "uri": "session://bench/ch340c/measurement-log"},
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
        "measurements": [
            {"kind": "resistance", "target": "power to ground no-short", "value": "pass", "status": "pass"},
            {"kind": "continuity", "target": "connector ground to exposed ground", "value": "pass", "status": "pass"},
            {"kind": "voltage", "target": "logic high voltage", "value": "3.3", "status": "pass"},
            {"kind": "current", "target": "current draw under current-limited supply", "value": "pass", "status": "pass"},
            {"kind": "thermal", "target": "thermal behavior after first power", "value": "normal", "status": "pass"},
        ],
    }


def _outcome():
    return {
        "decision": "reused",
        "selected_resource_ids_used": ["topology_j1"],
        "measurements_recorded": True,
        "cash_spent_usd": 0,
        "value_recovered_usd": 8,
        "time_spent_minutes": 18,
        "deviations_from_plan": [],
        "failure_or_stop_reason": "",
        "output_function_verified": True,
        "first_power_result": "pass",
        "thermal_result": "normal",
        "current_limit_used": True,
        "evidence_uri": "session://bench/ch340c/outcome",
    }


def _release():
    return {
        "release_id": "REL-CH340C-001",
        "selected_resource_ids": ["topology_j1"],
        "released_by": "operator-1",
        "released_at": "2026-05-26T05:00:00Z",
        "scope_statement": "Release is limited to measured CH340C UART header.",
        "artifact_uris": ["session://bench/ch340c/release"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def test_production_casefile_keeps_visual_candidate_at_measurement_capture():
    casefile = build_production_casefile(
        {
            "goal": "reuse this CH340C board as a USB serial debug adapter",
            "device_hint": "CH340C serial adapter",
            "board_evidence": _board_evidence(),
            "required_capabilities": ["usb_serial", "connector"],
            "strategy_mode": "constrained",
            "target_authority_level": "production_repair",
        }
    )

    assert casefile["summary"]["current_authority_level"] == "visual_candidate"
    assert casefile["release_report"]["decision"] == "measurement_capture_required"
    assert casefile["authority_ledger"]["can"]["claim_production_repair_release"] is False
    assert casefile["measurement_capture_packet"]["bench_topology_capture_template"]["connectors"]
    assert casefile["field_operator"]["operational_call"]["action_id"] == "capture_topology_or_supply_netlist"


def test_production_casefile_closes_full_low_voltage_release():
    casefile = build_production_casefile(
        {
            "goal": "reuse this CH340C board as a USB serial debug adapter",
            "device_hint": "CH340C serial adapter",
            "board_evidence": _board_evidence(),
            "bench_topology_capture": _bench_capture(),
            "outcome_history": [_outcome()],
            "production_release": _release(),
            "required_capabilities": ["usb_serial", "connector"],
            "strategy_mode": "constrained",
            "target_authority_level": "production_repair",
        }
    )

    assert casefile["summary"]["current_authority_level"] == "production_repair"
    assert casefile["summary"]["production_authorized"] is True
    assert casefile["release_report"]["decision"] == "production_repair_authorized"
    assert casefile["authority_ledger"]["authority_score"] == 1.0
    assert casefile["release_report"]["remaining_tasks"] == []
