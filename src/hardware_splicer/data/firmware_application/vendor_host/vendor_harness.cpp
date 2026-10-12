// Host compile of the real Arduino adapter + pinned Adafruit sources against a
// modelled I2C bus. A pass is not silicon, not the ESP32 Wire driver's timing,
// and not electrical behaviour.
#include "Arduino.h"
#include "Wire.h"
#include "models.h"
#include <Adafruit_GFX.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <regex>
#include <string>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

extern void setup();
extern void loop();

// Live heap blocks, counted across the harness, the adapter and the pinned Adafruit sources. The application
// retries a missing sensor forever, so a block leaked per attempt is a real failure mode; this can see it.
static long g_live_allocs = 0;
void *operator new(std::size_t size) {
    void *block = std::malloc(size ? size : 1);
    if (!block) throw std::bad_alloc();
    g_live_allocs += 1;
    return block;
}
void operator delete(void *block) noexcept {
    if (!block) return;
    g_live_allocs -= 1;
    std::free(block);
}
void operator delete(void *block, std::size_t) noexcept { operator delete(block); }

// Adafruit_BME280.cpp init(): delay(10) after reset, optional delay(10) per
// isReadingCalibration poll, delay(100) after setSampling. Two successful
// begin() calls (probe match + rebind) are the recovery worst case.
static constexpr uint32_t kLoopBudgetMs = 2 * (10 + 100) + 2 * 10 + 10;  // 250

// Integer Adafruit formulas vs datasheet 8.1 double. Temp is 0.01°C quantized
// in Adafruit; 0.05°C covers that plus formula-family rounding. Pressure 0.2 hPa
// (20 Pa) and humidity 0.3 %RH cover 64-bit/int vs double (BST-BME280-DS001-24
// table 15 notes the families are different implementations).
static constexpr double kTempTolC = 0.05;
static constexpr double kPresTolHpa = 0.2;
static constexpr double kHumTolPct = 0.3;

static std::string json_escape(const std::string &text) {
    std::string out;
    out.reserve(text.size() + 8);
    for (char ch : text) {
        if (ch == '\\') out += "\\\\";
        else if (ch == '"') out += "\\\"";
        else if (ch == '\n') out += "\\n";
        else out += ch;
    }
    return out;
}

static int count_exact(const std::vector<std::string> &lines, const std::string &want) {
    int n = 0;
    for (const auto &line : lines)
        if (line == want) n += 1;
    return n;
}

static int count_contains(const std::vector<std::string> &lines, const std::string &part) {
    int n = 0;
    for (const auto &line : lines)
        if (line.find(part) != std::string::npos) n += 1;
    return n;
}

static bool call_loop(uint32_t *elapsed = nullptr) {
    sim_begin_loop();
    try {
        loop();
    } catch (const WatchdogAbort &) {
    }
    if (elapsed) *elapsed = sim_loop_elapsed_ms();
    const bool hung = g_sim_clock.watchdog_fired;
    sim_end_loop();
    return !hung;
}

static uint32_t g_max_loop_ms = 0;

static bool tracked_loop() {
    uint32_t elapsed = 0;
    const bool ok = call_loop(&elapsed);
    if (elapsed > g_max_loop_ms) g_max_loop_ms = elapsed;
    return ok;
}

static void pump_to(uint32_t t_ms) {
    while (millis() < t_ms) {
        const uint32_t now = millis();
        const uint32_t step = (t_ms - now > 50) ? 50 : (t_ms - now);
        if (step == 0) break;
        sim_advance_ms(step);
        if (!tracked_loop()) return;
    }
}

struct OkReading {
    uint32_t t_ms = 0;
    double temp_c = 0;
    double hum_pct = 0;
    double pres_hpa = 0;
};

static bool parse_ok(const std::string &line, OkReading &out) {
    unsigned t = 0;
    if (std::sscanf(line.c_str(), "T=%u STATE=OK TEMP_C=%lf HUM_PCT=%lf PRES_HPA=%lf", &t, &out.temp_c,
                    &out.hum_pct, &out.pres_hpa) != 4)
        return false;
    out.t_ms = t;
    return true;
}

