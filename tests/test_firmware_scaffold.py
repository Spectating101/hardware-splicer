from __future__ import annotations

from hardware_splicer.firmware_scaffold import generate_firmware_from_salvage, generate_firmware_scaffold


def test_firmware_scaffold_for_esp32_build():
    payload = generate_firmware_scaffold(
        build_id="sensor_logger",
        build_graph={
            "nodes": [
                {"id": "n1", "moduleId": "esp32-devkit"},
                {"id": "n2", "moduleId": "bme280"},
            ],
            "wires": [],
        },
    )
    assert payload["mcu_family"] == "esp32"
    assert payload["filename"].endswith(".ino")
    assert "sensor_logger" in payload["source"]


def test_firmware_scaffold_plant_watering_has_pump_logic():
    payload = generate_firmware_scaffold(
        build_id="automatic_plant_watering",
        build_graph={"nodes": [{"id": "n1", "moduleId": "esp32-devkit"}], "wires": []},
    )
    assert "PUMP_PIN" in payload["source"]
    assert "SOIL_PIN" in payload["source"]


def test_firmware_scaffold_plant_watering_pins_from_graph():
    payload = generate_firmware_scaffold(
        build_id="automatic_plant_watering",
        build_graph={
            "nodes": [
                {"id": "n1", "moduleId": "esp32-devkit"},
                {"id": "n2", "moduleId": "soil_moisture"},
                {"id": "n3", "moduleId": "mosfet-irlz44n"},
            ],
            "wires": [
                {"id": "w1", "from": {"nodeId": "n2", "pinId": "A0"}, "to": {"nodeId": "n1", "pinId": "GPIO34"}},
                {"id": "w2", "from": {"nodeId": "n1", "pinId": "GPIO4"}, "to": {"nodeId": "n3", "pinId": "SIG"}},
            ],
        },
    )
    assert "SOIL_PIN = 34" in payload["source"]
    assert "PUMP_PIN = 4" in payload["source"]
    assert payload["pins"]["sourced_from_graph"] is True


def test_salvage_relay_sketch():
    payload = generate_firmware_from_salvage(
        build_id="smart_relay_box",
        bringup_card={
            "gpio_assignments": [
                {"from_pin": "GPIO26", "to_role": "rly", "to_pin": "SIG", "purpose": "relay control"},
            ]
        },
        module_ids=["esp32-devkit", "relay-1ch-5v"],
        goal="wifi lamp relay",
    )
    assert "RELAY_PIN = 26" in payload["source"]
    assert payload["pins"].get("relay") == 26


def test_salvage_pan_tilt_dual_servo_pins():
    payload = generate_firmware_from_salvage(
        build_id="inspection_motion_fixture",
        bringup_card={
            "gpio_assignments": [
                {"from_pin": "GPIO18", "to_role": "svo", "to_pin": "SIG", "purpose": "servo pan"},
                {"from_pin": "GPIO19", "to_role": "svo", "to_pin": "SIG", "purpose": "servo tilt"},
            ]
        },
        module_ids=["esp32-devkit", "sg90", "sg90"],
        goal="pan tilt mount",
    )
    assert "PAN_PIN = 18" in payload["source"]
    assert "TILT_PIN = 19" in payload["source"]
    assert payload["pins"].get("servo_pan") == 18
    assert payload["pins"].get("servo_tilt") == 19


def test_pan_tilt_graph_gpio_zero_not_replaced_by_default():
    """Regression: `pins.get('servo_pan') or 18` treated GPIO0 as missing."""
    from hardware_splicer.firmware_scaffold import generate_firmware_scaffold

    payload = generate_firmware_scaffold(
        build_id="inspection_motion_fixture",
        build_graph={
            "nodes": [
                {"id": "n1", "moduleId": "esp32-devkit"},
                {"id": "n2", "moduleId": "sg90"},
                {"id": "n3", "moduleId": "sg90"},
            ],
            "wires": [
                {"from": {"nodeId": "n1", "pinId": "GPIO18"}, "to": {"nodeId": "n2", "pinId": "SIG"}},
                {"from": {"nodeId": "n1", "pinId": "GPIO16"}, "to": {"nodeId": "n3", "pinId": "SIG"}},
            ],
        },
    )
    assert payload["pins"].get("servo_pan") == 18
    assert payload["pins"].get("servo_tilt") == 16
    assert "PAN_PIN = 18" in payload["source"]
    assert "TILT_PIN = 16" in payload["source"]


def test_salvage_fume_fan_pin():
    payload = generate_firmware_from_salvage(
        build_id="usb_fume_extractor",
        bringup_card={
            "gpio_assignments": [
                {"from_pin": "GPIO25", "to_label": "mosfet", "to_pin": "SIG", "purpose": "fan control"},
            ]
        },
        module_ids=["esp32-devkit", "cooling_fan_5v", "mosfet-irlz44n"],
        goal="usb fume extractor",
    )
    assert "FAN_PIN = 25" in payload["source"]
