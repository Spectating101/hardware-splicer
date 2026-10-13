"""Which vendor-host files, libraries and scenarios belong to which part's Arduino adapter.

A descriptor names a profile (``adapter.vendor_profile``); everything else here is fixed in code, so a descriptor
can select a lane but never introduces a source file, a compiler argument or a library of its own.
"""
from __future__ import annotations

from typing import Any

# Shared by every profile: the host Arduino shim, the Wire model, the SSD1306 model and the harness helpers.
COMMON_FILES = (
    "Arduino.h", "Print.h", "SPI.h", "Stream.h", "WString.h", "Wire.cpp", "Wire.h", "arduino_core.cpp",
    "pgmspace.h", "ssd1306_model.cpp", "ssd1306_model.h", "vendor_common.h", "README.md",
)

_SSD1306_STACK_DIRS = ("Adafruit SSD1306", "Adafruit GFX Library", "Adafruit BusIO")
_SSD1306_STACK_SOURCES = (
    ("Adafruit SSD1306", "Adafruit_SSD1306.cpp"),
    ("Adafruit GFX Library", "Adafruit_GFX.cpp"),
    ("Adafruit BusIO", "Adafruit_I2CDevice.cpp"),
    ("Adafruit BusIO", "Adafruit_SPIDevice.cpp"),
)

VENDOR_PROFILES: dict[str, dict[str, Any]] = {
    "bme280": {
        "lib_dirs": ("Adafruit BME280 Library", *_SSD1306_STACK_DIRS, "Adafruit Unified Sensor"),
        "lib_sources": (
            ("Adafruit BME280 Library", "Adafruit_BME280.cpp"),
            *_SSD1306_STACK_SOURCES,
            ("Adafruit Unified Sensor", "Adafruit_Sensor.cpp"),
        ),
        "model_files": ("models.cpp", "models.h"),
        "model_sources": ("models.cpp",),
        "harness": "vendor_harness.cpp",
        "scenarios": (
            "sensor_default_address_0x77_with_display_0x3C", "sensor_0x76_only", "display_at_0x3D_only",
            "display_absent", "sensor_absent_then_appears", "unplug_replug_mid_run", "both_addresses_answer",
            "transient_data_nack", "wire_pins_stay_explicit", "blocking_budget", "im_update_never_clears",
        ),
    },
    "bh1750": {
        "lib_dirs": _SSD1306_STACK_DIRS,
        "lib_sources": _SSD1306_STACK_SOURCES,
        "model_files": ("models_bh1750.cpp", "models_bh1750.h"),
        "model_sources": ("models_bh1750.cpp",),
        "harness": "vendor_harness_bh1750.cpp",
        "scenarios": (
            "sensor_default_address_0x23_with_display_0x3C", "sensor_0x5C_only", "display_at_0x3D_only",
            "display_absent", "sensor_absent_then_appears", "unplug_replug_mid_run", "both_addresses_answer",
            "transient_data_nack", "wire_pins_stay_explicit", "blocking_budget", "first_read_waits_for_conversion",
        ),
        "model_note": (
            "The BH1750 sensor is driven by the adapter's own Wire code, so only the SSD1306 stack is vendor code here. "
            "Its bus model is written from the Rohm datasheet (2009.04 Rev.B) with the datasheet's worked examples as "
            "the oracle; it does not model L-resolution quantisation, the H-resolution mode 2 or the sensitivity register."
        ),
    },
}


def vendor_profile(name: str) -> dict[str, Any]:
    try:
        return VENDOR_PROFILES[name]
    except KeyError:
        raise ValueError(f"unknown vendor-host profile {name!r}") from None


def vendor_files(name: str) -> tuple[str, ...]:
    """The files under ``vendor_host/`` that a package for this profile carries."""
    profile = vendor_profile(name)
    return tuple(sorted({*COMMON_FILES, *profile["model_files"], profile["harness"]}))
