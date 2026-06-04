from src.intelligence.board_omniscience_map import build_board_omniscience_map


def _trusted():
    return {
        "instrument_id": "bench_dmm_01",
        "instrument_type": "calibrated_dmm",
        "calibration_status": "valid",
        "recorded_at": "2026-06-02T05:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": "session://omniscience/topology",
    }


def _visual_usb_uart_photo_set():
    return {
        "goal": "inspect this board and work out reuse options",
        "board_photo_set": {
            "photo_observations": [
                {
                    "photo_id": "wide",
                    "view_hint": "wide angled board photo",
                    "provider": "qwen",
                    "board_evidence": {
                        "schema_version": "board_evidence.v1",
                        "components": [{"id": "u1", "label": "unknown USB bridge IC", "kind": "integrated_circuit"}],
                        "connectors": [{"id": "j1", "label": "USB connector", "kind": "connector"}],
                        "damage": [],
                    },
                },
                {
                    "photo_id": "marking",
                    "view_hint": "marking closeup",
                    "provider": "qwen",
                    "board_evidence": {
                        "schema_version": "board_evidence.v1",
                        "markings": [{"id": "m1", "marking": "CH340C", "label": "CH340C marking"}],
                        "connectors": [{"id": "h1", "label": "UART header", "kind": "header"}],
                        "damage": [],
                    },
                },
            ]
        },
    }


def _uart_topology():
    return {
        "schema_version": "topology_evidence.v1",
        **_trusted(),
        "connectors": [
            {
                "ref": "J1",
                "label": "measured low-voltage UART header",
                "pins": [
                    {"pin": "1", "net": "VBUS", "role": "power", "voltage": 5.0, "status": "verified"},
                    {"pin": "2", "net": "GND", "role": "ground", "status": "verified"},
                    {"pin": "3", "net": "TXD", "role": "uart_tx", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "4", "net": "RXD", "role": "uart_rx", "logic_voltage": 3.3, "status": "verified"},
                ],
            }
        ],
        "resistance": [{"target": "power to ground no-short", "value": "pass", "status": "pass", "unit": "ohm"}],
        "voltage": [{"target": "input voltage and polarity", "value": 5.0, "status": "pass", "unit": "V"}],
        "current": [{"target": "current draw under current-limited supply", "value": 0.12, "status": "pass", "unit": "A"}],
        "thermal": [{"target": "thermal behavior after first power", "value": "normal", "status": "pass", "unit": "C"}],
    }


def _bench_capture():
    return {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "bench-uart-001",
        "operator_id": "operator-1",
        "recorded_at": "2026-06-02T05:00:00Z",
        "instruments": [{"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"}],
        "artifacts": [{"kind": "measurement_log", "uri": "session://omniscience/bench-log"}],
        "connectors": _uart_topology()["connectors"],
        "measurements": [
            {"kind": "resistance", "target": "power to ground no-short", "value": "pass", "status": "pass"},
            {"kind": "voltage", "target": "logic high voltage", "value": "3.3", "status": "pass"},
            {"kind": "current", "target": "USB-side current draw and no backfeed", "value": "pass", "status": "pass"},
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
        "evidence_uri": "session://omniscience/outcome",
    }


def _release():
    return {
        "release_id": "REL-OMNI-001",
        "selected_resource_ids": ["topology_j1"],
        "released_by": "operator-1",
        "released_at": "2026-06-02T05:20:00Z",
        "scope_statement": "Release is limited to measured low-voltage UART adapter reuse.",
        "artifact_uris": ["session://omniscience/release"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def test_omniscience_map_keeps_visual_only_as_candidate_and_routes_to_topology_capture():
    result = build_board_omniscience_map(_visual_usb_uart_photo_set())

    assert result["summary"]["production_authorized"] is False
    assert result["summary"]["authority_level"] == "visual_candidate"
    assert result["summary"]["next_best_action_id"] == "capture_topology_or_supply_netlist"
    assert result["model_routes"]["qwen_vision"]["never_treat_as"][0] == "measured pinout"


def test_omniscience_map_uses_measured_topology_and_routes_to_remaining_uart_gate():
    result = build_board_omniscience_map(
        {
            "diy_project": "Build a USB UART debug adapter from a measured low-voltage header.",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _uart_topology(),
        }
    )

    assert result["summary"]["authority_level"] == "electrical_simulation"
    assert result["dimensions"]["measured_topology"]["status"] == "pass"
    assert result["next_evidence_batch"][0]["action_id"] == "close_gate_profile_usb_uart_debug_adapter_2"
    assert "USB-side current draw" in result["next_evidence_batch"][0]["prompt"]


def test_omniscience_map_closes_scoped_production_release():
    result = build_board_omniscience_map(
        {
            "goal": "release a measured low-voltage UART debug adapter repair",
            "board_evidence": {
                "schema_version": "board_evidence.v1",
                "components": [{"id": "u1", "label": "CH340C USB serial bridge IC", "kind": "integrated_circuit"}],
                "connectors": [{"id": "j1", "label": "UART header", "kind": "header"}],
                "damage": [],
            },
            "bench_topology_capture": _bench_capture(),
            "outcome_history": [_outcome()],
            "production_release": _release(),
            "required_capabilities": ["usb_serial", "connector"],
            "strategy_mode": "constrained",
            "target_authority_level": "production_repair",
        }
    )

    assert result["summary"]["omniscience_level"] == "scoped_production_repair_map"
    assert result["summary"]["omniscience_score"] == 1.0
    assert result["summary"]["next_best_action_id"] is None
    assert result["next_evidence_batch"] == []
