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
from .device_parts import available_parts, render_fixtures, render_traits
from .device_plan import DevicePlanError, build_device_plan, module_library
from .device_vendor_profiles import vendor_files, vendor_profile

SCHEMA = "hardware_splicer.device_application_proposal.v1"
BME280_ID = "adafruit-bme280-stemma-qt"
SSD1306_ID = "ssd1306-096-i2c"
SUPPORTED_I2C = {BME280_ID, SSD1306_ID}  # kept for callers; sensors now come from the part descriptors
TEMPLATE_DIR = Path(__file__).resolve().parent / "data" / "firmware_application"
BOUNDARY = (
    "Host-testable application proposal. No flashing, powering, measurements or physical authorization. "
    "Host scenarios exercise application logic against a modelled bus. They do not test Adafruit libraries, "
    "the Wire driver, timing, electrical behaviour or any real device."
)
VENDOR_HOST_BOUNDARY = (
    "Vendor-host compile of the real Arduino adapter and the pinned Adafruit sources against a modelled "
    "I2C bus and a host Arduino shim. A pass is not silicon, not the ESP32 Wire driver's real timing, "
    "and not electrical behaviour. It does not authorize flashing or power-on."
)
NON_CLAIMS = [
    "Does not authorize flashing, powering or physical use.",
    "Does not pick an I2C address; declared alternatives are tried and the chip-id match is reported.",
    "Host scenarios are a model of application logic, not a sensor, display, timing or electrical test.",
    "Does not test the Adafruit libraries, the Wire driver, pull-ups, supply or any real device.",
    "Vendor-host scenarios compile those Adafruit sources against a model; they are still not silicon, "
    "not ESP32 Wire timing, and not electrical behaviour.",
    "Compilation is NOT_RUN until a separate compiler result exists.",
    "Behaviour tests are NOT_RUN until a separate host-harness result exists.",
    "physical_correctness remains UNPROVEN even if host tests and compilation later pass.",
]


NO_VENDOR_BOUNDARY = (
    "No vendor-host lane exists for this part: there is no register-level bus model, so its Arduino adapter "
    "was not tested against a modelled bus. The host scenarios cover application logic only."
)


PICO_PLATFORM = "https://github.com/maxgerhardt/platform-raspberrypi.git#5d4561a05e3b212660ac6fdd3fbfb328d1988aa1"

# What changes with the controller board: the compile target and how the adapter starts the I2C bus. Everything the
# application does lives in app_core.h and is the same on both.
_ESP32_START = "    Wire.setTimeOut(50);\n    Wire.begin(SDA_PIN, SCL_PIN, 100000);"
_ESP32_RESTART = "        Wire.end();\n        Wire.setTimeOut(50);\n        return Wire.begin(SDA_PIN, SCL_PIN, 100000);"
# arduino-pico (earlephilhower): pins are set before begin(); begin() returns nothing. In the core this platform commit
# pins, setSDA/setSCL return true for a pin this I2C controller can use and otherwise call panic(), which halts with a
# FATAL message (libraries/Wire/src/Wire.cpp). The planner refuses such pins first, so the check below never fires in
# a planned package; it is kept so a hand edit to SDA_PIN or SCL_PIN still cannot start the bus on other pins.
_PICO_START = (
    "    if (!{w}.setSDA(SDA_PIN) || !{w}.setSCL(SCL_PIN)) {{\n"
    "        // Unreachable in practice: the core panics on an illegal pin before returning false.\n"
    "        for (;;) {{ Serial.println(\"I2C pins rejected by the RP2040 core; no bus started.\"); delay(1000); }}\n"
    "    }}\n"
    "    {w}.setClock(100000);\n    {w}.setTimeout(50);\n    {w}.begin();"
)
_PICO_RESTART = (
    "        {w}.end();\n"
    "        if (!{w}.setSDA(SDA_PIN) || !{w}.setSCL(SCL_PIN)) return false;\n"
    "        {w}.setClock(100000);\n        {w}.setTimeout(50);\n        {w}.begin();\n        return true;"
)
CONTROLLERS: dict[str, dict[str, Any]] = {
    "esp32-devkitc-v4": {
        "target": {"platform": PLATFORM, "board": "esp32dev", "framework": "arduino"},
        "ini": f"platform = {PLATFORM}\nboard = esp32dev\nframework = arduino",
        "board_note": "Board profile esp32dev is a software compile target, not proof of exact hardware identity.\n",
        "vendor_host": True,
    },
    "raspberry-pi-pico": {
        "target": {"platform": PICO_PLATFORM, "board": "pico", "framework": "arduino", "core": "earlephilhower"},
        "ini": f"platform = {PICO_PLATFORM}\nboard = pico\nframework = arduino\nboard_build.core = earlephilhower",
        "board_note": (
            "Board profile pico with the earlephilhower arduino-pico core is a software compile target, not proof of "
            "exact hardware identity. The platform is pinned to one commit of maxgerhardt/platform-raspberrypi.\n"
        ),
        # The vendor-host lane swaps in a model of the arduino-pico TwoWire (vendor_host/rp2040/).
        "vendor_host": True,
    },
}
NO_VENDOR_CONTROLLER_BOUNDARY = (
    "No vendor-host lane exists for this controller: the host shim has no model of its Arduino core's Wire, so the "
    "Arduino adapter was not tested against a modelled bus. The host scenarios cover application logic only."
)


