from __future__ import annotations

import pytest

from hardware_splicer.robotics_simulation import build_robotics_simulation_packet


def test_robotics_simulation_testing_mode_clears_blockers(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_TESTING_MODE", "1")
    payload = {
        "project": {
            "constraints": {"max_speed_mps": 99},
        },
        "platform": {
            "wheel_diameter_mm": 65,
            "motor_max_rpm": 10,
        },
    }
    packet = build_robotics_simulation_packet(payload)
    assert packet.get("simulation_ready") is True
    assert packet.get("blocking_finding_count") == 0
