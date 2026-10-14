#pragma once
// Host model of earlephilhower/arduino-pico TwoWire, libraries/Wire at commit fd65f6d4, for the calls the libraries
// and the adapter use. Master mode only. Not the RP2040 I2C peripheral, not the pico-sdk, not silicon.
// Drafted by Gemini 4 Argon from that source; reviewed and integrated by Hardware-Splicer.

#include "Arduino.h"
#include "Stream.h"
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#define WIRE_HAS_END 1
#define WIRE_HAS_BUFFER_SIZE 1

#ifndef WIRE_BUFFER_SIZE
#define WIRE_BUFFER_SIZE 256
#endif
#ifndef WIRE_BUFFER_SIZE_MIN
#define WIRE_BUFFER_SIZE_MIN 32
#endif

// variants/rpipico/pins_arduino.h
#ifndef PIN_WIRE0_SDA
#define PIN_WIRE0_SDA (4u)
#endif
#ifndef PIN_WIRE0_SCL
#define PIN_WIRE0_SCL (5u)
#endif
#ifndef PIN_WIRE1_SDA
#define PIN_WIRE1_SDA (26u)
#endif
#ifndef PIN_WIRE1_SCL
#define PIN_WIRE1_SCL (27u)
#endif

// The controller the plan wires the devices to (board_config.h). The other controller's bus has no devices.
#ifndef HS_PLANNED_I2C
#define HS_PLANNED_I2C 0
#endif

#ifndef __PIN_SIZE_T_DEFINED
#define __PIN_SIZE_T_DEFINED
typedef uint8_t pin_size_t;
#endif

struct i2c_inst {
    uint8_t index;
};
using i2c_inst_t = i2c_inst;

extern i2c_inst_t *const i2c0;
extern i2c_inst_t *const i2c1;

inline uint8_t i2c_hw_index(const i2c_inst_t *i2c) { return i2c ? i2c->index : 0; }

// The real core calls panic(), which halts. The model records the message and throws, so a scenario fails with it.
class HsPanic : public std::runtime_error {
public:
    explicit HsPanic(const std::string &msg) : std::runtime_error(msg) {}
};

std::vector<std::string> &wire_panics();

// Shared with the ESP32 model: device models and harnesses use these unchanged.
enum class I2cDir : uint8_t { Write = 0, Read = 1 };

struct I2cTransaction {
    uint8_t address = 0;
    I2cDir direction = I2cDir::Write;
    std::vector<uint8_t> bytes;
    uint8_t result = 0;  // endTransmission codes, or 0 for a completed read
    bool stop = true;
    bool bare_probe = false;  // beginTransmission + endTransmission with 0 payload
    uint32_t clock_hz = 0;    // model-only: the clock the transaction ran at
};

struct WireBeginCall {
    int sda_arg = -1;
    int scl_arg = -1;
    uint32_t freq_arg = 0;
    int sda_in_effect = -1;
    int scl_in_effect = -1;
    bool default_args = false;  // RP2040: neither setSDA nor setSCL was called on this instance
    bool bus_was_inited = false;
    bool actually_inited = false;
};

class I2cDevice {
public:
    virtual ~I2cDevice() = default;
    virtual bool present() const = 0;
    virtual uint8_t on_write(const uint8_t *data, size_t len) = 0;
    virtual size_t on_read(uint8_t *data, size_t len) = 0;
};

class I2cBus {
public:
    I2cDevice *device[128]{};
    std::vector<I2cTransaction> log;
    int next_write_result = -1;  // if >= 0, next endTransmission returns this (an ESP32-style 3 becomes 4)
    int remaining_read_fails = 0;
    int remaining_data_nacks = 0;
    int data_nack_skip = 0;  // data writes let through before remaining_data_nacks starts NACKing

    void attach(uint8_t addr, I2cDevice *dev);
    void detach(uint8_t addr);
    void clear_log();
    I2cDevice *at(uint8_t addr) const;
};

extern I2cBus g_i2c_bus;        // the planned controller's bus
extern I2cBus g_i2c_bus_other;  // the other controller's bus: anything logged here went to the wrong controller
extern int g_hs_planned_i2c;

class TwoWire : public Stream {
public:
    TwoWire(i2c_inst_t *i2c, pin_size_t sda, pin_size_t scl);
    ~TwoWire() override;

    void begin();
    void begin(uint8_t address);
    void end();

    bool setSDA(pin_size_t sda);
    bool setSCL(pin_size_t scl);

    void setClock(uint32_t freqHz);

    void beginTransmission(uint8_t address);
    uint8_t endTransmission(bool stopBit);
    uint8_t endTransmission(void);

    size_t requestFrom(uint8_t address, size_t quantity, bool stopBit);
    size_t requestFrom(uint8_t address, size_t quantity);

    size_t write(uint8_t data) override;
    size_t write(const uint8_t *data, size_t quantity) override;

    int available(void) override;
    int read(void) override;
    int peek(void) override;
    void flush(void) override;

    inline size_t write(unsigned long n) { return write((uint8_t)n); }
    inline size_t write(long n) { return write((uint8_t)n); }
    inline size_t write(unsigned int n) { return write((uint8_t)n); }
    inline size_t write(int n) { return write((uint8_t)n); }

    void setTimeout(uint32_t timeout = 25, bool reset_with_timeout = false);
    bool getTimeoutFlag(void);
    void clearTimeoutFlag(void);

    size_t setBufferSize(size_t bSize);

    // Model-only introspection for the harness.
    int sda_pin() const { return static_cast<int>(_sda); }
    int scl_pin() const { return static_cast<int>(_scl); }
    bool inited() const { return _running; }
    uint32_t getClock() const { return static_cast<uint32_t>(_clkHz); }
    uint32_t timeout_ms() const { return _timeout; }
    const std::vector<WireBeginCall> &begin_calls() const { return begin_calls_; }
    void reset_model();

private:
    I2cBus &bus() const;
    void _handleTimeout(bool reset);

    i2c_inst_t *_i2c;
    pin_size_t _sda;
    pin_size_t _scl;
    pin_size_t _default_sda;
    pin_size_t _default_scl;
    bool _sda_set = false;
    bool _scl_set = false;
    int _clkHz;

    bool _running;
    bool _slave;
    uint8_t _addr;
    bool _txBegun;

    uint32_t _timeout;
    bool _timeoutFlag;
    bool _reset_with_timeout;

    uint8_t *_buff;
    size_t _buffSize;
    int _buffLen;
    int _buffOff;

    static const uint32_t TWI_CLOCK = 100000;

    std::vector<WireBeginCall> begin_calls_;
};

extern TwoWire Wire;
extern TwoWire Wire1;