def _wiring(controller_id: str, bindings: dict[str, Any]) -> dict[str, str]:
    """The adapter's I2C start and restart code for this controller and these pins."""
    if controller_id == "esp32-devkitc-v4":
        return {"WIRE": "Wire", "WIRE_START": _ESP32_START, "WIRE_RESTART": _ESP32_RESTART}
    indices = {bindings[signal].get("i2c_controller") for signal in ("sda", "scl")}
    if len(indices) != 1 or None in indices:
        raise DevicePlanError("SDA and SCL must both be pins of the same RP2040 I2C controller")
    wire = "Wire" if indices.pop() == 0 else "Wire1"
    return {"WIRE": wire, "WIRE_START": _PICO_START.format(w=wire), "WIRE_RESTART": _PICO_RESTART.format(w=wire)}


def _boundary(part: dict[str, Any]) -> str:
    """The claim boundary, without naming libraries this package does not use."""
    if part["adapter"]["vendor_host"]:
        return BOUNDARY
    return BOUNDARY.replace("They do not test Adafruit libraries,", "They do not test the Arduino adapter,")


def _non_claims(part: dict[str, Any]) -> list[str]:
    claims = list(NON_CLAIMS)
    if part["identity"] is None:
        claims = [
            c.replace("the chip-id match is reported", "the acknowledging address is reported") for c in claims
        ]
    if not part["adapter"]["vendor_host"]:
        claims = [c for c in claims if not c.startswith("Vendor-host scenarios")]
        claims = [c.replace("Does not test the Adafruit libraries, the Wire driver,", "Does not test the Arduino adapter, the Wire driver,") for c in claims]
        claims.append(NO_VENDOR_BOUNDARY)
    if part["identity"] is None:
        claims.append(f"The {part['chip']} has no ID register: a chip that acknowledges a declared address cannot be told from one.")
    note = vendor_profile(part["adapter"]["vendor_profile"]).get("model_note") if part["adapter"]["vendor_host"] else None
    if note:
        claims.append(note)
    claims.append("The part descriptor is a cited extract and stays UNREVIEWED_EXTRACT until a person reviews it.")
    return claims


