"""Refresh HS's snapshot of Wokwi's part pin data (MIT, github.com/wokwi/wokwi-elements).

    python scripts/import_wokwi_parts.py <wokwi-elements source dir> <40-hex commit>

Each element's `pinInfo` list (pin names and the signals Wokwi gives them: I2C, SPI, UART, PWM, analog, power and voltage)
is read as data with the literal parser from import_esplabs_snapshot.py, after its helper calls (i2c('SDA'), VCC(3.3) and
the like) are rewritten to the objects pin.ts says they return. Nothing is executed. Pin x/y are Wokwi's drawing
coordinates and are kept as such, never as millimetres. Elements whose pinInfo is computed rather than written out are
listed as skipped.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/third_party/wokwi"
_spec = importlib.util.spec_from_file_location("esplabs_import", Path(__file__).with_name("import_esplabs_snapshot.py"))
_lit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lit)

HELPERS = [
    (r"\bi2c\(\s*'(SDA|SCL)'\s*(?:,\s*(\d+))?\s*\)", lambda m: f'{{type: "i2c", signal: "{m[1]}", bus: {m[2] or 0}}}'),
    (r"\bspi\(\s*'(SCK|MOSI|MISO|SS)'\s*(?:,\s*(\d+))?\s*\)", lambda m: f'{{type: "spi", signal: "{m[1]}", bus: {m[2] or 0}}}'),
    (r"\busart\(\s*'(RX|TX)'\s*(?:,\s*(\d+))?\s*\)", lambda m: f'{{type: "usart", signal: "{m[1]}", bus: {m[2] or 0}}}'),
    (r"\banalog\(\s*(\d+)\s*\)", lambda m: f'{{type: "analog", channel: {m[1]}}}'),
    (r"\bGND\(\s*\)", lambda m: '{type: "power", signal: "GND"}'),
    (r"\bVCC\(\s*([\d.]+)?\s*\)", lambda m: f'{{type: "power", signal: "VCC"{", voltage: " + m[1] if m[1] else ""}}}'),
]


def pin_info(source: str) -> list | None:
    m = re.search(r"pinInfo\s*(?::\s*[\w\[\]]+)?\s*=\s*(\[)", source)
    if not m:
        return None
    start, depth, i = m.start(1), 0, m.start(1)
    while i < len(source):
        depth += {"[": 1, "]": -1}.get(source[i], 0)
        if depth == 0:
            break
        i += 1
    text = source[start:i + 1]
    for pattern, repl in HELPERS:
        text = re.sub(pattern, repl, text)
    try:
        return _lit._Parser(_lit._tokens(text), {}).value()
    except _lit.LiteralError:
        return None


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"[0-9a-f]{40}", argv[1]):
        print(__doc__, file=sys.stderr)
        return 2
    src, commit = Path(argv[0]), argv[1]
    parts, skipped = {}, []
    for path in sorted((src / "src").glob("*-element.ts")):
        source = path.read_text(encoding="utf-8")
        tag = re.search(r"@customElement\('([\w-]+)'\)", source)
        if not tag:
            continue
        pins = pin_info(source)
        if pins is None:
            skipped.append(tag[1])
            continue
        parts[tag[1]] = {"element": tag[1], "file": path.name, "pins": pins}
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / "LICENSE", OUT / "LICENSE")
    (OUT / "parts.json").write_text(json.dumps(parts, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "SNAPSHOT.json").write_text(json.dumps({
        "source": "https://github.com/wokwi/wokwi-elements", "commit": commit, "license": "MIT (see LICENSE in this folder)",
        "counts": {"parts": len(parts), "skipped_computed_pin_info": len(skipped)}, "skipped": skipped,
        "note": "Wokwi's pin names and signals, unchanged. x and y are Wokwi drawing coordinates, not millimetres.",
    }, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"parts": len(parts), "skipped": skipped}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
