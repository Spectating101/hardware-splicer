from __future__ import annotations

import pytest

from hardware_splicer.module_resolver import resolve_parts_to_modules


PART_CASES = [
    ("ESP32 DevKit", "microcontroller", "esp32-devkit"),
    ("ESP32-WROOM board", "mcu", "esp32-devkit"),
    ("Arduino Nano clone", "microcontroller", "arduino-nano"),
    ("Raspberry Pi Pico", "mcu", "rpi-pico"),
    ("soil moisture sensor", "sensor", "soil_moisture"),
    ("DHT22 temp humidity", "sensor", "dht22"),
    ("BME280 breakout", "sensor", "bme280"),
    ("IRLZ44N MOSFET module", "driver", "mosfet-irlz44n"),
    ("IRF520 driver", "driver", "mosfet-irlz44n"),
    ("relay module 5v", "driver", "relay-1ch-5v"),
    ("L298N motor driver", "driver", "l298n"),
    ("SG90 servo", "actuator", "sg90"),
    ("USB power bank", "power_source", "usb-power-5v"),
    ("phone charger 5v", "power", "usb-power-5v"),
    ("12V barrel supply", "power_source", "dc-barrel-12v"),
    ("LM2596 buck", "power_regulator", "buck-lm2596"),
    ("MP1584 mini buck", "regulator", "buck-mp1584"),
    ("SSD1306 OLED", "display", "ssd1306"),
    ("mini pump 5v", "pump", "mini-pump-5v"),
    ("cooling fan 5v", "fan", "cooling_fan_5v"),
    ("CH340 USB serial", "interface", "usb-uart"),
    ("HC-SR04 ultrasonic", "sensor", None),
    ("peristaltic pump", "pump", "mini-pump-5v"),
    ("MOSFET driver board", "driver", "mosfet-irlz44n"),
    ("logic level mosfet", "driver", "mosfet-irlz44n"),
    ("TP4056 charger", "power", "tp4056"),
    ("wall wart 12v", "power", "dc-barrel-12v"),
    ("USB 5V wall wart", "power_source", "usb-power-5v"),
    ("esp32 devkit v1", "mcu", "esp32-devkit"),
    ("moisture sensor for plants", "sensor", "soil_moisture"),
    ("IRLZ44N", "driver", "mosfet-irlz44n"),
]


@pytest.mark.parametrize("name,part_type,expected", PART_CASES)
def test_resolve_part_name(name: str, part_type: str, expected: str | None) -> None:
    resolved = resolve_parts_to_modules([{"name": name, "type": part_type}])
    module_id = resolved[0].get("module_id") if resolved else None
    if expected is None:
        assert module_id is None or isinstance(module_id, str)
    else:
        assert module_id == expected, f"{name} -> {module_id}"