def _template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _fill(template: str, mapping: dict[str, str]) -> str:
    text = template
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def _vendor_host_files(profile: str, controller_id: str = "esp32-devkitc-v4", bindings: dict[str, Any] | None = None) -> dict[str, bytes]:
    root = TEMPLATE_DIR / "vendor_host"
    files = {f"test/vendor_host/{name}": (root / name).read_bytes() for name in vendor_files(profile)}
    if controller_id == "raspberry-pi-pico":
        # The RP2040 core's Wire replaces the ESP32 one; the harness and device models are shared.
        for name in ("Wire.h", "Wire.cpp", "wire_pins_rp2040.h", "util/delay.h", "api/deprecated-avr-comp/avr/pgmspace.h"):
            files[f"test/vendor_host/{name}"] = (root / "rp2040" / name).read_bytes()
        readme = files["test/vendor_host/README.md"].decode()
        files["test/vendor_host/README.md"] = (
            readme.replace("not the ESP32 Wire driver's real timing", "not the RP2040 Wire driver's real timing")
            .replace("-DESP32 -DARDUINO_ARCH_ESP32", "-DHS_RP2040 -DARDUINO_ARCH_RP2040 -DARDUINO_RASPBERRY_PI_PICO")
            .replace("The Wire model follows arduino-esp32 2.0.17:", "On the ESP32 the Wire model follows arduino-esp32 2.0.17:")
            + "\nThis package is for the Raspberry Pi Pico. `Wire.h` and `Wire.cpp` here model the arduino-pico TwoWire at the "
            "pinned core commit, not arduino-esp32, and `board_config.h` names the planned I2C controller and pins.\n"
        ).encode()
        assert bindings is not None
        controller_index = bindings["sda"]["i2c_controller"]
        files["test/vendor_host/board_config.h"] = (
            "#pragma once\n"
            "// Generated from this package's plan: the Raspberry Pi Pico, and the I2C controller and pins it wires.\n"
            "#define HS_RP2040 1\n"
            f"#define HS_PLANNED_I2C {controller_index}\n"
            f"#define HS_WIRE {'Wire1' if controller_index == 1 else 'Wire'}\n"
            f"#define HS_PLANNED_SDA {bindings['sda']['gpio']}\n"
            f"#define HS_PLANNED_SCL {bindings['scl']['gpio']}\n"
        ).encode()
    return files


