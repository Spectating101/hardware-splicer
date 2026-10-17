#pragma once
#include <Arduino.h>
#include <stdint.h>
#include <stdio.h>

// A software proposal, not measured pull-up suitability or physical debounce.
// Arduino API semantics: INPUT_PULLUP, digitalRead LOW/HIGH, unsigned millis.
namespace hs_donor {
static constexpr uint8_t kPins[] = { {{PINS}} };
static constexpr unsigned kCount = sizeof kPins / sizeof kPins[0];
static constexpr uint32_t kDebounceMs = 20;
struct InputState {
    bool raw_pressed = false;
    bool stable_pressed = false;
    bool known = false;
    uint32_t changed_ms = 0;
};
static InputState states[kCount];
static bool started = false;

inline void begin() {
    for (unsigned i = 0; i < kCount; ++i) {
        pinMode(kPins[i], INPUT_PULLUP);
        states[i] = InputState{};
        states[i].raw_pressed = digitalRead(kPins[i]) == LOW;
        states[i].changed_ms = uint32_t(millis());
    }
    started = true;
}

inline void tick() {
    if (!started) return;
    const uint32_t now = uint32_t(millis());
    for (unsigned i = 0; i < kCount; ++i) {
        auto& state = states[i];
        const bool pressed = digitalRead(kPins[i]) == LOW;
        if (pressed != state.raw_pressed) {
            state.raw_pressed = pressed;
            state.changed_ms = now;
        }
        // Unsigned subtraction crosses the 32-bit millisecond rollover.
        // This is stability of sampled levels, not proof of continuous electrical stability.
        if (uint32_t(now - state.changed_ms) >= kDebounceMs &&
            (!state.known || state.stable_pressed != state.raw_pressed)) {
            state.stable_pressed = state.raw_pressed;
            state.known = true;
            char line[64];
            snprintf(line, sizeof line, "DONOR_INPUT index=%u pressed=%u", i, unsigned(state.stable_pressed));
            Serial.println(line);
        }
    }
}
}  // namespace hs_donor
