#!/usr/bin/env python3
"""Mutation benchmark for the generated application's host fault matrix.

Seeds realistic bugs into the generated ``src/app_core.h`` and measures which
detector notices each one:

* ``smoke``    - ``boot_ok`` only: the application boots and prints an OK reading.
* ``healthy``  - every scenario on an unfaulted bus (``boot_ok``,
                 ``default_address_binding``, ``read_period``).
* ``matrix``   - all 15 host scenarios, including injected faults.

``serial_grammar`` re-runs other scenarios, so it is never counted as a healthy-bus
detector. A surviving mutant is not automatically a test gap: each survivor is either
reviewed as behaviourally equivalent (with a written reason) or reported as a gap.

This measures how well the *host model's* tests catch application-logic bugs. It does
not measure silicon, timing, the Adafruit libraries or physical correctness, and it
never changes any authority flag.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.bounded_process import BoundedProcessError
from hardware_splicer.device_application_execution import HOST_SCENARIOS, _execute, _scenario_failure
from hardware_splicer.device_vendor_profiles import vendor_profile

SCHEMA = "hardware_splicer.device_fault_matrix_benchmark.v1"
SMOKE = frozenset({"boot_ok"})
HEALTHY = frozenset({"boot_ok", "default_address_binding", "read_period"})
CLAIM_BOUNDARY = (
    "Mutation benchmark of host application-logic tests against a modelled bus. It is not silicon, "
    "ESP32 timing, vendor-library behaviour or electrical evidence, and it authorizes nothing."
)


@dataclass(frozen=True)
class Mutant:
    id: str
    bug_class: str
    story: str
    old: str
    new: str
    # Set only after a written review of a survivor; never to make a score look better.
    equivalent_reason: str = ""
    target: str = "src/app_core.h"
    # A real hardware bug that no host model can observe. Set only after seeing it survive; it is never excused.
    blind_spot: str = ""
    part: str = ""  # a library id when the mutant targets that part's generated headers; "" = the generic engine


def _m(id, bug_class, story, old, new, equivalent_reason="", target="src/app_core.h", blind_spot="", part=""):
    return Mutant(id, bug_class, story, old, new, equivalent_reason, target, blind_spot, part)


BME280 = "adafruit-bme280-stemma-qt"
BH1750 = "adafruit-bh1750-stemma-qt"
TRAITS = "src/part_traits.h"


MUTANTS: tuple[Mutant, ...] = (
    # --- fault thresholds and timing constants -------------------------------------------------
    _m("fail_threshold_off_by_one", "threshold", "needs four failed reads, not three, before declaring a read fault",
       "if (consecutive_fails_ >= kReadFailThreshold) {", "if (consecutive_fails_ > kReadFailThreshold) {"),
    _m("fail_threshold_too_eager", "threshold", "declares a read fault after two failures",
       "static constexpr int kReadFailThreshold = 3;", "static constexpr int kReadFailThreshold = 2;"),
    _m("read_period_wrong", "timing", "reads every 2.5 s instead of every 2 s",
       "static constexpr uint32_t kReadPeriodMs = 2000;", "static constexpr uint32_t kReadPeriodMs = 2500;"),
    _m("backoff_initial_wrong", "timing", "first retry waits 2 s instead of 1 s",
       "static constexpr uint32_t kBackoffInitialMs = 1000;", "static constexpr uint32_t kBackoffInitialMs = 2000;"),
    _m("backoff_cap_unbounded", "timing", "retry backoff cap is effectively removed",
       "static constexpr uint32_t kBackoffCapMs = 30000;", "static constexpr uint32_t kBackoffCapMs = 3000000;"),
    _m("backoff_never_grows_when_missing", "timing", "a missing sensor is retried at a constant interval",
       "                    return;\n                }\n                backoff_ms_ *= 2;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {",
       "                    return;\n                }\n                backoff_ms_ *= 1;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {"),
    _m("naive_clock_rollover", "timing", "elapsed time clamps to zero when the 32-bit millisecond counter wraps",
       "    const uint32_t elapsed = now - then;\n    return elapsed;", "    return now >= then ? now - then : 0;"),
    # --- plausibility ---------------------------------------------------------------------------
    _m("nan_not_rejected", "plausibility", "NaN readings are accepted as real data",
       "    if (std::isnan(reading.temp_c) || std::isnan(reading.hum_pct) || std::isnan(reading.pres_hpa)) return false;\n", "", target=TRAITS, part=BME280),
    _m("humidity_upper_bound_removed", "plausibility", "humidity above 100 % is accepted",
       " || reading.hum_pct > kHumMaxPct", "", target=TRAITS, part=BME280),
    _m("pressure_upper_bound_removed", "plausibility", "pressure above 1100 hPa is accepted",
       " || reading.pres_hpa > kPresMaxHpa", "", target=TRAITS, part=BME280),
    _m("temperature_range_widened", "plausibility", "temperature up to 125 C is accepted",
       "static constexpr float kTempMaxC = 85.0f;", "static constexpr float kTempMaxC = 125.0f;", target=TRAITS, part=BME280),
    _m("pressure_floor_removed", "plausibility", "pressure of 0 hPa is accepted",
       "static constexpr float kPresMinHpa = 300.0f;", "static constexpr float kPresMinHpa = 0.0f;", target=TRAITS, part=BME280),
    _m("plausibility_skipped_on_read", "plausibility", "a successful bus read is trusted without a range check",
       "const bool ok = hal_.sensor_read(reading) && reading_is_plausible(reading);",
       "const bool ok = hal_.sensor_read(reading) && (reading_is_plausible(reading) || true);"),
    # --- identity and addressing ----------------------------------------------------------------
    _m("first_matching_address_wins", "addressing", "stops probing at the first chip that answers, so a second device is never noticed",
       "                hits += 1;\n                found = addr;\n            }", "                hits += 1;\n                found = addr;\n                break;\n            }"),
    _m("failed_rebind_ignored", "addressing", "a failed rebind to the matched address is ignored",
       "            if (!hal_.sensor_begin(found)) return 0;\n", "            (void)hal_.sensor_begin(found);\n"),
    _m("no_rebind_after_probe", "addressing", "driver is left bound to the last address probed",
       "            if (!hal_.sensor_begin(found)) return 0;\n", ""),
    _m("boot_ignores_ambiguity", "addressing", "two answering chips at boot are not treated as ambiguous",
       "        const int hits = probe_sensor();\n        if (hits > 1) {\n            enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, \"AMBIGUOUS ADDR\");\n            return;\n        }\n        if (hits == 0) {",
       "        const int hits = probe_sensor();\n        if (hits > 99) {\n            enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, \"AMBIGUOUS ADDR\");\n            return;\n        }\n        if (hits == 0) {"),
    _m("ambiguity_not_latched", "addressing", "after an ambiguous-address fault the application keeps reading",
       "        if (state_ == AppState::FAULT_AMBIGUOUS_ADDRESS) {\n            return;\n        }\n", ""),
    _m("display_first_address_only", "addressing", "only the first declared display address is tried",
       "for (size_t i = 0; i < n_display_; ++i) {\n            const uint8_t addr = display_addrs_[i];",
       "for (size_t i = 0; i < n_display_ && i < 1; ++i) {\n            const uint8_t addr = display_addrs_[i];"),
    # --- display behaviour ----------------------------------------------------------------------
    _m("display_missing_never_logged", "display", "an absent declared display is never reported",
       "if (display_declared_ && !display_ok_ && !display_missing_logged_) {", "if (false) {"),
    _m("display_missing_log_repeats", "display", "the missing-display line repeats on every loop",
       "            display_missing_logged_ = true;\n", ""),
    _m("writes_to_absent_display", "display", "draws readings even when no display answered",
       "        if (!display_ok_) {\n            return;\n        }\n        if (!have_last_) {",
       "        if (!have_last_) {"),
    _m("fault_drawn_without_display", "display", "draws fault text even when no display answered",
       "        if (display_ok_) {\n            hal_.display_show(message, \"\", \"\", \"\");", "        if (true) {\n            hal_.display_show(message, \"\", \"\", \"\");"),
    _m("stale_headlined_as_ok", "display", "a stale reading is shown under an OK headline",
       "show_reading(\"STATE STALE\");", "show_reading(\"STATE OK\");"),
    _m("last_reading_not_kept", "display", "the last good reading is never remembered, so stale shows no data",
       "        have_last_ = true;\n", ""),
    # --- recovery and state machine -------------------------------------------------------------
    _m("recovery_from_missing_not_announced", "recovery", "a sensor that reappears is not announced as recovered",
       "                if (hits == 1) {\n                    hal_.log(\"RECOVERED\");", "                if (hits == 1) {"),
    _m("read_fault_recovery_not_announced", "recovery", "a read fault that clears is not announced as recovered",
       "        if (was_fault) {\n            hal_.log(\"RECOVERED\");\n        }", "        if (was_fault && false) {\n            hal_.log(\"RECOVERED\");\n        }"),
    _m("failure_count_not_cleared_on_success", "recovery", "isolated failures accumulate across good reads and eventually fault",
       "        consecutive_fails_ = 0;\n        last_ = reading;", "        last_ = reading;"),
    _m("stale_not_logged", "recovery", "the first failed read is not reported as STALE",
       "            log_state(now, AppState::STALE);\n", ""),
    _m("no_bus_recovery_on_fault_entry", "recovery", "entering a read fault does not try to recover the bus",
       "                    log_state(now, AppState::FAULT_SENSOR_READ);\n                    (void)hal_.bus_recover();",
       "                    log_state(now, AppState::FAULT_SENSOR_READ);"),
    _m("no_bus_recovery_on_retry", "recovery", "retries from a read fault never recover the bus",
       "                last_action_ms_ = now;\n                (void)hal_.bus_recover();\n                const int hits = probe_sensor();",
       "                last_action_ms_ = now;\n                const int hits = probe_sensor();"),
    _m("no_rebind_on_fault_entry", "recovery", "entering a read fault does not rebind the driver",
       "                    (void)hal_.sensor_begin(sensor_addr_);\n", ""),
    _m("read_fault_backoff_not_reset", "recovery", "backoff keeps its grown value after a read fault clears, so the next fault starts slow",
       "                    if (state_ == AppState::OK) {\n                        backoff_ms_ = kBackoffInitialMs;\n                        return;",
       "                    if (state_ == AppState::OK) {\n                        return;",
       "backoff_ms_ is read only inside the two fault branches, and every entry into FAULT_SENSOR_READ "
       "resets it in take_reading, so also resetting it at recovery is unobservable."),
    # --- output grammar -------------------------------------------------------------------------
    _m("state_line_grammar_drift", "grammar", "the state line separator changes from '=' to ': '",
       "\"T=%u STATE=%s\"", "\"T=%u STATE: %s\""),
    _m("boot_line_addresses_swapped", "grammar", "the BOOT line reports the display address as the sensor's",
       "sensor_addr_, display_addr_);\n        } else {", "display_addr_, sensor_addr_);\n        } else {"),
    # --- reviewed equivalents (kept so the benchmark proves it handles them honestly) ------------
    _m("missing_recovery_clears_count_redundant", "recovery", "drops a counter reset that take_reading repeats immediately",
       "                    state_ = AppState::OK;\n                    consecutive_fails_ = 0;\n                    backoff_ms_ = kBackoffInitialMs;\n                    take_reading(now);",
       "                    state_ = AppState::OK;\n                    backoff_ms_ = kBackoffInitialMs;\n                    take_reading(now);",
       "FAULT_SENSOR_MISSING is reachable only from boot(), where consecutive_fails_ is still 0, and "
       "take_reading() clears it on the next success; the extra reset cannot change any output."),
)


# Written after the harness was strengthened and never used to tune it, so they estimate how well
# the matrix generalises beyond the mutants it was tuned against.
HELDOUT_MUTANTS: tuple[Mutant, ...] = (
    _m("heldout_sensor_addr_not_recorded", "addressing", "the matched address is never stored, so BOOT reports 0x00",
       "            sensor_addr_ = found;\n", ""),
    _m("heldout_read_fault_backoff_linear", "timing", "read-fault retry backoff grows by a constant instead of doubling",
       "                backoff_ms_ *= 2;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (wrap_elapsed(now, last_action_ms_) >= kReadPeriodMs) {",
       "                backoff_ms_ += 1000;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (wrap_elapsed(now, last_action_ms_) >= kReadPeriodMs) {"),
    _m("heldout_period_boundary_exclusive", "timing", "a reading is taken only strictly after the period, so the period edge is missed",
       "if (wrap_elapsed(now, last_action_ms_) >= kReadPeriodMs) {", "if (wrap_elapsed(now, last_action_ms_) > kReadPeriodMs) {"),
    _m("heldout_missing_retry_boundary_exclusive", "timing", "a missing sensor is retried only strictly after its backoff",
       "        if (state_ == AppState::FAULT_SENSOR_MISSING) {\n            if (wrap_elapsed(now, last_action_ms_) >= backoff_ms_) {",
       "        if (state_ == AppState::FAULT_SENSOR_MISSING) {\n            if (wrap_elapsed(now, last_action_ms_) > backoff_ms_) {"),
    _m("heldout_temperature_floor_removed", "plausibility", "readings below -40 C are accepted",
       "reading.temp_c < kTempMinC || ", "", target=TRAITS, part=BME280),
    _m("heldout_humidity_floor_removed", "plausibility", "negative humidity is accepted",
       "reading.hum_pct < kHumMinPct || ", "", target=TRAITS, part=BME280),
    _m("heldout_recovery_skips_boot_line", "recovery", "a sensor that reappears is not re-identified in the BOOT line",
       "                    hal_.log(\"RECOVERED\");\n                    log_boot();", "                    hal_.log(\"RECOVERED\");"),
    _m("heldout_display_never_probed", "display", "the display is never probed, so it is always reported missing",
       "        probe_display();\n        const int hits = probe_sensor();", "        const int hits = probe_sensor();"),
    _m("heldout_pressure_unit_wrong", "display", "the display shows pressure in Pa while labelled hPa elsewhere",
       "\"%.1f hPa\"", "\"%.1f Pa\"", target=TRAITS, part=BME280),
    _m("heldout_missing_backoff_cap_removed", "timing", "the 30 s cap is not applied to a missing sensor's backoff",
       "                backoff_ms_ *= 2;\n                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {",
       "                backoff_ms_ *= 2;\n            }\n            return;\n        }\n        if (state_ == AppState::FAULT_SENSOR_READ) {"),
    _m("heldout_stale_state_not_tracked", "recovery", "the STALE state is logged but not tracked internally",
       "            state_ = AppState::STALE;\n", "",
       "STALE is never read back by loop_once or take_reading: only FAULT_* and OK are branched on, and "
       "log_state takes the state as an argument, so tracking it internally is unobservable."),
    _m("heldout_boot_clock_not_recorded", "timing", "the boot time is not recorded as the first action time",
       "            booted_ = true;\n            last_action_ms_ = now;\n", "            booted_ = true;\n"),
)


# The Arduino adapter is what runs on the ESP32. The core harness never compiles it; only the vendor-host
# lane does, against the pinned Adafruit sources and a modelled I2C bus.
VENDOR_SMOKE = frozenset({"sensor_default_address_0x77_with_display_0x3C"})
VENDOR_HEALTHY = frozenset({"sensor_default_address_0x77_with_display_0x3C", "sensor_0x76_only", "display_at_0x3D_only"})
# Per part: the default-address scenario is the smoke test; the healthy bus adds the other sensor address and the
# display's second address. Nothing here changes which scenarios exist.
VENDOR_DETECTORS = {
    "adafruit-bme280-stemma-qt": (VENDOR_SMOKE, VENDOR_HEALTHY),
    "adafruit-bh1750-stemma-qt": (
        frozenset({"sensor_default_address_0x23_with_display_0x3C"}),
        frozenset({"sensor_default_address_0x23_with_display_0x3C", "sensor_0x5C_only", "display_at_0x3D_only"}),
    ),
}
_A = "src/main.cpp"
ADAPTER_MUTANTS: tuple[Mutant, ...] = (
    _m("adapter_chip_id_wrong", "identity", "rejects a real BME280 by comparing against the BMP280 id",
       "value != 0x60", "value != 0x58", target=_A),
    _m("adapter_chip_id_unchecked", "identity", "accepts any chip that answers at the address",
       " || value != 0x60) return false;", ") return false;", target=_A),
    _m("adapter_init_wait_unbounded", "bounded-wait", "the status wait loses its 50 ms bound and can spin forever",
       "            if (uint32_t(millis() - started) >= 50) return false;\n", "", target=_A),
    _m("adapter_init_wait_too_long", "bounded-wait", "the status wait is bounded at 5 s instead of 50 ms",
       "(millis() - started) >= 50)", "(millis() - started) >= 5000)", target=_A),
    _m("adapter_reset_write_failure_ignored", "bus-errors", "a NACKed soft-reset write is ignored",
       "        if (!i2c_dev->write(reset, sizeof reset)) return false;\n", "        (void)i2c_dev->write(reset, sizeof reset);\n", target=_A),
    _m("adapter_status_read_failure_ignored", "bus-errors", "a failed status read is treated as ready",
       "            if (!read_checked(BME280_REGISTER_STATUS, value)) return false;\n", "            (void)read_checked(BME280_REGISTER_STATUS, value);\n", target=_A),
    _m("adapter_chip_id_read_failure_ignored", "bus-errors", "a failed chip-id read is treated as a match",
       "        if (!read_checked(BME280_REGISTER_CHIPID, value) || value != 0x60) return false;\n",
       "        (void)read_checked(BME280_REGISTER_CHIPID, value);\n        value = 0x60;\n", target=_A),
    _m("adapter_pressure_unit_wrong", "units", "pressure is reported in pascal while the application expects hPa",
       "bme_.readPressure() / 100.0f;", "bme_.readPressure();", target=_A),
    _m("adapter_display_presence_not_checked", "display", "any address is treated as a display because begin() cannot detect one",
       "        Wire.beginTransmission(addr);\n        if (Wire.endTransmission() != 0) return false;\n", "", target=_A),
    _m("adapter_display_reinitialises_bus", "pins", "the display library calls Wire.begin() again and resets the pins",
       "SSD1306_SWITCHCAPVCC, addr, true, false)", "SSD1306_SWITCHCAPVCC, addr, true, true)", target=_A),
    _m("adapter_recovery_loses_pins", "pins", "bus recovery restarts Wire on the default pins",
       "return Wire.begin(SDA_PIN, SCL_PIN, 100000);", "return Wire.begin();", target=_A),
    _m("adapter_setup_loses_pins", "pins", "setup starts Wire on the default pins",
       "    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n    static SensorApp", "    Wire.begin();\n    static SensorApp", target=_A),
    _m("adapter_setup_pins_swapped", "pins", "setup swaps SDA and SCL",
       "    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n    static SensorApp", "    Wire.begin(SCL_PIN, SDA_PIN, 100000);\n    static SensorApp", target=_A),
    _m("adapter_setup_no_timeout", "bounded-wait", "setup never sets the Wire timeout",
       "    Wire.setTimeOut(50);\n    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n    static SensorApp", "    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n    static SensorApp",
       "In arduino-esp32 2.0.17 (espressif32@6.10.0) the TwoWire constructor sets _timeOutMillis(50) (Wire.cpp:48), "
       "so the explicit 50 ms restates the default. Valid only for that framework version.", target=_A),
    _m("adapter_recovery_no_timeout", "bounded-wait", "bus recovery never re-applies the Wire timeout",
       "        Wire.end();\n        Wire.setTimeOut(50);\n", "        Wire.end();\n",
       "TwoWire::end() in arduino-esp32 2.0.17 frees buffers and deinitialises the bus but never touches "
       "_timeOutMillis, so re-applying 50 ms after end() is redundant. Valid only for that framework version.", target=_A),
    _m("adapter_display_never_flushed", "display", "the frame is built but display() is never called",
       "        display_.display();\n", "", target=_A),
    _m("adapter_display_not_cleared", "display", "the previous frame is never cleared before drawing",
       "        display_.clearDisplay();\n", "", target=_A),
    _m("adapter_log_without_newline", "grammar", "serial lines are written without a terminator",
       "Serial.println(line);", "Serial.print(line);", target=_A),
    _m("adapter_sampling_never_configured", "bme280-setup", "the sampling mode is never set, leaving the sensor in sleep mode",
       "        setSampling();\n", "", target=_A),
    _m("adapter_coefficients_not_read", "bme280-setup", "calibration coefficients are never read",
       "        readCoefficients();\n", "", target=_A),
    _m("adapter_reset_settle_removed", "bme280-setup", "no settling delay after the soft reset",
       "        delay(10);\n        const uint32_t started", "        const uint32_t started", target=_A,
       blind_spot="The model has no start-up window in which the chip does not answer after a soft reset, so the "
                  "settling delay cannot matter to it. The datasheet specifies a start-up time; silicon may enforce it."),
    _m("adapter_old_device_leaked", "resources", "each begin leaks the previous I2C device object",
       "        delete i2c_dev;\n", "", target=_A),
    _m("adapter_bus_speed_changed", "physical", "the bus runs at 400 kHz instead of 100 kHz",
       "    Wire.begin(SDA_PIN, SCL_PIN, 100000);\n    static SensorApp", "    Wire.begin(SDA_PIN, SCL_PIN, 400000);\n    static SensorApp", target=_A),
)


# Written after the vendor-host harness was strengthened and never used to tune it.
ADAPTER_HELDOUT_MUTANTS: tuple[Mutant, ...] = (
    _m("heldout_adapter_humidity_before_temperature", "bme280-setup", "humidity and pressure are compensated before temperature, so they use a stale t_fine",
       "        out.temp_c = bme_.readTemperature();\n        out.hum_pct = bme_.readHumidity();\n        out.pres_hpa = bme_.readPressure() / 100.0f;  // Adafruit reports Pascal\n",
       "        out.hum_pct = bme_.readHumidity();\n        out.pres_hpa = bme_.readPressure() / 100.0f;  // Adafruit reports Pascal\n        out.temp_c = bme_.readTemperature();\n", target=_A),
    _m("heldout_adapter_fourth_line_dropped", "display", "the fourth display line is never printed",
       "        display_.println(l4);\n", "", target=_A),
    _m("heldout_adapter_text_size_doubled", "display", "the display text is drawn at size 2",
       "display_.setTextSize(1);", "display_.setTextSize(2);", target=_A),
    _m("heldout_adapter_display_address_fixed", "addressing", "the display is always initialised at 0x3C whatever address answered",
       "SSD1306_SWITCHCAPVCC, addr, true, false)", "SSD1306_SWITCHCAPVCC, 0x3C, true, false)", target=_A),
    _m("heldout_adapter_sensor_address_fixed", "addressing", "the sensor driver is always bound to 0x76 whatever address was probed",
       "i2c_dev = new Adafruit_I2CDevice(addr, wire);", "i2c_dev = new Adafruit_I2CDevice(0x76, wire);", target=_A),
    _m("heldout_adapter_log_duplicated", "grammar", "every serial line is written twice",
       "Serial.println(line);", "Serial.println(line);\n        Serial.println(line);", target=_A),
    _m("heldout_adapter_bus_recovery_never_ends_bus", "recovery", "bus recovery restarts Wire without ending it first, so the peripheral is never reset",
       "        Wire.end();\n        Wire.setTimeOut(50);\n", "        Wire.setTimeOut(50);\n", target=_A),
    _m("heldout_adapter_recovery_result_inverted", "recovery", "bus_recover reports failure whatever happened",
       "return Wire.begin(SDA_PIN, SCL_PIN, 100000);", "Wire.begin(SDA_PIN, SCL_PIN, 100000);\n        return false;",
       "SensorApp discards bus_recover()'s result at both call sites with (void), so its value is unobservable.", target=_A),
    _m("heldout_adapter_pressure_scale_wrong", "units", "pressure is divided by 1000 instead of 100",
       "readPressure() / 100.0f;", "readPressure() / 1000.0f;", target=_A),
)


# Part-specific mutants for the BH1750 traits. Written before the generic battery was ever run against that part,
# and never used to tune it.
BH1750_TRAITS_MUTANTS: tuple[Mutant, ...] = (
    _m("bh1750_nan_not_rejected", "plausibility", "NaN illuminance is accepted as a reading",
       "    if (std::isnan(reading.lux)) return false;\n", "", target=TRAITS, part=BH1750),
    _m("bh1750_upper_bound_removed", "plausibility", "illuminance above 65535 lx is accepted",
       " || reading.lux > kLuxMax", "", target=TRAITS, part=BH1750),
    _m("bh1750_lower_bound_removed", "plausibility", "negative illuminance is accepted",
       "reading.lux < kLuxMin || ", "", target=TRAITS, part=BH1750),
    _m("bh1750_range_widened", "plausibility", "illuminance up to 1,000,000 lx is accepted",
       "static constexpr float kLuxMax = 65535.0f;", "static constexpr float kLuxMax = 1000000.0f;", target=TRAITS, part=BH1750),
    _m("bh1750_dark_rejected", "plausibility", "a valid dark reading of 0 lx is rejected as implausible",
       "static constexpr float kLuxMin = 0.0f;", "static constexpr float kLuxMin = 1.0f;", target=TRAITS, part=BH1750),
    _m("bh1750_serial_precision_drift", "grammar", "the serial reading loses its decimal place",
       "LUX=%.1f", "LUX=%.0f", target=TRAITS, part=BH1750),
    _m("bh1750_serial_key_renamed", "grammar", "the serial key changes from LUX to LX",
       "STATE=OK LUX=", "STATE=OK LX=", target=TRAITS, part=BH1750),
    _m("bh1750_display_unit_dropped", "display", "the display line loses its unit",
       '"%.1f lx"', '"%.1f"', target=TRAITS, part=BH1750),
)


_NEVER_READ_UNCONFIGURED = (
    "SensorApp reads only after a sensor_begin() of the same device succeeded: every take_reading() call site follows a successful "
    "probe and rebind, and after a failed re-begin the state is FAULT_SENSOR_READ, which probes again before reading. The driver is "
    "therefore never read while unconfigured. Valid for SensorApp as written."
)
# Shared template text whose effect differs for the BH1750: its display has only one data line, so lines 3 and 4 are empty.
BH1750_SHARED_EQUIVALENTS = {
    "heldout_adapter_fourth_line_dropped": (
        "The BH1750 has one channel, so display lines 3 and 4 are always empty strings; printing or omitting the empty fourth line "
        "leaves the framebuffer pixel-identical."
    ),
}

# Adapter mutants for the BH1750's direct Wire driver, written from the adapter template before the BH1750
# vendor-host harness was ever scored against any of them, and not used to tune it.
BH1750_ADAPTER_MUTANTS: tuple[Mutant, ...] = (
    _m("bh_mode_one_time", "bh1750-driver", "the chip is started in one-time mode, so it powers down after the first measurement",
       "static constexpr uint8_t kContinuousHighRes = 0x10;", "static constexpr uint8_t kContinuousHighRes = 0x20;", target=_A, part=BH1750),
    _m("bh_mode_low_resolution", "bh1750-driver", "the chip is started in continuous L-resolution mode",
       "static constexpr uint8_t kContinuousHighRes = 0x10;", "static constexpr uint8_t kContinuousHighRes = 0x13;", target=_A, part=BH1750,
       blind_spot="The model implements no resolution modes: L-resolution (datasheet p.2, 4 lx resolution, 16 ms typical, 24 ms maximum) "
                  "returns the same count as H-resolution, so the mode choice cannot matter to it. Silicon returns a coarser value."),
    _m("bh_opcode_undefined", "bh1750-driver", "the measurement opcode is one the datasheet does not define",
       "static constexpr uint8_t kContinuousHighRes = 0x10;", "static constexpr uint8_t kContinuousHighRes = 0x14;", target=_A, part=BH1750),
    _m("bh_begin_ignores_nack", "bus-errors", "a NACKed measurement command still counts as a successful begin",
       "        if (wire_->endTransmission() != 0) return false;\n        started_ms_", "        wire_->endTransmission();\n        started_ms_", target=_A, part=BH1750),
    _m("bh_failed_begin_stays_configured", "bus-errors", "a failed begin leaves the driver marked as configured",
       "        configured_ = false;\n        wire_->beginTransmission", "        wire_->beginTransmission", target=_A, part=BH1750,
       equivalent_reason=_NEVER_READ_UNCONFIGURED),
    _m("bh_conversion_wait_removed", "bh1750-timing", "the first read does not wait for the conversion, so it returns the reset value 0",
       "        if (waited < kMaxMeasurementMs) delay(kMaxMeasurementMs - waited);\n", "", target=_A, part=BH1750),
    _m("bh_conversion_wait_too_short", "bh1750-timing", "the conversion wait is 100 ms, below the datasheet's 180 ms maximum",
       "static constexpr uint32_t kMaxMeasurementMs = 180;", "static constexpr uint32_t kMaxMeasurementMs = 100;", target=_A, part=BH1750),
    _m("bh_conversion_wait_too_long", "bh1750-timing", "the conversion wait is a full second",
       "static constexpr uint32_t kMaxMeasurementMs = 180;", "static constexpr uint32_t kMaxMeasurementMs = 1000;", target=_A, part=BH1750),
    _m("bh_conversion_start_not_recorded", "bh1750-timing", "begin never records when the conversion started, so a replugged chip is read without waiting",
       "        started_ms_ = millis();\n        configured_ = true;", "        configured_ = true;", target=_A, part=BH1750),
    _m("bh_reads_one_byte", "bh1750-driver", "only one result byte is requested",
       "requestFrom(int(addr_), 2) != 2", "requestFrom(int(addr_), 1) != 1", target=_A, part=BH1750),
    _m("bh_short_read_unchecked", "bus-errors", "a failed read is not noticed and the empty buffer is used as a result",
       "if (wire_->requestFrom(int(addr_), 2) != 2) return false;", "wire_->requestFrom(int(addr_), 2);", target=_A, part=BH1750,
       equivalent_reason="After a failed requestFrom, read() returns -1, so the unchecked buffer is (0xFFFF << 8 | 0xFFFF) / 1.2, about 14 million lx. "
                         "reading_is_plausible rejects that (kLuxMax is 65535), so the application behaves exactly as with the check. "
                         "Defence in depth, valid only while the plausibility ceiling stays below that value."),
    _m("bh_byte_order_swapped", "bh1750-driver", "the result bytes are combined low byte first",
       "(high << 8) | low", "(low << 8) | high", target=_A, part=BH1750),
    _m("bh_divisor_wrong", "bh1750-driver", "the raw count is not divided by 1.2",
       "/ 1.2f", "/ 1.0f", target=_A, part=BH1750),
    _m("bh_high_byte_only", "bh1750-driver", "the low byte is dropped from the result",
       "float((high << 8) | low)", "float(high << 8)", target=_A, part=BH1750),
    _m("bh_address_fixed", "addressing", "the driver is always bound to 0x23 whatever address was probed",
       "        addr_ = addr;\n        configured_ = false;", "        addr_ = 0x23;\n        configured_ = false;", target=_A, part=BH1750),
    _m("bh_hal_begin_result_ignored", "bus-errors", "the HAL reports every begin as successful",
       "bool sensor_begin(uint8_t addr) override { return bh_.begin(addr, &Wire); }",
       "bool sensor_begin(uint8_t addr) override { bh_.begin(addr, &Wire); return true; }", target=_A, part=BH1750),
    _m("bh_wrong_wire_instance", "pins", "the driver is handed Wire1, which setup() never starts",
       "return bh_.begin(addr, &Wire); }", "return bh_.begin(addr, &Wire1); }", target=_A, part=BH1750),
)

BH1750_ADAPTER_HELDOUT_MUTANTS: tuple[Mutant, ...] = (
    _m("heldout_bh_divisor_1_44", "bh1750-driver", "the divisor is the datasheet's upper bound 1.44 instead of the typical 1.2",
       "/ 1.2f", "/ 1.44f", target=_A, part=BH1750),
    _m("heldout_bh_read_without_configuration", "bus-errors", "a read is attempted on a driver that never started a measurement",
       "        if (!configured_) return false;\n", "", target=_A, part=BH1750,
       equivalent_reason=_NEVER_READ_UNCONFIGURED),
    _m("heldout_bh_low_byte_zero", "bh1750-driver", "the second result byte is read but replaced by zero",
       "const uint16_t low = uint16_t(wire_->read());", "const uint16_t low = 0;", target=_A, part=BH1750),
    _m("heldout_bh_mode_two", "bh1750-driver", "the chip is started in continuous H-resolution mode 2",
       "static constexpr uint8_t kContinuousHighRes = 0x10;", "static constexpr uint8_t kContinuousHighRes = 0x11;", target=_A, part=BH1750,
       blind_spot="The model implements no resolution modes: H-resolution mode 2 (0.5 lx resolution) returns the same count as mode 1, "
                  "so the mode choice cannot matter to it. Silicon scales the result differently."),
    _m("heldout_bh_power_down_after_read", "bh1750-driver", "the chip is powered down after every read, so it stops converting",
       "        lux = float((high << 8) | low) / 1.2f;\n        return true;",
       "        lux = float((high << 8) | low) / 1.2f;\n        wire_->beginTransmission(addr_);\n        wire_->write(uint8_t(0x00));\n        wire_->endTransmission();\n        return true;",
       target=_A, part=BH1750),
)

# Bugs in the template text that the BME280 and BH1750 adapters share (display, pins, bus recovery, serial output).
SHARED_ADAPTER_IDS = (
    "adapter_display_presence_not_checked", "adapter_display_reinitialises_bus", "adapter_recovery_loses_pins",
    "adapter_setup_loses_pins", "adapter_setup_pins_swapped", "adapter_setup_no_timeout", "adapter_recovery_no_timeout",
    "adapter_display_never_flushed", "adapter_display_not_cleared", "adapter_log_without_newline", "adapter_bus_speed_changed",
)
SHARED_ADAPTER_HELDOUT_IDS = (
    "heldout_adapter_fourth_line_dropped", "heldout_adapter_text_size_doubled", "heldout_adapter_display_address_fixed",
    "heldout_adapter_log_duplicated", "heldout_adapter_bus_recovery_never_ends_bus", "heldout_adapter_recovery_result_inverted",
)


def adapter_mutants(part_id: str, which: str = "all") -> tuple[Mutant, ...]:
    """The adapter mutants that apply to a part: its own, plus the shared template text for the BH1750."""
    if part_id == BME280:
        pools = {"primary": ADAPTER_MUTANTS, "heldout": ADAPTER_HELDOUT_MUTANTS, "all": ADAPTER_MUTANTS + ADAPTER_HELDOUT_MUTANTS}
        return pools[which]
    by_id = {m.id: dataclasses.replace(m, equivalent_reason=BH1750_SHARED_EQUIVALENTS.get(m.id, m.equivalent_reason))
             for m in ADAPTER_MUTANTS + ADAPTER_HELDOUT_MUTANTS}
    primary = tuple(by_id[i] for i in SHARED_ADAPTER_IDS) + BH1750_ADAPTER_MUTANTS
    heldout = tuple(by_id[i] for i in SHARED_ADAPTER_HELDOUT_IDS) + BH1750_ADAPTER_HELDOUT_MUTANTS
    return {"primary": primary, "heldout": heldout, "all": primary + heldout}[which]


def apply_mutant(source: str, mutant: Mutant) -> str:
    """Return mutated source; refuse a mutant that matches zero or several places."""
    count = source.count(mutant.old)
    if count != 1:
        raise ValueError(f"mutant {mutant.id} matched {count} places, expected exactly 1")
    mutated = source.replace(mutant.old, mutant.new, 1)
    if mutated == source:
        raise ValueError(f"mutant {mutant.id} did not change the source")
    return mutated


def spec_for_part(part_id: str) -> dict:
    """The ESP32 + OLED + sensor example wired for the given supported part."""
    from hardware_splicer.device_parts import example_spec_for_part

    return example_spec_for_part(part_id)


def build_package(directory: Path, part_id: str = BME280) -> Path:
    from hardware_splicer.device_application import build_device_application

    _metadata, archive = build_device_application(spec_for_part(part_id))
    zip_path = directory / "application.zip"
    zip_path.write_bytes(archive)
    project = directory / "baseline"
    with zipfile.ZipFile(zip_path) as bundle:
        bundle.extractall(project)
    return project


def run_project(project: Path, *, compile_timeout: float = 120, run_timeout: float = 60) -> dict:
    """Compile with the production flags and run; return the scenario results."""
    gxx = shutil.which("g++")
    if not gxx:
        raise RuntimeError("g++ is required")
    try:
        compiled = _execute(
            [gxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", "src", "test/host/harness.cpp", "-o", "harness"],
            cwd=project, capture_output=True, timeout=compile_timeout, check=False,
        )
    except (subprocess.TimeoutExpired, BoundedProcessError):
        return {"outcome": "STILLBORN", "failed": [], "detail": "compile timed out"}
    if compiled.returncode != 0:
        first = (compiled.stderr or b"").decode(errors="replace").strip().splitlines()[:1]
        return {"outcome": "STILLBORN", "failed": [], "detail": first[0] if first else "compile failed"}
    try:
        ran = _execute([str(project / "harness")], cwd=project, timeout=run_timeout)
    except (subprocess.TimeoutExpired, BoundedProcessError):
        return {"outcome": "KILLED", "failed": ["<timeout>"], "detail": "harness did not finish"}
    failed, problem = _failed_rows(ran, HOST_SCENARIOS)
    return {"outcome": "KILLED" if failed else "SURVIVED", "failed": failed, "detail": problem}


def evaluate(mutant: Mutant, baseline: Path, workdir: Path) -> dict:
    project = workdir / mutant.id
    shutil.copytree(baseline, project)
    core = project / mutant.target
    core.write_text(apply_mutant(core.read_text(encoding="utf-8"), mutant), encoding="utf-8")
    result = run_project(project)
    failed = set(result["failed"])
    return {
        "id": mutant.id,
        "bug_class": mutant.bug_class,
        "story": mutant.story,
        "outcome": result["outcome"],
        "failing_scenarios": sorted(failed),
        "detected_by": {
            "smoke": bool(failed & SMOKE),
            "healthy": bool(failed & HEALTHY),
            "matrix": result["outcome"] == "KILLED",
        },
        "equivalent_reason": mutant.equivalent_reason,
        "detail": result["detail"],
    }


def summarize(rows: list[dict]) -> dict:
    live = [row for row in rows if row["outcome"] != "STILLBORN"]
    reviewed_equivalent = [row for row in live if row["outcome"] == "SURVIVED" and row["equivalent_reason"]]
    scored = [row for row in live if row not in reviewed_equivalent]

    def tier(name: str) -> dict:
        killed = sum(1 for row in scored if row["detected_by"][name])
        return {"killed": killed, "of": len(scored), "score": round(killed / len(scored), 3) if scored else None}

    classes: dict[str, dict] = {}
    for row in scored:
        entry = classes.setdefault(row["bug_class"], {"total": 0, "smoke": 0, "healthy": 0, "matrix": 0})
        entry["total"] += 1
        for name in ("smoke", "healthy", "matrix"):
            entry[name] += int(row["detected_by"][name])
    return {
        "mutants_defined": len(rows),
        "stillborn_compile_errors": [row["id"] for row in rows if row["outcome"] == "STILLBORN"],
        "reviewed_equivalent": [row["id"] for row in reviewed_equivalent],
        "scored_mutants": len(scored),
        "tiers": {name: tier(name) for name in ("smoke", "healthy", "matrix")},
        "survivors_without_review": [row["id"] for row in scored if row["outcome"] == "SURVIVED"],
        "caught_only_by_fault_scenarios": [row["id"] for row in scored if row["detected_by"]["matrix"] and not row["detected_by"]["healthy"]],
        "by_bug_class": classes,
    }


def _failed_rows(ran: subprocess.CompletedProcess, expected: tuple[str, ...]) -> tuple[list[str], str]:
    """Return (failing scenario names, problem) for one harness run, as the product's verifier reads it."""
    try:
        rows = [json.loads(line) for line in ran.stdout.decode().splitlines() if line.strip()]
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ["<malformed output>"], "harness output was not JSON"
    problem = _scenario_failure(rows, expected, ran.returncode)
    failed = [str(row.get("scenario")) for row in rows if isinstance(row, dict)
              and (row.get("pass") is not True or row.get("finding", False) is not False)]
    if problem and not failed:
        failed = ["<exit code>" if ran.returncode != 0 else "<invalid scenario output>"]
    return failed, problem


