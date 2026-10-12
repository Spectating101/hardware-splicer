#include "Arduino.h"
#include "SPI.h"

SimClock g_sim_clock;
HardwareSerial Serial;
SPIClass SPI;

unsigned long millis() { return static_cast<unsigned long>(g_sim_clock.us / 1000ull); }
unsigned long micros() { return static_cast<unsigned long>(g_sim_clock.us); }

static void check_watchdog() {
    if (!g_sim_clock.in_loop) return;
    if (g_sim_clock.us - g_sim_clock.loop_start_us >= g_sim_clock.watchdog_limit_us) {
        g_sim_clock.watchdog_fired = true;
        throw WatchdogAbort{};
    }
}

void delay(unsigned long ms) {
    g_sim_clock.us += static_cast<uint64_t>(ms) * 1000ull;
    check_watchdog();
}

void delayMicroseconds(unsigned int us) { g_sim_clock.us += us; }

void sim_advance_ms(uint32_t ms) { g_sim_clock.us += static_cast<uint64_t>(ms) * 1000ull; }

uint32_t sim_loop_elapsed_ms() {
    return static_cast<uint32_t>((g_sim_clock.us - g_sim_clock.loop_start_us) / 1000ull);
}

void sim_begin_loop() {
    g_sim_clock.loop_start_us = g_sim_clock.us;
    g_sim_clock.in_loop = true;
    g_sim_clock.watchdog_fired = false;
}

void sim_end_loop() { g_sim_clock.in_loop = false; }

void pinMode(uint8_t, uint8_t) {}
void digitalWrite(uint8_t, uint8_t) {}
int digitalRead(uint8_t) { return LOW; }

void HardwareSerial::begin(unsigned long) {}

void HardwareSerial::clear_capture() {
    raw_.clear();
    current_.clear();
    lines_.clear();
}

size_t HardwareSerial::write(uint8_t ch) {
    raw_.push_back(static_cast<char>(ch));
    if (ch == '\n') {
        if (!current_.empty() && current_.back() == '\r') current_.pop_back();
        lines_.push_back(current_);
        current_.clear();
    } else if (ch != '\r') {
        current_.push_back(static_cast<char>(ch));
    }
    return 1;
}