static bool readings_match_oracle(const Bme280Model &bme, std::string &detail) {
    const Bme280Oracle o = bme.oracle();
    const double o_hpa = o.pressure_pa / 100.0;
    int n = 0;
    for (const auto &line : Serial.lines()) {
        OkReading r;
        if (!parse_ok(line, r)) continue;
        n += 1;
        if (std::fabs(r.temp_c - o.temp_c) > kTempTolC) {
            detail = "TEMP_C " + std::to_string(r.temp_c) + " vs oracle " + std::to_string(o.temp_c);
            return false;
        }
        if (std::fabs(r.hum_pct - o.humidity_pct) > kHumTolPct) {
            detail = "HUM_PCT " + std::to_string(r.hum_pct) + " vs oracle " + std::to_string(o.humidity_pct);
            return false;
        }
        if (std::fabs(r.pres_hpa - o_hpa) > kPresTolHpa) {
            detail = "PRES_HPA " + std::to_string(r.pres_hpa) + " vs oracle " + std::to_string(o_hpa);
            return false;
        }
    }
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
        if (parse_ok(line, r)) found = true;
    }
    if (!found) return false;
    char a[24], b[24], c[24];
    std::snprintf(a, sizeof a, "%.2f C", r.temp_c);
    std::snprintf(b, sizeof b, "%.1f %%", r.hum_pct);
    std::snprintf(c, sizeof c, "%.1f hPa", r.pres_hpa);
    l1 = "STATE OK";
    l2 = a;
    l3 = b;
    l4 = c;
    return true;
}

static bool framebuffer_matches(const Ssd1306Model &oled, const std::string &l1, const std::string &l2,
                                const std::string &l3, const std::string &l4, std::string &detail) {
    // Pixel compare, not raw buffer: GFXcanvas1 packs horizontally MSB-first
    // (Adafruit_GFX.cpp:2077); SSD1306 packs vertically by page
    // (Adafruit_SSD1306.cpp:678). Same four println() calls must light the same
    // pixels.
    GFXcanvas1 canvas(128, 64);
    canvas.fillScreen(0);
    canvas.setTextSize(1);
    canvas.setTextColor(1);
    canvas.setCursor(0, 0);
    canvas.println(l1.c_str());
    canvas.println(l2.c_str());
    canvas.println(l3.c_str());
    canvas.println(l4.c_str());
    for (int y = 0; y < 64; ++y) {
        for (int x = 0; x < 128; ++x) {
            if (oled.pixel(x, y) != canvas.getPixel(x, y)) {
                detail = "framebuffer pixels differ from GFXcanvas1 at " + std::to_string(x) + "," +
                         std::to_string(y);
                return false;
            }
        }
    }
    return true;
}

static bool sensor_reads_go_to(uint8_t addr, std::string &detail) {
    bool any = false;
    for (const auto &tx : g_i2c_bus.log) {
        if (tx.direction != I2cDir::Read) continue;
        if (tx.address != 0x76 && tx.address != 0x77) continue;
        any = true;
        if (tx.address != addr) {
            detail = "sensor I2C read went to 0x" + std::to_string(tx.address) + " not 0x" +
                     std::to_string(addr);
            return false;
        }
    }
    if (!any) {
        detail = "no sensor I2C reads recorded";
        return false;
    }
    return true;
}

static bool default_begin_inited_bus() {
    for (const auto &c : Wire.begin_calls()) {
        if (c.default_args && c.actually_inited) return true;
    }
    return false;
}

static int default_begin_count() {
    int n = 0;
    for (const auto &c : Wire.begin_calls())
        if (c.default_args) n += 1;
    return n;
}

struct World {
    Bme280Model bme77{0x77};
    Bme280Model bme76{0x76};
    Ssd1306Model oled3c{0x3C};
    Ssd1306Model oled3d{0x3D};

    void attach() {
        g_i2c_bus.attach(0x77, &bme77);
        g_i2c_bus.attach(0x76, &bme76);
        g_i2c_bus.attach(0x3C, &oled3c);
        g_i2c_bus.attach(0x3D, &oled3d);
    }
};

static int32_t gAdcT, gAdcP, gAdcH;

static void plug_sensor(Bme280Model &m, const Bme280Calib &c) {
    synthetic_adc_a(gAdcT, gAdcP, gAdcH);
    m.plug(c, gAdcT, gAdcP, gAdcH);
}

struct Result {
    bool pass = false;
    std::string detail;
    bool finding = false;
};

