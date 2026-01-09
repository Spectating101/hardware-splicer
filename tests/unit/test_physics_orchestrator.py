from src.engines.physics_orchestrator import validate_high_level_design


def test_orchestrator_returns_json_friendly_payload():
    design = {
        "microcontroller": "esp32",
        "components": ["bme280"],
        "power_source": {"type": "usb", "voltage_v": 5.0, "current_limit_a": 0.5},
        "scenario": "max",
    }

    out = validate_high_level_design(design)

    assert "rails" in out.compiled
    assert "netlist" in out.compiled
    assert "node_v" in out.results
    assert isinstance(out.issues, list)
