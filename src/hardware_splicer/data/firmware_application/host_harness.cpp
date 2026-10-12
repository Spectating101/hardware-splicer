// Host model of SensorApp. No wall clock, no randomness, no hardware.
#include "app_core.h"

#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <regex>
#include <string>
#include <vector>

static const uint8_t kSensorAddrs[] = {0x77, 0x76};
static const uint8_t kDisplayAddrs[] = {0x3C, 0x3D};
static constexpr size_t kSensorCount = sizeof kSensorAddrs / sizeof kSensorAddrs[0];
static constexpr size_t kDisplayCount = sizeof kDisplayAddrs / sizeof kDisplayAddrs[0];
static constexpr uint8_t kBme280ChipId = 0x60;  // Bosch register 0xD0 “id”

struct ReadCmd {
    bool fail = false;
    Reading value{};
};

static std::vector<std::string> g_serial_trace;

class FakeHal final : public Hal {
public:
    uint32_t clock = 0;
    bool present[256]{};
    uint8_t chip_id[256]{};
    std::deque<ReadCmd> reads;
    ReadCmd default_read{};
    bool has_default = false;
    std::vector<std::string> logs;
    std::vector<std::array<std::string, 4>> displays;
    int sensor_begin_calls = 0;
    int display_begin_calls = 0;
    int read_calls = 0;
    int recover_calls = 0;
    std::vector<uint8_t> sensor_begin_addrs;
    uint8_t bound_addr = 0;
    bool calibrated = false;

    uint8_t chip_address() const {
        uint8_t found = 0;
        int n = 0;
        for (int a = 0; a < 256; ++a) {
            if (present[a] && chip_id[a] == kBme280ChipId) {
                found = static_cast<uint8_t>(a);
                n += 1;
            }
        }
        return n == 1 ? found : 0;
    }

    uint32_t now_ms() override { return clock; }

    bool sensor_begin(uint8_t addr) override {
        sensor_begin_calls += 1;
        sensor_begin_addrs.push_back(addr);
        bound_addr = addr;  // Adafruit_BME280 2.3.0 begin always (re)binds, even when it returns false
        calibrated = present[addr] && chip_id[addr] == kBme280ChipId;
        return calibrated;
    }

    bool sensor_read(Reading& out) override {
        read_calls += 1;
        if (bound_addr != chip_address() || !calibrated) {
            return false;
        }
        ReadCmd cmd;
        if (!reads.empty()) {
            cmd = reads.front();
            reads.pop_front();
        } else if (has_default) {
            cmd = default_read;
        } else {
            return false;
        }
        if (cmd.fail) {
            return false;
        }
        out = cmd.value;
        return true;
    }

    bool display_begin(uint8_t addr) override {
        // Not a model of SSD1306 detection. Adafruit_SSD1306 2.5.17 begin() returns true
        // without probing the bus (Adafruit_SSD1306.cpp: "return true; // Success").
        // Presence is checked in main.cpp and by the compile, not by this harness.
        display_begin_calls += 1;
        return present[addr];
    }

    void display_show(const char* l1, const char* l2, const char* l3, const char* l4) override {
        displays.push_back({l1 ? l1 : "", l2 ? l2 : "", l3 ? l3 : "", l4 ? l4 : ""});
    }

    void log(const char* line) override {
        logs.push_back(line ? line : "");
        g_serial_trace.push_back(line ? line : "");
    }

    bool bus_recover() override {
        recover_calls += 1;
        return true;
    }

    void set_sensor(uint8_t addr, bool on, uint8_t id = kBme280ChipId) {
        present[addr] = on;
        chip_id[addr] = id;
        if (!on) {
            calibrated = false;  // unplug: registers reset, calibration lost
        }
    }

    void set_display(uint8_t addr, bool on) { present[addr] = on; }

    void set_default(float t, float h, float p) {
        default_read.fail = false;
        default_read.value = {t, h, p};
        has_default = true;
    }

    void queue_fail() {
        ReadCmd cmd;
        cmd.fail = true;
        reads.push_back(cmd);
    }

    void queue_value(float t, float h, float p) {
        ReadCmd cmd;
        cmd.fail = false;
        cmd.value = {t, h, p};
        reads.push_back(cmd);
    }