// The adapter keeps function-static state and a simulated clock, so each sub-case runs in a forked child
// that starts from the same pristine process and reports its Result through a pipe.
static Result run_isolated(Result (*fn)(int), int arg) {
    int fds[2];
    if (pipe(fds) != 0) return {false, "could not create a pipe for an isolated case", false};
    const pid_t pid = fork();
    if (pid < 0) return {false, "could not fork an isolated case", false};
    if (pid == 0) {
        close(fds[0]);
        const Result r = fn(arg);
        const std::string wire = std::string(r.pass ? "1" : "0") + r.detail;
        const ssize_t sent = write(fds[1], wire.data(), wire.size());
        (void)sent;
        _exit(0);
    }
    close(fds[1]);
    std::string got;
    char chunk[512];
    for (ssize_t n; (n = read(fds[0], chunk, sizeof chunk)) > 0;) got.append(chunk, static_cast<size_t>(n));
    close(fds[0]);
    int status = 0;
    waitpid(pid, &status, 0);
    if (got.empty() || !WIFEXITED(status) || WEXITSTATUS(status) != 0) return {false, "an isolated case did not finish", false};
    return {got[0] == '1', got.substr(1), false};
}

static Result scenario_sensor_default_address() {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(2500);
    Result r;
    if (count_contains(Serial.lines(), "BOOT sensor=0x77 display=0x3C") != 1) {
        r.detail = "missing BOOT sensor=0x77 display=0x3C";
        return r;
    }
    if (!readings_match_oracle(w.bme77, r.detail)) return r;
    if (!sensor_reads_go_to(0x77, r.detail)) return r;
    if (!w.oled3c.saw_display_on()) {
        r.detail = "SSD1306 init sequence lacked display-on 0xAF";
        return r;
    }
    std::string l1, l2, l3, l4;
    if (!last_ok_lines(l1, l2, l3, l4) || !framebuffer_matches(w.oled3c, l1, l2, l3, l4, r.detail))
        return r;
    r.pass = true;
    r.detail = "oracle match vs datasheet 8.1 double; I2C reads at 0x77; synthetic set A";
    return r;
}

static Result scenario_sensor_0x76_only() {
    World w;
    w.attach();
    int32_t t, p, h;
    synthetic_adc_b(t, p, h);
    w.bme76.plug(synthetic_calib_b(), t, p, h);
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(2500);
    Result r;
    if (count_contains(Serial.lines(), "BOOT sensor=0x76 display=0x3C") != 1) {
        r.detail = "missing BOOT sensor=0x76 display=0x3C";
        return r;
    }
    if (!readings_match_oracle(w.bme76, r.detail)) return r;
    if (!sensor_reads_go_to(0x76, r.detail)) return r;
    r.pass = true;
    r.detail = "oracle match synthetic set B; I2C reads at 0x76";
    return r;
}

static Result scenario_display_0x3D_only() {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    w.oled3d.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(2500);
    Result r;
    if (count_contains(Serial.lines(), "BOOT sensor=0x77 display=0x3D") != 1) {
        r.detail = "missing BOOT sensor=0x77 display=0x3D";
        return r;
    }
    if (!w.oled3d.saw_display_on()) {
        r.detail = "0x3D init sequence lacked 0xAF";
        return r;
    }
    std::string l1, l2, l3, l4;
    if (!last_ok_lines(l1, l2, l3, l4) || !framebuffer_matches(w.oled3d, l1, l2, l3, l4, r.detail))
        return r;
    r.pass = true;
    r.detail = "framebuffer pixels match GFXcanvas1 of the four text lines";
    return r;
}

static Result scenario_display_absent() {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(4000);
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
        if (tx.address == 0x3C && probe) {
            probes_3c += 1;
            continue;
        }
        if (tx.address == 0x3D && probe) {
            probes_3d += 1;
            continue;
        }
        r.detail = "non-probe transaction to display address after presence check";
        return r;
    }
    if (probes_3c < 1 || probes_3d < 1) {
        r.detail = "expected a presence probe at both 0x3C and 0x3D";
        return r;
    }
    r.pass = true;
    r.detail = "DISPLAY MISSING once; only bare address probes to 0x3C/0x3D";
    return r;
}

