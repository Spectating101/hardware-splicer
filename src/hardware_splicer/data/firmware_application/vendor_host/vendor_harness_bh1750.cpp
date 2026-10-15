// Host compile of the real BH1750 Arduino adapter + the pinned SSD1306/GFX/BusIO sources against a modelled
// I2C bus. The BH1750 model is written from the Rohm datasheet (2009.04 Rev.B), see models_bh1750.h.
// A pass is not silicon, not the ESP32 Wire driver's real timing, and not electrical behaviour.
#include "models_bh1750.h"
#include "vendor_common.h"

// The datasheet's own worked examples (p.7) are the oracle, so the divide-by-1.2 is not checked against itself:
//   0x8390 (33680 counts)  ->  "28067 [lx]"        0x0110 (272 counts)  ->  "227 [lx]"
static constexpr uint16_t kRawBright = 0x8390;
static constexpr double kLuxBright = 28067.0;
static constexpr uint16_t kRawDim = 0x0110;
static constexpr double kLuxDim = 227.0;
// The datasheet rounds to whole lx; the application prints one decimal.
static constexpr double kLuxTol = 0.5;

// One conversion wait per loop at most: p.2 gives 180 ms maximum for H-resolution. Bus recovery and a rebind
// start a conversion but do not wait for it; only the read that follows does.
static constexpr uint32_t kLoopBudgetMs = 180;

struct OkReading {
    uint32_t t_ms = 0;
    double lux = 0;
};

static bool parse_ok(const std::string &line, OkReading &out) {
    unsigned t = 0;
    if (std::sscanf(line.c_str(), "T=%u STATE=OK LUX=%lf", &t, &out.lux) != 2) return false;
    out.t_ms = t;
    return true;
}

// Every STATE=OK line from `from` on must read `expected`; returns how many there were.
static bool lux_is(double expected, size_t from, std::string &detail, int *count = nullptr) {
    int n = 0;
    const auto &lines = Serial.lines();
    for (size_t i = from; i < lines.size(); ++i) {
        OkReading r;
        if (!parse_ok(lines[i], r)) continue;
        n += 1;
        if (std::fabs(r.lux - expected) > kLuxTol) {
            detail = "LUX " + std::to_string(r.lux) + " at T=" + std::to_string(r.t_ms) + " vs datasheet " +
                     std::to_string(expected);
            return false;
        }
    }
    if (count) *count = n;
    if (n == 0) {
        detail = "no STATE=OK reading lines";
        return false;
    }
    return true;
}

static bool last_ok_lines(std::string &l1, std::string &l2, std::string &l3, std::string &l4) {
    OkReading r;
    bool found = false;
    for (const auto &line : Serial.lines()) {
        OkReading candidate;
        if (parse_ok(line, candidate)) {
            r = candidate;
            found = true;
        }
    }
    if (!found) return false;
    char a[24];
    std::snprintf(a, sizeof a, "%.1f lx", r.lux);
    l1 = "STATE OK";
    l2 = a;
    l3 = "";
    l4 = "";
    return true;
}

static bool sensor_reads_go_to(uint8_t addr, std::string &detail) {
    bool any = false;
    for (const auto &tx : g_i2c_bus.log) {
        if (tx.direction != I2cDir::Read) continue;
        if (tx.address != 0x23 && tx.address != 0x5C) continue;
        any = true;
        if (tx.address != addr) {
            detail = "sensor I2C read went to 0x" + std::to_string(tx.address) + " not 0x" + std::to_string(addr);
            return false;
        }
    }
    if (!any) {
        detail = "no sensor I2C reads recorded";
        return false;
    }
    return true;
}

static int sensor_tx_count() {
    int n = 0;
    for (const auto &tx : g_i2c_bus.log)
        if (tx.address == 0x23 || tx.address == 0x5C) n += 1;
    return n;
}

struct World {
    Bh1750Model bh23{0x23};
    Bh1750Model bh5c{0x5C};
    Ssd1306Model oled3c{0x3C};
    Ssd1306Model oled3d{0x3D};

    void attach() {
        g_i2c_bus.attach(0x23, &bh23);
        g_i2c_bus.attach(0x5C, &bh5c);
        g_i2c_bus.attach(0x3C, &oled3c);
        g_i2c_bus.attach(0x3D, &oled3d);
    }
    int illegal_opcodes() const { return bh23.unknown_opcodes() + bh5c.unknown_opcodes(); }
};