    void queue_nan() {
        ReadCmd cmd;
        cmd.fail = false;
        cmd.value = {std::nanf(""), std::nanf(""), std::nanf("")};
        reads.push_back(cmd);
    }
};

static std::string json_escape(const std::string& text) {
    std::string out;
    out.reserve(text.size() + 8);
    for (char ch : text) {
        switch (ch) {
            case '\\':
                out += "\\\\";
                break;
            case '"':
                out += "\\\"";
                break;
            case '\n':
                out += "\\n";
                break;
            default:
                out += ch;
                break;
        }
    }
    return out;
}

static bool grammar_ok(const std::string& line) {
    static const std::regex allowed[] = {
        std::regex(R"(^BOOT sensor=0x[0-9A-F]{2} display=(0x[0-9A-F]{2}|NONE)$)"),
        std::regex(R"(^T=[0-9]+ STATE=OK TEMP_C=-?[0-9]+\.[0-9]{2} HUM_PCT=-?[0-9]+\.[0-9] PRES_HPA=-?[0-9]+\.[0-9]$)"),
        std::regex(R"(^T=[0-9]+ STATE=STALE$)"),
        std::regex(R"(^T=[0-9]+ STATE=FAULT_SENSOR_MISSING$)"),
        std::regex(R"(^T=[0-9]+ STATE=FAULT_SENSOR_READ$)"),
        std::regex(R"(^T=[0-9]+ STATE=FAULT_AMBIGUOUS_ADDRESS$)"),
        std::regex(R"(^DISPLAY MISSING$)"),
        std::regex(R"(^RECOVERED$)"),
    };
    for (const auto& pattern : allowed) {
        if (std::regex_match(line, pattern)) {
            return true;
        }
    }
    return false;
}

static int count_exact(const std::vector<std::string>& lines, const std::string& want) {
    int n = 0;
    for (const auto& line : lines) {
        if (line == want) {
            n += 1;
        }
    }
    return n;
}

static int count_contains(const std::vector<std::string>& lines, const std::string& part) {
    int n = 0;
    for (const auto& line : lines) {
        if (line.find(part) != std::string::npos) {
            n += 1;
        }
    }
    return n;
}

static bool has_exact(const std::vector<std::string>& lines, const std::string& want) {
    return count_exact(lines, want) > 0;
}

static bool check_grammar(const FakeHal& hal, std::string& detail) {
    for (const auto& line : hal.logs) {
        if (!grammar_ok(line)) {
            detail = "illegal serial line: " + line;
            return false;
        }
    }
    return true;
}

static Reading kGood{21.50f, 45.0f, 1013.3f};

static void wire_boot_ok_bus(FakeHal& hal) {
    hal.set_sensor(0x77, true, 0x00);  // present but identity does not match
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.set_display(0x3C, true);
    hal.set_display(0x3D, false);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
}

static int count_ok_readings(const std::vector<std::string>& lines) {
    return count_contains(lines, "STATE=OK TEMP_C=");
}

static bool display_shows_a_reading(const FakeHal& hal) {
    for (const auto& shown : hal.displays) {
        if (shown[0] == "STATE OK" || shown[0] == "STATE STALE" ||
            shown[1].find(" C") != std::string::npos ||
            shown[2].find(" %") != std::string::npos ||
            shown[3].find("hPa") != std::string::npos) {
            return true;
        }
    }
    return false;
}

struct BoundCase {
    const char* name;
    float temp_c;
    float hum_pct;
    float pres_hpa;
    bool accept;
};

static bool check_isolated_bound(const BoundCase& c, std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    hal.has_default = false;
    hal.queue_value(c.temp_c, c.hum_pct, c.pres_hpa);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!check_grammar(hal, detail)) {
        detail = std::string(c.name) + ": " + detail;
        return false;
    }
    const bool got_ok = count_ok_readings(hal.logs) > 0;
    const bool got_stale = has_exact(hal.logs, "T=0 STATE=STALE");
    if (c.accept) {
        if (!got_ok || got_stale) {
            detail = std::string(c.name) + " must be accepted as a reading";
            return false;
        }
    } else {
        if (got_ok || !got_stale) {
            detail = std::string(c.name) + " must be rejected as a failed read";
            return false;
        }
        if (count_contains(hal.logs, "nan") || count_contains(hal.logs, "NaN")) {
            detail = std::string(c.name) + " was logged as a reading";
            return false;
        }
    }
    return true;
}