static int sensor_tx_count() {
    int n = 0;
    for (const auto &tx : g_i2c_bus.log)
        if (tx.address == 0x76 || tx.address == 0x77) n += 1;
    return n;
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
        if (sensor_tx_count() != prev)
            return {false, "probe before backoff expiry at t=" + std::to_string(t - 1), false};
        if (t == 15000) plug_sensor(w.bme76, synthetic_calib_a());
        pump_to(t);
        tracked_loop();
        if (sensor_tx_count() <= prev)
            return {false, "no probe at backoff t=" + std::to_string(t), false};
        prev = sensor_tx_count();
        if (t == 3000) live_after_second_retry = g_live_allocs;
        if (t == 7000 && g_live_allocs > live_after_second_retry) {
            return {false, "each failed retry leaked a heap block (" + std::to_string(g_live_allocs - live_after_second_retry) +
                               " more live after the next retry); the application retries forever", false};
        }
    }
    Result r;
    if (count_exact(Serial.lines(), "RECOVERED") < 1) {
        r.detail = "expected RECOVERED after sensor appeared at 8 s backoff";
        return r;
    }
    if (!readings_match_oracle(w.bme76, r.detail)) return r;
    r.pass = true;
    r.detail = "FAULT_SENSOR_MISSING; probes at 1,2,4,8 s backoff intervals of simulated time; RECOVERED";
    return r;
}

static Result scenario_unplug_replug() {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(2500);
    w.bme77.unplug();
    pump_to(9000);
    Result r;
    if (count_contains(Serial.lines(), "FAULT_SENSOR_READ") < 1 &&
        count_contains(Serial.lines(), "STATE=STALE") < 1) {
        r.detail = "unplug did not produce STALE or FAULT_SENSOR_READ";
        return r;
    }
    plug_sensor(w.bme77, synthetic_calib_a());
    for (uint32_t t = millis(); t < millis() + 40000 && t < 60000; t += 1000) {
        pump_to(t);
        if (count_exact(Serial.lines(), "RECOVERED") >= 1) break;
    }
    if (count_exact(Serial.lines(), "RECOVERED") < 1) {
        r.detail = "retry after replug did not log RECOVERED";
        return r;
    }
    // Oracle against post-replug NVM/ADC (begin reloaded coefficients).
    if (!readings_match_oracle(w.bme77, r.detail)) return r;
    r.pass = true;
    r.detail = "calibration lost on unplug; fault; re-begin; oracle values resume";
    return r;
}

