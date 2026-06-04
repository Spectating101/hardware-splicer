from src.intelligence.authority_ledger import build_authority_ledger


def _visual_board():
    return {
        "goal": "salvage useful low-voltage board functions",
        "board_evidence": {
            "schema_version": "board_evidence.v1",
            "components": [{"id": "u1", "label": "USB bridge IC", "kind": "integrated_circuit"}],
            "connectors": [{"id": "j1", "label": "GPIO header", "kind": "header"}],
            "markings": [{"id": "m1", "label": "CH340C"}],
            "damage": [],
            "test_points": [],
            "salvage_candidates": [{"id": "s1", "label": "GPIO header reuse"}],
        },
        "use_reference_catalog": False,
    }


def _measured_topology(*, short=False):
    return {
        "schema_version": "topology_evidence.v1",
        "instrument_id": "bench_dmm_01",
        "instrument_type": "calibrated_dmm",
        "calibration_status": "valid",
        "recorded_at": "2026-06-02T05:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": "session://authority-ledger/topology",
        "connectors": [
            {
                "ref": "J1",
                "label": "measured low-voltage header",
                "pins": [
                    {"pin": "1", "net": "VBUS", "role": "power", "voltage": 5.0, "status": "verified"},
                    {"pin": "2", "net": "GND", "role": "ground", "status": "verified"},
                    {"pin": "3", "net": "TXD", "role": "uart_tx", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "4", "net": "RXD", "role": "uart_rx", "logic_voltage": 3.3, "status": "verified"},
                ],
            }
        ],
        "resistance": [
            {
                "target": "power to ground no-short",
                "value": "fail" if short else "pass",
                "status": "failed" if short else "pass",
                "instrument_id": "bench_dmm_01",
                "instrument_type": "calibrated_dmm",
                "calibration_status": "valid",
                "recorded_at": "2026-06-02T05:01:00Z",
                "operator_id": "operator-1",
                "evidence_uri": "session://authority-ledger/no-short",
            }
        ],
        "current": [
            {
                "target": "current draw under current-limited supply",
                "value": 0.12,
                "unit": "A",
                "status": "pass",
                "instrument_id": "bench_meter_01",
                "instrument_type": "inline_power_meter",
                "calibration_status": "valid",
                "recorded_at": "2026-06-02T05:02:00Z",
                "operator_id": "operator-1",
                "evidence_uri": "session://authority-ledger/current",
            }
        ],
        "thermal": [
            {
                "target": "thermal behavior after first power",
                "value": "normal",
                "status": "pass",
                "instrument_id": "thermal_probe_01",
                "instrument_type": "thermal_probe",
                "calibration_status": "valid",
                "recorded_at": "2026-06-02T05:03:00Z",
                "operator_id": "operator-1",
                "evidence_uri": "session://authority-ledger/thermal",
            }
        ],
    }


def _public_reference_topology():
    return {
        "schema_version": "topology_evidence.v1",
        "source_type": "public_reference_topology",
        "reference_uri": "https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html",
        "connectors": [
            {
                "ref": "J1",
                "label": "SparkFun CH340C FTDI-style header",
                "pins": [
                    {"pin": "1", "net": "DTR", "role": "dtr"},
                    {"pin": "2", "net": "RXI", "role": "rxi", "logic_voltage": 3.3},
                    {"pin": "3", "net": "TXO", "role": "txo", "logic_voltage": 3.3},
                    {"pin": "4", "net": "VCC", "role": "vcc", "voltage": 3.3},
                    {"pin": "5", "net": "CTS", "role": "cts"},
                    {"pin": "6", "net": "GND", "role": "gnd"},
                ],
            }
        ],
    }


def test_authority_ledger_keeps_qwen_visual_case_candidate_only():
    ledger = build_authority_ledger(_visual_board())
    stages = {stage["stage_id"]: stage for stage in ledger["stages"]}

    assert ledger["current_authority_level"] == "visual_candidate"
    assert stages["visual_candidate"]["status"] == "pass"
    assert stages["measured_topology"]["status"] == "open"
    assert ledger["can"]["use_visual_candidates"] is True
    assert ledger["can"]["use_measured_pinout"] is False
    assert ledger["can"]["claim_production_repair_release"] is False
    assert "production repair release" in stages["visual_candidate"]["blocked_actions"]


