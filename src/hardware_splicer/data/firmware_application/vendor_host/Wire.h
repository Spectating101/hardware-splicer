#pragma once
// Host model of arduino-esp32 2.0.17 TwoWire for the calls the libraries use.
// Source read: Wire.h / Wire.cpp tag 2.0.17. Not the ESP32 I2C HAL, not silicon.

#include "Arduino.h"
#include "Stream.h"
#include <vector>

#ifndef I2C_BUFFER_LENGTH
#define I2C_BUFFER_LENGTH 128
#endif

#define WIRE_HAS_BUFFER_SIZE 1
#define WIRE_HAS_END 1

enum class I2cDir : uint8_t { Write = 0, Read = 1 };

struct I2cTransaction {
    uint8_t address = 0;
    I2cDir direction = I2cDir::Write;
    std::vector<uint8_t> bytes;
    uint8_t result = 0;  // endTransmission codes, or 0 for a completed read
    bool stop = true;
    bool bare_probe = false;  // beginTransmission + endTransmission with 0 payload
};

struct WireBeginCall {
    int sda_arg = -1;
    int scl_arg = -1;
    uint32_t freq_arg = 0;
    int sda_in_effect = -1;
    int scl_in_effect = -1;
    bool default_args = false;
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
    int next_write_result = -1;  // if >= 0, next endTransmission(true) returns this
    int remaining_read_fails = 0;
    int remaining_data_nacks = 0;
    int data_nack_skip = 0;  // data writes let through before remaining_data_nacks starts NACKing

    void attach(uint8_t addr, I2cDevice *dev);
    void detach(uint8_t addr);
    void clear_log();
    I2cDevice *at(uint8_t addr) const;
};

extern I2cBus g_i2c_bus;

class TwoWire : public Stream {
public:
    explicit TwoWire(uint8_t bus_num);
    bool begin(int sda, int scl, uint32_t frequency = 0);
    inline bool begin() { return begin(-1, -1, static_cast<uint32_t>(0)); }
    bool end();
    bool setClock(uint32_t frequency);
    uint32_t getClock() const { return clock_hz_; }
    void setTimeOut(uint16_t timeOutMillis);
    uint16_t getTimeOut() const { return time_out_ms_; }

    void beginTransmission(uint16_t address);
    void beginTransmission(uint8_t address);
    void beginTransmission(int address);
    uint8_t endTransmission(bool sendStop);
    uint8_t endTransmission(void) { return endTransmission(true); }

    size_t requestFrom(uint16_t address, size_t size, bool sendStop);
    uint8_t requestFrom(uint8_t address, uint8_t size, uint8_t sendStop);
    uint8_t requestFrom(uint8_t address, uint8_t size);
    uint8_t requestFrom(int address, int size);
    uint8_t requestFrom(int address, int size, int sendStop);

    size_t write(uint8_t data) override;
    size_t write(const uint8_t *data, size_t quantity) override;
    int available() override;
    int read() override;
    int peek() override;
    void flush() override;

    int sda_pin() const { return sda_; }
    int scl_pin() const { return scl_; }
    bool inited() const { return inited_; }
    const std::vector<WireBeginCall> &begin_calls() const { return begin_calls_; }
    void reset_model();

private:
    bool init_pins(int sda_pin, int scl_pin);
    uint8_t do_write(uint8_t address, const uint8_t *data, size_t len, bool stop);
    size_t do_read(uint8_t address, uint8_t *data, size_t len);

    uint8_t num_;
    int sda_ = -1;
    int scl_ = -1;
    bool inited_ = false;
    uint32_t clock_hz_ = 0;
    uint16_t time_out_ms_ = 50;
    bool non_stop_ = false;
    uint16_t tx_address_ = 0;
    std::vector<uint8_t> tx_buffer_;
    std::vector<uint8_t> rx_buffer_;
    size_t rx_index_ = 0;
    std::vector<WireBeginCall> begin_calls_;
};

extern TwoWire Wire;
extern TwoWire Wire1;
