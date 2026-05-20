"""Second-source ingester: data/extracted_pinouts/<IC>_pinout.json -> ts.

These are bare IC pinouts (op-amps, USB-UART bridges, flash chips, raw
MCUs, logic, etc.) extracted from datasheets. Schema:
  { ic_name, pins: [{pin, name, function}], total_pins }

We map each to a ModuleSpec with source="ingested-pinout-extract", best-guess
category from the IC name, and role inference from pin name + datasheet
prose. Entries already covered by the curated library or the component DB
ingest are skipped.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINOUT_DIR = ROOT / "data/extracted_pinouts"
OUT = ROOT / "circuit-ai-frontend/lib/modules/ingested-pinouts.ts"
CURATED = (ROOT / "circuit-ai-frontend/lib/modules/module-library.ts").read_text()
INGESTED_DB = (ROOT / "circuit-ai-frontend/lib/modules/ingested.ts").read_text()
EXISTING = set(re.findall(r'id:\s*"([^"]+)"', CURATED + INGESTED_DB))
EXISTING_PNS = set(s.lower() for s in re.findall(r'partNumber:\s*"([^"]+)"', CURATED + INGESTED_DB))

# Category guesses by IC name family.
CAT_GUESS = [
    (r"^(LM|TL|OP|NE5|MCP6)", "other"),          # op-amps / comparators -> other
    (r"^74HC", "interface"),                      # logic gates
    (r"^(ATmega|ATtiny|PIC|STM32|SAM)", "mcu"),  # raw MCUs
    (r"^ESP", "mcu"),
    (r"^(W25|AT24|24LC|MX25)", "interface"),     # SPI/I2C memory
    (r"^(LM2596|MT3608|LM78|TPS|LDO|AMS)", "power"),
    (r"^(FT|CP|CH)", "interface"),               # USB-UART/SPI bridges
    (r"^(WS28|APA10)", "display"),               # addressable LEDs
    (r"^(ADS|MCP3|MAX17)", "sensor"),            # ADC/sensors
    (r"^(BMP|BME|DHT|MPU|HMC|HC|ICM)", "sensor"),# sensors
    (r"^(ULN|L29[28]|TB6|DRV|IRF)", "actuator"), # drivers / FETs
]
def guess_category(name: str) -> str:
    for pat, cat in CAT_GUESS:
        if re.match(pat, name, re.IGNORECASE):
            return cat
    return "other"


def infer_role(name: str, fn: str = "") -> str:
    n = name.strip().upper(); f = (fn or "").lower()
    # Explicit function-text classification wins
    if "chip select" in f or "slave select" in f or re.search(r"\bcs\b", f):
        return "spi_cs"
    if "mosi" in f or ("master" in f and "slave" in f and "out" in f and "in" in f):
        return "spi_mosi"
    if "miso" in f:
        return "spi_miso"
    if "spi clock" in f or "shift clock" in f:
        return "spi_sck"
    if "i2c data" in f or "sda" in f and "i2c" in f:
        return "i2c_sda"
    if "i2c clock" in f or ("scl" in f and "i2c" in f):
        return "i2c_scl"
    if "transmit data" in f or "tx data" in f or "uart tx" in f or "serial out" in f:
        return "uart_tx"
    if "receive data" in f or "rx data" in f or "uart rx" in f or "serial in" in f:
        return "uart_rx"
    if "pwm" in f:
        return "pwm"
    if "ground" in f or "circuit ground" in f or n in {"GND","VSS","0V"}:
        return "gnd"
    if "positive input supply" in f or "supply voltage" in f or "vdd" in f or n in {"VCC","VDD","VIN","V+","VBAT","VBUS","VSYS","IN+","VS"}:
        return "power_in"
    if "regulated" in f and "output" in f or n in {"VOUT","OUT+","BAT+"}:
        return "power_out"
    if "analog" in f or "adc" in f or re.fullmatch(r"A\d+|AIN\d+", n):
        return "analog_in"
    if n in {"SDA"}: return "i2c_sda"
    if n in {"SCL"}: return "i2c_scl"
    if n in {"MOSI"}: return "spi_mosi"
    if n in {"MISO"}: return "spi_miso"
    if n in {"SCK","SCLK"}: return "spi_sck"
    if n in {"CS","CSN","SS"}: return "spi_cs"
    if n in {"TX","TXD"}: return "uart_tx"
    if n in {"RX","RXD"}: return "uart_rx"
    if n in {"RST","RESET","EN","ENABLE"}: return "reset"
    if re.fullmatch(r"D\d+|GPIO\d+|P[A-D]\d+", n): return "digital_io"
    if re.fullmatch(r"IN\d*", n): return "digital_in"
    if re.fullmatch(r"OUT\d*|DO", n): return "digital_out"
    return "other"


def ts(s):
    s = (s or "").replace("\\","\\\\").replace('"','\\"').replace("\n"," ").replace("\r"," ").strip()
    return f'"{s}"'


def safe_id(ic: str) -> str:
    return re.sub(r"[^a-z0-9]+","_",ic.lower()).strip("_") + "_chip"


emitted = []
skipped = 0
for f in sorted(PINOUT_DIR.glob("*_pinout.json")):
    try:
        d = json.load(open(f))
    except Exception as e:
        print(f"skip {f.name}: {e}", file=sys.stderr); skipped += 1; continue
    ic = d.get("ic_name","").strip()
    if not ic:
        skipped += 1; continue
    eid = safe_id(ic)
    if eid in EXISTING or ic.lower() in EXISTING_PNS:
        skipped += 1; continue
    cat = guess_category(ic)
    # Dedup pin names within one IC (extracted data sometimes has dupes
    # because numbered chip pins can share alt-function names).
    seen = set(); pin_lines = []
    for p in d.get("pins", []):
        nm = (p.get("name") or "").strip()
        fn = (p.get("function") or "").strip()
        if not nm or nm.upper() == "UNKNOWN":
            continue
        pid = re.sub(r"\s+", "_", nm)
        if pid in seen:
            continue
        seen.add(pid)
        role = infer_role(nm, fn)
        notes = ""
        short = (fn[:117] + "...") if len(fn) > 120 else fn
        if short and short.lower() != "unknown":
            notes = f', notes: {ts(short)}'
        pin_lines.append(f'      {{ id: {ts(pid)}, label: {ts(nm)}, role: "{role}"{notes} }},')
    if not pin_lines:
        skipped += 1; continue
    summary = f"{ic} datasheet pinout (extracted)"
    extras = [f'    partNumber: {ts(ic)},']
    block = (
        "  {\n"
        f"    id: {ts(eid)},\n"
        f"    label: {ts(ic)},\n"
        f"    category: {ts(cat)},\n"
        f"    summary: {ts(summary)},\n"
        + "\n".join(extras) + "\n"
        "    pins: [\n"
        + "\n".join(pin_lines) + "\n"
        "    ],\n"
        '    source: "ingested-pinout-extract",\n'
        "  },"
    )
    emitted.append(block)

OUT.write_text(
    '// AUTO-GENERATED from data/extracted_pinouts/*.json by scripts/\n'
    '// ingest_pinout_extracts.py — bare-IC datasheet pinouts complementing\n'
    '// the module-breakout entries in ingested.ts. Re-run the script to refresh.\n\n'
    'import type { ModuleSpec } from "./module-library";\n\n'
    'export const INGESTED_PINOUTS: ModuleSpec[] = [\n'
    + "\n".join(emitted) + "\n];\n"
)
print(f"ingested {len(emitted)} bare-IC pinouts; skipped {skipped} -> {OUT}")