static bool scenario_boot_ok(std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!check_grammar(hal, detail)) {
        return false;
    }
    if (!has_exact(hal.logs, "BOOT sensor=0x76 display=0x3C")) {
        detail = "missing BOOT with the identity-matched addresses";
        return false;
    }
    if (!has_exact(hal.logs, "T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
        detail = "first cycle did not show the reading";
        return false;
    }
    if (hal.displays.empty()) {
        detail = "display_show was not called";
        return false;
    }
    const auto& shown = hal.displays.front();
    if (shown[0] != "STATE OK" || shown[1] != "21.50 C" || shown[2] != "45.0 %" || shown[3] != "1013.3 hPa") {
        detail = "display did not show the first reading";
        return false;
    }
    if (has_exact(hal.logs, "BOOT sensor=0x77 display=0x3C")) {
        detail = "picked 0x77 without a matching chip identity";
        return false;
    }
    return true;
}

static bool scenario_default_address_binding(std::string& detail) {
    FakeHal hal;
    hal.set_sensor(0x77, true, kBme280ChipId);
    hal.set_display(0x3C, true);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!check_grammar(hal, detail)) {
        return false;
    }
    if (!has_exact(hal.logs, "BOOT sensor=0x77 display=0x3C")) {
        detail = "chip at the first declared address 0x77 was not reported";
        return false;
    }
    if (!has_exact(hal.logs, "T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
        detail = "reading failed: driver left bound to a later probed address";
        return false;
    }
    if (hal.sensor_begin_addrs.empty() || hal.sensor_begin_addrs.back() != 0x77) {
        detail = "last sensor_begin was not the matched address 0x77 (rebind after probe)";
        return false;
    }
    if (hal.displays.empty()) {
        detail = "display_show was not called";
        return false;
    }
    return true;
}