static bool boot_and_settle(uint32_t until_ms) {
    setup();
    if (!tracked_loop()) return false;
    pump_to(until_ms);
    return true;
}

static Result scenario_sensor_default_address() {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    w.oled3c.plug();
    if (!boot_and_settle(2500)) return {false, "watchdog during boot", false};
    Result r;
    if (count_contains(Serial.lines(), "BOOT sensor=0x23 display=0x3C") != 1) {
        r.detail = "missing BOOT sensor=0x23 display=0x3C";
        return r;
    }
    if (!lux_is(kLuxBright, 0, r.detail)) return r;
    if (!sensor_reads_go_to(0x23, r.detail)) return r;
    if (w.bh23.measurement_commands() < 1) {
        r.detail = "no measurement command ever reached the chip, so its data register stayed at the reset value";
        return r;
    }
    if (w.illegal_opcodes() != 0) {
        r.detail = "the adapter sent a byte sequence the datasheet instruction set does not define";
        return r;
    }
    if (!w.oled3c.saw_display_on()) {
        r.detail = "SSD1306 init sequence lacked display-on 0xAF";
        return r;
    }
    std::string l1, l2, l3, l4;
    if (!last_ok_lines(l1, l2, l3, l4) || !framebuffer_matches(w.oled3c, l1, l2, l3, l4, r.detail)) return r;
    // The light level changes: later readings must follow it. A chip left in a one-time mode, or an adapter that
    // stops conversions, keeps returning the old value.
    const size_t mark = Serial.lines().size();
    w.bh23.set_raw(kRawDim);
    pump_to(7000);
    int after = 0;
    for (size_t i = mark; i < Serial.lines().size(); ++i) {
        OkReading o;
        if (!parse_ok(Serial.lines()[i], o)) continue;
        after += 1;
        if (std::fabs(o.lux - kLuxDim) > kLuxTol && std::fabs(o.lux - kLuxBright) > kLuxTol) {
            r.detail = "LUX " + std::to_string(o.lux) + " is neither the old nor the new level";
            return r;
        }
    }
    OkReading last;
    bool have = false;
    for (const auto &line : Serial.lines()) {
        OkReading o;
        if (parse_ok(line, o)) {
            last = o;
            have = true;
        }
    }
    if (!have || after < 2 || std::fabs(last.lux - kLuxDim) > kLuxTol) {
        r.detail = "readings did not follow a change in light: last LUX " + std::to_string(last.lux);
        return r;
    }
    r.pass = true;
    r.detail = "datasheet p.7 worked examples 28067 lx and 227 lx; measurement command at 0x23; light change followed";
    return r;
}

static Result scenario_sensor_0x5c_only() {
    World w;
    w.attach();
    w.bh5c.plug(kRawDim);
    w.oled3c.plug();
    if (!boot_and_settle(2500)) return {false, "watchdog during boot", false};
    Result r;
    if (count_contains(Serial.lines(), "BOOT sensor=0x5C display=0x3C") != 1) {
        r.detail = "missing BOOT sensor=0x5C display=0x3C";
        return r;
    }
    if (!lux_is(kLuxDim, 0, r.detail)) return r;
    if (!sensor_reads_go_to(0x5C, r.detail)) return r;
    r.pass = true;
    r.detail = "datasheet p.7 example 227 lx; I2C reads at 0x5C";
    return r;
}

static Result scenario_display_0x3d_only() {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    w.oled3d.plug();
    if (!boot_and_settle(2500)) return {false, "watchdog during boot", false};
    Result r;
    if (count_contains(Serial.lines(), "BOOT sensor=0x23 display=0x3D") != 1) {
        r.detail = "missing BOOT sensor=0x23 display=0x3D";
        return r;
    }
    if (!w.oled3d.saw_display_on()) {
        r.detail = "0x3D init sequence lacked 0xAF";
        return r;
    }
    std::string l1, l2, l3, l4;
    if (!last_ok_lines(l1, l2, l3, l4) || !framebuffer_matches(w.oled3d, l1, l2, l3, l4, r.detail)) return r;
    r.pass = true;
    r.detail = "framebuffer pixels match GFXcanvas1 of the four text lines";
    return r;
}

