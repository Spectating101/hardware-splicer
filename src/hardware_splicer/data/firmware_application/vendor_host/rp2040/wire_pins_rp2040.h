#pragma once
// The Raspberry Pi Pico's version of wire_pins_stay_explicit: the planned I2C controller, its pins and clock after boot
// and after recovery, nothing on the other controller, and no core panic. Drafted by Gemini 4 Argon; made generic over
// the sensor and integrated by Hardware-Splicer. Include it after the harness defines setup(), tracked_loop() and pump_to().

#include <string>

#include "Wire.h"
#include "vendor_common.h"

// board_config.h names the planned instance and pins; there is no default, so a package without it does not compile.
#ifndef HS_WIRE
#error "board_config.h must define HS_WIRE, HS_PLANNED_SDA and HS_PLANNED_SCL for the RP2040 lane"
#endif

template <typename WorldT, typename Plug, typename Unplug>
static Result scenario_wire_pins_rp2040(WorldT &w, Plug plug_sensor_now, Unplug unplug_sensor_now) {
    const char *name = (&HS_WIRE == &Wire1) ? "Wire1" : "Wire";
    const auto at = [&](const char *when) {
        return std::string(when) + ", " + name + " is on sda=" + std::to_string(HS_WIRE.sda_pin()) + " scl=" +
               std::to_string(HS_WIRE.scl_pin()) + ", not the planned sda=" + std::to_string(HS_PLANNED_SDA) +
               " scl=" + std::to_string(HS_PLANNED_SCL);
    };
    const auto other_bus = [&](const char *when) -> std::string {
        if (g_i2c_bus_other.log.empty()) return "";
        return "the other I2C controller carried " + std::to_string(g_i2c_bus_other.log.size()) +
               " transaction(s) " + when + ": the adapter talked on the wrong controller";
    };

    w.attach();
    plug_sensor_now(w);
    w.oled3c.plug();
    setup();  // a core panic throws; vendor_main fails the scenario with its message
    // Read before any loop, as on the ESP32: the display library resets the clock after its own init.
    if (!HS_WIRE.inited()) return {false, std::string("after setup(), ") + name + " is not running", false};
    if (HS_WIRE.sda_pin() != HS_PLANNED_SDA || HS_WIRE.scl_pin() != HS_PLANNED_SCL) return {false, at("after setup()"), false};
    if (HS_WIRE.getClock() != 100000) {
        return {false, std::string("setup() set ") + name + " to " + std::to_string(HS_WIRE.getClock()) +
                           " Hz, not the planned 100000 Hz", false};
    }
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    if (const std::string bad = other_bus("during boot"); !bad.empty()) return {false, bad, false};

    unplug_sensor_now(w);
    pump_to(9000);
    plug_sensor_now(w);
    for (uint32_t t = millis(); t < 60000; t += 1000) {
        pump_to(t);
        if (count_exact(Serial.lines(), "RECOVERED") >= 1) break;
    }
    if (count_exact(Serial.lines(), "RECOVERED") < 1) return {false, "no RECOVERED after the sensor was replugged", false};
    if (const std::string bad = other_bus("during recovery"); !bad.empty()) return {false, bad, false};
    if (!HS_WIRE.inited() || HS_WIRE.sda_pin() != HS_PLANNED_SDA || HS_WIRE.scl_pin() != HS_PLANNED_SCL) {
        return {false, at("after recovery"), false};
    }
    // begin() on a running bus is a no-op on this core, so recovery must end() first: boot plus recovery is at least two
    // begin() calls that really started the bus.
    int started = 0;
    for (const auto &c : HS_WIRE.begin_calls()) started += c.actually_inited ? 1 : 0;
    if (started < 2) {
        return {false, "bus recovery did not end and restart " + std::string(name) + ": " + std::to_string(started) +
                           " begin() call(s) started it", false};
    }
    if (!wire_panics().empty()) return {false, "the core panicked: " + wire_panics().front(), false};
    return {true, std::string(name) + " on sda=" + std::to_string(HS_WIRE.sda_pin()) + " scl=" + std::to_string(HS_WIRE.scl_pin()) +
                      " at 100000 Hz after boot and recovery; nothing on the other controller; " + std::to_string(started) +
                      " begin() calls started the bus",
            false};
}
