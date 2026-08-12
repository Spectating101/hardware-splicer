from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.bench_capture_bridge import (
    bench_capture_to_splice_measurements,
    build_bench_capture_template_from_gates,
)
from hardware_splicer.splice_bench import SESSION_FILE, submit_bench_measurements


def _gate(
    *,
    gate_id: str,
    board_id: str,
    measurement_id: str,
    expected_unit: str | None = None,
    lower: float | None = None,
    upper: float | None = None,
) -> dict:
    return {
        "gate_id": gate_id,
        "source": "evidence_recipe",
        "prompt": f"Controlled stimulus: {measurement_id}",
        "stage": "before_power_on",
        "critical": True,
        "block_id": "driver",
        "board_id": board_id,
        "gate_type": "interface_measurement",
        "status": "open",
        "measurement": None,
        "closed_at": None,
        "notes": [],
        "interface_id": f"if:{board_id}:driver",
        "phase_id": "controlled_stimulus",
        "measurement_id": measurement_id,
        "expected_unit": expected_unit,
        "lower": lower,
        "upper": upper,
        "required": True,
        "validators": [],
    }


def test_structured_measurement_identity_selects_matching_board_gate() -> None:
    gates = [
        _gate(
            gate_id="evidence_if_board_a_driver_measurement_response_observed",
            board_id="board_a",
            measurement_id="response_observed",
        ),
        _gate(
            gate_id="evidence_if_board_b_driver_measurement_response_observed",
            board_id="board_b",
            measurement_id="response_observed",
        ),
    ]
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "operator_id": "operator_01",
        "measurements": [
            {
                "measurement_id": "response_observed",
                "kind": "functional_response",
                "status": "pass",
                "value": "pass",
                "method": "protected_stimulus_response",
                "instrument_id": "dmm_01",
                "interface_selector": {"board_id": "board_b"},
                "notes": "Expected output transition observed.",
            }
        ],
    }

    mapped = bench_capture_to_splice_measurements(capture, gates=gates)

    assert len(mapped) == 1
    assert mapped[0]["gate_id"] == "evidence_if_board_b_driver_measurement_response_observed"
    assert mapped[0]["operator"] == "operator_01"
    assert mapped[0]["method"] == "protected_stimulus_response"
    assert mapped[0]["instrument_id"] == "dmm_01"


def test_structured_measurement_identity_fails_closed_when_ambiguous() -> None:
    gates = [
        _gate(
            gate_id="evidence_if_board_a_driver_measurement_response_observed",
            board_id="board_a",
            measurement_id="response_observed",
        ),
        _gate(
            gate_id="evidence_if_board_b_driver_measurement_response_observed",
            board_id="board_b",
            measurement_id="response_observed",
        ),
    ]
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "operator_id": "operator_01",
        "measurements": [
            {
                "measurement_id": "response_observed",
                "status": "pass",
                "value": "pass",
                "method": "protected_stimulus_response",
            }
        ],
    }

    assert bench_capture_to_splice_measurements(capture, gates=gates) == []


def test_qualitative_interface_measurement_template_does_not_invent_numeric_unit() -> None:
    gate = _gate(
        gate_id="evidence_if_board_driver_measurement_response_observed",
        board_id="board",
        measurement_id="response_observed",
    )

    template = build_bench_capture_template_from_gates([gate], project_name="bench")
    row = template["measurements"][0]

    assert row["kind"] == "functional_response"
    assert "unit" not in row


def test_qualitative_interface_observation_can_close_but_numeric_still_requires_unit(
    tmp_path: Path,
) -> None:
    response_gate = _gate(
        gate_id="evidence_if_board_driver_measurement_response_observed",
        board_id="board",
        measurement_id="response_observed",
    )
    voltage_gate = _gate(
        gate_id="evidence_if_board_driver_measurement_idle_voltage_v",
        board_id="board",
        measurement_id="idle_voltage_v",
        expected_unit="V",
        lower=0.0,
        upper=5.5,
    )
    session = {
        "schema_version": "hardware_splicer.splice_bench.v1",
        "build_dir": str(tmp_path),
        "gates": [response_gate, voltage_gate],
    }
    (tmp_path / SESSION_FILE).write_text(json.dumps(session), encoding="utf-8")

    response = submit_bench_measurements(
        tmp_path,
        [
            {
                "gate_id": response_gate["gate_id"],
                "status": "verified",
                "value": "pass",
                "method": "protected_stimulus_response",
                "instrument_id": "dmm_01",
                "operator": "operator_01",
                "notes": "Expected output transition observed.",
            }
        ],
    )
    stored_response = next(row for row in response["gates"] if row["gate_id"] == response_gate["gate_id"])
    assert stored_response["status"] == "closed"
    assert stored_response["measurement"]["instrument_id"] == "dmm_01"

    numeric = submit_bench_measurements(
        tmp_path,
        [
            {
                "gate_id": voltage_gate["gate_id"],
                "status": "verified",
                "value": 3.3,
                "method": "dmm_dc_voltage",
                "instrument_id": "dmm_01",
                "operator": "operator_01",
            }
        ],
    )
    applied = numeric["last_submission"]["applied"][0]
    assert applied["ok"] is False
    assert applied["error"] == "measurement_validation_failed"
    assert "unit" in applied["reason"]