static Result scenario_display_absent() {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    if (!boot_and_settle(4000)) return {false, "watchdog during boot", false};
    Result r;
    if (count_exact(Serial.lines(), "DISPLAY MISSING") != 1) {
        r.detail = "DISPLAY MISSING must appear exactly once";
        return r;
    }
    if (w.oled3c.saw_data_bytes() || w.oled3d.saw_data_bytes()) {
        r.detail = "framebuffer data written with no display on the bus";
        return r;
    }
    int probes_3c = 0, probes_3d = 0;
    for (const auto &tx : g_i2c_bus.log) {
        if (tx.address != 0x3C && tx.address != 0x3D) continue;
        const bool probe = tx.bare_probe && tx.direction == I2cDir::Write;
        if (probe && tx.address == 0x3C) {
            probes_3c += 1;
        } else if (probe && tx.address == 0x3D) {
            probes_3d += 1;
        } else {
            r.detail = "non-probe transaction to display address after presence check";
            return r;
        }
    }
    if (probes_3c < 1 || probes_3d < 1) {
        r.detail = "expected a presence probe at both 0x3C and 0x3D";
        return r;
    }
    if (!lux_is(kLuxBright, 0, r.detail)) return r;
    r.pass = true;
    r.detail = "DISPLAY MISSING once; only bare address probes to 0x3C/0x3D; readings continue";
    return r;
}

static Result scenario_sensor_absent_then_appears() {
    World w;
    w.attach();
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    if (count_contains(Serial.lines(), "FAULT_SENSOR_MISSING") != 1) {
        return {false, "expected FAULT_SENSOR_MISSING at boot", false};
    }
    const uint32_t retry_at[] = {1000, 3000, 7000, 15000};
    int prev = sensor_tx_count();
    long live_after_second_retry = 0;
    for (uint32_t t : retry_at) {
        pump_to(t - 1);
        if (sensor_tx_count() != prev) return {false, "probe before backoff expiry at t=" + std::to_string(t - 1), false};
        if (t == 15000) w.bh5c.plug(kRawDim);
        pump_to(t);
        tracked_loop();
        if (sensor_tx_count() <= prev) return {false, "no probe at backoff t=" + std::to_string(t), false};
        prev = sensor_tx_count();
        if (t == 3000) live_after_second_retry = live_allocs_excluding_bus_log();
        if (t == 7000 && live_allocs_excluding_bus_log() > live_after_second_retry) {
            return {false, "each failed retry leaked a heap block (" + std::to_string(live_allocs_excluding_bus_log() - live_after_second_retry) +
                               " more live after the next retry); the application retries forever", false};
        }
    }
    Result r;
    if (count_exact(Serial.lines(), "RECOVERED") < 1) {
        r.detail = "expected RECOVERED after sensor appeared at 8 s backoff";
        return r;
    }
    if (!lux_is(kLuxDim, 0, r.detail)) return r;
    r.pass = true;
    r.detail = "FAULT_SENSOR_MISSING; probes at 1,2,4,8 s backoff intervals of simulated time; RECOVERED";
    return r;
}

static Result scenario_unplug_replug() {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    w.oled3c.plug();
    if (!boot_and_settle(2500)) return {false, "watchdog during boot", false};
    w.bh23.unplug();
    pump_to(9000);
    Result r;
    if (count_contains(Serial.lines(), "FAULT_SENSOR_READ") < 1 && count_contains(Serial.lines(), "STATE=STALE") < 1) {
        r.detail = "unplug did not produce STALE or FAULT_SENSOR_READ";
        return r;
    }
    // A replugged chip is back in its power-down state with a zeroed data register (p.4, p.5). Reading it without
    // sending a measurement command again returns 0, which is a valid-looking dark reading.
    const size_t mark = Serial.lines().size();
    w.bh23.plug(kRawBright);
    for (uint32_t t = millis(); t < millis() + 40000 && t < 60000; t += 1000) {
        pump_to(t);
        if (count_exact(Serial.lines(), "RECOVERED") >= 1) break;
    }
    if (count_exact(Serial.lines(), "RECOVERED") < 1) {
        r.detail = "retry after replug did not log RECOVERED";
        return r;
    }
    pump_to(millis() + 4000);
    if (!lux_is(kLuxBright, mark, r.detail)) return r;
    if (w.bh23.measurement_commands() < 1) {
        r.detail = "the replugged chip was never told to measure";
        return r;
    }
    r.pass = true;
    r.detail = "unplug faults; the replugged chip is restarted and reads resume at the true level";
    return r;
}