def run_vendor_project(project: Path, libdeps: Path, *, compile_timeout: float = 240, run_timeout: float = 60) -> dict:
    """Compile the adapter with the product's own vendor-host command and run its scenarios."""
    from hardware_splicer.device_application_execution import vendor_host_compile_command

    descriptor = json.loads((project / "PART_DESCRIPTOR.json").read_text(encoding="utf-8"))
    profile = descriptor["adapter"].get("vendor_profile") or "bme280"
    binary = project / "vendor_harness"
    try:
        compiled = _execute(vendor_host_compile_command(project, libdeps, binary, profile), cwd=project,
                                  capture_output=True, timeout=compile_timeout, check=False)
    except (subprocess.TimeoutExpired, BoundedProcessError):
        return {"outcome": "STILLBORN", "failed": [], "detail": "compile timed out"}
    if compiled.returncode != 0:
        first = [line for line in (compiled.stderr or b"").decode(errors="replace").splitlines() if "error" in line][:1]
        return {"outcome": "STILLBORN", "failed": [], "detail": first[0] if first else "compile failed"}
    try:
        ran = _execute([str(binary)], cwd=project, timeout=run_timeout)
    except (subprocess.TimeoutExpired, BoundedProcessError):
        return {"outcome": "KILLED", "failed": ["<timeout>"], "detail": "vendor harness did not finish"}
    failed, problem = _failed_rows(ran, vendor_profile(profile)["scenarios"])
    return {"outcome": "KILLED" if failed else "SURVIVED", "failed": failed, "detail": problem}


