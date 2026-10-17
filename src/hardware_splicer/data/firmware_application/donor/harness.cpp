#include "Arduino.h"
#include "donor_inputs.h"
#include <cstdio>
#include <algorithm>

uint32_t now_ms = 0;
int levels[256];
int modes[256];
unsigned mode_calls = 0;
TestSerial Serial;
static constexpr uint8_t expected_pins[] = { {{PINS}} };
static constexpr unsigned count = {{COUNT}};

static void poll(uint32_t at) { now_ms = at; hs_donor::tick(); }
static void all_levels(int level) { for (auto pin : expected_pins) levels[pin] = level; }
static void reset(int level = HIGH, uint32_t start = 0) {
    std::fill(levels, levels + 256, HIGH);
    std::fill(modes, modes + 256, -1);
    mode_calls = 0;
    Serial.lines.clear();
    now_ms = start;
    all_levels(level);
    hs_donor::begin();
}
static bool reports(bool pressed) {
    if (Serial.lines.size() != count) return false;
    for (unsigned i = 0; i < count; ++i) {
        char expected[64];
        snprintf(expected, sizeof expected, "DONOR_INPUT index=%u pressed=%u", i, unsigned(pressed));
        if (Serial.lines[i] != expected) return false;
    }
    return true;
}
static void settled(int level = HIGH) { reset(level); poll(20); Serial.lines.clear(); }

static bool scenario(unsigned n) {
    switch (n) {
    case 0:
        reset();
        if (mode_calls != count) return false;
        for (unsigned pin = 0; pin < 256; ++pin) {
            const bool used = std::find(expected_pins, expected_pins + count, pin) != expected_pins + count;
            if (modes[pin] != (used ? INPUT_PULLUP : -1)) return false;
        }
        return true;
    case 1:
    case 2:
        reset(n == 1 ? HIGH : LOW);
        poll(0); poll(19);
        if (!Serial.lines.empty()) return false;
        poll(20);
        return reports(n == 2);
    case 3:
    case 4: {
        const bool press = n == 3;
        settled(press ? HIGH : LOW);
        all_levels(press ? LOW : HIGH); poll(21);
        all_levels(press ? HIGH : LOW); poll(25);
        all_levels(press ? LOW : HIGH); poll(30); poll(49);
        if (!Serial.lines.empty()) return false;
        poll(50);
        return reports(press);
    }
    case 5:
        settled(LOW);
        poll(21); poll(1000); poll(1000000);
        return Serial.lines.empty();
    case 6:
        settled();
        for (unsigned i = 0; i < count; ++i) {
            Serial.lines.clear();
            levels[expected_pins[i]] = LOW;
            poll(100 + i * 100); poll(120 + i * 100);
            char expected[64];
            snprintf(expected, sizeof expected, "DONOR_INPUT index=%u pressed=1", i);
            if (Serial.lines.size() != 1 || Serial.lines[0] != expected) return false;
        }
        return true;
    case 7: {
        const uint32_t start = UINT32_MAX - 10;
        reset(LOW, start);
        poll(start); poll(start + uint32_t(19));
        if (!Serial.lines.empty()) return false;
        poll(start + uint32_t(20));
        return reports(true);
    }
    case 8:
        settled();
        all_levels(LOW); poll(21);
        all_levels(HIGH); poll(30); poll(50);
        return Serial.lines.empty();
    case 9:
        settled(LOW);
        now_ms = 100;
        hs_donor::begin();
        poll(119);
        if (!Serial.lines.empty()) return false;
        poll(120);
        return reports(true);
    }
    return false;
}

int main() {
    const char* names[] = {"input_pullups", "released_boot", "held_boot", "bounce_press", "bounce_release",
                          "held_no_repeat", "independent_inputs", "clock_wrap", "no_short_pulse", "restart_requires_settle"};
    bool passed = true;
    for (unsigned i = 0; i < sizeof names / sizeof names[0]; ++i) {
        const bool ok = scenario(i);
        printf("{\"scenario\":\"%s\",\"pass\":%s}\n", names[i], ok ? "true" : "false");
        passed = passed && ok;
    }
    return passed ? 0 : 1;
}
