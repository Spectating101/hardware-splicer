import json
from pathlib import Path

from hardware_splicer.bench_capture_bridge import build_bench_capture_template_from_gates
from hardware_splicer.bench_loop import build_simulated_capture
from hardware_splicer.splice_bench import (
    SESSION_FILE,
    _gates_from_evidence_integrations,
    submit_bench_measurements,
)


def _package():
    return {
        "evidence_integrations": {
            "interfaces": [
                {
                    "blockers": ["signals.control.direction"],
                    "interface_contract": {
                        "interface_id": "if:enabot:driver",
                        "board_id": "enabot",
                        "block_id": "driver",
                        "unresolved_fields": ["signals.control.direction"],
                    },
                    "bench_recipe": {
                        "phases": [
                            {
                                "phase_id": "idle_voltage",
                                "title": "Measure idle logic voltage",
                                "measurements": [
                                    {
                                        "measurement_id": "idle_voltage_v",
                                        "description": "Idle contact voltage",
                                        "unit": "V",
                                        "lower": 0.0,
                                        "upper": 5.5,
                                        "required": True,
                                    }
                                ],
                            }
                        ]
                    },
                }
            ]
        }
    }


def test_evidence_interfaces_generate_contract_and_measurement_gates() -> None:
    gates = _gates_from_evidence_integrations(_package())
    assert len(gates) == 2

    field_gate = next(row for row in gates if row["gate_type"] == "interface_contract_field")
    assert field_gate["requires_contract_edit"] is True
    assert field_gate["evidence_field"] == "signals.control.direction"
    assert field_gate["critical"] is True

    measurement_gate = next(row for row in gates if row["gate_type"] == "interface_measurement")
    assert measurement_gate["measurement_id"] == "idle_voltage_v"
    assert measurement_gate["expected_unit"] == "V"
    assert measurement_gate["lower"] == 0.0
    assert measurement_gate["upper"] == 5.5
    assert measurement_gate["required"] is True


def test_capture_template_separates_contract_actions_from_measurements() -> None:
    gates = _gates_from_evidence_integrations(_package())
    template = build_bench_capture_template_from_gates(gates, project_name="robot")

    assert len(template["contract_actions"]) == 1
    assert template["contract_actions"][0]["action"] == "update_interface_contract"
    assert template["contract_actions"][0]["evidence_field"] == "signals.control.direction"
    assert len(template["measurements"]) == 1
    measurement = template["measurements"][0]
    assert measurement["measurement_id"] == "idle_voltage_v"
    assert measurement["unit"] == "V"
    assert measurement["lower"] == 0.0
    assert measurement["upper"] == 5.5

    simulated = build_simulated_capture(template)
    assert len(simulated["measurements"]) == 1
    assert simulated["measurements"][0]["value"] == 3.3
    assert simulated["measurements"][0]["unit"] == "V"


def test_structural_contract_gate_cannot_be_closed_by_scalar_submission(tmp_path: Path) -> None:
    gates = _gates_from_evidence_integrations(_package())
    session = {
        "schema_version": "hardware_splicer.splice_bench.v1",
        "build_dir": str(tmp_path),
        "gates": gates,
    }
    (tmp_path / SESSION_FILE).write_text(json.dumps(session), encoding="utf-8")

    field_gate = next(row for row in gates if row["gate_type"] == "interface_contract_field")
    measurement_gate = next(row for row in gates if row["gate_type"] == "interface_measurement")

    result = submit_bench_measurements(
        tmp_path,
        [
            {
                "gate_id": field_gate["gate_id"],
                "status": "verified",
                "value": "input",
                "method": "operator assertion",
            },
            {
                "gate_id": measurement_gate["gate_id"],
                "status": "verified",
                "value": 3.3,
                "unit": "V",
                "method": "DMM",
            },
        ],
    )

    applied = {row["gate_id"]: row for row in result["last_submission"]["applied"]}
    assert applied[field_gate["gate_id"]]["error"] == "contract_edit_required"
    assert applied[measurement_gate["gate_id"]]["ok"] is True

    stored = {row["gate_id"]: row for row in result["gates"]}
    assert stored[field_gate["gate_id"]]["status"] == "open"
    assert stored[measurement_gate["gate_id"]]["status"] == "closed"
    assert result["power_on_authorized"] is False
    assert result["critical_open_count"] == 1


def test_out_of_range_evidence_measurement_stays_blocked(tmp_path: Path) -> None:
    gates = _gates_from_evidence_integrations(_package())
    measurement_gate = next(row for row in gates if row["gate_type"] == "interface_measurement")
    session = {
        "schema_version": "hardware_splicer.splice_bench.v1",
        "build_dir": str(tmp_path),
        "gates": [measurement_gate],
    }
    (tmp_path / SESSION_FILE).write_text(json.dumps(session), encoding="utf-8")

    result = submit_bench_measurements(
        tmp_path,
        [{
            "gate_id": measurement_gate["gate_id"],
            "status": "verified",
            "value": 8.0,
            "unit": "V",
            "method": "DMM",
        }],
    )

    applied = result["last_submission"]["applied"][0]
    assert applied["error"] == "measurement_validation_failed"
    assert "upper bound" in applied["reason"]
    assert result["gates"][0]["status"] == "blocked"
    assert result["power_on_authorized"] is False


def test_wrong_unit_evidence_measurement_stays_blocked(tmp_path: Path) -> None:
    gates = _gates_from_evidence_integrations(_package())
    measurement_gate = next(row for row in gates if row["gate_type"] == "interface_measurement")
    session = {
        "schema_version": "hardware_splicer.splice_bench.v1",
        "build_dir": str(tmp_path),
        "gates": [measurement_gate],
    }
    (tmp_path / SESSION_FILE).write_text(json.dumps(session), encoding="utf-8")

    result = submit_bench_measurements(
        tmp_path,
        [{
            "gate_id": measurement_gate["gate_id"],
            "status": "verified",
            "value": 3.3,
            "unit": "A",
            "method": "DMM",
        }],
    )

    applied = result["last_submission"]["applied"][0]
    assert applied["error"] == "measurement_validation_failed"
    assert "expected" in applied["reason"]
    assert result["gates"][0]["status"] == "blocked"
