#pragma once
// Host Arduino shim for compiling Adafruit libraries + main.cpp.
// Clock is simulated: delay(ms) advances it; nothing sleeps. Not ESP32 timing.

#include <cmath>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define ARDUINO 10812
// A package for a board other than the ESP32 carries board_config.h (HS_RP2040, the planned I2C controller and pins).
#if __has_include("board_config.h")
#include "board_config.h"
#endif
#ifdef HS_RP2040
// The Raspberry Pi Pico lane: the libraries see the RP2040 core's architecture macros, as under PlatformIO's board = pico.
#ifndef ARDUINO_ARCH_RP2040
#define ARDUINO_ARCH_RP2040
#endif
#ifndef ARDUINO_RASPBERRY_PI_PICO
#define ARDUINO_RASPBERRY_PI_PICO
#endif
#define ARDUINO_BOARD "pico"
// ArduinoCore-API api/Common.h, which the RP2040 core's Arduino.h includes.
typedef enum { LSBFIRST = 0, MSBFIRST = 1 } BitOrder;
#else
#ifndef ESP32
#define ESP32
#endif
#ifndef ARDUINO_ARCH_ESP32
#define ARDUINO_ARCH_ESP32
#endif
#define ARDUINO_BOARD "esp32dev"
#endif

#define HIGH 0x1
#define LOW 0x0
#define INPUT 0x0
#define OUTPUT 0x1
#define INPUT_PULLUP 0x2
#define INPUT_PULLDOWN 0x3
#ifdef HS_RP2040
#define LED_BUILTIN 25  // variants/rpipico/pins_arduino.h PIN_LED
#else
#define LED_BUILTIN 2
#endif

#define PI 3.1415926535897932384626433832795
#define DEG_TO_RAD 0.017453292519943295769236907684886
#define RAD_TO_DEG 57.295779513082320876798154814105

using boolean = bool;
using byte = uint8_t;
using word = uint16_t;

#ifndef min
template <typename T, typename U>
constexpr auto min(T a, U b) -> decltype(a < b ? a : b) {
    return a < b ? a : b;
}
#endif
#ifndef max
template <typename T, typename U>
constexpr auto max(T a, U b) -> decltype(a > b ? a : b) {
    return a > b ? a : b;
}
#endif

template <typename T>
constexpr T abs_t(T x) {
    return x < 0 ? -x : x;
}
#ifndef abs
#define abs(x) abs_t(x)
#endif

#define bitRead(value, bit) (((value) >> (bit)) & 0x01)
#define bitSet(value, bit) ((value) |= (1UL << (bit)))
#define bitClear(value, bit) ((value) &= ~(1UL << (bit)))
#define bitWrite(value, bit, bitvalue) ((bitvalue) ? bitSet(value, bit) : bitClear(value, bit))
#define bit(b) (1UL << (b))
#define lowByte(w) ((uint8_t)((w) & 0xff))
#define highByte(w) ((uint8_t)((w) >> 8))
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))
#define sq(x) ((x) * (x))
inline float radians(float deg) { return deg * DEG_TO_RAD; }
inline float degrees(float rad) { return rad * RAD_TO_DEG; }

#define F(s) (s)
#define FPSTR(s) (s)

inline void yield() {}

#ifdef HS_RP2040
// variants/rpipico/pins_arduino.h in arduino-pico at commit fd65f6d4: PIN_WIRE0_* and PIN_SPI0_*
static const uint8_t SDA = 4;
static const uint8_t SCL = 5;
static const uint8_t SS = 17;
static const uint8_t MOSI = 19;
static const uint8_t MISO = 16;
static const uint8_t SCK = 18;
#else
// variants/esp32/pins_arduino.h in arduino-esp32 2.0.17
static const uint8_t SDA = 21;
static const uint8_t SCL = 22;
static const uint8_t SS = 5;
static const uint8_t MOSI = 23;
static const uint8_t MISO = 19;
static const uint8_t SCK = 18;
#endif

unsigned long millis();
unsigned long micros();
void delay(unsigned long ms);
void delayMicroseconds(unsigned int us);
void pinMode(uint8_t pin, uint8_t mode);
void digitalWrite(uint8_t pin, uint8_t val);
int digitalRead(uint8_t pin);

// FAST_PINIO stand-ins used only if Adafruit_SPIDevice's SW-SPI path is compiled.
inline uint32_t *portOutputRegister(uint8_t) {
    static uint32_t dummy;
    return &dummy;
}
inline uint32_t *portInputRegister(uint8_t) {
    static uint32_t dummy;
    return &dummy;
}
inline uint8_t digitalPinToPort(uint8_t) { return 0; }
inline uint32_t digitalPinToBitMask(uint8_t) { return 1; }

#include "WString.h"
#include "Print.h"
#include "Stream.h"
#include "pgmspace.h"

class HardwareSerial : public Stream {
public:
    void begin(unsigned long baud);
    void end() {}
    operator bool() const { return true; }
    size_t write(uint8_t ch) override;
    int available() override { return 0; }
    int read() override { return -1; }
    int peek() override { return -1; }
    const std::vector<std::string> &lines() const { return lines_; }
    const std::string &raw() const { return raw_; }
    void clear_capture();

private:
    std::string raw_;
    std::string current_;
    std::vector<std::string> lines_;
};

extern HardwareSerial Serial;

struct SimClock {
    uint64_t us = 0;
    uint64_t loop_start_us = 0;
    bool in_loop = false;
    bool watchdog_fired = false;
    uint64_t watchdog_limit_us = 5000ull * 1000ull;
};

extern SimClock g_sim_clock;
void sim_advance_ms(uint32_t ms);
uint32_t sim_loop_elapsed_ms();
void sim_begin_loop();
void sim_end_loop();

struct WatchdogAbort {};
