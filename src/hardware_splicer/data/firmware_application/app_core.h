// Host-testable application core. Platform-independent C++17. No Arduino/ESP headers.
// Behaviour lives here. The Arduino adapter only implements Hal.
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cmath>

// Reading, plausible ranges and line formats are specific to one part and generated from its descriptor.
#include "part_traits.h"

// Software choice, not a validated sampling rate.
static constexpr uint32_t kReadPeriodMs = 2000;

static constexpr int kReadFailThreshold = 3;
static constexpr uint32_t kBackoffInitialMs = 1000;
static constexpr uint32_t kBackoffCapMs = 30000;

class Hal {
public:
    virtual ~Hal() = default;
    virtual uint32_t now_ms() = 0;
    virtual bool sensor_begin(uint8_t addr) = 0;  // (re)binds the driver to addr even when it returns false; true only if chip identity matched
    virtual bool sensor_read(Reading& out) = 0;
    virtual bool display_begin(uint8_t addr) = 0;
    virtual void display_show(const char* l1, const char* l2, const char* l3, const char* l4) = 0;
    virtual void log(const char* line) = 0;
    virtual bool bus_recover() = 0;
};

enum class AppState : uint8_t {
    OK = 0,
    STALE,
    FAULT_SENSOR_MISSING,
    FAULT_SENSOR_READ,
    FAULT_AMBIGUOUS_ADDRESS,
};

static uint32_t wrap_elapsed(uint32_t now, uint32_t then) {
    const uint32_t elapsed = now - then;
    return elapsed;
}

static const char* state_text(AppState state) {
    switch (state) {
        case AppState::OK:
            return "OK";
        case AppState::STALE:
            return "STALE";
        case AppState::FAULT_SENSOR_MISSING:
            return "FAULT_SENSOR_MISSING";
        case AppState::FAULT_SENSOR_READ:
            return "FAULT_SENSOR_READ";
        case AppState::FAULT_AMBIGUOUS_ADDRESS:
            return "FAULT_AMBIGUOUS_ADDRESS";
    }
    return "OK";
}

class SensorApp {
public:
    SensorApp(Hal& hal,
              const uint8_t* sensor_addrs, size_t n_sensor,
              const uint8_t* display_addrs, size_t n_display)
        : hal_(hal),
          sensor_addrs_(sensor_addrs),
          n_sensor_(n_sensor),
          display_addrs_(display_addrs),
          n_display_(n_display),
          display_declared_(n_display > 0) {}

    void loop_once() {
        const uint32_t now = hal_.now_ms();
        if (!booted_) {
            boot(now);
            booted_ = true;
            last_action_ms_ = now;
            maybe_log_display_missing();
            if (state_ == AppState::OK) {
                take_reading(now);
            }
            return;
        }
        maybe_log_display_missing();
        if (state_ == AppState::FAULT_AMBIGUOUS_ADDRESS) {
            return;
        }
        if (state_ == AppState::FAULT_SENSOR_MISSING) {
            if (wrap_elapsed(now, last_action_ms_) >= backoff_ms_) {
                last_action_ms_ = now;
                const int hits = probe_sensor();
                if (hits > 1) {
                    enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, "AMBIGUOUS ADDR");
                    return;
                }
                if (hits == 1) {
                    hal_.log("RECOVERED");
                    log_boot();
                    state_ = AppState::OK;
                    consecutive_fails_ = 0;
                    backoff_ms_ = kBackoffInitialMs;
                    take_reading(now);
                    return;
                }
                backoff_ms_ *= 2;
                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;
            }
            return;
        }
        if (state_ == AppState::FAULT_SENSOR_READ) {
            if (wrap_elapsed(now, last_action_ms_) >= backoff_ms_) {
                last_action_ms_ = now;
                (void)hal_.bus_recover();
                const int hits = probe_sensor();
                if (hits > 1) {
                    enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, "AMBIGUOUS ADDR");
                    return;
                }
                if (hits == 1) {
                    take_reading(now);
                    if (state_ == AppState::OK) {
                        backoff_ms_ = kBackoffInitialMs;
                        return;
                    }
                }
                backoff_ms_ *= 2;
                if (backoff_ms_ > kBackoffCapMs) backoff_ms_ = kBackoffCapMs;
            }
            return;
        }
        if (wrap_elapsed(now, last_action_ms_) >= kReadPeriodMs) {
            last_action_ms_ = now;
            take_reading(now);
        }
    }

