from __future__ import annotations

from src.engines.machine_system_engineering import simulate_power_distribution


def test_power_tree_row_current_splits_single_board_sources():
    machine = {
        "boards": [{"board_id": "main_ctrl", "estimated_current_a": 1.27}],
        "power_tree": [
            {
                "source": "usb_vbus",
                "board_id": "main_ctrl",
                "rail": "VIN/3V3",
                "voltage_v": 5.0,
                "max_current_a": 0.5,
                "load_current_a": 0.27,
            },
            {
                "source": "servo_5v_supply",
                "board_id": "main_ctrl",
                "rail": "SERVO_5V",
                "voltage_v": 5.0,
                "max_current_a": 1.5,
                "load_current_a": 1.0,
            },
        ],
    }

    result = simulate_power_distribution(machine, placement={})

    assert result["issues"] == []
    assert result["source_currents_a"] == {"usb_vbus": 0.27, "servo_5v_supply": 1.0}
