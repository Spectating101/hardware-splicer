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

#include "part_fixtures.h"

static const uint8_t kDisplayAddrs[] = {0x3C, 0x3D};
static constexpr size_t kSensorCount = sizeof kSensorAddrs / sizeof kSensorAddrs[0];
static constexpr size_t kDisplayCount = sizeof kDisplayAddrs / sizeof kDisplayAddrs[0];

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
    int fail_begin_call = 0;  // 1-based: that sensor_begin call fails (driver rebinds, stays uncalibrated)
    int display_begin_calls = 0;
    int read_calls = 0;
    int recover_calls = 0;
    std::vector<uint8_t> sensor_begin_addrs;
    uint8_t bound_addr = 0;
    bool calibrated = false;

    // A sensor answers at one of its two declared addresses and, when the part can identify itself, with the
    // right id. A part with no ID register (kHasIdentity false) is recognised by its acknowledgement alone.
    bool sensor_here(int a) const {
        return present[a] && (a == kAddrA || a == kAddrB) && (!kHasIdentity || chip_id[a] == kChipId);
    }

    uint8_t chip_address() const {
        uint8_t found = 0;
        int n = 0;
        for (int a = 0; a < 256; ++a) {
            if (sensor_here(a)) {
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
        calibrated = sensor_here(addr) && sensor_begin_calls != fail_begin_call;
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

    void set_sensor(uint8_t addr, bool on, uint8_t id = kChipId) {
        present[addr] = on;
        chip_id[addr] = id;
        if (!on) {
            calibrated = false;  // unplug: registers reset, calibration lost
        }
    }

    void set_display(uint8_t addr, bool on) { present[addr] = on; }

    void set_default(const Reading& value) {
        default_read.fail = false;
        default_read.value = value;
        has_default = true;
    }

    void queue_fail() {
        ReadCmd cmd;
        cmd.fail = true;
        reads.push_back(cmd);
    }

    void queue_value(const Reading& value) {
        ReadCmd cmd;
        cmd.fail = false;
        cmd.value = value;
        reads.push_back(cmd);
    }

    void queue_nan() {
        ReadCmd cmd;
        cmd.fail = false;
        cmd.value = reading_filled(std::nanf(""));
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
        std::regex(kOkLineRegex),
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

static std::string ok_line(uint32_t t) {
    return "T=" + std::to_string(t) + " STATE=OK" + kGoodLineSuffix;
}

static std::string boot_line(uint8_t sensor, const char* display) {
    char line[64];
    std::snprintf(line, sizeof line, "BOOT sensor=0x%02X display=%s", sensor, display);
    return line;
}

static bool display_is_good(const std::array<std::string, 4>& shown) {
    for (size_t i = 0; i < 4; ++i) {
        if (shown[i] != kGoodDisplay[i]) {
            return false;
        }
    }
    return true;
}

static void wire_boot_ok_bus(FakeHal& hal) {
    if (kHasIdentity) {
        hal.set_sensor(kAddrA, true, 0x00);  // present but identity does not match
    }
    hal.set_sensor(kAddrB, true, kChipId);
    hal.set_display(0x3C, true);
    hal.set_display(0x3D, false);
    hal.set_default(kGood);
}

static int count_ok_readings(const std::vector<std::string>& lines) {
    return count_contains(lines, kOkMarker);
}

static bool display_shows_a_reading(const FakeHal& hal) {
    for (const auto& shown : hal.displays) {
        if (shown[0] == "STATE OK" || shown[0] == "STATE STALE") {
            return true;
        }
        for (size_t i = 0; i < 3; ++i) {
            if (kDisplayMarkers[i][0] != '\0' && shown[i + 1].find(kDisplayMarkers[i]) != std::string::npos) {
                return true;
            }
        }
    }
    return false;
}

static bool check_isolated_bound(const BoundCase& c, std::string& detail) {
    FakeHal hal;
    wire_boot_ok_bus(hal);
    hal.has_default = false;
    hal.queue_value(c.value);
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
    if (!has_exact(hal.logs, boot_line(kAddrB, "0x3C"))) {
        detail = "missing BOOT with the identity-matched addresses";
        return false;
    }
    if (!has_exact(hal.logs, ok_line(0))) {
        detail = "first cycle did not show the reading";
        return false;
    }
    if (hal.displays.empty()) {
        detail = "display_show was not called";
        return false;
    }
    const auto& shown = hal.displays.front();
    if (!display_is_good(shown)) {
        detail = "display did not show the first reading";
        return false;
    }
    if (has_exact(hal.logs, boot_line(kAddrA, "0x3C"))) {
        detail = "picked the first declared address without a matching chip identity";
        return false;
    }
    return true;
}

static bool scenario_default_address_binding(std::string& detail) {
    FakeHal hal;
    hal.set_sensor(kAddrA, true, kChipId);
    hal.set_display(0x3C, true);
    hal.set_default(kGood);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!check_grammar(hal, detail)) {
        return false;
    }
    if (!has_exact(hal.logs, boot_line(kAddrA, "0x3C"))) {
        detail = "chip at the first declared address was not reported";
        return false;
    }
    if (!has_exact(hal.logs, ok_line(0))) {
        detail = "reading failed: driver left bound to a later probed address";
        return false;
    }
    if (hal.sensor_begin_addrs.empty() || hal.sensor_begin_addrs.back() != kAddrA) {
        detail = "last sensor_begin was not the matched first address (rebind after probe)";
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
    hal.set_sensor(kAddrB, true, kChipId);
    hal.set_default(kGood);
    hal.clock = 61000;
    app.loop_once();
    if (!has_exact(hal.logs, "RECOVERED")) {
        detail = "capped 30 s retry did not recover when the sensor appeared";
        return false;
    }
    if (!has_exact(hal.logs, boot_line(kAddrB, "0x3C"))) {
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
    {
        // The probe found the chip, but the final rebind to it fails (call 3: probe A, probe B, rebind A).
        // A chip that was seen once but cannot be bound again must not be reported as a usable device.
        FakeHal flaky;
        flaky.set_sensor(kAddrA, true, kChipId);
        flaky.set_display(0x3C, true);
        flaky.set_default(kGood);
        flaky.fail_begin_call = 3;
        SensorApp flaky_app(flaky, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
        flaky.clock = 0;
        flaky_app.loop_once();
        if (count_contains(flaky.logs, "BOOT sensor=") != 0) {
            detail = "a failed rebind was reported as a usable sensor";
            return false;
        }
        if (count_contains(flaky.logs, "FAULT_SENSOR_MISSING") != 1 || count_contains(flaky.logs, "STATE=OK") != 0) {
            detail = "a failed rebind must leave FAULT_SENSOR_MISSING and no reading";
            return false;
        }
    }
    return true;
}

static bool scenario_display_missing(std::string& detail) {
    FakeHal hal;
    hal.set_sensor(kAddrB, true, kChipId);
    hal.set_default(kGood);
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
    if (!has_exact(hal.logs, boot_line(kAddrB, "NONE"))) {
        detail = "missing display was not reported as NONE";
        return false;
    }
    if (count_contains(hal.logs, "STATE=OK") < 1) {
        detail = "readings must still be logged on serial";
        return false;
    }
    // Faults must not draw on a display that never answered, whether the sensor read fails or is absent.
    hal.queue_fail();
    hal.clock = 8000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 10000;
    app.loop_once();
    hal.queue_fail();
    hal.clock = 12000;
    app.loop_once();
    if (count_contains(hal.logs, "FAULT_SENSOR_READ") != 1) {
        detail = "the sensor read fault was not reached while the display was missing";
        return false;
    }
    if (!hal.displays.empty()) {
        detail = "a read fault must not draw on a display that never answered";
        return false;
    }
    {
        FakeHal bare;
        SensorApp bare_app(bare, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
        bare.clock = 0;
        bare_app.loop_once();
        if (count_contains(bare.logs, "FAULT_SENSOR_MISSING") != 1 || !bare.displays.empty()) {
            detail = "a missing sensor must not draw on a display that never answered";
            return false;
        }
    }
    if (!check_grammar(hal, detail)) {
        return false;
    }
    return true;
}

static bool scenario_display_at_second_address(std::string& detail) {
    FakeHal hal;
    hal.set_sensor(kAddrB, true, kChipId);
    hal.set_display(0x3C, false);
    hal.set_display(0x3D, true);
    hal.set_default(kGood);
    SensorApp app(hal, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
    hal.clock = 0;
    app.loop_once();
    if (!check_grammar(hal, detail)) {
        return false;
    }
    if (!has_exact(hal.logs, boot_line(kAddrB, "0x3D"))) {
        detail = "display at the second declared address 0x3D was not reported";
        return false;
    }
    if (!has_exact(hal.logs, ok_line(0))) {
        detail = "reading did not reach serial when the display is at 0x3D";
        return false;
    }
    if (hal.displays.empty()) {
        detail = "readings did not reach the display at 0x3D";
        return false;
    }
    const auto& shown = hal.displays.front();
    if (!display_is_good(shown)) {
        detail = "display at 0x3D did not show the reading";
        return false;
    }
    if (has_exact(hal.logs, "DISPLAY MISSING") || has_exact(hal.logs, boot_line(kAddrB, "NONE"))) {
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
    if (hal.displays.empty() || hal.displays.back()[0] != "STATE STALE" || hal.displays.back()[1] != kGoodDisplay[1]) {
        detail = "a stale reading must be shown as STATE STALE with the last good values, not as fresh";
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
    hal.queue_value(kGood);
    hal.clock = 8000;
    app.loop_once();
    if (!has_exact(hal.logs, "RECOVERED")) {
        detail = "a good read did not clear the fault with RECOVERED";
        return false;
    }
    if (!has_exact(hal.logs, ok_line(8000))) {
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
    hal.set_sensor(kAddrB, false);
    hal.set_sensor(kAddrA, false);
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
    hal.set_sensor(kAddrB, true, kChipId);
    hal.set_default(kGood);
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
    if (!has_exact(hal.logs, ok_line(21000))) {
        detail = "normal readings did not resume after read-fault recovery";
        return false;
    }
    if (hal.sensor_begin_addrs.empty() || hal.sensor_begin_addrs.back() != kAddrB) {
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
    hal.set_sensor(kAddrA, true, kChipId);
    hal.set_sensor(kAddrB, true, kChipId);
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
    hal.set_sensor(kAddrB, false);
    hal.set_sensor(kAddrA, false);
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
    hal.set_sensor(kAddrB, true, kChipId);
    hal.set_default(kGood);
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
    if (!has_exact(hal.logs, boot_line(kAddrB, "0x3C"))) {
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
    for (const auto& c : kBoundCases) {
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
    for (size_t i = 0; i < sizeof kOutOfRangeCases / sizeof kOutOfRangeCases[0]; ++i) {
        const auto& c = kOutOfRangeCases[i];
        const uint32_t t_good = 4000 + 4000 * static_cast<uint32_t>(i);
        hal.queue_value(kGood);
        hal.clock = t_good;
        app.loop_once();
        hal.queue_value(c.value);
        hal.clock = t_good + 2000;
        app.loop_once();
        if (count_contains(hal.logs, c.must_not_log)) {
            detail = c.detail;
            return false;
        }
        if (!has_exact(hal.logs, "T=" + std::to_string(t_good + 2000) + " STATE=STALE")) {
            detail = std::string(c.name) + " out of range must count as a failed read";
            return false;
        }
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
    {
        // A real first loop runs some time after reset. The period is measured from that boot, not from zero.
        FakeHal late;
        wire_boot_ok_bus(late);
        SensorApp late_app(late, kSensorAddrs, kSensorCount, kDisplayAddrs, kDisplayCount);
        late.clock = 1500;
        late_app.loop_once();
        late.clock = 2000;
        late_app.loop_once();
        late.clock = 3499;
        late_app.loop_once();
        if (late.read_calls != 1) {
            detail = "a boot at t=1500 must not read again before t=3500";
            return false;
        }
        late.clock = 3500;
        late_app.loop_once();
        if (late.read_calls != 2) {
            detail = "a boot at t=1500 must read again at t=3500";
            return false;
        }
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
        if (hal.read_calls != 1 || !has_exact(hal.logs, ok_line(0))) {
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
        if (hal.read_calls != 2 || !has_exact(hal.logs, ok_line(2000))) {
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
        if (hal.read_calls != 3 || !has_exact(hal.logs, ok_line(4000))) {
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
        if (!has_exact(hal.logs, ok_line(0)) ||
            !has_exact(hal.logs, ok_line(2000)) ||
            !has_exact(hal.logs, ok_line(4000))) {
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
    hal.set_sensor(kAddrA, true, kChipId);
    hal.set_sensor(kAddrB, true, kChipId);
    hal.set_display(0x3C, true);
    hal.set_default(kGood);
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
    if (has_exact(hal.logs, boot_line(kAddrA, "0x3C")) || has_exact(hal.logs, boot_line(kAddrB, "0x3C"))) {
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
    if (!has_exact(hal.logs, ok_line(0))) {
        detail = "reading line shape did not match the part's serial grammar";
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
