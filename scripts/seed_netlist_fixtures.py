#!/usr/bin/env python3
"""Seed examples/netlist_fixtures from catalog compose graphs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.netlist.lower import build_graph_to_netlist

FIXTURE_DIR = ROOT / "examples" / "netlist_fixtures"

COMPOSE_FIXTURES = [
    ("usb_esp_dht22", ["usb-power-5v", "esp32-devkit", "dht22"]),
    ("usb_esp_bme280", ["usb-power-5v", "esp32-devkit", "bme280"]),
    ("usb_esp_relay", ["usb-power-5v", "esp32-devkit", "relay-1ch-5v"]),
    ("usb_esp_soil", ["usb-power-5v", "esp32-devkit", "soil_moisture"]),
    ("usb_esp_servo", ["usb-power-5v", "esp32-devkit", "sg90"]),
    ("usb_esp_oled", ["usb-power-5v", "esp32-devkit", "ssd1306-128x64"]),
    ("usb_pico_dht22", ["usb-power-5v", "rpi-pico", "dht22"]),
    ("usb_arduino_relay", ["usb-power-5v", "arduino-nano", "relay-1ch-5v"]),
    ("usb_esp_ch340", ["usb-power-5v", "esp32-devkit", "ch340-usb-ttl"]),
    ("motor_driver_minimal", ["usb-power-5v", "esp32-devkit", "l298n"]),
]


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "id": "esp32_servo_kicad",
            "type": "kicad_netlist",
            "path": "kicad/esp32_servo.net",
            "description": "KiCad netlist ingest (ESP32 + USB + servo ports)",
        }
    ]

    for fixture_id, module_ids in COMPOSE_FIXTURES:
        graph = compose_build_graph_from_module_ids(module_ids)["graph"]
        netlist = build_graph_to_netlist(graph, source=f"fixture:{fixture_id}")
        rel = f"json/{fixture_id}.json"
        out = FIXTURE_DIR / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(netlist.to_dict(), indent=2), encoding="utf-8")
        entries.append(
            {
                "id": fixture_id,
                "type": "netlist_json",
                "path": rel,
                "module_ids": module_ids,
            }
        )

    kicad_dst = FIXTURE_DIR / "kicad" / "esp32_servo.net"
    kicad_dst.parent.mkdir(parents=True, exist_ok=True)
    kicad_src = ROOT / "examples" / "main_ctrl_esp32_servo.net"
    kicad_dst.write_text(kicad_src.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = {"schema_version": "hardware_splicer.netlist_fixtures.v1", "fixtures": entries}
    (FIXTURE_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(entries)} fixtures to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
