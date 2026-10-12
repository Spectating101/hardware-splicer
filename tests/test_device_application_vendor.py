"""Vendor-host compile of the real adapter + pinned Adafruit sources.

A pass is not silicon, not ESP32 Wire timing, and not electrical behaviour.
"""
from __future__ import annotations

import importlib.util
import io
import os
import shutil
import zipfile
from pathlib import Path

import pytest

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_plan import example_specs

REPO = Path(__file__).resolve().parents[1]
VENDOR_SCENARIOS = (
    "sensor_default_address_0x77_with_display_0x3C",
    "sensor_0x76_only",
    "display_at_0x3D_only",
    "display_absent",
    "sensor_absent_then_appears",
    "unplug_replug_mid_run",
    "both_addresses_answer",
    "transient_data_nack",
    "wire_pins_stay_explicit",
    "blocking_budget",
    "im_update_never_clears",
)

# Each mutation is one textual change the vendor harness must reject.
VENDOR_MUTATIONS = (
    (
        "remove_display_presence_check",
        "src/main.cpp",
        "        Wire.beginTransmission(addr);\n"
        "        if (Wire.endTransmission() != 0) return false;\n",
        "",
    ),
    (
        "remove_rebind_after_probing",
        "src/app_core.h",
        "            if (!hal_.sensor_begin(found)) return 0;\n",
        "",
    ),
    (
        "bus_recover_default_wire_begin",
        "src/main.cpp",
        "        Wire.end();\n        Wire.setTimeOut(50);\n        return Wire.begin(SDA_PIN, SCL_PIN, 100000);\n",
        "        Wire.end();\n        Wire.setTimeOut(50);\n        return Wire.begin();\n",
    ),
    (
        "drop_display_begin_true_false",
        "src/main.cpp",
        "        return display_.begin(SSD1306_SWITCHCAPVCC, addr, true, false);\n",
        "        return display_.begin(SSD1306_SWITCHCAPVCC, addr);\n",
    ),
    (
        "pressure_without_dividing_by_100",
        "src/main.cpp",
        "        out.pres_hpa = bme_.readPressure() / 100.0f;  // Adafruit reports Pascal\n",
        "        out.pres_hpa = bme_.readPressure();  // Adafruit reports Pascal\n",
    ),
    (
        "remove_calibration_timeout",
        "src/main.cpp",
        "            if (uint32_t(millis() - started) >= 50) return false;\n",
        "",
    ),
)


def _verify_mod():
    path = REPO / "scripts" / "verify_device_application.py"
    spec = importlib.util.spec_from_file_location("verify_device_application", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_libdeps() -> Path | None:
    """The pinned libraries exist only after a PlatformIO compile; HS_VENDOR_LIBS names such a libdeps directory."""
    verify = _verify_mod()
    named = os.environ.get("HS_VENDOR_LIBS", "").strip()
    if named and verify.vendor_libs_available(Path(named)):
        return Path(named)
    cache = REPO / ".cache" / "hardware-splicer" / "device-application"
    if cache.is_dir():
        matches = sorted(cache.glob("*/project/.pio/libdeps/application"))
        for path in matches:
            if verify.vendor_libs_available(path):
                return path
    return None


def _require_libdeps() -> Path:
    path = _find_libdeps()
    if path is None:
        pytest.skip("not run: libraries not available")
    return path


def _extract(data: bytes, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(dest)
    return dest


def _pins_25_26_spec():
    spec = example_specs()["esp32_oled_bme280_usb"]
    for wire in spec["connections"]:
        wire["to"] = wire["to"].replace("IO21", "IO25").replace("IO22", "IO26")
    return spec


def test_package_includes_vendor_host_files():
    _meta, data = build_device_application(example_specs()["esp32_oled_bme280_usb"])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
    assert "test/vendor_host/vendor_harness.cpp" in names
    assert "test/vendor_host/Wire.cpp" in names
    assert "test/vendor_host/README.md" in names
    readme = zipfile.ZipFile(io.BytesIO(data)).read("test/vendor_host/README.md").decode()
    assert "not silicon" in readme.lower() or "Not silicon" in readme


def test_vendor_libs_missing_is_not_a_pass(tmp_path):
    verify = _verify_mod()
    _meta, data = build_device_application(example_specs()["esp32_oled_bme280_usb"])
    project = _extract(data, tmp_path / "app")
    report, _log = verify._run_vendor_host(project, tmp_path / "no-such-libs")
    assert report["pass"] is False
    assert report["reason"] == "not run: libraries not available"
    assert report["firmware_authorized"] is False
    assert report["physical_correctness"] == "UNPROVEN"


def test_vendor_host_scenarios_against_the_model(tmp_path):
    libdeps = _require_libdeps()
    verify = _verify_mod()
    _meta, data = build_device_application(example_specs()["esp32_oled_bme280_usb"])
    project = _extract(data, tmp_path / "app")
    report, log = verify._run_vendor_host(project, libdeps)
    assert report["pass"] is True, log.decode(errors="replace")[-4000:]
    names = [row["scenario"] for row in report["scenarios"] if not row.get("finding")]
    assert names == list(VENDOR_SCENARIOS)
    for row in report["scenarios"]:
        assert row["pass"] is True, row
    assert report["findings"] == []
    assert report["firmware_authorized"] is False
    assert "not silicon" in report["claim_boundary"].lower() or "Not silicon" in report["claim_boundary"]


def test_wire_pins_from_example_and_from_io25_io26(tmp_path):
    libdeps = _require_libdeps()
    verify = _verify_mod()
    cases = (
        (example_specs()["esp32_oled_bme280_usb"], 21, 22),
        (_pins_25_26_spec(), 25, 26),
    )
    for spec, sda, scl in cases:
        _meta, data = build_device_application(spec)
        project = _extract(data, tmp_path / f"pins_{sda}_{scl}")
        report, log = verify._run_vendor_host(project, libdeps)
        pins = next(row for row in report["scenarios"] if row["scenario"] == "wire_pins_stay_explicit")
        assert pins["pass"] is True, log.decode(errors="replace")[-2000:]
        assert f"sda={sda}" in pins["detail"]
        assert f"scl={scl}" in pins["detail"]


def test_vendor_mutations_are_caught(tmp_path):
    libdeps = _require_libdeps()
    verify = _verify_mod()
    _meta, data = build_device_application(example_specs()["esp32_oled_bme280_usb"])
    original = _extract(data, tmp_path / "original")
    caught = {}
    for name, rel, old, new in VENDOR_MUTATIONS:
        target = original / rel
        text = target.read_text(encoding="utf-8")
        assert text.count(old) == 1, f"mutation {name} original text must occur exactly once in {rel}"
        mutated = tmp_path / name
        shutil.copytree(original, mutated)
        (mutated / rel).write_text(text.replace(old, new, 1), encoding="utf-8")
        report, log = verify._run_vendor_host(mutated, libdeps)
        # A mutant that does not even build is not "caught by behaviour": require that scenarios ran and one failed.
        ran = [row for row in report.get("scenarios", []) if not row.get("finding")]
        assert ran, f"mutation {name} produced no scenario results (did it compile?): {log.decode(errors='replace')[-800:]}"
        failed = any(not row["pass"] for row in ran)
        caught[name] = failed
        assert failed, (
            f"mutation {name} did not change vendor-host-observable behaviour; "
            f"scenarios={report.get('scenarios')} log={log.decode(errors='replace')[-1500:]}"
        )
    assert len(caught) >= 6 and all(caught.values())
