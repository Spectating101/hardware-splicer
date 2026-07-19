from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .integrations.jlcsearch_client import JlcSearchClient


SCHEMA_VERSION = "hardware_splicer.bom.v1"

_MODULE_LABELS: Dict[str, str] = {
    "esp32-devkit": "ESP32 DevKit (Wi-Fi/BLE MCU)",
    "soil_moisture": "Capacitive soil moisture sensor",
    "buck-mp1584": "MP1584 adjustable buck (5V pump rail)",
    "buck-lm2596": "LM2596 buck regulator",
    "mosfet-irlz44n": "IRLZ44N logic-level MOSFET module",
    "mosfet-irf520": "IRF520 MOSFET module",
    "dc-barrel-12v": "12V DC barrel jack input",
    "sg90": "SG90 micro servo",
    "l298n": "L298N dual H-bridge",
    "relay-1ch": "1-channel relay module",
    "dht22": "DHT22 temp/humidity sensor",
    "rpi-pico": "Raspberry Pi Pico",
    "arduino-nano": "Arduino Nano",
    "tp4056": "TP4056 Li-ion charger",
    "fan-5v": "5V DC fan",
    "mini-pump-5v": "5V mini water pump",
    "usb-power-5v": "USB 5V power input",
    "ch340-usb-ttl": "CH340 USB-TTL serial adapter",
    "pir-hc-sr501": "HC-SR501 PIR motion sensor",
    "nrf24l01": "nRF24L01+ 2.4GHz radio",
    "ldo-ams1117-3v3": "AMS1117 3.3V LDO module",
    "ldo-ams1117-5v": "AMS1117 5V LDO module",
    "bme280": "BME280 environmental sensor",
    "hc-sr04": "HC-SR04 ultrasonic range sensor",
    "ssd1306-128x64": "SSD1306 OLED 128x64",
    "relay-1ch-5v": "1-channel 5V relay module",
    "mpu6050": "MPU6050 6-axis IMU",
    "level-shifter-4ch": "4-channel logic level shifter",
    "ili9341_tft": "ILI9341 2.4\" SPI color TFT",
    "max98357a-i2s-amp": "MAX98357A I2S class-D amplifier",
    "esp32-cam-module": "ESP32-CAM camera module",
    "a4988-stepper": "A4988 stepper motor driver",
    "limit-switch-3pin": "3-pin mechanical limit switch",
}