static Result both_addresses_case(int) {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    plug_sensor(w.bme76, synthetic_calib_a());
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(4000);
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

// A chip that answers at 0x77 but identifies as something else (0x58 is a BMP280's id) is not a second BME280:
// the real sensor at 0x76 must still be chosen, with no ambiguity.
static Result decoy_chip_case(int) {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    w.bme77.set_chip_id(0x58);
    int32_t t, p, h;
    synthetic_adc_b(t, p, h);
    w.bme76.plug(synthetic_calib_b(), t, p, h);
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(2500);
    Result r;
    if (count_contains(Serial.lines(), "FAULT_AMBIGUOUS_ADDRESS") != 0) {
        r.detail = "a chip with the wrong identity was counted as a second BME280";
        return r;
    }
    if (count_contains(Serial.lines(), "BOOT sensor=0x76 display=0x3C") != 1) {
        r.detail = "the real BME280 at 0x76 was not chosen beside a wrong-identity chip at 0x77";
        return r;
    }
    if (!readings_match_oracle(w.bme76, r.detail)) return r;
    r.pass = true;
    return r;
}

static Result scenario_both_addresses() {
    Result r = run_isolated(both_addresses_case, 0);
    if (!r.pass) return r;
    const Result decoy = run_isolated(decoy_chip_case, 0);
    if (!decoy.pass) return decoy;
    r.detail += "; a wrong-identity chip at the other address is not a second sensor";
    return r;
}

static Result transient_read_case(int) {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    g_i2c_bus.remaining_read_fails = 2;
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
    r.pass = true;
    r.detail = "1-2 requestFrom failures → STALE then OK, no fault";
    return r;
}

// A NACK on one of the first three data writes of the sensor's init (chip-id pointer, soft reset, status pointer)
// must fail that begin(), leave FAULT_SENSOR_MISSING at boot, and recover on the next retry. No display is
// attached so the display's own init writes do not use up the NACK.
static Result init_nack_case(int skip) {
    static const char *const step[] = {"chip-id", "soft-reset", "status"};
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    g_i2c_bus.data_nack_skip = skip;
    g_i2c_bus.remaining_data_nacks = 1;
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    Result r;
    if (count_exact(Serial.lines(), "T=0 STATE=FAULT_SENSOR_MISSING") != 1 || count_contains(Serial.lines(), "BOOT sensor=") != 0 ||
        count_contains(Serial.lines(), "STATE=OK") != 0) {
        r.detail = std::string("a NACK on the ") + step[skip] + " write must fail begin(), fault at boot and log no reading";
        return r;
    }
    pump_to(3000);
    if (count_exact(Serial.lines(), "RECOVERED") < 1) {
        r.detail = std::string("the sensor did not recover after a transient ") + step[skip] + " NACK";
        return r;
    }
    r.pass = true;
    return r;
}

static Result scenario_transient_nack() {
    Result r = run_isolated(transient_read_case, 0);
    if (!r.pass) return r;
    for (int skip = 0; skip < 3; ++skip) {
        const Result c = run_isolated(init_nack_case, skip);
        if (!c.pass) return c;
    }
    r.detail += "; a NACK on the chip-id, reset or status write at boot faults, then recovers";
    return r;
}

static Result scenario_wire_pins() {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
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
    // Extra default begin during display init (periphBegin=true) shows up as a
    // default-arg begin after setup's explicit begin and before the first sensor
    // I2CDevice begin. Count default begins on this path: 0x77 begin + 0x76 begin
    // + rebind = 3. Display periphBegin=true adds a 4th.
    const int defaults_after_boot = default_begin_count();
    if (defaults_after_boot > 3) {
        return {false,
                "Wire.begin() with default arguments ran during display begin (periphBegin not false); "
                "arduino-esp32 2.0.17 Wire.cpp begin() with no args calls begin(-1,-1,0); if the bus "
                "is already inited it returns true without changing pins, else initPins uses SDA=21 "
                "SCL=22 from variants/esp32/pins_arduino.h when sda_ is still -1",
                false};
    }
    w.bme77.unplug();
    pump_to(9000);
    plug_sensor(w.bme77, synthetic_calib_a());
    for (uint32_t t = millis(); t < 60000; t += 1000) {
        pump_to(t);
        if (count_exact(Serial.lines(), "RECOVERED") >= 1) break;
    }
    Result r;
    if (default_begin_inited_bus()) {
        r.detail =
            "Wire.begin() with default arguments actually re-inited the bus (bus_recover after "
            "Wire.end()). 2.0.17: begin() → begin(-1,-1,0); initPins reuses prior sda/scl if set, "
            "else SDA=21 SCL=22; frequency 0. Adapter must re-init with the planned pins and 100000 Hz";
        return r;
    }
    if (Wire.sda_pin() != explicit_sda || Wire.scl_pin() != explicit_scl) {
        r.detail = "pins after recovery are not the planned pins";
        return r;
    }
    // Recovery exists to reset a stuck peripheral: begin() on an already-initialised bus is a no-op, so the
    // adapter must end() first. Boot plus recovery means at least two explicit begin() calls that really initialised it.
    int explicit_inits = 0;
    for (const auto &c : Wire.begin_calls()) {
        if (c.actually_inited && !c.default_args) explicit_inits += 1;
    }
    if (explicit_inits < 2) {
        r.detail = "bus recovery did not re-initialise the bus: Wire.begin() ran on a bus that was never ended";
        return r;
    }
    r.pass = true;
    r.detail = "sda=" + std::to_string(explicit_sda) + " scl=" + std::to_string(explicit_scl) +
               " after boot and recovery; default-arg begin() count=" + std::to_string(default_begin_count()) +
               " (2.0.17: already-inited begin(-1,-1,0) is a no-op for pins; Adafruit_I2CDevice::begin "
               "calls it)";
    return r;
}

static Result scenario_blocking_budget() {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    w.oled3c.plug();
    setup();
    if (!tracked_loop()) return {false, "watchdog during boot", false};
    pump_to(2500);
    w.bme77.unplug();
    pump_to(9000);
    plug_sensor(w.bme77, synthetic_calib_a());
    for (uint32_t t = millis(); t < 60000; t += 1000) {
        pump_to(t);
        if (count_exact(Serial.lines(), "RECOVERED") >= 1) break;
    }
    Result r;
    if (g_max_loop_ms > kLoopBudgetMs) {
        r.detail = "loop() used " + std::to_string(g_max_loop_ms) + " ms of simulated time; budget is " +
                   std::to_string(kLoopBudgetMs) +
                   " ms from Adafruit_BME280.cpp init delay(10)+delay(100) times two begins plus "
                   "one calibration poll each";
        return r;
    }
    r.pass = true;
    r.detail = "max loop simulated time " + std::to_string(g_max_loop_ms) + " ms <= " +
               std::to_string(kLoopBudgetMs) + " ms";
    return r;
}

static Result scenario_im_update_hang() {
    World w;
    w.attach();
    plug_sensor(w.bme77, synthetic_calib_a());
    w.bme77.set_im_update_stuck(true);
    w.oled3c.plug();
    setup();
    Result r;
    const bool returned = tracked_loop();
    if (g_sim_clock.watchdog_fired || !returned) {
        r.detail = "bounded initializer did not return before the host watchdog";
        return r;
    }
    if (g_max_loop_ms > kLoopBudgetMs || count_exact(Serial.lines(), "T=0 STATE=FAULT_SENSOR_MISSING") != 1
        || count_contains(Serial.lines(), "STATE=OK") != 0) {
        r.detail = "stuck calibration must be bounded, faulted, and produce no readings";
        return r;
    }
    pump_to(1000);
    if (g_sim_clock.watchdog_fired || count_contains(Serial.lines(), "STATE=OK") != 0) {
        r.detail = "retry while calibration is stuck must also remain bounded";
        return r;
    }
    w.bme77.set_im_update_stuck(false);
    pump_to(10000);
    if (count_exact(Serial.lines(), "RECOVERED") < 1 || !readings_match_oracle(w.bme77, r.detail)) return r;
    r.pass = true;
    r.detail = "stuck calibration returns a fault within the software budget, no stale reading, then recovers; model only";
    return r;
}

static Result run_named(const char *name) {
    if (std::strcmp(name, "sensor_default_address_0x77_with_display_0x3C") == 0)
        return scenario_sensor_default_address();
    if (std::strcmp(name, "sensor_0x76_only") == 0) return scenario_sensor_0x76_only();
    if (std::strcmp(name, "display_at_0x3D_only") == 0) return scenario_display_0x3D_only();
    if (std::strcmp(name, "display_absent") == 0) return scenario_display_absent();
    if (std::strcmp(name, "sensor_absent_then_appears") == 0) return scenario_sensor_absent_then_appears();
    if (std::strcmp(name, "unplug_replug_mid_run") == 0) return scenario_unplug_replug();
    if (std::strcmp(name, "both_addresses_answer") == 0) return scenario_both_addresses();
    if (std::strcmp(name, "transient_data_nack") == 0) return scenario_transient_nack();
    if (std::strcmp(name, "wire_pins_stay_explicit") == 0) return scenario_wire_pins();
    if (std::strcmp(name, "blocking_budget") == 0) return scenario_blocking_budget();
    if (std::strcmp(name, "im_update_never_clears") == 0) return scenario_im_update_hang();
    Result r;
    r.detail = "unknown scenario";
    return r;
}

static const char *kScenarios[] = {
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
};

int main(int argc, char **argv) {
    if (argc >= 2 && argv[1][0] != '\0') {
        const Result r = run_named(argv[1]);
            std::printf("{\"scenario\":\"%s\",\"pass\":%s,\"detail\":\"%s\"%s}\n", argv[1],
                    r.pass ? "true" : "false", json_escape(r.detail).c_str(),
                    r.finding ? ",\"finding\":true" : "");
        std::fflush(stdout);
        return r.finding ? 0 : (r.pass ? 0 : 1);
    }
    bool all = true;
    for (const char *name : kScenarios) {
        const pid_t pid = fork();
        if (pid < 0) {
            std::fprintf(stderr, "fork failed\n");
            return 1;
        }
        if (pid == 0) {
            const Result r = run_named(name);
            std::printf("{\"scenario\":\"%s\",\"pass\":%s,\"detail\":\"%s\"%s}\n", name,
                        r.pass ? "true" : "false", json_escape(r.detail).c_str(),
                        r.finding ? ",\"finding\":true" : "");
            std::fflush(stdout);
            _exit(r.finding ? 0 : (r.pass ? 0 : 1));
        }
        int status = 0;
        waitpid(pid, &status, 0);
        if (!(WIFEXITED(status) && WEXITSTATUS(status) == 0)) all = false;
    }
    return all ? 0 : 1;
}