def test_authority_ledger_advances_measured_topology_and_simulation_without_release():
    ledger = build_authority_ledger(
        {
            "diy_project": "Build a USB UART debug adapter from a measured low-voltage header.",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _measured_topology(),
            "constraints": {"current_limit_a": 0.5},
            "use_reference_catalog": False,
        }
    )
    stages = {stage["stage_id"]: stage for stage in ledger["stages"]}

    assert stages["measured_topology"]["status"] == "pass"
    assert stages["electrical_simulation"]["status"] == "pass"
    assert ledger["current_authority_level"] in {"measured_topology", "electrical_simulation"}
    assert ledger["can"]["use_measured_pinout"] is True
    assert ledger["can"]["claim_production_repair_release"] is False
    assert stages["controlled_bench"]["status"] == "open"


def test_authority_ledger_keeps_public_reference_simulation_planning_only():
    ledger = build_authority_ledger(
        {
            "goal": "reuse public-reference SparkFun CH340C serial header",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "topology_evidence": _public_reference_topology(),
            "board_evidence": {
                "schema_version": "board_evidence.v1",
                "components": [{"id": "u1", "label": "CH340C", "kind": "integrated_circuit"}],
                "connectors": [{"id": "j1", "label": "FTDI-style header", "kind": "header"}],
                "markings": [{"id": "m1", "label": "CH340C"}],
                "damage": [],
                "test_points": [],
                "salvage_candidates": [{"id": "s1", "label": "USB serial adapter reuse"}],
            },
            "use_reference_catalog": False,
        }
    )
    stages = {stage["stage_id"]: stage for stage in ledger["stages"]}

    assert ledger["current_authority_level"] == "visual_candidate"
    assert stages["measured_topology"]["status"] == "open"
    assert ledger["evidence_summary"]["topology"]["measurement_backed"] is False
    assert ledger["evidence_summary"]["topology"]["reference_only"] is True
    assert "public reference topology attached" in stages["measured_topology"]["evidence"]
    assert stages["electrical_simulation"]["status"] == "open"
    assert ledger["can"]["use_electrical_simulation"] is False
    assert ledger["can"]["use_measured_pinout"] is False
    assert ledger["can"]["power_or_splice_now"] is False


def test_authority_ledger_blocks_measured_short():
    ledger = build_authority_ledger(
        {
            "diy_project": "Reuse a measured low-voltage header.",
            "topology_evidence": _measured_topology(short=True),
            "constraints": {"current_limit_a": 0.5},
            "use_reference_catalog": False,
        }
    )
    stages = {stage["stage_id"]: stage for stage in ledger["stages"]}

    assert stages["measured_topology"]["status"] == "blocked"
    assert ledger["current_authority_level"] == "blocked_safety_or_electrical"
    assert ledger["can"]["use_measured_pinout"] is False


def test_authority_ledger_treats_authorized_production_casefile_as_scoped_top_authority():
    ledger = build_authority_ledger(
        {
            "hardware_plan": {
                "analysis": {},
                "integrated_plan": {
                    "production_repair_authority": {
                        "authorized": True,
                        "decision": "authorized_low_voltage_repair_release",
                        "authority_casefile": {"status": "release_ready", "blocked_claim_count": 0},
                        "blockers": [],
                    }
                },
            },
            "outcome_history": [
                {
                    "output_function_verified": True,
                    "first_power_result": "pass",
                    "thermal_result": "normal",
                    "evidence_uri": "session://outcome/release-ready",
                }
            ],
        }
    )
    stages = {stage["stage_id"]: stage for stage in ledger["stages"]}

    assert ledger["current_authority_level"] == "production_repair"
    assert ledger["authority_score"] == 1.0
    assert ledger["next_unlocks"] == []
    assert stages["production_repair"]["status"] == "pass"
    assert stages["measured_topology"]["status"] == "pass"
    assert "covered by authorized production repair casefile" in stages["measured_topology"]["evidence"][-1]