_PART_HINTS: Dict[str, Dict[str, str]] = {
    "esp32-devkit": {"mpn": "ESP32-WROOM-32", "footprint": "ESP32-DEVKITC-32E", "supplier_sku": "ESP32-DEVKITC-32E"},
    "soil_moisture": {"mpn": "Capacitive-Soil-Moisture-v1.2", "footprint": "SOIL-MOISTURE-3PIN", "supplier_sku": "SKU-SOIL-CAP"},
    "buck-mp1584": {"mpn": "MP1584EN", "footprint": "BUCK-MP1584-MODULE", "supplier_sku": "MP1584-DC-DC"},
    "buck-lm2596": {"mpn": "LM2596S-ADJ", "footprint": "BUCK-LM2596-MODULE", "supplier_sku": "LM2596-DC-DC"},
    "mosfet-irlz44n": {"mpn": "IRLZ44NPBF", "footprint": "MOSFET-LOGIC-MODULE", "supplier_sku": "IRLZ44N-MOD"},
    "mosfet-irf520": {"mpn": "IRF520NPBF", "footprint": "MOSFET-IRF520-MODULE", "supplier_sku": "IRF520-MOD"},
    "l298n": {"mpn": "L298N", "footprint": "L298N-HBRIDGE-MODULE", "supplier_sku": "L298N-MOD"},
    "relay-1ch": {"mpn": "SRD-05VDC-SL-C", "footprint": "RELAY-1CH-5V", "supplier_sku": "RELAY-1CH-5V"},
    "sg90": {"mpn": "SG90", "footprint": "SG90-SERVO", "supplier_sku": "SG90-MICRO"},
    "dht22": {"mpn": "DHT22", "footprint": "DHT22-SENSOR", "supplier_sku": "DHT22-AM2302"},
    "rpi-pico": {"mpn": "RP2040", "footprint": "Raspberry_Pi_Pico", "supplier_sku": "SC0915"},
    "arduino-nano": {"mpn": "ATmega328P-AU", "footprint": "Arduino_Nano", "supplier_sku": "A000005"},
    "tp4056": {"mpn": "TP4056", "footprint": "TP4056-CHARGER", "supplier_sku": "TP4056-MOD"},
    "fan-5v": {"mpn": "Fan-5V-40mm", "footprint": "FAN-5V-2PIN", "supplier_sku": "FAN-5V-40"},
    "mini-pump-5v": {"mpn": "Mini-Submersible-Pump-5V", "footprint": "PUMP-5V-MINI", "supplier_sku": "PUMP-5V"},
    "dc-barrel-12v": {"mpn": "DC-005", "footprint": "BarrelJack_CUI_PJ-002A", "supplier_sku": "DC-BARREL-12V"},
    "usb-power-5v": {"mpn": "USB-Micro-B-5V", "footprint": "USB-MICRO-POWER", "supplier_sku": "USB-5V-IN"},
    "ch340-usb-ttl": {"mpn": "CH340G", "footprint": "USB-TTL-CH340", "supplier_sku": "CH340G-USB-TTL"},
    "pir-hc-sr501": {"mpn": "HC-SR501", "footprint": "HC-SR501-PIR", "supplier_sku": "HC-SR501"},
    "nrf24l01": {"mpn": "NRF24L01+", "footprint": "NRF24L01-MODULE", "supplier_sku": "NRF24L01-PA-LNA"},
    "ldo-ams1117-3v3": {"mpn": "AMS1117-3.3", "footprint": "AMS1117-3V3-MODULE", "supplier_sku": "AMS1117-3.3"},
    "ldo-ams1117-5v": {"mpn": "AMS1117-5.0", "footprint": "AMS1117-5V-MODULE", "supplier_sku": "AMS1117-5.0"},
    "bme280": {"mpn": "BME280", "footprint": "BME280-SENSOR", "supplier_sku": "BME280-BREAKOUT"},
    "hc-sr04": {"mpn": "HC-SR04", "footprint": "HC-SR04-ULTRASONIC", "supplier_sku": "HC-SR04"},
    "ssd1306-128x64": {"mpn": "SSD1306", "footprint": "SSD1306-OLED-128X64", "supplier_sku": "SSD1306-I2C"},
    "relay-1ch-5v": {"mpn": "SRD-05VDC-SL-C", "footprint": "RELAY-1CH-5V", "supplier_sku": "RELAY-1CH-5V"},
    "mpu6050": {"mpn": "MPU-6050", "footprint": "MPU6050-IMU", "supplier_sku": "MPU6050-BREAKOUT"},
    "level-shifter-4ch": {"mpn": "TXS0108E", "footprint": "LEVEL-SHIFTER-4CH", "supplier_sku": "LOGIC-LEVEL-4CH"},
    "ili9341_tft": {"mpn": "ILI9341", "footprint": "ILI9341-TFT-2.4", "supplier_sku": "ILI9341-SPI-240"},
    "max98357a-i2s-amp": {"mpn": "MAX98357A", "footprint": "MAX98357A-I2S-AMP", "supplier_sku": "MAX98357A-BRK"},
    "esp32-cam-module": {"mpn": "ESP32-CAM", "footprint": "ESP32-CAM-MODULE", "supplier_sku": "ESP32-CAM"},
    "a4988-stepper": {"mpn": "A4988", "footprint": "A4988-STEPPER", "supplier_sku": "A4988-DRIVER"},
    "limit-switch-3pin": {"mpn": "SS-5GL2", "footprint": "LIMIT-SWITCH-3PIN", "supplier_sku": "LIMIT-SW-3P"},
}