private:
    Hal& hal_;
    const uint8_t* sensor_addrs_;
    size_t n_sensor_;
    const uint8_t* display_addrs_;
    size_t n_display_;
    bool display_declared_;
    bool booted_ = false;
    bool display_ok_ = false;
    bool display_missing_logged_ = false;
    bool have_last_ = false;
    uint8_t sensor_addr_ = 0;
    uint8_t display_addr_ = 0;
    AppState state_ = AppState::OK;
    uint32_t last_action_ms_ = 0;
    uint32_t backoff_ms_ = kBackoffInitialMs;
    int consecutive_fails_ = 0;
    Reading last_{};

    int probe_sensor() {
        int hits = 0;
        uint8_t found = 0;
        for (size_t i = 0; i < n_sensor_; ++i) {
            const uint8_t addr = sensor_addrs_[i];
            if (hal_.sensor_begin(addr)) { // identity must match; do not pick the first address
                hits += 1;
                found = addr;
            }
        }
        if (hits == 1) {
            // A failed rebind must not turn an earlier probe into a usable device.
            if (!hal_.sensor_begin(found)) return 0;
            sensor_addr_ = found;
        }
        return hits;
    }

    void probe_display() {
        display_ok_ = false;
        if (!display_declared_) {
            return;
        }
        for (size_t i = 0; i < n_display_; ++i) {
            const uint8_t addr = display_addrs_[i];
            if (hal_.display_begin(addr)) {
                display_ok_ = true;
                display_addr_ = addr;
                return;
            }
        }
    }

    void maybe_log_display_missing() {
        if (display_declared_ && !display_ok_ && !display_missing_logged_) {
            hal_.log("DISPLAY MISSING");
            display_missing_logged_ = true;
        }
    }

    void log_boot() {
        char line[48];
        if (display_ok_) {
            std::snprintf(line, sizeof line, "BOOT sensor=0x%02X display=0x%02X", sensor_addr_, display_addr_);
        } else {
            std::snprintf(line, sizeof line, "BOOT sensor=0x%02X display=NONE", sensor_addr_);
        }
        hal_.log(line);
    }

    void log_state(uint32_t now, AppState state) {
        char line[48];
        std::snprintf(line, sizeof line, "T=%u STATE=%s", (unsigned)now, state_text(state));
        hal_.log(line);
    }

    void show_fault(const char* message) {
        if (display_ok_) {
            hal_.display_show(message, "", "", "");
        }
    }

    void show_reading(const char* headline) {
        if (!display_ok_) {
            return;
        }
        if (!have_last_) {
            hal_.display_show("NO DATA", "", "", "");
            return;
        }
        char l2[24];
        char l3[24];
        char l4[24];
        format_display_lines(last_, l2, l3, l4, sizeof l2);
        hal_.display_show(headline, l2, l3, l4);
    }

    void enter_fault(uint32_t now, AppState state, const char* display_message) {
        if (state_ != state) {
            state_ = state;
            log_state(now, state);
            show_fault(display_message);
        }
    }

    void boot(uint32_t now) {
        probe_display();
        const int hits = probe_sensor();
        if (hits > 1) {
            enter_fault(now, AppState::FAULT_AMBIGUOUS_ADDRESS, "AMBIGUOUS ADDR");
            return;
        }
        if (hits == 0) {
            enter_fault(now, AppState::FAULT_SENSOR_MISSING, "SENSOR MISSING");
            backoff_ms_ = kBackoffInitialMs;
            return;
        }
        state_ = AppState::OK;
        log_boot();
    }

    void take_reading(uint32_t now) {
        Reading reading{};
        const bool ok = hal_.sensor_read(reading) && reading_is_plausible(reading);
        if (!ok) {
            consecutive_fails_ += 1;
            if (consecutive_fails_ >= kReadFailThreshold) {
                if (state_ != AppState::FAULT_SENSOR_READ) {
                    state_ = AppState::FAULT_SENSOR_READ;
                    log_state(now, AppState::FAULT_SENSOR_READ);
                    (void)hal_.bus_recover();
                    (void)hal_.sensor_begin(sensor_addr_);
                    show_fault("SENSOR READ FAULT");
                    backoff_ms_ = kBackoffInitialMs;
                }
                return;
            }
            state_ = AppState::STALE;
            log_state(now, AppState::STALE);
            show_reading("STATE STALE");
            return;
        }
        const bool was_fault = state_ == AppState::FAULT_SENSOR_READ;
        consecutive_fails_ = 0;
        last_ = reading;
        have_last_ = true;
        state_ = AppState::OK;
        if (was_fault) {
            hal_.log("RECOVERED");
        }
        char line[96];
        format_ok_line(line, sizeof line, now, reading);
        hal_.log(line);
        show_reading("STATE OK");
    }
};
