#pragma once
// Register-less model of the Rohm BH1750FVI, written from the datasheet (2009.04 Rev.B). Not silicon.
//
//   p.4   initial state is power down; the Power On command may be omitted before a measurement command
//   p.5   instruction set: 0x00 power down, 0x01 power on, 0x07 reset, 0x10/0x11/0x13 continuous,
//         0x20/0x21/0x23 one time. "Don't input the other opecode."
//   p.2   a measurement takes at most 180 ms (H-resolution) or 24 ms (L-resolution)
//   p.5   the data register resets to 0, and one-time modes return to power down after measuring
//   p.7   the result is 16 bits, high byte first
//
// The model completes a measurement exactly at the datasheet's stated maximum, so it behaves as the slowest
// compliant device: a read before that returns the data register's previous value (0 after power-up).

#include "Wire.h"
#include <cstdint>

class Bh1750Model final : public I2cDevice {
public:
    explicit Bh1750Model(uint8_t addr);
    void plug(uint16_t raw_counts);  // powers the chip: power-down state, data register 0
    void unplug();
    void set_raw(uint16_t raw_counts) { raw_ = raw_counts; }
    bool present() const override { return present_; }
    uint8_t address() const { return addr_; }
    int measurement_commands() const { return measurement_commands_; }
    int unknown_opcodes() const { return unknown_opcodes_; }

    uint8_t on_write(const uint8_t *data, size_t len) override;
    size_t on_read(uint8_t *data, size_t len) override;

private:
    enum class State : uint8_t { PowerDown, PowerOn, Measuring };
    void settle();

    uint8_t addr_;
    bool present_ = false;
    State state_ = State::PowerDown;
    bool continuous_ = false;
    uint32_t window_ms_ = 180;
    uint32_t started_ms_ = 0;
    uint16_t raw_ = 0;     // what the light level would read once a measurement completes
    uint16_t data_reg_ = 0;  // what the chip returns
    int measurement_commands_ = 0;
    int unknown_opcodes_ = 0;
};
