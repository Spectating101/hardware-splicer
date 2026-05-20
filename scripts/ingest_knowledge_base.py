"""Third ingester: knowledge_base/{boards,components}/*.json -> ts.

Board files (knowledge_base/boards/*.json) have richer per-pin metadata
including physical coordinates and named header groupings. Component files
(knowledge_base/components/common_ics.json) list common IC archetypes that
the earlier ingestion passes missed.

Output: circuit-ai-frontend/lib/modules/ingested-kb.ts
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge_base"
OUT = ROOT / "circuit-ai-frontend/lib/modules/ingested-kb.ts"

# Already covered ids (curated + earlier ingest passes) to skip.
def existing_ids():
    libs = ["module-library.ts", "ingested.ts", "ingested-pinouts.ts", "curated-extended.ts"]
    text = "".join((ROOT / "circuit-ai-frontend/lib/modules" / n).read_text() for n in libs)
    return set(re.findall(r'id:\s*"([^"]+)"', text)), set(s.lower() for s in re.findall(r'partNumber:\s*"([^"]+)"', text))

EXISTING_IDS, EXISTING_PNS = existing_ids()


def infer_role(name: str) -> str:
    n = name.strip().upper()
    if n in {"GND","VSS","0V"} or n.endswith("_GND"): return "gnd"
    if n in {"VCC","VDD","VIN","V+","VBAT","VBUS","VSYS","5V_IN"}: return "power_in"
    if n in {"5V","3V3","3.3V","VOUT","OUT+","BAT+","1.8V","1V8"}: return "power_out"
    if n == "SDA": return "i2c_sda"
    if n == "SCL": return "i2c_scl"
    if n == "MOSI": return "spi_mosi"
    if n == "MISO": return "spi_miso"
    if n in {"SCK","SCLK"}: return "spi_sck"
    if n in {"CS","CSN","SS"}: return "spi_cs"
    if n in {"TX","TXD","TX0","TX1","TX2"} or "/TX" in n: return "uart_tx"
    if n in {"RX","RXD","RX0","RX1","RX2"} or "/RX" in n: return "uart_rx"
    if re.fullmatch(r"A\d+", n): return "analog_in"
    if re.fullmatch(r"D\d+|D\d+/.+", n): return "digital_io"
    if re.fullmatch(r"GPIO\d+(/.+)?", n): return "digital_io"
    if n.startswith("GP") and any(c.isdigit() for c in n): return "digital_io"  # rpi-pico style
    if "/SDA" in n: return "i2c_sda"
    if "/SCL" in n: return "i2c_scl"
    if "/PWM" in n: return "pwm"
    if n in {"AREF"}: return "analog_in"
    if n in {"RST","RESET","EN","ENABLE"}: return "reset"
    if n == "IOREF": return "power_out"
    return "other"


def ts(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ").strip()
    return f'"{s}"'


CAT_MAP = {
    "microcontroller": "mcu",
    "single_board_computer": "mcu",  # rpi4
    "mcu": "mcu",
    "sensor": "sensor",
}


emitted = []
skipped = 0

# Boards
for board_file in sorted((KB / "boards").glob("*.json")):
    d = json.load(open(board_file))
    eid = re.sub(r"[^a-z0-9]+", "_", d.get("id", board_file.stem).lower()).strip("_") + "_board"
    pn = d.get("name", "").split()[0] if d.get("name") else None
    if eid in EXISTING_IDS:
        skipped += 1
        continue
    pins_seen = set()
    pin_lines = []
    for h in d.get("headers", []):
        for p in h.get("pins", []):
            nm = p.get("name", "").strip()
            if not nm or nm in pins_seen: continue
            pins_seen.add(nm)
            pid = re.sub(r"\s+", "_", nm)
            role = infer_role(nm)
            pin_lines.append(f'      {{ id: {ts(pid)}, label: {ts(nm)}, role: "{role}" }},')
    if not pin_lines: continue
    summary = f"{d.get('name')} pinout — {d.get('gpio_pins','?')} GPIO, {d.get('operating_voltage','?')} logic"
    extras = []
    iv = d.get("input_voltage")
    if isinstance(iv, str):
        m = re.match(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)V", iv)
        if m: extras.append(f"    inputVoltageRange: [{m.group(1)}, {m.group(2)}],")
    ov = d.get("operating_voltage")
    if isinstance(ov, str):
        v = re.match(r"(\d+\.?\d*)\s*V", ov)
        if v: extras.append(f"    logicVoltage: {v.group(1)},")
    cat = CAT_MAP.get(d.get("type"), "mcu")
    block = (
        "  {\n"
        f"    id: {ts(eid)},\n"
        f"    label: {ts(d.get('name', eid))},\n"
        f"    category: {ts(cat)},\n"
        f"    summary: {ts(summary)},\n"
        + ("\n".join(extras) + "\n" if extras else "")
        + "    pins: [\n"
        + "\n".join(pin_lines) + "\n"
        "    ],\n"
        '    source: "ingested-kb-board",\n'
        "  },"
    )
    emitted.append(block)

# Common ICs from components/common_ics.json — minimal pinout entries
ICS = json.load(open(KB / "components/common_ics.json")).get("ics", [])
# Hand-curated pinouts for the ones in common_ics that we don't already have.
IC_PINOUTS = {
    "ne555": {
        "category": "interface", "summary": "Precision timer IC, DIP-8.",
        "datasheetUrl": "https://www.ti.com/product/NE555",
        "manufacturer": "Texas Instruments", "partNumber": "NE555",
        "inputVoltageRange": [4.5, 16.0],
        "pins": [
            ("GND", "gnd", "Pin 1: Ground"),
            ("TRIG", "digital_in", "Pin 2: Trigger input (active low, below 1/3 VCC)"),
            ("OUT", "digital_out", "Pin 3: Timer output"),
            ("RESET", "reset", "Pin 4: Active-low reset"),
            ("CTRL", "analog_in", "Pin 5: Control voltage (typically bypassed)"),
            ("THRES", "analog_in", "Pin 6: Threshold input"),
            ("DISCH", "digital_out", "Pin 7: Discharge — open collector to GND"),
            ("VCC", "power_in", "Pin 8: Supply 4.5-16V"),
        ],
    },
    "lm317": {
        "category": "power", "summary": "Adjustable linear voltage regulator, 1.5A.",
        "datasheetUrl": "https://www.ti.com/product/LM317",
        "manufacturer": "Texas Instruments", "partNumber": "LM317",
        "inputVoltageRange": [3.0, 40.0],
        "pins": [
            ("ADJ", "analog_in", "Adjust pin (resistor divider sets VOUT)"),
            ("VOUT", "power_out", "Regulated output (1.25-37V)"),
            ("VIN", "power_in", "Unregulated input"),
        ],
    },
    "lm7805": {
        "category": "power", "summary": "Fixed 5V linear voltage regulator, 1A, TO-220.",
        "datasheetUrl": "https://www.st.com/en/power-management/l7805.html",
        "manufacturer": "STMicroelectronics", "partNumber": "L7805",
        "inputVoltageRange": [7.0, 35.0],
        "pins": [
            ("VIN", "power_in", "Pin 1: Unregulated input (7-35V)"),
            ("GND", "gnd", "Pin 2: Ground"),
            ("VOUT", "power_out", "Pin 3: Regulated 5V output"),
        ],
    },
}

for ic in ICS:
    eid = ic.get("id", "").lower()
    if not eid or eid in EXISTING_IDS or eid in EXISTING_PNS:
        skipped += 1
        continue
    pinout = IC_PINOUTS.get(eid)
    if not pinout:
        skipped += 1
        continue
    pin_lines = []
    for pname, role, notes in pinout["pins"]:
        pid = re.sub(r"\s+", "_", pname)
        pin_lines.append(
            f'      {{ id: {ts(pid)}, label: {ts(pname)}, role: "{role}", notes: {ts(notes)} }},'
        )
    extras = []
    if pinout.get("inputVoltageRange"):
        lo, hi = pinout["inputVoltageRange"]
        extras.append(f"    inputVoltageRange: [{lo}, {hi}],")
    extras.append(f"    manufacturer: {ts(pinout['manufacturer'])},")
    extras.append(f"    partNumber: {ts(pinout['partNumber'])},")
    extras.append(f"    datasheetUrl: {ts(pinout['datasheetUrl'])},")
    block = (
        "  {\n"
        f"    id: {ts(eid)},\n"
        f"    label: {ts(ic.get('description', eid))},\n"
        f"    category: {ts(pinout['category'])},\n"
        f"    summary: {ts(pinout['summary'])},\n"
        + "\n".join(extras) + "\n"
        "    pins: [\n"
        + "\n".join(pin_lines) + "\n"
        "    ],\n"
        '    source: "ingested-kb-ic",\n'
        "  },"
    )
    emitted.append(block)

OUT.write_text(
    "// AUTO-GENERATED from knowledge_base/{boards,components}/*.json by\n"
    "// scripts/ingest_knowledge_base.py — adds full-board pinouts (Arduino Uno,\n"
    "// Nano V3, ESP32 DevKit V1, RPi 4B) and the common-IC catalog (NE555, LM317,\n"
    "// LM7805). Re-run to refresh.\n\n"
    'import type { ModuleSpec } from "./module-library";\n\n'
    "export const INGESTED_KB: ModuleSpec[] = [\n"
    + "\n".join(emitted) + "\n];\n"
)
print(f"ingested {len(emitted)} entries; skipped {skipped}")