def _for_board(text: str, controller_id: str) -> str:
    """The vendor-host wording names the Arduino core whose Wire the host model stands in for."""
    if controller_id == "raspberry-pi-pico":
        return text.replace("the ESP32 Wire driver's real timing", "the RP2040 Wire driver's real timing").replace(
            "not ESP32 Wire timing", "not RP2040 Wire timing")
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
    controller = CONTROLLERS.get(mcu["module"])
    if controller is None:
        raise DevicePlanError("application source supports only the catalog ESP32-DevKitC V4 and Raspberry Pi Pico")
    library = {m["id"]: m for m in module_library()["modules"]}
    parts = available_parts()
    i2c_placed = [m for m in plan["modules"] if library[m["module"]].get("i2c")]
    sensors = [m for m in i2c_placed if m["module"] in parts]
    other = [m for m in i2c_placed if m["module"] not in parts and m["module"] != SSD1306_ID]
    names = " or ".join(part["chip"] for part in parts.values())
    if not sensors:
        raise DevicePlanError(
            f"application source supports a controller + a sensor breakout ({names}) + optionally SSD1306 and needs one "
            f"of: {', '.join(sorted(parts))}; the diagnostic export remains available for other parts"
        )
    if len(sensors) > 1:
        raise DevicePlanError(
            f"application source supports only one sensor breakout ({names}) plus optionally SSD1306; "
            "the diagnostic export remains available for other parts"
        )
    if other:
        raise DevicePlanError(
            f"application source supports a controller + one sensor ({names}) + optionally SSD1306; "
            "the diagnostic export remains available for other parts"
        )
    part = parts[sensors[0]["module"]]
    if not controller["vendor_host"] and part["adapter"]["vendor_host"]:
        # Same descriptor, but no vendor-host lane on this controller: the package must not ship or claim one.
        part = {**part, "adapter": {**part["adapter"], "vendor_host": False}}
    bindings, declarations = resolve_shared_i2c_bus(
        plan,
        bus_error="application source requires exactly one shared SDA GPIO and one distinct SCL GPIO",
    )
    sensor = next(d for d in declarations if d["library_id"] == part["library_id"])
    if list(sensor["possible_addresses"]) != list(part["addresses"]):
        raise DevicePlanError("the part descriptor's addresses disagree with the catalog; refusing to export")
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
    descriptor_bytes = _json(part)
    main = _fill(
        _template(part["adapter"]["template"]),
        {
            "SDA": str(bindings["sda"]["gpio"]),
            "SCL": str(bindings["scl"]["gpio"]),
            "SENSOR_ADDRS": sensor_addrs,
            "DISPLAY_DECL": display_decl,
            "DISPLAY_PTR": display_ptr,
            "DISPLAY_COUNT": display_count,
            **_wiring(mcu["module"], bindings),
        },
    )
    files = {
        "src/app_core.h": _template("app_core.h").encode(),
        "src/part_traits.h": render_traits(part).encode(),
        "src/main.cpp": main.encode(),
        "platformio.ini": _fill(
            _template("platformio.ini.tmpl"),
            {"TARGET": controller["ini"], "LIB_DEPS": "\n".join("    " + lib for lib in part["adapter"]["lib_deps"])},
        ).encode(),
        "test/host/harness.cpp": _template("host_harness.cpp").encode(),
        "test/host/part_fixtures.h": render_fixtures(part).encode(),
        "test/host/README.md": _template("host_README.md").encode(),
        "PART_DESCRIPTOR.json": descriptor_bytes,
    }
    if part["adapter"]["vendor_host"]:
        files.update(_vendor_host_files(part["adapter"]["vendor_profile"], mcu["module"], bindings))
    files.update({
        "DEVICE_SPEC.json": spec_bytes,
        "DEVICE_PLAN.json": _json(plan),
        "README.md": (
            f"# Host-testable {part['chip']} application proposal\n\n"
            + _boundary(part)
            + "\n\n"
            "This package is a proposal. firmware_authorized and power_on_authorized are false. "
            "physical_correctness is UNPROVEN.\n\n"
            "Host tests (no hardware): "
            "`g++ -std=c++17 -Wall -Wextra -Werror -I src test/host/harness.cpp -o harness && ./harness`\n\n"
            "Optional compile with PlatformIO Core 6.1.18: `pio run -e application`. Do not upload from this package.\n"
            + controller["board_note"]
            + (
                "Addresses are declared alternatives. The application reports the chip-id match; it does not assume 0x76 or 0x3C.\n"
                if part["identity"]
                else f"Addresses are declared alternatives. The {part['chip']} has no ID register, so the application reports which "
                "address acknowledged and cannot confirm the chip's identity.\n"
            )
            + "Review exact hardware, supplies, grounds and pull-ups separately before any physical operation.\n"
            "The diagnostic export remains available for other catalog parts.\n\n"
            + (
                _for_board(VENDOR_HOST_BOUNDARY, mcu["module"]) + "\nVendor-host tests need the pinned libdeps directory; see test/vendor_host/README.md.\n"
                if part["adapter"]["vendor_host"]
                else (NO_VENDOR_BOUNDARY if controller["vendor_host"] else NO_VENDOR_CONTROLLER_BOUNDARY) + "\n"
            )
        ).encode(),
    })
    metadata = {
        "schema_version": SCHEMA,
        "claim_boundary": _boundary(part),
        "vendor_host_claim_boundary": _for_board(VENDOR_HOST_BOUNDARY, mcu["module"]) if part["adapter"]["vendor_host"]
        else NO_VENDOR_BOUNDARY if controller["vendor_host"] else NO_VENDOR_CONTROLLER_BOUNDARY,
        "status": "HOST_TESTABLE_PROPOSAL",
        "compilation": "NOT_RUN",
        "behaviour_tests": "NOT_RUN",
        "physical_correctness": "UNPROVEN",
        "firmware_authorized": False,
        "power_on_authorized": False,
        "target": controller["target"],
        "pins": bindings,
        "declared_devices": declarations,
        "non_claims": [_for_board(claim, mcu["module"]) for claim in _non_claims(part)],
        "part": {
            "library_id": part["library_id"],
            "chip": part["chip"],
            "review_status": part["review_status"],
            "descriptor_sha256": _sha(descriptor_bytes),
            "identity_check": part["identity"] is not None,
            "vendor_host_supported": part["adapter"]["vendor_host"],
            "vendor_profile": part["adapter"].get("vendor_profile"),
        },
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
