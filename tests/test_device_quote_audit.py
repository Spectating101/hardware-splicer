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


def _audit(tmp_path, module_extra, *, capture="Captured statement."):
    source_dir = tmp_path / "sources"
    source_dir.mkdir(exist_ok=True)
    (source_dir / "ada_bme_pinouts.txt").write_text(capture, encoding="utf-8")
    module = {"id": "fixture", "sources": [{"url": BME}], **module_extra}
    library_path = tmp_path / "library.json"
    library_path.write_text(json.dumps({"modules": [module]}), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/verify_device_module_quotes.py"),
                             "--library", str(library_path), "--source-dir", str(source_dir)], capture_output=True, text=True, check=False)
    return result, json.loads(result.stdout)


LOAD = {"mode": "m", "kind": "peak", "max_ma": 1, "rail_v": 3.3, "conditions": "c", "locator": "table", "source": BME}


@pytest.mark.parametrize("where", ["engineering_load", "engineering_temperature", "pullups"])
@pytest.mark.parametrize("quote,expected", [("Captured statement.", True), ("A statement the page never made.", False)])
def test_a_quote_on_an_engineering_figure_or_a_pullup_is_checked_like_any_other(tmp_path, where, quote, expected):
    extra = {
        "engineering_load": {"engineering": {"loads": [{**LOAD, "quote": quote}]}},
        "engineering_temperature": {"engineering": {"operating_temp_c": {"min": 0, "max": 70, "kind": "recommended", "quote": quote, "locator": "l", "source": BME}}},
        "pullups": {"i2c": {"pullups": {"ohm": 10000, "rail": None, "quote": quote, "source": BME}}},
    }[where]
    result, report = _audit(tmp_path, extra)
    assert report["pass"] is expected
    assert result.returncode == (0 if expected else 1)
    assert report["quotes_checked"] == 1
    if not expected:
        assert report["failed"][0]["claim"].startswith(("engineering", "i2c.pullups"))


def test_an_engineering_figure_cited_to_a_source_the_module_does_not_declare_fails(tmp_path):
    extra = {"engineering": {"loads": [{**LOAD, "quote": "Captured statement.", "source": BH}]}}
    result, report = _audit(tmp_path, extra)
    assert report["pass"] is False and result.returncode == 1


def test_a_figure_with_no_quote_is_reported_but_does_not_fail_the_audit(tmp_path):
    extra = {"quotes": [{"claim": "c", "quote": "Captured statement.", "source": BME}], "engineering": {"loads": [LOAD]}}
    result, report = _audit(tmp_path, extra)
    assert report["pass"] is True
    assert report["figures_without_a_quote"] == ["fixture.engineering.loads[0]"]
