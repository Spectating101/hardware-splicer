"""Stateless host-testable application packages derived from catalog device plans.

A generated package reports and proposes. It never approves flashing, powering
or physical use. Callers' findings and authority flags are ignored.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from .device_firmware import PLATFORM, resolve_shared_i2c_bus, _json, _sha
from .device_plan import DevicePlanError, build_device_plan, module_library

SCHEMA = "hardware_splicer.device_application_proposal.v1"
BME280_ID = "adafruit-bme280-stemma-qt"
SSD1306_ID = "ssd1306-096-i2c"
SUPPORTED_I2C = {BME280_ID, SSD1306_ID}
TEMPLATE_DIR = Path(__file__).resolve().parent / "data" / "firmware_application"
BOUNDARY = (
    "Host-testable application proposal. No flashing, powering, measurements or physical authorization. "
    "Host scenarios exercise application logic against a modelled bus. They do not test Adafruit libraries, "
    "the Wire driver, timing, electrical behaviour or any real device."
)
NON_CLAIMS = [
    "Does not authorize flashing, powering or physical use.",
    "Does not pick an I2C address; declared alternatives are tried and the chip-id match is reported.",
    "Host scenarios are a model of application logic, not a sensor, display, timing or electrical test.",
    "Does not test the Adafruit libraries, the Wire driver, pull-ups, supply or any real device.",
    "Compilation is NOT_RUN until a separate compiler result exists.",
    "Behaviour tests are NOT_RUN until a separate host-harness result exists.",
    "physical_correctness remains UNPROVEN even if host tests and compilation later pass.",
]


def _template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _fill(template: str, mapping: dict[str, str]) -> str:
    text = template
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def build_device_application(spec: Any) -> tuple[dict[str, Any], bytes]:
    """Recompute from spec; never credit caller-supplied plan/findings/authority."""
    plan = build_device_plan(spec)
    try:
        spec_bytes = _json(spec)
    except (ValueError, TypeError, RecursionError) as exc:
        raise DevicePlanError("the spec must contain finite, JSON-compatible values") from exc
    blockers = [f for f in plan["findings"] if f["severity"] in {"error", "warning"}]
    if blockers:
        raise DevicePlanError(
            "Resolve wiring checks before exporting application source: "
            + ", ".join(sorted({f["rule"] for f in blockers}))
        )
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    if mcu["module"] != "esp32-devkitc-v4":
        raise DevicePlanError("application source supports only the catalog ESP32-DevKitC V4")
    library = {m["id"]: m for m in module_library()["modules"]}
    i2c_placed = [m for m in plan["modules"] if library[m["module"]].get("i2c")]
    bme = [m for m in i2c_placed if m["module"] == BME280_ID]
    other = [m for m in i2c_placed if m["module"] not in SUPPORTED_I2C]
    if not bme:
        raise DevicePlanError(
            "application source supports ESP32 + BME280 + optionally SSD1306 and needs a BME280 "
            "breakout (adafruit-bme280-stemma-qt); the diagnostic export remains available for other parts"
        )
    if len(bme) > 1:
        raise DevicePlanError("application source supports only one BME280 breakout")
    if other:
        raise DevicePlanError(
            "application source supports ESP32 + BME280 + optionally SSD1306; "
            "the diagnostic export remains available for other parts"
        )
    bindings, declarations = resolve_shared_i2c_bus(
        plan,
        bus_error="application source requires exactly one shared SDA GPIO and one distinct SCL GPIO",
    )
    sensor = next(d for d in declarations if d["library_id"] == BME280_ID)
    display = next((d for d in declarations if d["library_id"] == SSD1306_ID), None)
    sensor_addrs = ", ".join(sensor["possible_addresses"])
    if display:
        display_decl = "static const uint8_t kDisplayAddrs[] = { " + ", ".join(display["possible_addresses"]) + " };\n"
        display_ptr = "kDisplayAddrs"
        display_count = "sizeof kDisplayAddrs / sizeof kDisplayAddrs[0]"
    else:
        display_decl = ""
        display_ptr = "nullptr"
        display_count = "0"
    main = _fill(
        _template("main.cpp.tmpl"),
        {
            "SDA": str(bindings["sda"]["gpio"]),
            "SCL": str(bindings["scl"]["gpio"]),
            "SENSOR_ADDRS": sensor_addrs,
            "DISPLAY_DECL": display_decl,
            "DISPLAY_PTR": display_ptr,
            "DISPLAY_COUNT": display_count,
        },
    )
    files = {
        "src/app_core.h": _template("app_core.h").encode(),
        "src/main.cpp": main.encode(),
        "platformio.ini": _template("platformio.ini.tmpl").encode(),
        "test/host/harness.cpp": _template("host_harness.cpp").encode(),
        "test/host/README.md": _template("host_README.md").encode(),
        "DEVICE_SPEC.json": spec_bytes,
        "DEVICE_PLAN.json": _json(plan),
        "README.md": (
            "# Host-testable BME280 application proposal\n\n"
            + BOUNDARY
            + "\n\n"
            "This package is a proposal. firmware_authorized and power_on_authorized are false. "
            "physical_correctness is UNPROVEN.\n\n"
            "Host tests (no hardware): "
            "`g++ -std=c++17 -Wall -Wextra -Werror -I src test/host/harness.cpp -o harness && ./harness`\n\n"
            "Optional compile with PlatformIO Core 6.1.18: `pio run -e application`. Do not upload from this package.\n"
            "Board profile esp32dev is a software compile target, not proof of exact hardware identity.\n"
            "Addresses are declared alternatives. The application reports the chip-id match; it does not assume 0x76 or 0x3C.\n"
            "Review exact hardware, supplies, grounds and pull-ups separately before any physical operation.\n"
            "The diagnostic export remains available for other catalog parts.\n"
        ).encode(),
    }
    metadata = {
        "schema_version": SCHEMA,
        "claim_boundary": BOUNDARY,
        "status": "HOST_TESTABLE_PROPOSAL",
        "compilation": "NOT_RUN",
        "behaviour_tests": "NOT_RUN",
        "physical_correctness": "UNPROVEN",
        "firmware_authorized": False,
        "power_on_authorized": False,
        "target": {"platform": PLATFORM, "board": "esp32dev", "framework": "arduino"},
        "pins": bindings,
        "declared_devices": declarations,
        "non_claims": list(NON_CLAIMS),
        "spec_sha256": _sha(files["DEVICE_SPEC.json"]),
        "plan_sha256": _sha(files["DEVICE_PLAN.json"]),
        "files": {name: {"sha256": _sha(data), "size_bytes": len(data)} for name, data in sorted(files.items())},
    }
    files["FIRMWARE_PROPOSAL.json"] = _json(metadata)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return metadata, output.getvalue()
