from __future__ import annotations

from hardware_splicer.mechanism_bridge import (
    build_mecha_project_spec,
    mechanism_kinds_present,
    select_mechanism_kind,
)


def test_select_pan_tilt_from_dual_servos():
    kind = select_mechanism_kind(
        build_id="inspection_motion_fixture",
        goal="pan tilt camera",
        resolved_modules=[
            {"role": "mcu", "module_id": "esp32-devkit"},
            {"role": "svo", "module_id": "sg90"},
            {"role": "svo", "module_id": "sg90"},
        ],
    )
    assert kind == "pan_tilt"


def test_select_enclosure_for_sensor_logger():
    kind = select_mechanism_kind(
        build_id="sensor_logger",
        goal="wifi dht logger",
        resolved_modules=[
            {"role": "mcu", "module_id": "esp32-devkit"},
            {"role": "sns", "module_id": "dht22"},
        ],
    )
    assert kind == "enclosure"


def test_build_pan_tilt_spec_has_pan_tilt_key():
    selected = build_mecha_project_spec(
        project_name="pt",
        build_id="inspection_motion_fixture",
        goal="pan tilt",
        resolved_modules=[
            {"role": "svo", "module_id": "sg90"},
            {"role": "svo", "module_id": "sg90"},
        ],
    )
    assert selected["kind"] == "pan_tilt"
    assert "pan_tilt" in selected["project_spec"]
    assert "enclosure" in selected["project_spec"]


def test_mechanism_kinds_present_aliases():
    assert "enclosure" in mechanism_kinds_present({"kind": "enclosure"})
    assert "pan_tilt" in mechanism_kinds_present({"kind": "pan_tilt"})
    assert "drive_base" in mechanism_kinds_present({"kind": "mobile_drive"})