def build_bom_from_graph(
    graph: Mapping[str, Any],
    *,
    resolved_modules: List[Mapping[str, Any]] | None = None,
    salvaged_refs: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    nodes = list(graph.get("nodes") or [])
    inventory_by_module = {
        str(row.get("module_id")): str(row.get("part_name") or "")
        for row in (resolved_modules or [])
        if row.get("module_id")
    }
    lines: List[Dict[str, Any]] = []
    for index, node in enumerate(nodes, start=1):
        module_id = str(node.get("moduleId") or node.get("module_id") or "")
        if not module_id:
            continue
        ref = str(node.get("ref") or f"U{index}")
        salvaged = inventory_by_module.get(module_id) or (salvaged_refs or {}).get(module_id)
        hints = dict(_PART_HINTS.get(module_id) or {})
        synthetic_support = bool(node.get("supportComponentId"))
        lines.append(
            {
                "ref": ref,
                "module_id": module_id,
                "description": str(node.get("value") or _MODULE_LABELS.get(module_id, module_id)),
                "mpn": hints.get("mpn", ""),
                "footprint": str(node.get("footprint") or hints.get("footprint") or "MOD-2.54HDR"),
                "supplier_sku": hints.get("supplier_sku", ""),
                "qty": 1,
                "source": "synthetic_support" if synthetic_support else "salvage" if salvaged else "catalog",
                "salvaged_part": salvaged or "",
                "node_id": str(node.get("id") or ""),
                **(
                    {"support_component_id": node.get("supportComponentId")}
                    if node.get("supportComponentId")
                    else {}
                ),
                **({"operator_id": node.get("operatorId")} if node.get("operatorId") else {}),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "line_count": len(lines),
        "lines": lines,
    }


def _jlc_enrich_enabled() -> bool:
    return os.environ.get("HARDWARE_SPLICER_JLC_ENRICH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def enrich_bom_with_jlcsearch(
    bom: Mapping[str, Any],
    *,
    client: Optional["JlcSearchClient"] = None,
) -> Dict[str, Any]:
    """Attach LCSC/JLC hints for passives when jlcsearch API is reachable."""
    if not _jlc_enrich_enabled():
        return dict(bom)

    from .integrations.jlcsearch_client import JlcSearchClient

    client = client or JlcSearchClient()
    enriched_lines: List[Dict[str, Any]] = []
    for row in bom.get("lines") or []:
        line = dict(row)
        module_id = str(line.get("module_id") or "")
        if module_id.startswith("resistor-"):
            try:
                value = module_id.replace("resistor-", "").replace("_", ".")
                hits = client.search_resistors(resistance=value, package="0603", limit=1)
                if hits:
                    hit = hits[0]
                    line["jlc_lcsc"] = str(hit.get("lcsc") or hit.get("lcsc_id") or "")
                    line["jlc_mpn"] = str(hit.get("mpn") or hit.get("manufacturer_part_number") or "")
            except Exception:
                pass
        elif module_id.startswith("capacitor-"):
            try:
                value = module_id.replace("capacitor-", "").replace("_", ".")
                hits = client.search_capacitors(capacitance=value, package="0603", limit=1)
                if hits:
                    hit = hits[0]
                    line["jlc_lcsc"] = str(hit.get("lcsc") or hit.get("lcsc_id") or "")
                    line["jlc_mpn"] = str(hit.get("mpn") or hit.get("manufacturer_part_number") or "")
            except Exception:
                pass
        # Bouni-style CPL fields when footprint/position metadata already on the line
        if line.get("footprint") and not line.get("jlc_cpl_footprint"):
            line["jlc_cpl_footprint"] = str(line.get("footprint") or "")
        if line.get("ref") and not line.get("jlc_designator"):
            line["jlc_designator"] = str(line.get("ref") or "")
        for pos_key in ("mid_x", "mid_y", "rotation", "layer"):
            if line.get(pos_key) is not None and f"jlc_{pos_key}" not in line:
                line[f"jlc_{pos_key}"] = line.get(pos_key)
        enriched_lines.append(line)

    out = dict(bom)
    out["lines"] = enriched_lines
    out["jlc_enriched"] = True
    out["jlc_cpl_shape"] = True
    return out


def write_bom_artifacts(bom: Mapping[str, Any], out_dir: str | Path) -> Dict[str, str]:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "BOM.json"
    csv_path = target / "BOM.csv"
    json_path.write_text(json.dumps(dict(bom), indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ref",
                "module_id",
                "description",
                "mpn",
                "footprint",
                "supplier_sku",
                "jlc_lcsc",
                "jlc_mpn",
                "jlc_designator",
                "jlc_cpl_footprint",
                "jlc_mid_x",
                "jlc_mid_y",
                "jlc_rotation",
                "jlc_layer",
                "qty",
                "source",
                "salvaged_part",
                "node_id",
            ],
        )
        writer.writeheader()
        for row in bom.get("lines") or []:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    return {"bom_json": str(json_path), "bom_csv": str(csv_path)}
