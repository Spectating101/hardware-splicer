from src.api.v1 import main as main_module
from src.intelligence.measurement_authority_closure import build_measurement_authority_closure


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


def _bench_capture(*, artifacts=True):
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "bench-ch340c-001",
        "operator_id": "operator-1",
        "recorded_at": "2026-06-02T06:00:00Z",
        "instruments": [
            {"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"},
            {"instrument_id": "bench_supply_01", "instrument_type": "current_limited_supply", "calibration_status": "valid"},
            {"instrument_id": "thermal_probe_01", "instrument_type": "thermal_probe", "calibration_status": "valid"},
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
            {"kind": "resistance", "target": "power to ground no-short", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
            {"kind": "continuity", "target": "connector ground to exposed ground", "value": "pass", "status": "pass", "instrument_id": "bench_dmm_01"},
            {"kind": "voltage", "target": "logic high voltage", "value": 3.3, "unit": "V", "status": "pass", "instrument_id": "bench_dmm_01"},
            {"kind": "current", "target": "current draw under current-limited supply", "value": 0.12, "unit": "A", "status": "pass", "instrument_id": "bench_supply_01"},
            {"kind": "thermal", "target": "thermal behavior after first power", "value": "normal", "status": "pass", "instrument_id": "thermal_probe_01"},
        ],
    }
    if artifacts:
        capture["artifacts"] = [
            {"kind": "photo", "uri": "session://bench/ch340c/pinout-photo"},
            {"kind": "measurement_log", "uri": "session://bench/ch340c/measurement-log"},
        ]
    return capture


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
        "release_id": "REL-MEASURE-CLOSE-001",
        "selected_resource_ids": ["topology_j1"],
        "released_by": "operator-1",
        "released_at": "2026-06-02T06:30:00Z",
        "scope_statement": "Release is limited to measured CH340C UART header reuse.",
        "artifact_uris": ["session://bench/ch340c/release"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def _payload(**extra):
    body = {
        "goal": "reuse this CH340C board as a USB serial debug adapter",
        "device_hint": "CH340C serial adapter",
        "board_evidence": _board_evidence(),
        "required_capabilities": ["usb_serial", "connector"],
        "strategy_mode": "constrained",
        "target_authority_level": "production_repair",
        "constraints": {"current_limit_a": 0.5},
        "use_reference_catalog": False,
    }
    body.update(extra)
    return body


def test_measurement_closure_keeps_visual_only_at_capture_packet():
    closure = build_measurement_authority_closure(
        _payload(),
        include_casefile=False,
        include_omniscience=False,
    )

    assert closure["authority_after"]["current_authority_level"] == "visual_candidate"
    assert closure["capture_integrity"]["verdict"] == "measurement_capture_required"
    assert closure["capture_packet"]["bench_topology_capture_template"]["connectors"]
    assert closure["capture_packet"]["visual_topology_measurement_queue"]
    assert closure["next_action"]["action_id"] == "record_bench_topology_capture"


def test_measurement_closure_advances_measured_capture_without_claiming_release():
    closure = build_measurement_authority_closure(
        _payload(bench_topology_capture=_bench_capture()),
        include_casefile=True,
        include_omniscience=False,
    )
    after = closure["authority_after"]
    integrity = closure["capture_integrity"]

    assert integrity["verdict"] == "production_measurement_packet_ready"
    assert integrity["missing_measurement_categories"] == []
    assert integrity["missing_trusted_categories"] == []
    assert integrity["missing_artifact_categories"] == []
    assert after["can"]["use_measured_pinout"] is True
    assert after["can"]["claim_production_repair_release"] is False
    assert closure["authority_delta"]["level_delta"] >= 1
    assert "measured_topology" in closure["authority_delta"]["newly_passed_stages"]
    assert closure["next_action"]["action_id"] in {"record_controlled_bench_outcome", "run_controlled_bench_outcome"}


def test_measurement_closure_blocks_incomplete_artifact_provenance():
    closure = build_measurement_authority_closure(
        _payload(bench_topology_capture=_bench_capture(artifacts=False)),
        include_casefile=False,
        include_omniscience=False,
    )
    integrity = closure["capture_integrity"]

    assert integrity["verdict"] == "measurement_capture_incomplete"
    assert "evidence_uri" in integrity["missing_root_provenance"]
    assert set(integrity["missing_artifact_categories"]) == {"continuity", "current", "resistance", "thermal", "voltage"}
    assert closure["authority_after"]["can"]["claim_production_repair_release"] is False
    assert closure["next_action"]["action_id"] == "complete_measurement_capture"


def test_measurement_closure_closes_full_production_release_scope():
    closure = build_measurement_authority_closure(
        _payload(
            bench_topology_capture=_bench_capture(),
            outcome_history=[_outcome()],
            production_release=_release(),
        )
    )

    assert closure["authority_after"]["current_authority_level"] == "production_repair"
    assert closure["authority_after"]["authority_score"] == 1.0
    assert closure["authority_after"]["can"]["claim_production_repair_release"] is True
    assert closure["production_casefile"]["summary"]["production_authorized"] is True
    assert closure["board_omniscience_map"]["summary"]["production_authorized"] is True
    assert closure["board_omniscience_map"]["summary"]["omniscience_score"] == 1.0
    assert closure["next_action"]["action_id"] == "release_ready"


def test_measurement_authority_closure_api_returns_delta_metadata():
    response = main_module.hardware_measurement_authority_close(
        _payload(bench_topology_capture=_bench_capture()),
        include_casefile=False,
        include_omniscience=False,
        current_user={"user_id": "operator-1"},
    )

    assert response["metadata"]["user_id"] == "operator-1"
    assert response["metadata"]["score_delta"] > 0
    assert response["measurement_authority_closure"]["capture_integrity"]["pinout_known"] is True
