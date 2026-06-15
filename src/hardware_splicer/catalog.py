"""Canonical catalog build IDs for the Python compile engine.

Must stay in sync with SUPPORTED_BUILD_IDS in
apps/circuit-ai/circuit-ai-frontend/lib/salvage/plan-to-graph.ts
(verified by scripts/verify_catalog_parity.cjs and tests/test_catalog_parity.py).
"""

from __future__ import annotations

from typing import List

# Sorted for stable diffs; parity script compares as sets.
CATALOG_BUILD_IDS: List[str] = sorted(
    [
        "automatic_plant_watering",
        "automatic_plant_watering_usb",
        "bench_power_adapter",
        "camera_ir_light_or_sensor_mount",
        "generic_low_voltage_build",
        "indicator_or_task_light",
        "inspection_motion_fixture",
        "low_voltage_motor_test_jig",
        "network_status_indicator",
        "plotter_motion_stage",
        "robot_drive_base",
        "room_display_station",
        "salvaged_input_panel",
        "sensor_logger",
        "small_audio_amp_box",
        "smart_relay_box",
        "usb_fume_extractor",
        "usb_uart_debug_adapter",
    ]
)
