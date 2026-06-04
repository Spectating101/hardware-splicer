"""One-shot ingester: data/component_cache/component_database.json -> TypeScript ModuleSpec[].

Pin roles are inferred from pin name + function text using a vocabulary
adapted to the existing PinRole enum. Voltage ranges parsed from common
strings. Curated entries (already in the hand-written library) are skipped
by part_number/id overlap so curated wins.

Output: circuit-ai-frontend/lib/modules/ingested.ts (committed alongside
the curated module-library.ts).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = json.load(open(ROOT / "data/component_cache/component_database.json"))
OUT = ROOT / "circuit-ai-frontend/lib/modules/ingested.ts"
CURATED = ROOT / "circuit-ai-frontend/lib/modules/module-library.ts"
curated_text = CURATED.read_text()

# Which curated ids/part numbers are already covered (skip DB duplicates).
CURATED_KEYS = set(re.findall(r'id:\s*"([^"]+)"', curated_text)) | set(
    re.findall(r"buck-lm2596|ams1117|mp1584|mt3608|tp4056|level-shifter|dht22|bme280|hc-sr04|mpu6050|ssd1306|relay-1ch|mosfet-irf520|l298n|sg90|nrf24l01|ch340", curated_text)
)

# --- Pin-name -> PinRole inference -----------------------------------------
# Ordered: more specific first.
def infer_role(name: str, fn: str = "") -> str:
    n = name.strip().upper()
    f = (fn or "").lower()
    # FUNCTION TEXT WINS when it explicitly names a role — pin names like SDA
    # can mean SPI-CS on chips like the RC522.
    if "chip select" in f or "slave select" in f or "spi cs" in f or f.strip() == "cs":
        return "spi_cs"
    if "spi mosi" in f or ("mosi" in f and "spi" in f):
        return "spi_mosi"
    if "spi miso" in f or ("miso" in f and "spi" in f):
        return "spi_miso"
    if "spi clock" in f or "spi sck" in f:
        return "spi_sck"
    if "i2c data" in f:
        return "i2c_sda"
    if "i2c clock" in f:
        return "i2c_scl"
    if "uart tx" in f or "serial tx" in f or "transmit data" in f:
        return "uart_tx"
    if "uart rx" in f or "serial rx" in f or "receive data" in f:
        return "uart_rx"
    if "pwm" in f:
        return "pwm"
    # Power/ground (function text first, then name)
    if "ground" in f or n in {"GND", "GND-", "VSS", "0V"} or (n.endswith("-") and "gnd" in f):
        return "gnd"
    if ("power" in f and "input" in f) or ("supply" in f and "input" in f) or n in {"VCC", "VDD", "VIN", "V+", "VBAT", "VBUS", "VSYS", "IN+"}:
        return "power_in"
    if ("regulated" in f and "output" in f) or n in {"5V", "3V3", "3.3V", "VOUT", "OUT+", "BAT+", "1.8V"}:
        return "power_out"
    # Bus pin names as fallback when function didn't explicitly classify
    if n == "SDA":
        return "i2c_sda"
    if n == "SCL":
        return "i2c_scl"
    if n == "MOSI":
        return "spi_mosi"
    if n == "MISO":
        return "spi_miso"
    if n in {"SCK"}:
        return "spi_sck"
    if n in {"CS", "CSN", "SS"}:
        return "spi_cs"
    if n in {"TX", "TXD"}:
        return "uart_tx"
    if n in {"RX", "RXD"}:
        return "uart_rx"
    # Analog
    if re.fullmatch(r"A\d+", n) or "analog" in f or "adc" in f:
        return "analog_in"
    if n in {"VOUT", "OUT"} and "analog" in f:
        return "analog_in"
    # PWM hints
    if "pwm" in f:
        return "pwm"
    # Digital IO / direction hints
    if re.fullmatch(r"(IN|IN\d+)", n) or "input" in f:
        return "digital_in"
    if re.fullmatch(r"(OUT|OUT\d+|DO|DOUT)", n) or ("output" in f and "voltage" not in f):
        return "digital_out"
    if re.fullmatch(r"D\d+", n) or n == "DATA":
        return "digital_io"
    if n in {"RST", "RESET", "EN", "ENABLE"}:
        return "reset"
    return "other"


def parse_voltage_range(s):
    """Returns [lo, hi] in volts, or None."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    # "3.3-5V", "4.5-24V", "3-6V DC"
    m = re.match(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*V", s, re.I)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    # "3.3V/5V" or "3.3V or 5V" — multiple distinct voltages
    parts = re.findall(r"(\d+\.?\d*)\s*V", s, re.I)
    if len(parts) >= 2:
        vs = sorted(set(float(p) for p in parts))
        if vs[0] != vs[-1]:
            return [vs[0], vs[-1]]
    # "5V", "12V DC" — single voltage
    m = re.match(r"(\d+\.?\d*)\s*V", s, re.I)
    if m:
        v = float(m.group(1))
        return [v, v]
    return None


# --- DB category -> our category --------------------------------------------
CAT_MAP = {
    "microcontroller": "mcu",
    "sensor": "sensor",
    "actuator": "actuator",
    "display": "display",
    "communication": "radio",
    "audio": "actuator",
    "input": "interface",
    "storage": "interface",
    "timekeeping": "interface",
    "power": "power",
}


def looks_curated(entry):
    pn = (entry.get("part_number") or "").lower()
    eid = (entry.get("id") or "").lower()
    name = (entry.get("name") or "").lower()
    for key in CURATED_KEYS:
        k = key.lower()
        if not k or len(k) < 4:
            continue
        if k in pn or k in eid or k in name:
            return True
    # Specific hard-wired skips (curated overrides)
    skip_part_numbers = {"esp32", "esp32-devkit", "lm2596", "mt3608", "tp4056",
                          "ams1117-3.3", "ams1117-5.0", "ssd1306", "bme280",
                          "hc-sr04", "mpu6050", "sg90", "nrf24l01+", "ch340g",
                          "dht22", "atmega328p"}
    if pn in skip_part_numbers:
        return True
    return False


def ts_string(s):
    if s is None:
        return "undefined"
    s = str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{s.strip()}"'


def emit_entry(e):
    eid = e.get("id") or re.sub(r"[^a-z0-9-]+", "-", (e.get("name") or "?").lower())
    cat = CAT_MAP.get(e.get("category"), "other")
    label = e.get("name", eid)
    summary = (e.get("specs") or {}).get("measures") or (e.get("specs") or {}).get("description") or ""
    if not summary:
        ifc = (e.get("specs") or {}).get("interface")
        summary = f"{label}" + (f" ({ifc})" if ifc else "")
    vr = parse_voltage_range((e.get("specs") or {}).get("operating_voltage"))
    pins_dict = e.get("pinout") or {}
    pin_lines = []
    seen = set()
    for pin_name, fn in pins_dict.items():
        pid = re.sub(r"\s+", "_", pin_name.strip())
        if pid in seen:
            continue
        seen.add(pid)
        role = infer_role(pin_name, fn)
        voltage_field = ""
        if role in {"power_in", "power_out"}:
            ov = (e.get("specs") or {}).get("operating_voltage")
            if ov:
                voltage_field = f", voltage: {ts_string(ov)}"
        notes_field = ""
        if fn and fn.strip().lower() not in {pin_name.strip().lower(), "unknown", ""}:
            short = fn.strip()
            if len(short) > 120:
                short = short[:117] + "..."
            notes_field = f", notes: {ts_string(short)}"
        pin_lines.append(
            f'      {{ id: {ts_string(pid)}, label: {ts_string(pin_name)}, role: "{role}"{voltage_field}{notes_field} }},'
        )
    extra_lines = []
    if vr:
        extra_lines.append(f"    inputVoltageRange: [{vr[0]}, {vr[1]}],")
    if e.get("manufacturer"):
        extra_lines.append(f"    manufacturer: {ts_string(e['manufacturer'])},")
    if e.get("part_number"):
        extra_lines.append(f"    partNumber: {ts_string(e['part_number'])},")
    if e.get("datasheet_url"):
        extra_lines.append(f"    datasheetUrl: {ts_string(e['datasheet_url'])},")
    if e.get("cost_usd") is not None:
        extra_lines.append(f"    priceUsd: {e['cost_usd']},")
    block = (
        "  {\n"
        f"    id: {ts_string(eid)},\n"
        f"    label: {ts_string(label)},\n"
        f"    category: {ts_string(cat)},\n"
        f"    summary: {ts_string(summary)},\n"
        + ("\n".join(extra_lines) + "\n" if extra_lines else "")
        + "    pins: [\n"
        + "\n".join(pin_lines)
        + "\n    ],\n"
        "    source: \"ingested-component-db\",\n"
        "  },"
    )
    return block


emitted = []
skipped = 0
for entry in DB:
    if looks_curated(entry):
        skipped += 1
        continue
    try:
        emitted.append(emit_entry(entry))
    except Exception as ex:
        print(f"skip {entry.get('id')}: {ex}", file=sys.stderr)
        skipped += 1

header = """// AUTO-GENERATED from data/component_cache/component_database.json by
// .ingest_modules.py (kept out of the repo — re-run with that script
// to refresh). Each entry's source is recorded for traceability.
//
// Curated entries in module-library.ts take precedence by id; this file
// supplements with the broader encyclopedia drawn from the existing
// component database (100 entries across 10 categories).

import type { ModuleSpec } from "./module-library";

export const INGESTED_MODULES: ModuleSpec[] = [
"""
footer = "\n];\n"

OUT.write_text(header + "\n".join(emitted) + footer)
print(f"ingested {len(emitted)} entries; skipped {skipped} curated/duplicates -> {OUT}")