// A chip that acknowledges its address but not a data byte is not a BH1750: the real one at the other address
// must still be chosen, with no ambiguity.
class AckOnlyChip final : public I2cDevice {
public:
    bool present() const override { return true; }
    uint8_t on_write(const uint8_t *, size_t len) override { return len == 0 ? 0 : 3; }
    size_t on_read(uint8_t *, size_t) override { return 0; }
};

static Result both_addresses_case(int) {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    w.bh5c.plug(kRawBright);
    w.oled3c.plug();
    if (!boot_and_settle(4000)) return {false, "watchdog during boot", false};
    Result r;
    if (count_contains(Serial.lines(), "FAULT_AMBIGUOUS_ADDRESS") != 1) {
        r.detail = "expected FAULT_AMBIGUOUS_ADDRESS once";
        return r;
    }
    for (const auto &line : Serial.lines()) {
        OkReading tmp;
        if (parse_ok(line, tmp)) {
            r.detail = "readings were logged despite ambiguous address";
            return r;
        }
    }
    r.pass = true;
    r.detail = "FAULT_AMBIGUOUS_ADDRESS; no readings";
    return r;
}

static Result foreign_chip_case(int) {
    World w;
    w.attach();
    AckOnlyChip foreign;
    g_i2c_bus.attach(0x5C, &foreign);
    w.bh23.plug(kRawBright);
    w.oled3c.plug();
    if (!boot_and_settle(2500)) return {false, "watchdog during boot", false};
    Result r;
    if (count_contains(Serial.lines(), "FAULT_AMBIGUOUS_ADDRESS") != 0) {
        r.detail = "a chip that refuses the measurement command was counted as a second BH1750";
        return r;
    }
    if (count_contains(Serial.lines(), "BOOT sensor=0x23 display=0x3C") != 1) {
        r.detail = "the real BH1750 at 0x23 was not chosen beside a chip that refuses the command";
        return r;
    }
    if (!lux_is(kLuxBright, 0, r.detail)) return r;
    r.pass = true;
    return r;
}

static Result scenario_both_addresses() {
    Result r = run_isolated(both_addresses_case, 0);
    if (!r.pass) return r;
    const Result foreign = run_isolated(foreign_chip_case, 0);
    if (!foreign.pass) return foreign;
    r.detail += "; a chip at the other address that refuses the command is not a second sensor";
    return r;
}

static Result transient_read_case(int) {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    g_i2c_bus.remaining_read_fails = 1;  // one requestFrom per reading in this adapter
    pump_to(2500);
    Result r;
    if (count_contains(Serial.lines(), "STATE=STALE") < 1) {
        r.detail = "expected STALE after transient requestFrom failures";
        return r;
    }
    if (count_contains(Serial.lines(), "FAULT_SENSOR_READ") != 0) {
        r.detail = "transient nack raised a fault";
        return r;
    }
    pump_to(5000);
    if (count_contains(Serial.lines(), "STATE=OK") < 2) {
        r.detail = "did not recover to OK after transient nack";
        return r;
    }
    if (!lux_is(kLuxBright, 0, r.detail)) return r;
    r.pass = true;
    return r;
}

// A NACK on the measurement command at boot must fail that begin(). The data writes at boot are, in order: the
// probe of 0x23, the attempt at 0x5C (which an absent chip NACKs anyway) and the rebind of 0x23. Either way the
// application must fault at boot with no reading and recover on the next retry. No display is attached so the
// display's own init writes do not use up the NACK.
static Result init_nack_case(int skip) {
    const char *const step = skip == 0 ? "probe" : "rebind";
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    g_i2c_bus.data_nack_skip = skip;
    g_i2c_bus.remaining_data_nacks = 1;
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    Result r;
    if (count_exact(Serial.lines(), "T=0 STATE=FAULT_SENSOR_MISSING") != 1 || count_contains(Serial.lines(), "BOOT sensor=") != 0 ||
        count_contains(Serial.lines(), "STATE=OK") != 0) {
        r.detail = std::string("a NACK on the ") + step + " measurement command must fail begin(), fault at boot and log no reading";
        return r;
    }
    pump_to(3000);
    if (count_exact(Serial.lines(), "RECOVERED") < 1) {
        r.detail = std::string("the sensor did not recover after a transient ") + step + " NACK";
        return r;
    }
    if (!lux_is(kLuxBright, 0, r.detail)) return r;
    r.pass = true;
    return r;
}

