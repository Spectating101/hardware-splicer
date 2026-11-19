"""Check module quotes against the capture of their exact cited source.

Unlike an all-document substring search, an unrelated page cannot validate a
quote here. Case is preserved; whitespace and typographic apostrophes/dashes are
normalised. The supplied source directory remains an external review capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts": "ada_bme_pinouts.txt",
    "https://www.adafruit.com/product/2652": "ada_bme_product.txt",
    "https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf": "bosch_bme280.txt",
    "https://learn.adafruit.com/adafruit-bh1750-ambient-light-sensor/pinouts": "ada_bh_pinouts.txt",
    "https://www.adafruit.com/product/4681": "ada_bh_product.txt",
    "https://web.archive.org/web/20230104181611/http://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf": "rohm_bh1750.txt",
    "https://learn.adafruit.com/adafruit-ds3231-precision-rtc-breakout/pinouts": "ada_ds_pinouts.txt",
    "https://learn.adafruit.com/adafruit-ds3231-precision-rtc-breakout/arduino-usage": "ada_ds_usage.txt",
    "https://www.adafruit.com/product/5188": "ada_ds_product.txt",
    "https://web.archive.org/web/20201114123152id_/https://datasheets.maximintegrated.com/en/ds/DS3231.pdf": "maxim_ds3231.txt",
    "https://learn.adafruit.com/adafruit-ina219-current-sensor-breakout/pinouts": "ada_ina_pinouts.txt",
    "https://www.adafruit.com/product/904": "ada_ina_product.txt",
    "https://www.ti.com/lit/ds/symlink/ina219.pdf": "ina219_datasheet.txt",
    "https://learn.adafruit.com/mpu6050-6-dof-accelerometer-and-gyro/pinouts": "ada_mpu_pinouts.txt",
    "https://www.adafruit.com/product/3886": "ada_mpu_product.txt",
    "https://web.archive.org/web/20201112015226/https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Datasheet1.pdf": "mpu6050_datasheet.txt",
    "https://learn.adafruit.com/adafruit-4-channel-adc-breakouts/pinouts": "ada_ads_pinouts.txt",
    "https://www.adafruit.com/product/1085": "ada_ads_product.txt",
    "https://www.ti.com/lit/ds/symlink/ads1115.pdf": "ads1115_datasheet.txt",
    "https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf": "pico_datasheet.txt",
    "https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf": "esp32_wroom_32e.txt",
    "https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf": "ssd1306.txt",
    "https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/pcb-layout-design.html": "esp_hw_design_pcb_layout.txt",
}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("−", "-").replace("–", "-").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def _walk(node, path=""):
    """Every dict that carries a verbatim quote, with where it sits in the module, however the library nests it."""
    if isinstance(node, dict):
        if "quote" in node:
            yield path, node
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")


def _quoted_items(module):
    """The module's `quotes` list and every other quote (a pull-up, an antenna clearance, a temperature note, a current)."""
    for item in module.get("quotes", []):
        yield item["claim"], item
    for path, item in _walk({key: value for key, value in module.items() if key != "quotes"}):
        yield path, item


def _figures_without_quote(module):
    """Engineering figures that state a number but carry no quote, so nothing can check them. Reported, not failed."""
    engineering = module.get("engineering", {})
    rows = [(name, engineering[name]) for name in ("operating_temp_c", "supply_min_a", "power_stage") if name in engineering]
    rows += [(f"loads[{index}]", row) for index, row in enumerate(engineering.get("loads", []))]
    return [f"{module['id']}.engineering.{name}" for name, row in rows if "quote" not in row]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=ROOT / "src/hardware_splicer/data/device_modules.json")
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    library = json.loads(args.library.read_text(encoding="utf-8"))
    sources = {}
    checks = []
    unquoted = []
    for module in library["modules"]:
        declared = {source["url"] for source in module["sources"]} | {source["url"] for source in module.get("engineering_sources", [])}
        for claim, item in _quoted_items(module):
            url = item.get("source")
            filename = SOURCE_FILES.get(url)
            path = args.source_dir / filename if filename else None
            supported = False
            if url in declared and path is not None and path.is_file():
                raw = path.read_bytes()
                sources[url] = {"file": filename, "sha256": hashlib.sha256(raw).hexdigest()}
                supported = bool(item["quote"].strip()) and normalise(item["quote"]) in normalise(raw.decode("utf-8"))
            checks.append({"module": module["id"], "claim": claim, "source": url, "supported": supported})
        unquoted += _figures_without_quote(module)
    passed = bool(checks) and all(row["supported"] for row in checks)
    print(json.dumps({"pass": passed, "quotes_checked": len(checks), "failed": [row for row in checks if not row["supported"]],
                      "figures_without_a_quote": unquoted, "sources": sources}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
