from __future__ import annotations

from hardware_splicer.firmware_scaffold import generate_firmware_scaffold


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