static Result scenario_transient_nack() {
    Result r = run_isolated(transient_read_case, 0);
    if (!r.pass) return r;
    for (const int skip : {0, 2}) {
        const Result c = run_isolated(init_nack_case, skip);
        if (!c.pass) return c;
    }
    r.detail = "a failed requestFrom gives STALE then OK; a NACK on the probe or rebind command faults at boot, then recovers";
    return r;
}

#ifdef HS_RP2040
#include "wire_pins_rp2040.h"
#endif

static Result scenario_wire_pins() {
    World w;
#ifdef HS_RP2040
    // On the Pico the pins, the controller and the recovery path are checked the RP2040 core's way.
    return scenario_wire_pins_rp2040(w, [](World &world) { world.bh23.plug(kRawBright); }, [](World &world) { world.bh23.unplug(); });
#endif
    w.attach();
    w.bh23.plug(kRawBright);
    w.oled3c.plug();
    setup();
    // Read before any loop: Adafruit_SSD1306 restores the clock to 100 kHz after its own init, which would hide
    // a different frequency requested by setup().
    if (Wire.getClock() != 100000) {
        return {false, "setup() requested " + std::to_string(Wire.getClock()) + " Hz, not the planned 100000 Hz", false};
    }
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    const int sda_boot = Wire.sda_pin();
    const int scl_boot = Wire.scl_pin();
    int explicit_sda = -1, explicit_scl = -1;
    for (const auto &c : Wire.begin_calls()) {
        if (c.actually_inited && !c.default_args) {
            explicit_sda = c.sda_in_effect;
            explicit_scl = c.scl_in_effect;
        }
    }
    if (sda_boot != explicit_sda || scl_boot != explicit_scl) {
        return {false, "pins in effect after boot are not the explicit begin() pins", false};
    }
    // Nothing in this adapter calls Wire.begin() without arguments: the sensor is driven directly, and the display
    // is started with periphBegin=false (the pinned Adafruit_I2CDevice::begin() does not call it either). A
    // default-argument begin() therefore means the display library took over the bus, and on a bus that is not
    // yet initialised it would start on the default pins 21/22 with frequency 0.
    if (default_begin_count() != 0) {
        return {false, "Wire.begin() with default arguments ran during boot (display periphBegin not false)", false};
    }
    const size_t begins_at_boot = Wire.begin_calls().size();
    w.bh23.unplug();
    pump_to(9000);
    w.bh23.plug(kRawBright);
    for (uint32_t t = millis(); t < 60000; t += 1000) {
        pump_to(t);
        if (count_exact(Serial.lines(), "RECOVERED") >= 1) break;
    }
    Result r;
    if (default_begin_count() != 0) {
        r.detail = "Wire.begin() with default arguments ran during bus recovery (after Wire.end()). "
                   "Adapter must re-init with the planned pins and 100000 Hz";
        return r;
    }
    if (Wire.sda_pin() != explicit_sda || Wire.scl_pin() != explicit_scl) {
        r.detail = "pins after recovery are not the planned pins";
        return r;
    }
    // Count restarts from the unplug so extra starts at boot cannot stand in for recovery. The display restores
    // 100 kHz after its own transfers, so check initialisation frequencies and every non-display transaction.
    const auto &calls = Wire.begin_calls();
    int explicit_inits = 0;
    for (size_t i = begins_at_boot; i < calls.size(); ++i) {
        const auto &c = calls[i];
        if (c.actually_inited && !c.default_args) explicit_inits += 1;
    }
    if (explicit_inits < 1) {
        r.detail = "bus recovery did not re-initialise the bus: Wire.begin() ran on a bus that was never ended";
        return r;
    }
    for (const auto &c : calls) {
        if (c.actually_inited && !c.default_args && c.freq_arg != 100000) {
            r.detail = "Wire.begin() started the bus at " + std::to_string(c.freq_arg) + " Hz, not the planned 100000 Hz";
            return r;
        }
    }
    for (const auto &tx : g_i2c_bus.log) {
        if (tx.address != 0x3C && tx.address != 0x3D && tx.clock_hz != 100000) {
            char hex[3];
            std::snprintf(hex, sizeof hex, "%02X", tx.address);
            r.detail = std::string("a transaction with 0x") + hex + " ran at " + std::to_string(tx.clock_hz) +
                       " Hz, not the planned 100000 Hz";
            return r;
        }
    }
    r.pass = true;
    r.detail = "sda=" + std::to_string(explicit_sda) + " scl=" + std::to_string(explicit_scl) +
               " after boot and recovery; every real initialisation used the explicit pins";
    return r;
}