def evaluate_adapter(mutant: Mutant, baseline: Path, workdir: Path, libdeps: Path, part_id: str = BME280) -> dict:
    project = workdir / mutant.id
    shutil.copytree(baseline, project)
    target = project / mutant.target
    target.write_text(apply_mutant(target.read_text(encoding="utf-8"), mutant), encoding="utf-8")
    vendor = run_vendor_project(project, libdeps)
    core = run_project(project)  # the core harness does not compile main.cpp; measured, not assumed
    failed = set(vendor["failed"])
    smoke, healthy = VENDOR_DETECTORS[part_id]
    return {
        "id": mutant.id, "bug_class": mutant.bug_class, "story": mutant.story,
        "outcome": vendor["outcome"],
        "failing_scenarios": sorted(failed),
        "detected_by": {
            "core_lane": core["outcome"] == "KILLED",
            "vendor_smoke": bool(failed & smoke),
            "vendor_healthy": bool(failed & healthy),
            "vendor_matrix": vendor["outcome"] == "KILLED",
        },
        "equivalent_reason": mutant.equivalent_reason, "blind_spot": mutant.blind_spot, "detail": vendor["detail"],
    }


def summarize_adapter(rows: list[dict]) -> dict:
    live = [row for row in rows if row["outcome"] != "STILLBORN"]
    reviewed = [row for row in live if row["outcome"] == "SURVIVED" and row["equivalent_reason"]]
    scored = [row for row in live if row not in reviewed]
    names = ("core_lane", "vendor_smoke", "vendor_healthy", "vendor_matrix")
    classes: dict[str, dict] = {}
    for row in scored:
        entry = classes.setdefault(row["bug_class"], {"total": 0, **{name: 0 for name in names}})
        entry["total"] += 1
        for name in names:
            entry[name] += int(row["detected_by"][name])
    survivors = [row for row in scored if row["outcome"] == "SURVIVED"]
    return {
        "mutants_defined": len(rows),
        "stillborn_compile_errors": [row["id"] for row in rows if row["outcome"] == "STILLBORN"],
        "reviewed_equivalent": [row["id"] for row in reviewed],
        "scored_mutants": len(scored),
        "tiers": {name: {"killed": sum(1 for row in scored if row["detected_by"][name]), "of": len(scored),
                         "score": round(sum(1 for row in scored if row["detected_by"][name]) / len(scored), 3) if scored else None}
                  for name in names},
        "known_host_model_blind_spots": [row["id"] for row in survivors if row["blind_spot"]],
        "survivors_without_review": [row["id"] for row in survivors if not row["blind_spot"]],
        "by_bug_class": classes,
    }


