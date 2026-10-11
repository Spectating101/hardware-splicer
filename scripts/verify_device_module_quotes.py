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
}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("−", "-").replace("–", "-").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=ROOT / "src/hardware_splicer/data/device_modules.json")
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    library = json.loads(args.library.read_text(encoding="utf-8"))
    sources = {}
    checks = []
    for module in library["modules"]:
        declared = {source["url"] for source in module["sources"]}
        for item in module.get("quotes", []):
            url = item["source"]
            filename = SOURCE_FILES.get(url)
            path = args.source_dir / filename if filename else None
            supported = False
            if url in declared and path is not None and path.is_file():
                raw = path.read_bytes()
                sources[url] = {"file": filename, "sha256": hashlib.sha256(raw).hexdigest()}
                supported = bool(item["quote"].strip()) and normalise(item["quote"]) in normalise(raw.decode("utf-8"))
            checks.append({"module": module["id"], "claim": item["claim"], "source": url, "supported": supported})
    passed = bool(checks) and all(row["supported"] for row in checks)
    print(json.dumps({"pass": passed, "quotes_checked": len(checks), "failed": [row for row in checks if not row["supported"]], "sources": sources}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
