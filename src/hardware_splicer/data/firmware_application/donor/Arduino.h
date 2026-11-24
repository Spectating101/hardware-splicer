#pragma once
// Test-only digital GPIO/clock shim. Not a model of either physical Arduino core.
#include <cstdint>
#include <string>
#include <vector>
#define HIGH 1
#define LOW 0
#define INPUT_PULLUP 2
extern uint32_t now_ms;
extern int levels[256];
extern int modes[256];
extern unsigned mode_calls;
inline unsigned long millis() { return now_ms; }
inline int digitalRead(uint8_t pin) { return levels[pin]; }
inline void pinMode(uint8_t pin, uint8_t mode) { modes[pin] = mode; ++mode_calls; }
struct TestSerial {
    std::vector<std::string> lines;
    void println(const char* line) { lines.emplace_back(line); }
};
extern TestSerial Serial;
