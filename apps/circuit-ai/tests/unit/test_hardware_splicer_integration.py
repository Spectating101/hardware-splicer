from pathlib import Path

from src.engines.cam.splicer_engine import SplicerEngine
from src.engines.machine_system_engineering import resolve_mecha_splicer_root, run_mecha_bridge
from src.utils.bridge_adapter import BridgeAdapter


def test_resolve_mecha_splicer_root_handles_consolidated_layout():
    root = resolve_mecha_splicer_root()

    assert root is not None
    assert (root / "scripts" / "mecha_splicer_spec.py").exists()


def test_run_mecha_bridge_generates_bundle_without_3d_service():
    machine = {
        "machine_name": "BridgeSmoke",
        "boards": [
            {
                "board_id": "main_ctrl",
                "pcb_outline_mm": [80, 50, 1.6],
                "capabilities": {"pwm_channels": 2, "actuation_current_budget_a": 0.8},
            }
        ],
    }
    mechanism = {
        "project_name": "bridge_smoke",
        "pan_tilt": {"name": "pt", "pan_servo": "sg90", "tilt_servo": "sg90"},
    }

    result = run_mecha_bridge(
        machine,
        mechanism,
        simulation_fidelity="starter",
        use_3d_splicer=False,
    )

    assert result["ok"] is True
    assert result["returncode"] == 0
    assert Path(result["bundle_file"]).exists()
    assert result["simulation"]
    assert result["use_3d_splicer"] is False


def test_bridge_adapter_payload_matches_3d_splicer_contract():
    payload = BridgeAdapter.sanitize_vision_data(
        {
            "device_name": "demo_board",
            "width": 80,
            "height": 50,
            "thickness": 1.6,
            "ports": [{"label": "usb", "box": [35, -1, 45, 3]}],
            "mounts": [{"x_mm": 6, "y_mm": 6, "diameter_mm": 2.2}],
        }
    )

    assert payload["version"] == "v1"
    assert payload["device"] == "demo_board"
    assert {"width_mm", "height_mm", "thickness_mm", "corner_radius_mm"} <= set(payload["pcb"])
    assert {"wall_mm", "clearance_mm", "lip_mm", "fillet_mm"} <= set(payload["enclosure"])
    assert payload["ports"][0]["type"] == "rect"
    assert payload["ports"][0]["side"] in {"left", "right", "top", "bottom"}
    assert "diameter_mm" in payload["mounts"][0]


def test_splicer_engine_derives_matching_script_endpoint(monkeypatch):
    monkeypatch.setenv("SPLICER_API_URL", "http://splicer.local")
    monkeypatch.setenv("SPLICER_ENDPOINT", "/generate")
    monkeypatch.delenv("SPLICER_SCRIPT_ENDPOINT", raising=False)

    engine = SplicerEngine()

    assert engine.api_url == "http://splicer.local"
    assert engine.endpoint == "/generate"
    assert engine.script_endpoint == "/generate/script"
