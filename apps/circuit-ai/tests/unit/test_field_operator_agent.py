from src.intelligence.field_operator_agent import build_field_operator_next_action


def _topology(*, current=None, current_unit="A", short=False):
    topology = {
        "schema_version": "topology_evidence.v1",
        "instrument_id": "bench_dmm_01",
        "instrument_type": "calibrated_dmm",
        "calibration_status": "valid",
        "recorded_at": "2026-06-02T05:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": "session://field/operator",
        "connectors": [
            {
                "ref": "J1",
                "pins": [
                    {"pin": "1", "net": "VBUS", "role": "power", "voltage": 5.0, "status": "verified"},
                    {"pin": "2", "net": "GND", "role": "ground", "status": "verified"},
                ],
            }
        ],
        "resistance": [
            {
                "target": "power to ground no-short",
                "value": "fail" if short else "pass",
                "notes": "short detected" if short else "",
                "status": "failed" if short else "pass",
            }
        ],
    }
    if current is not None:
        topology["current"] = [
            {
                "target": "current draw under current-limited supply",
                "value": current,
                "unit": current_unit,
                "status": "pass",
            }
        ]
    return topology


def test_field_operator_measures_bounded_unknown_load_next():
    result = build_field_operator_next_action(
        {
            "diy_project": "Build USB load from measured power pins.",
            "topology_evidence": _topology(),
            "constraints": {"current_limit_a": 0.5},
        }
    )
    call = result["operational_call"]

    assert call["action_id"] == "measure_unknown_load_current"
    assert call["action_type"] == "measurement"
    assert call["pass_fail_thresholds"]["steady_current_a_max"] == 0.4
    assert call["pass_fail_thresholds"]["startup_current_a_max"] == 0.5
    assert result["capture_packet"]["expected_input_schema"]["topology_evidence.current[]"]
    assert any(row["model"] == "deepseek_reasoner" for row in result["model_assignments"])


def test_field_operator_blocks_overcurrent_and_assigns_redesign():
    result = build_field_operator_next_action(
        {
            "diy_project": "Build USB load from measured power pins.",
            "topology_evidence": _topology(current=1.2),
            "constraints": {"current_limit_a": 0.5},
        }
    )
    call = result["operational_call"]

    assert call["action_id"] == "resolve_power_budget_failure"
    assert call["authority"] == "operational_block"
    assert call["pass_fail_thresholds"]["limit_a"] == 0.5
    assert call["pass_fail_thresholds"]["over_a"] == 0.7
    assert "Do not run" in call["procedure"][0]


def test_field_operator_hard_stops_short_topology():
    result = build_field_operator_next_action(
        {
            "diy_project": "Build USB load from measured power pins.",
            "topology_evidence": _topology(current=0.1, short=True),
            "constraints": {"current_limit_a": 0.5},
        }
    )
    call = result["operational_call"]

    assert call["action_id"] == "stop_hazard_clearance"
    assert call["authority"] == "hard_stop"
    assert call["pass_fail_thresholds"]["power_allowed"] is False
    assert any(row["model"] == "qwen_vision" for row in result["model_assignments"])


def test_field_operator_requests_topology_when_no_simulation_model_exists():
    result = build_field_operator_next_action(
        {
            "diy_project": "Build a small gadget from junk boards.",
            "qwen_advisory": {"candidate_connector": "J1 may be power"},
        }
    )
    call = result["operational_call"]

    assert call["action_id"] == "capture_topology_or_supply_netlist"
    assert call["action_type"] == "capture_or_measurement"
    assert any(row["model"] == "qwen_vision" for row in result["model_assignments"])
    assert result["capture_packet"]["expected_input_schema"]["topology_evidence"]


def test_field_operator_uses_visual_context_without_misclassifying_intake_as_hazard():
    result = build_field_operator_next_action(
        {
            "goal": "Salvage useful low-voltage functions from this physical board.",
            "board_photo_set": {
                "photo_observations": [
                    {
                        "photo_id": "wide",
                        "provider": "qwen",
                        "board_evidence": {
                            "schema_version": "board_evidence.v1",
                            "connectors": [{"id": "j1", "label": "GPIO header", "kind": "header"}],
                        },
                    }
                ]
            },
        }
    )
    call = result["operational_call"]

    assert call["action_id"] == "capture_topology_or_supply_netlist"
    assert call["authority"] == "operational_advisory"
    assert call["action_type"] == "capture_or_measurement"
    assert "Use Qwen/vision" in call["procedure"][0]
