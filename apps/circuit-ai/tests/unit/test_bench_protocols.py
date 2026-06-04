from src.intelligence.bench_protocols import build_bench_protocol_pack


def test_bench_protocol_pack_for_uart_requires_loopback_artifacts():
    pack = build_bench_protocol_pack(
        primary_function_id="usb_serial_debug_bridge",
        capabilities=["usb_serial", "connector"],
        matched_parts=[
            {
                "part_id": "ch340_usb_uart",
                "canonical_part": "CH340C",
                "family": "USB/UART bridge",
                "verification_required": ["measured pinout", "logic voltage", "loopback"],
            }
        ],
        authority_status="visual_only",
    )

    assert pack["schema_version"] == "bench_protocol_pack.v1"
    assert pack["primary_function_id"] == "usb_serial_debug_bridge"
    assert "logic" in pack["required_measurement_categories"]
    assert any(step["lane_id"] == "loopback" for step in pack["steps"])
    assert any("loopback" in artifact for artifact in pack["release_artifacts_required"])
    assert any("CH340C" in control for control in pack["setup_controls"])
    assert pack["model_policy"]["llm_can_clear_required_steps"] is False


def test_bench_protocol_pack_for_battery_is_specialist_only():
    pack = build_bench_protocol_pack(
        primary_function_id="battery_or_charger",
        capabilities=["battery", "power"],
        authority_status="visual_only",
    )

    assert pack["specialist_only"] is True
    assert "specialist_authority" in {step["required_before"] for step in pack["steps"]}
    assert "Specialist-only" in pack["release_boundary"]
