from src.intelligence.field_model_advisory import build_field_model_advisory


def test_field_model_advisory_dry_run_uses_visual_measurement_context():
    result = build_field_model_advisory(
        {
            "goal": "Salvage useful low-voltage functions from this physical board.",
            "board_evidence": {
                "schema_version": "board_evidence.v1",
                "connectors": [{"id": "j1", "label": "GPIO header", "kind": "header"}],
            },
            "visual_topology_hypothesis": {
                "readiness": {"can_power_or_splice": False},
                "measurement_queue": [
                    {
                        "task_id": "measure_ground",
                        "target": "GPIO header ground reference",
                        "measurement_type": "continuity",
                        "prompt": "Find ground by continuity.",
                    }
                ],
            },
        },
        live=False,
    )

    preview = result["prompt_preview"]

    assert result["mode"] == "dry_run"
    assert result["field_action_id"] == "capture_topology_or_supply_netlist"
    assert "GPIO header" in preview
    assert "measure_ground" in preview
    assert result["advisory"]["warnings"] == ["live flag was not set"]