static Result scenario_blocking_budget() {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    w.oled3c.plug();
    if (!boot_and_settle(2500)) return {false, "watchdog during boot", false};
    w.bh23.unplug();
    pump_to(9000);
    w.bh23.plug(kRawBright);
    for (uint32_t t = millis(); t < 60000; t += 1000) {
        pump_to(t);
        if (count_exact(Serial.lines(), "RECOVERED") >= 1) break;
    }
    Result r;
    if (g_max_loop_ms > kLoopBudgetMs) {
        r.detail = "loop() used " + std::to_string(g_max_loop_ms) + " ms of simulated time; budget is " +
                   std::to_string(kLoopBudgetMs) + " ms, one 180 ms H-resolution conversion wait (datasheet p.2)";
        return r;
    }
    r.pass = true;
    r.detail = "max loop simulated time " + std::to_string(g_max_loop_ms) + " ms <= " + std::to_string(kLoopBudgetMs) + " ms";
    return r;
}

// The chip's data register is 0 until the first conversion ends (p.4, p.5), and 0 is a legitimate dark reading.
// The first reading after power-up must therefore wait out the conversion: with a bright scene, 0 is wrong.
static Result scenario_first_read_waits() {
    World w;
    w.attach();
    w.bh23.plug(kRawBright);
    setup();
    Result r;
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(2100);
    int n = 0;
    if (!lux_is(kLuxBright, 0, r.detail, &n)) return r;
    OkReading first;
    for (const auto &line : Serial.lines())
        if (parse_ok(line, first)) break;
    r.pass = true;
    r.detail = "first reading (" + std::to_string(first.lux) + " lx) is the bright scene, not the reset value 0";
    return r;
}

static Result run_named(const char *name) {
    if (std::strcmp(name, "sensor_default_address_0x23_with_display_0x3C") == 0) return scenario_sensor_default_address();
    if (std::strcmp(name, "sensor_0x5C_only") == 0) return scenario_sensor_0x5c_only();
    if (std::strcmp(name, "display_at_0x3D_only") == 0) return scenario_display_0x3d_only();
    if (std::strcmp(name, "display_absent") == 0) return scenario_display_absent();
    if (std::strcmp(name, "sensor_absent_then_appears") == 0) return scenario_sensor_absent_then_appears();
    if (std::strcmp(name, "unplug_replug_mid_run") == 0) return scenario_unplug_replug();
    if (std::strcmp(name, "both_addresses_answer") == 0) return scenario_both_addresses();
    if (std::strcmp(name, "transient_data_nack") == 0) return scenario_transient_nack();
    if (std::strcmp(name, "wire_pins_stay_explicit") == 0) return scenario_wire_pins();
    if (std::strcmp(name, "blocking_budget") == 0) return scenario_blocking_budget();
    if (std::strcmp(name, "first_read_waits_for_conversion") == 0) return scenario_first_read_waits();
    Result r;
    r.detail = "unknown scenario";
    return r;
}

static const char *kScenarios[] = {
    "sensor_default_address_0x23_with_display_0x3C",
    "sensor_0x5C_only",
    "display_at_0x3D_only",
    "display_absent",
    "sensor_absent_then_appears",
    "unplug_replug_mid_run",
    "both_addresses_answer",
    "transient_data_nack",
    "wire_pins_stay_explicit",
    "blocking_budget",
    "first_read_waits_for_conversion",
};

int main(int argc, char **argv) {
    return vendor_main(argc, argv, kScenarios, sizeof kScenarios / sizeof kScenarios[0], run_named);
}
