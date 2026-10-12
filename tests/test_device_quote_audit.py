"""A quote appearing elsewhere must not validate its declared citation."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
BME = "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts"
BH = "https://learn.adafruit.com/adafruit-bh1750-ambient-light-sensor/pinouts"


@pytest.mark.parametrize("case,expected", [("matching", True), ("wrong_source", False), ("wrong_case", False), ("missing_capture", False)])
def test_quote_audit_requires_the_declared_source_capture(tmp_path, case, expected):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    if case != "missing_capture":
        (source_dir / "ada_bme_pinouts.txt").write_text("Captured statement.", encoding="utf-8")
    (source_dir / "ada_bh_pinouts.txt").write_text("Different statement.", encoding="utf-8")
    library = {
        "modules": [{
            "id": "fixture",
            "sources": [{"url": BME}, {"url": BH}],
            "quotes": [{
                "claim": "fixture statement",
                "quote": "captured statement." if case == "wrong_case" else "Captured statement.",
                "source": BH if case == "wrong_source" else BME,
            }],
        }],
    }
    library_path = tmp_path / "library.json"
    library_path.write_text(json.dumps(library), encoding="utf-8")
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/verify_device_module_quotes.py"),
        "--library", str(library_path), "--source-dir", str(source_dir),
    ], capture_output=True, text=True, check=False)
    report = json.loads(result.stdout)
    assert report["pass"] is expected
    assert result.returncode == (0 if expected else 1)
    assert report["quotes_checked"] == 1
