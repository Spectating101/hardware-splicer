"""The ESP32 pin scenario checks the clock and the restart through bus recovery, not only at boot.

The display library restores 100 kHz after its own transfers, which used to hide a recovery that restarted the bus at
another clock; restarts counted over the whole run let extra starts at boot stand in for a recovery that never restarts
the bus. Both holes were found in the Pico scenario by the Gemini 4 Argon review of #117; these are the ESP32 versions.
"""
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_application_execution import _run_vendor_host
from hardware_splicer.device_parts import example_spec_for_part
from hardware_splicer.device_plan import example_specs


def _vendor_run(tmp_path, spec, edits=()):
    named = os.environ.get("HS_VENDOR_LIBS", "").strip()
    if not named or not Path(named).is_dir():
        pytest.skip("not run: HS_VENDOR_LIBS names no pinned libdeps directory")
    _metadata, data = build_device_application(spec)
    project = tmp_path / "project"
    zipfile.ZipFile(io.BytesIO(data)).extractall(project)
    for old, new in edits:
        path = project / "src" / "main.cpp"
        text = path.read_text()
        assert text.count(old) == 1, old
        path.write_text(text.replace(old, new, 1))
    profile = json.loads((project / "FIRMWARE_PROPOSAL.json").read_text())["part"]["vendor_profile"]
    return _run_vendor_host(project, Path(named), profile)


SPECS = {
    "bme280": lambda: example_specs()["esp32_oled_bme280_usb"],
    "bh1750": lambda: example_spec_for_part("adafruit-bh1750-stemma-qt"),
}

RECOVERY = "        Wire.end();\n        Wire.setTimeOut(50);\n        return Wire.begin(SDA_PIN, SCL_PIN, 100000);"
ESP32_MUTANTS = [
    ("recovery restarts at 400 kHz",
     [("        return Wire.begin(SDA_PIN, SCL_PIN, 100000);", "        return Wire.begin(SDA_PIN, SCL_PIN, 400000);")]),
    ("boot starts the bus twice and recovery does nothing",
     [("\n    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n",
       "\n    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n    Wire.end();\n    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n"),
      (RECOVERY, "        return true;")]),
]


@pytest.mark.parametrize("part", sorted(SPECS))
def test_the_unmutated_esp32_adapter_still_passes_every_scenario(tmp_path, part):
    report, log = _vendor_run(tmp_path, SPECS[part]())
    assert report["scenarios"], log.decode(errors="replace")[-2000:]
    failed = [s for s in report["scenarios"] if not s["pass"] and not s.get("finding")]
    assert failed == [], failed


@pytest.mark.parametrize("part", sorted(SPECS))
@pytest.mark.parametrize("name,edits", ESP32_MUTANTS, ids=[m[0] for m in ESP32_MUTANTS])
def test_the_esp32_pin_scenario_fails_a_broken_recovery(tmp_path, part, name, edits):
    report, log = _vendor_run(tmp_path, SPECS[part](), edits)
    assert report["scenarios"], f"{name}: no scenario ran: {log.decode(errors='replace')[-1500:]}"
    pins = next(s for s in report["scenarios"] if s["scenario"] == "wire_pins_stay_explicit")
    assert not pins["pass"], f"{part}: {name} was not caught: {pins['detail']}"