def run_adapter_lane(args: argparse.Namespace) -> int:
    from hardware_splicer.device_application_execution import vendor_libs_available

    part_id = {"bme280": BME280, "bh1750": BH1750}[args.part]
    profile = args.part
    libdeps = args.libdeps or (Path(os.environ["HS_DEVICE_RUNTIME_VENDOR_LIBS"]) if os.environ.get("HS_DEVICE_RUNTIME_VENDOR_LIBS") else None)
    if libdeps is None or not vendor_libs_available(libdeps, profile):
        print("The adapter lane needs the pinned libdeps (--libdeps or HS_DEVICE_RUNTIME_VENDOR_LIBS); see test/vendor_host/README.md.", file=sys.stderr)
        return 2
    libdeps = libdeps.resolve()
    with tempfile.TemporaryDirectory(prefix="hs-adapter-matrix-") as scratch:
        work = Path(scratch)
        baseline = build_package(work, part_id)
        if args.vendor_host:
            shutil.rmtree(baseline / "test" / "vendor_host")
            shutil.copytree(args.vendor_host, baseline / "test" / "vendor_host")
        base = run_vendor_project(baseline, libdeps)
        if base["outcome"] != "SURVIVED":
            print(f"Vendor baseline is not clean ({base['outcome']}: {base['failed']}); the benchmark is invalid.", file=sys.stderr)
            return 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            chosen = adapter_mutants(part_id, args.set)
            rows = list(pool.map(lambda mutant: evaluate_adapter(mutant, baseline, work, libdeps, part_id), chosen))
    report = {
        "schema_version": SCHEMA,
        "lane": "adapter",
        "mutant_set": args.set,
        "claim_boundary": CLAIM_BOUNDARY,
        "part": part_id,
        "target": f"{part_id} Arduino adapter (src/main.cpp) against pinned Adafruit libraries and a modelled I2C bus",
        "vendor_host_override": args.vendor_host.name if args.vendor_host else None,
        "detectors": {"core_lane": "all 15 core scenarios (does not compile main.cpp)", "vendor_smoke": sorted(VENDOR_DETECTORS[part_id][0]),
                      "vendor_healthy": sorted(VENDOR_DETECTORS[part_id][1]), "vendor_matrix": "all 11 vendor-host scenarios"},
        "summary": summarize_adapter(rows),
        "mutants": rows,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(f"adapter mutants defined={summary['mutants_defined']} scored={summary['scored_mutants']} "
          f"stillborn={len(summary['stillborn_compile_errors'])} reviewed_equivalent={len(summary['reviewed_equivalent'])}")
    for name, tier in summary["tiers"].items():
        print(f"  {name:15s} {tier['killed']:>3}/{tier['of']:<3} = {tier['score']}")
    if summary["known_host_model_blind_spots"]:
        print("  known host-model blind spots:", ", ".join(summary["known_host_model_blind_spots"]))
    if summary["survivors_without_review"]:
        print("  SURVIVORS needing review:", ", ".join(summary["survivors_without_review"]))
    if summary["stillborn_compile_errors"]:
        print("  STILLBORN (fix the mutant):", ", ".join(summary["stillborn_compile_errors"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="write the JSON report here")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--lane", choices=("core", "adapter"), default="core",
                        help="core: application logic via the host harness; adapter: main.cpp via the vendor-host lane")
    parser.add_argument("--libdeps", type=Path, default=None,
                        help="pinned PlatformIO libdeps directory for --lane adapter (default: $HS_DEVICE_RUNTIME_VENDOR_LIBS)")
    parser.add_argument("--part", choices=("bme280", "bh1750"), default="bme280",
                        help="core lane: which supported part's generated package to test (default: bme280)")
    parser.add_argument("--set", choices=("primary", "heldout", "all"), default="primary",
                        help="which mutants to score (default: the primary set)")
    parser.add_argument("--vendor-host", type=Path, dest="vendor_host",
                        help="for --lane adapter: replace test/vendor_host with this directory, e.g. an earlier revision")
    parser.add_argument("--harness", type=Path,
                        help="use this host harness instead of the generated one, e.g. to score an earlier revision")
    args = parser.parse_args(argv)
    if args.lane == "adapter":
        return run_adapter_lane(args)

    part_id = {"bme280": BME280, "bh1750": BH1750}[args.part]
    with tempfile.TemporaryDirectory(prefix="hs-fault-matrix-") as scratch:
        work = Path(scratch)
        baseline = build_package(work, part_id)
        if args.harness:
            (baseline / "test" / "host" / "harness.cpp").write_bytes(args.harness.read_bytes())
        base = run_project(baseline)
        if base["outcome"] != "SURVIVED":
            print(f"Baseline is not clean ({base['outcome']}: {base['failed']}); the benchmark is invalid.", file=sys.stderr)
            return 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            extra = BH1750_TRAITS_MUTANTS if part_id == BH1750 else ()
            pools = {"primary": MUTANTS + extra, "heldout": HELDOUT_MUTANTS, "all": MUTANTS + extra + HELDOUT_MUTANTS}
            chosen = tuple(m for m in pools[args.set] if m.part in ("", part_id))
            rows = list(pool.map(lambda mutant: evaluate(mutant, baseline, work), chosen))
    report = {
        "schema_version": SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "target": f"{part_id} host application core (src/app_core.h and the part's src/part_traits.h)",
        "part": part_id,
        "mutant_set": args.set,
        "harness_override": args.harness.name if args.harness else None,
        "detectors": {"smoke": sorted(SMOKE), "healthy": sorted(HEALTHY), "matrix": "all host scenarios"},
        "summary": summarize(rows),
        "mutants": rows,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    summary = report["summary"]
    print(f"mutants defined={summary['mutants_defined']} scored={summary['scored_mutants']} "
          f"stillborn={len(summary['stillborn_compile_errors'])} reviewed_equivalent={len(summary['reviewed_equivalent'])}")
    for name, tier in summary["tiers"].items():
        print(f"  {name:8s} {tier['killed']:>3}/{tier['of']:<3} = {tier['score']}")
    if summary["survivors_without_review"]:
        print("  SURVIVORS needing review:", ", ".join(summary["survivors_without_review"]))
    if summary["stillborn_compile_errors"]:
        print("  STILLBORN (fix the mutant):", ", ".join(summary["stillborn_compile_errors"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
