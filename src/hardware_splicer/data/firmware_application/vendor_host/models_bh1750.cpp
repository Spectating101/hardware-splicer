#include "models_bh1750.h"
#include "Arduino.h"

Bh1750Model::Bh1750Model(uint8_t addr) : addr_(addr & 0x7f) {}

void Bh1750Model::plug(uint16_t raw_counts) {
    present_ = true;
    raw_ = raw_counts;
    data_reg_ = 0;  // p.5: the data register's reset value is 0
    state_ = State::PowerDown;  // p.4
    measurement_commands_ = 0;
    unknown_opcodes_ = 0;
}

void Bh1750Model::unplug() {
    present_ = false;
    state_ = State::PowerDown;
    data_reg_ = 0;
}

// Bring the data register up to date with the clock: a finished measurement replaces it.
void Bh1750Model::settle() {
    if (state_ != State::Measuring) return;
    if (millis() - started_ms_ < window_ms_) return;
    data_reg_ = raw_;
    if (continuous_) {
        started_ms_ = millis();  // the next conversion starts straight away
    } else {
        state_ = State::PowerDown;  // p.5: one-time modes power down after measuring
    }
}

uint8_t Bh1750Model::on_write(const uint8_t *data, size_t len) {
    if (!present_) return 2;
    if (len == 0) return 0;  // address-only presence probe
    settle();
    if (len != 1) {
        unknown_opcodes_ += 1;
        return 3;
    }
    const uint8_t opcode = data[0];
    switch (opcode) {
        case 0x00:
            state_ = State::PowerDown;
            return 0;
        case 0x01:
            state_ = State::PowerOn;
            return 0;
        case 0x07:
            if (state_ != State::PowerDown) data_reg_ = 0;  // p.5: not acceptable in power down
            return 0;
        case 0x10:
        case 0x11:
        case 0x20:
        case 0x21:
            window_ms_ = 180;
            break;
        case 0x13:
        case 0x23:
            window_ms_ = 24;
            break;
        default:
            unknown_opcodes_ += 1;
            return 3;  // "Don't input the other opecode"
    }
    continuous_ = (opcode & 0xF0) == 0x10;
    state_ = State::Measuring;
    started_ms_ = millis();
    measurement_commands_ += 1;
    return 0;
}

size_t Bh1750Model::on_read(uint8_t *data, size_t len) {
    if (!present_) return 0;
    settle();
    for (size_t i = 0; i < len; ++i) {
        if (i == 0) data[i] = static_cast<uint8_t>(data_reg_ >> 8);  // high byte first
        else if (i == 1) data[i] = static_cast<uint8_t>(data_reg_ & 0xFF);
        else data[i] = 0;
    }
    return len;
}