static bool scenario_sensor_missing_at_boot(std::string& detail) {
    FakeHal hal;
    hal.set_display(0x3C, true);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_MISSING") != 1) {
        detail = "fault must be logged once at the state change";
        return false;
    }
    if (hal.displays.empty() || hal.displays.back()[0] != "SENSOR MISSING") {
        detail = "display did not show SENSOR MISSING";
        return false;
    }
    const int begins_at_boot = hal.sensor_begin_calls;
    hal.clock = 500;
    app.loop_once();
    if (hal.sensor_begin_calls != begins_at_boot) {
        detail = "retry must not run before the 1 s backoff";
        return false;
    }
    if (count_contains(hal.logs, "FAULT_SENSOR_MISSING") != 1) {
        detail = "fault was logged again without a state change";
        return false;
    }
    const uint32_t retry_at[] = {1000, 3000, 7000, 15000, 31000};
    int expected_probes = 1;
    for (uint32_t t : retry_at) {
        // One millisecond early there must be no probe: the backoff doubles (1, 2, 4, 8, 16 s), it does not grow
        // linearly. Calling only at the due times cannot tell the two apart.
        hal.clock = t - 1;
        app.loop_once();
        if (hal.sensor_begin_calls != expected_probes * static_cast<int>(kSensorCount)) {
            detail = "retry ran before its backoff expired at t=" + std::to_string(t - 1);
            return false;
        }
        expected_probes += 1;
        hal.clock = t;
        app.loop_once();
        if (hal.sensor_begin_calls != begins_at_boot / static_cast<int>(kSensorCount) * 0 + expected_probes * static_cast<int>(kSensorCount)) {
            detail = "backoff retry did not probe both declared addresses at t=" + std::to_string(t);
            return false;
        }
        if (has_exact(hal.logs, "RECOVERED")) {
            detail = "recovered before the sensor was present";
            return false;
        }
    }
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    hal.clock = 61000;
    app.loop_once();
    if (!has_exact(hal.logs, "RECOVERED")) {
        detail = "capped 30 s retry did not recover when the sensor appeared";
        return false;
    }
    if (!has_exact(hal.logs, "BOOT sensor=0x76 display=0x3C")) {
        detail = "chosen address was not reported after recover";
        return false;
    }
    if (count_contains(hal.logs, "STATE=OK") < 1) {
        detail = "normal operation did not resume after recover";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_display_missing(std::string& detail) {
    FakeHal hal;
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    const uint32_t times[] = {0, 50, 2000, 4000, 6000};
    for (uint32_t t : times) {
        hal.clock = t;
        app.loop_once();
    }
    if (count_exact(hal.logs, "DISPLAY MISSING") != 1) {
        detail = "DISPLAY MISSING must be logged exactly once";
        return false;
    }
    if (!hal.displays.empty()) {
        detail = "display_show must not be called when the display is missing";
        return false;
    }
    if (!has_exact(hal.logs, "BOOT sensor=0x76 display=NONE")) {
        detail = "missing display was not reported as NONE";
        return false;
    }
    if (count_contains(hal.logs, "STATE=OK") < 1) {
        detail = "readings must still be logged on serial";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_display_at_second_address(std::string& detail) {
    FakeHal hal;
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.set_display(0x3C, false);
    hal.set_display(0x3D, true);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!check_grammar(hal, detail)) {
        return false;
    }
    if (!has_exact(hal.logs, "BOOT sensor=0x76 display=0x3D")) {
        detail = "display at the second declared address 0x3D was not reported";
        return false;
    }
    if (!has_exact(hal.logs, "T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
        detail = "reading did not reach serial when the display is at 0x3D";
        return false;
    }
    if (hal.displays.empty()) {
        detail = "readings did not reach the display at 0x3D";
        return false;
    }
    const auto& shown = hal.displays.front();
    if (shown[0] != "STATE OK" || shown[1] != "21.50 C" || shown[2] != "45.0 %" || shown[3] != "1013.3 hPa") {
        detail = "display at 0x3D did not show the reading";
        return false;
    }
    if (has_exact(hal.logs, "DISPLAY MISSING") || has_exact(hal.logs, "BOOT sensor=0x76 display=NONE")) {
        detail = "display at 0x3D was treated as missing";
        return false;
    }
    if (hal.display_begin_calls < 2) {
        detail = "display probe must try both declared addresses to find 0x3D";
        return false;
    }
    return true;
}

static bool scenario_transient_read_failure(std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 2000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 0 || hal.recover_calls != 0) {
        detail = "one failed read must stay STALE without a fault";
        return false;
    }
    if (!has_exact(hal.logs, "T=2000 STATE=STALE")) {
        detail = "first failed read was not marked STALE";
        return false;
    }
    hal.queue_fail();
    hal.clock = 4000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 0 || hal.recover_calls != 0) {
        detail = "two failed reads must stay STALE without a fault";
        return false;
    }
    const int begins_before_fault = hal.sensor_begin_calls;
    hal.queue_fail();
    hal.clock = 6000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 1) {
        detail = "third consecutive failure must enter FAULT_SENSOR_READ";
        return false;
    }
    if (hal.recover_calls != 1) {
        detail = "third failure must attempt bus_recover once";
        return false;
    }
    if (hal.sensor_begin_calls <= begins_before_fault) {
        detail = "third failure must re-begin the sensor";
        return false;
    }
    hal.queue_value(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    hal.clock = 8000;
    app.loop_once();
    if (!has_exact(hal.logs, "RECOVERED")) {
        detail = "a good read did not clear the fault with RECOVERED";
        return false;
    }
    if (!has_exact(hal.logs, "T=8000 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
        detail = "good read after the fault was not logged";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_read_fault_persistent_recovery(std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 2000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 4000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 6000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 1) {
        detail = "third consecutive failure must enter FAULT_SENSOR_READ";
        return false;
    }
    const int recover_at_fault = hal.recover_calls;
    const int begins_at_fault = hal.sensor_begin_calls;
    if (recover_at_fault != 1) {
        detail = "entering the read fault must attempt bus_recover once";
        return false;
    }
    hal.set_sensor(0x76, false);
    hal.set_sensor(0x77, false);
    hal.clock = 6500;
    app.loop_once();
    if (hal.recover_calls != recover_at_fault || hal.sensor_begin_calls != begins_at_fault) {
        detail = "read-fault retry must not run before the 1 s backoff";
        return false;
    }
    const uint32_t retry_at[] = {7000, 9000, 13000};
    int expected_recover = recover_at_fault;
    for (uint32_t t : retry_at) {
        // One millisecond before the due time nothing may run: the intervals are 1, 2, 4, 8 s, not linear.
        hal.clock = t - 1;
        app.loop_once();
        if (hal.recover_calls != expected_recover) {
            detail = "read-fault retry ran before its backoff expired at t=" + std::to_string(t - 1);
            return false;
        }
        expected_recover += 1;
        hal.clock = t;
        app.loop_once();
        if (hal.recover_calls != expected_recover) {
            detail = "read-fault backoff did not bus_recover at t=" + std::to_string(t);
            return false;
        }
        if (has_exact(hal.logs, "RECOVERED")) {
            detail = "recovered before the chip re-appeared";
            return false;
        }
        if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 1) {
            detail = "fault was logged again without a state change";
            return false;
        }
    }
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    hal.clock = 20999;
    app.loop_once();
    if (has_exact(hal.logs, "RECOVERED")) {
        detail = "read-fault retry ran before its 8 s backoff expired";
        return false;
    }
    hal.clock = 21000;
    app.loop_once();
    if (!has_exact(hal.logs, "RECOVERED")) {
        detail = "read-fault backoff did not recover when the chip re-appeared";
        return false;
    }
    if (!has_exact(hal.logs, "T=21000 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
        detail = "normal readings did not resume after read-fault recovery";
        return false;
    }
    if (hal.sensor_begin_addrs.empty() || hal.sensor_begin_addrs.back() != 0x76) {
        detail = "recovery probe did not rebind to the matched address";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_ambiguous_during_read_fault(std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 2000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 4000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 6000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 1) {
        detail = "third consecutive failure must enter FAULT_SENSOR_READ";
        return false;
    }
    const int reads_at_fault = hal.read_calls;
    const int ok_at_fault = count_ok_readings(hal.logs);
    const int boots_at_fault = count_contains(hal.logs, "BOOT sensor=");
    hal.set_sensor(0x77, true, kBme280ChipId);
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.clock = 7000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_AMBIGUOUS_ADDRESS") != 1) {
        detail = "two identity matches during a read-fault retry must be FAULT_AMBIGUOUS_ADDRESS";
        return false;
    }
    if (count_ok_readings(hal.logs) != ok_at_fault) {
        detail = "ambiguous address during read-fault retry must not show a new reading";
        return false;
    }
    if (count_contains(hal.logs, "BOOT sensor=") != boots_at_fault) {
        detail = "ambiguous read-fault retry picked an address";
        return false;
    }
    const int reads_at_ambiguous = hal.read_calls;
    for (uint32_t t = 8000; t <= 20000; t += 1000) {
        hal.clock = t;
        app.loop_once();
    }
    if (hal.read_calls != reads_at_ambiguous) {
        detail = "FAULT_AMBIGUOUS_ADDRESS must not keep calling sensor_read";
        return false;
    }
    if (count_contains(hal.logs, "FAULT_AMBIGUOUS_ADDRESS") != 1) {
        detail = "ambiguous state line must appear once";
        return false;
    }
    if (count_ok_readings(hal.logs) != ok_at_fault) {
        detail = "ambiguous address later showed a reading";
        return false;
    }
    if (hal.read_calls < reads_at_fault) {
        detail = "read-call count went backwards";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_second_read_fault_starts_at_one_second(std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 2000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 4000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 6000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 1) {
        detail = "third consecutive failure must enter FAULT_SENSOR_READ";
        return false;
    }
    hal.set_sensor(0x76, false);
    hal.set_sensor(0x77, false);
    const uint32_t grow_at[] = {7000, 9000, 13000};
    for (uint32_t t : grow_at) {
        hal.clock = t;
        app.loop_once();
        if (has_exact(hal.logs, "RECOVERED")) {
            detail = "recovered before backoff grew to 8 s";
            return false;
        }
    }
    // After the 13000 retry, backoff is 8 s. Recover on the next expiry.
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    hal.clock = 21000;
    app.loop_once();
    if (!has_exact(hal.logs, "RECOVERED")) {
        detail = "read-fault did not recover after backoff reached 8 s";
        return false;
    }
    hal.queue_fail();
    hal.clock = 23000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 25000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 27000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 2) {
        detail = "second read-fault episode did not start";
        return false;
    }
    const int recover_at_second = hal.recover_calls;
    const int begins_at_second = hal.sensor_begin_calls;
    hal.clock = 27999;
    app.loop_once();
    if (hal.recover_calls != recover_at_second || hal.sensor_begin_calls != begins_at_second) {
        detail = "first retry of the second read-fault episode ran before 1000 ms";
        return false;
    }
    hal.clock = 28000;
    app.loop_once();
    if (hal.recover_calls != recover_at_second + 1) {
        detail = "first retry of the second read-fault episode must come 1000 ms after entering it";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_first_read_fails(std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    hal.queue_fail();
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!has_exact(hal.logs, "BOOT sensor=0x76 display=0x3C")) {
        detail = "boot line missing after a failed first read";
        return false;
    }
    if (!has_exact(hal.logs, "T=0 STATE=STALE")) {
        detail = "failed first read was not marked STALE";
        return false;
    }
    if (count_contains(hal.logs, "FAULT_") != 0) {
        detail = "a single failed first read must not raise a fault";
        return false;
    }
    if (hal.displays.empty() || hal.displays.back()[0] != "NO DATA" ||
        hal.displays.back()[1] != "" || hal.displays.back()[2] != "" ||
        hal.displays.back()[3] != "") {
        detail = "display must show NO DATA on the first line with other lines empty";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_implausible_values(std::string& detail) {
    const BoundCase bounds[] = {
        {"temp_min_edge", -40.0f, 45.0f, 1013.3f, true},
        {"temp_min_beyond", -40.01f, 45.0f, 1013.3f, false},
        {"temp_max_edge", 85.0f, 45.0f, 1013.3f, true},
        {"temp_max_beyond", 85.01f, 45.0f, 1013.3f, false},
        {"hum_min_edge", 21.50f, 0.0f, 1013.3f, true},
        {"hum_min_beyond", 21.50f, -0.01f, 1013.3f, false},
        {"hum_max_edge", 21.50f, 100.0f, 1013.3f, true},
        {"hum_max_beyond", 21.50f, 100.01f, 1013.3f, false},
        {"pres_min_edge", 21.50f, 45.0f, 300.0f, true},
        {"pres_min_beyond", 21.50f, 45.0f, 299.99f, false},
        {"pres_max_edge", 21.50f, 45.0f, 1100.0f, true},
        {"pres_max_beyond", 21.50f, 45.0f, 1100.01f, false},
        {"nan_humidity_only", 21.50f, std::nanf(""), 1013.3f, false},
        {"nan_pressure_only", 21.50f, 45.0f, std::nanf(""), false},
    };
    for (const auto& c : bounds) {
        if (!check_isolated_bound(c, detail)) {
            return false;
        }
    }
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    hal.queue_nan();
    hal.clock = 2000;
    app.loop_once();
    if (count_contains(hal.logs, "nan") || count_contains(hal.logs, "NaN")) {
        detail = "NaN was logged as a reading";
        return false;
    }
    for (const auto& shown : hal.displays) {
        for (const auto& line : shown) {
            if (line.find("nan") != std::string::npos || line.find("NaN") != std::string::npos) {
                detail = "NaN was displayed";
                return false;
            }
        }
    }
    if (!has_exact(hal.logs, "T=2000 STATE=STALE")) {
        detail = "NaN must count as a failed read";
        return false;
    }
    hal.queue_value(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    hal.clock = 4000;
    app.loop_once();
    hal.queue_value(100.0f, 45.0f, 1013.3f);
    hal.clock = 6000;
    app.loop_once();
    if (count_contains(hal.logs, "TEMP_C=100.00")) {
        detail = "temperature outside -40..85 C was logged as a reading";
        return false;
    }
    if (!has_exact(hal.logs, "T=6000 STATE=STALE")) {
        detail = "out-of-range temperature must count as a failed read";
        return false;
    }
    hal.queue_value(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    hal.clock = 8000;
    app.loop_once();
    hal.queue_value(21.50f, 101.0f, 1013.3f);
    hal.clock = 10000;
    app.loop_once();
    if (count_contains(hal.logs, "HUM_PCT=101.0")) {
        detail = "humidity outside 0..100 % was logged as a reading";
        return false;
    }
    hal.queue_value(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    hal.clock = 12000;
    app.loop_once();
    hal.queue_value(21.50f, 45.0f, 200.0f);
    hal.clock = 14000;
    app.loop_once();
    if (count_contains(hal.logs, "PRES_HPA=200.0")) {
        detail = "pressure outside 300..1100 hPa was logged as a reading";
        return false;
    }
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 0) {
        detail = "interleaved implausible values should not raise a read fault";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_clock_wrap(std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    const int after_boot = hal.read_calls;
    hal.clock = 0xFFFFF830u;
    app.loop_once();
    const int after_jump = hal.read_calls;
    if (after_jump != after_boot + 1) {
        detail = "catch-up across a large jump must take exactly one read";
        return false;
    }
    hal.clock = 0xFFFFF830u + 100u;
    app.loop_once();
    if (hal.read_calls != after_jump) {
        detail = "read burst before the wrap";
        return false;
    }
    hal.clock = 100;
    app.loop_once();
    if (hal.read_calls != after_jump + 1) {
        detail = "wrap from 0xFFFFFFFF stalled the schedule";
        return false;
    }
    hal.clock = 200;
    app.loop_once();
    if (hal.read_calls != after_jump + 1) {
        detail = "wrap caused a burst of reads";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_read_period(std::string& detail) {
    {
        FakeHal hal;
        wire_boot_ok_bus(hal);
        SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
        hal.clock = 0;
        app.loop_once();
        if (hal.read_calls != 1 || !has_exact(hal.logs, "T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
            detail = "healthy chip must take a reading at t=0";
            return false;
        }
        for (uint32_t t = 1; t <= 1999; ++t) {
            hal.clock = t;
            app.loop_once();
            if (hal.read_calls != 1 || count_ok_readings(hal.logs) != 1) {
                detail = "1 ms steps: no reading until t=2000, extra at t=" + std::to_string(t);
                return false;
            }
        }
        hal.clock = 2000;
        app.loop_once();
        if (hal.read_calls != 2 || !has_exact(hal.logs, "T=2000 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
            detail = "healthy chip must take a reading at t=2000";
            return false;
        }
        for (uint32_t t = 2001; t <= 3999; ++t) {
            hal.clock = t;
            app.loop_once();
            if (hal.read_calls != 2 || count_ok_readings(hal.logs) != 2) {
                detail = "1 ms steps: no reading until t=4000, extra at t=" + std::to_string(t);
                return false;
            }
        }
        hal.clock = 4000;
        app.loop_once();
        if (hal.read_calls != 3 || !has_exact(hal.logs, "T=4000 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
            detail = "healthy chip must take a reading at t=4000";
            return false;
        }
        if (!check_grammar(hal, detail)) {
            return false;
        }
    }
    {
        FakeHal hal;
        wire_boot_ok_bus(hal);
        SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
        int expected_reads = 0;
        for (uint32_t t = 0; t <= 10000; t += 500) {
            hal.clock = t;
            app.loop_once();
            if (t % 2000u == 0) {
                expected_reads += 1;
            }
            if (hal.read_calls != expected_reads) {
                detail = "500 ms steps: unexpected sensor_read count " + std::to_string(hal.read_calls) +
                         " at t=" + std::to_string(t);
                return false;
            }
            if (count_ok_readings(hal.logs) != expected_reads) {
                detail = "500 ms steps: unexpected reading line count at t=" + std::to_string(t);
                return false;
            }
        }
        if (hal.read_calls != 6) {
            detail = "sensor_read count over a 10 s window must be 6, got " + std::to_string(hal.read_calls);
            return false;
        }
        if (!has_exact(hal.logs, "T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3") ||
            !has_exact(hal.logs, "T=2000 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3") ||
            !has_exact(hal.logs, "T=4000 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
            detail = "coarse 500 ms steps missed a period-edge reading";
            return false;
        }
        if (!check_grammar(hal, detail)) {
            return false;
        }
    }
    return true;
}

static bool scenario_two_devices_answer(std::string& detail) {
    FakeHal hal;
    hal.set_sensor(0x77, true, kBme280ChipId);
    hal.set_sensor(0x76, true, kBme280ChipId);
    hal.set_display(0x3C, true);
    hal.set_default(kGood.temp_c, kGood.hum_pct, kGood.pres_hpa);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    for (uint32_t t = 0; t <= 60000; t += 500) {
        hal.clock = t;
        app.loop_once();
    }
    if (hal.read_calls != 0) {
        detail = "ambiguous address must not call sensor_read";
        return false;
    }
    if (count_ok_readings(hal.logs) != 0) {
        detail = "an ambiguous address must not show a reading";
        return false;
    }
    if (count_contains(hal.logs, "FAULT_AMBIGUOUS_ADDRESS") != 1) {
        detail = "two identity matches must log FAULT_AMBIGUOUS_ADDRESS once";
        return false;
    }
    if (has_exact(hal.logs, "BOOT sensor=0x77 display=0x3C") || has_exact(hal.logs, "BOOT sensor=0x76 display=0x3C")) {
        detail = "ambiguous bus picked an address";
        return false;
    }
    if (display_shows_a_reading(hal)) {
        detail = "ambiguous bus displayed a reading";
        return false;
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_serial_grammar(std::string& detail) {
    std::string unused;
    if (!scenario_boot_ok(unused)) {
        detail = "grammar mix: boot_ok failed";
        return false;
    }
    if (!scenario_default_address_binding(unused)) {
        detail = "grammar mix: default_address_binding failed";
        return false;
    }
    if (!scenario_display_missing(unused)) {
        detail = "grammar mix: display_missing failed";
        return false;
    }
    if (!scenario_display_at_second_address(unused)) {
        detail = "grammar mix: display_at_second_address failed";
        return false;
    }
    if (!scenario_transient_read_failure(unused)) {
        detail = "grammar mix: transient_read_failure failed";
        return false;
    }
    if (!scenario_ambiguous_during_read_fault(unused)) {
        detail = "grammar mix: ambiguous_during_read_fault failed";
        return false;
    }
    if (!scenario_first_read_fails(unused)) {
        detail = "grammar mix: first_read_fails failed";
        return false;
    }
    if (!scenario_read_period(unused)) {
        detail = "grammar mix: read_period failed";
        return false;
    }
    if (!scenario_two_devices_answer(unused)) {
        detail = "grammar mix: two_devices_answer failed";
        return false;
    }
    FakeHal hal;
    wire_boot_ok_bus(hal);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!check_grammar(hal, detail)) {
        return false;
    }
    if (!has_exact(hal.logs, "T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3")) {
        detail = "reading line shape was not T=<ms> STATE=OK TEMP_C=<%.2f> HUM_PCT=<%.1f> PRES_HPA=<%.1f>";
        return false;
    }
    return true;
}

struct Scenario {
    const char* name;
    bool (*fn)(std::string&);
};

int main() {
    const Scenario scenarios[] = {
        {"boot_ok", scenario_boot_ok},
        {"default_address_binding", scenario_default_address_binding},
        {"sensor_missing_at_boot", scenario_sensor_missing_at_boot},
        {"display_missing", scenario_display_missing},
        {"display_at_second_address", scenario_display_at_second_address},
        {"transient_read_failure", scenario_transient_read_failure},
        {"read_fault_persistent_recovery", scenario_read_fault_persistent_recovery},
        {"ambiguous_during_read_fault", scenario_ambiguous_during_read_fault},
        {"second_read_fault_starts_at_one_second", scenario_second_read_fault_starts_at_one_second},
        {"implausible_values", scenario_implausible_values},
        {"clock_wrap", scenario_clock_wrap},
        {"read_period", scenario_read_period},
        {"two_devices_answer", scenario_two_devices_answer},
        {"first_read_fails", scenario_first_read_fails},
        {"serial_grammar", scenario_serial_grammar},
    };
    bool all = true;
    for (const auto& scenario : scenarios) {
        g_serial_trace.clear();
        std::string detail;
        const bool ok = scenario.fn(detail);
        std::printf("{\"scenario\":\"%s\",\"pass\":%s,\"detail\":\"%s\",\"modeled_serial\":[",
                    scenario.name, ok ? "true" : "false", json_escape(detail).c_str());
        for (size_t i = 0; i < g_serial_trace.size(); ++i) {
            std::printf("%s\"%s\"", i ? "," : "", json_escape(g_serial_trace[i]).c_str());
        }
        std::printf("]}\n");
        all = all && ok;
    }
    return all ? 0 : 1;
}
