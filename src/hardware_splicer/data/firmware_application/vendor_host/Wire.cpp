#include "Wire.h"
#include <algorithm>
#include <cstring>

I2cBus g_i2c_bus;
TwoWire Wire(0);
TwoWire Wire1(1);

void I2cBus::attach(uint8_t addr, I2cDevice *dev) { device[addr & 0x7f] = dev; }
void I2cBus::detach(uint8_t addr) { device[addr & 0x7f] = nullptr; }
void I2cBus::clear_log() { log.clear(); }
I2cDevice *I2cBus::at(uint8_t addr) const { return device[addr & 0x7f]; }

TwoWire::TwoWire(uint8_t bus_num) : num_(bus_num & 1) {
    tx_buffer_.reserve(I2C_BUFFER_LENGTH);
    rx_buffer_.reserve(I2C_BUFFER_LENGTH);
}

void TwoWire::reset_model() {
    sda_ = -1;
    scl_ = -1;
    inited_ = false;
    clock_hz_ = 0;
    time_out_ms_ = 50;
    non_stop_ = false;
    tx_address_ = 0;
    tx_buffer_.clear();
    rx_buffer_.clear();
    rx_index_ = 0;
    begin_calls_.clear();
}

bool TwoWire::init_pins(int sda_pin, int scl_pin) {
    // Wire.cpp 2.0.17 initPins: sdaPin < 0 means default param. If sda_ is still
    // -1, use SDA (pins_arduino.h); else reuse the prior pin.
    if (sda_pin < 0) {
        if (num_ == 0) {
            sda_pin = (sda_ == -1) ? static_cast<int>(SDA) : sda_;
        } else {
            return false;
        }
    }
    if (scl_pin < 0) {
        if (num_ == 0) {
            scl_pin = (scl_ == -1) ? static_cast<int>(SCL) : scl_;
        } else {
            return false;
        }
    }
    sda_ = sda_pin;
    scl_ = scl_pin;
    return true;
}

bool TwoWire::begin(int sda, int scl, uint32_t frequency) {
    WireBeginCall rec;
    rec.sda_arg = sda;
    rec.scl_arg = scl;
    rec.freq_arg = frequency;
    rec.default_args = (sda < 0 && scl < 0);
    rec.bus_was_inited = inited_;
    // Wire.cpp 2.0.17 master begin(): if already inited, log warning and return
    // true without calling initPins or i2cInit.
    if (inited_) {
        rec.sda_in_effect = sda_;
        rec.scl_in_effect = scl_;
        rec.actually_inited = false;
        begin_calls_.push_back(rec);
        return true;
    }
    if (!init_pins(sda, scl)) {
        rec.sda_in_effect = sda_;
        rec.scl_in_effect = scl_;
        begin_calls_.push_back(rec);
        return false;
    }
    inited_ = true;
    clock_hz_ = frequency == 0 ? 100000 : frequency;
    rec.sda_in_effect = sda_;
    rec.scl_in_effect = scl_;
    rec.actually_inited = true;
    begin_calls_.push_back(rec);
    return true;
}

bool TwoWire::end() {
    // Wire.cpp 2.0.17 end(): i2cDeinit + freeWireBuffer. Does not reset sda/scl.
    inited_ = false;
    non_stop_ = false;
    tx_buffer_.clear();
    rx_buffer_.clear();
    rx_index_ = 0;
    return true;
}

bool TwoWire::setClock(uint32_t frequency) {
    clock_hz_ = frequency;
    return true;
}

void TwoWire::setTimeOut(uint16_t timeOutMillis) { time_out_ms_ = timeOutMillis; }

void TwoWire::beginTransmission(uint16_t address) {
    non_stop_ = false;
    tx_address_ = address;
    tx_buffer_.clear();
}

void TwoWire::beginTransmission(uint8_t address) { beginTransmission(static_cast<uint16_t>(address)); }
void TwoWire::beginTransmission(int address) { beginTransmission(static_cast<uint16_t>(address)); }

uint8_t TwoWire::do_write(uint8_t address, const uint8_t *data, size_t len, bool stop) {
    I2cTransaction tx;
    tx.address = address;
    tx.direction = I2cDir::Write;
    tx.bytes.assign(data, data + len);
    tx.stop = stop;
    tx.bare_probe = (len == 0);
    I2cDevice *dev = g_i2c_bus.at(address);
    uint8_t result = 0;
    if (g_i2c_bus.next_write_result >= 0) {
        result = static_cast<uint8_t>(g_i2c_bus.next_write_result);
        g_i2c_bus.next_write_result = -1;
    } else if (g_i2c_bus.remaining_data_nacks > 0 && len > 0 && g_i2c_bus.data_nack_skip > 0) {
        g_i2c_bus.data_nack_skip -= 1;
        result = (!dev || !dev->present()) ? 2 : dev->on_write(data, len);
    } else if (g_i2c_bus.remaining_data_nacks > 0 && len > 0) {
        g_i2c_bus.remaining_data_nacks -= 1;
        result = 3;
    } else if (!dev || !dev->present()) {
        result = 2;  // ESP_FAIL → 2 NACK on address (Wire.cpp endTransmission)
    } else {
        result = dev->on_write(data, len);
    }
    tx.result = result;
    g_i2c_bus.log.push_back(tx);
    return result;
}

size_t TwoWire::do_read(uint8_t address, uint8_t *data, size_t len) {
    I2cTransaction tx;
    tx.address = address;
    tx.direction = I2cDir::Read;
    tx.stop = true;
    I2cDevice *dev = g_i2c_bus.at(address);
    size_t got = 0;
    if (g_i2c_bus.remaining_read_fails > 0) {
        g_i2c_bus.remaining_read_fails -= 1;
        got = 0;
        tx.result = 3;
    } else if (!dev || !dev->present()) {
        got = 0;
        tx.result = 2;
    } else {
        got = dev->on_read(data, len);
        tx.bytes.assign(data, data + got);
        tx.result = 0;
    }
    g_i2c_bus.log.push_back(tx);
    return got;
}

uint8_t TwoWire::endTransmission(bool sendStop) {
    // Wire.cpp 2.0.17 endTransmission() 447-450: the buffers exist only between begin() and end(); without them
    // "NULL TX buffer pointer" is logged and 4 returned. Nothing reaches the bus.
    if (!inited_) {
        tx_buffer_.clear();
        return 4;
    }
    // Wire.cpp 2.0.17: sendStop false marks nonStop and returns 0 without i2cWrite.
    if (!sendStop) {
        non_stop_ = true;
        return 0;
    }
    const uint8_t result = do_write(static_cast<uint8_t>(tx_address_), tx_buffer_.data(), tx_buffer_.size(), true);
    tx_buffer_.clear();
    return result;
}

size_t TwoWire::requestFrom(uint16_t address, size_t size, bool sendStop) {
    (void)sendStop;
    // Wire.cpp 2.0.17 requestFrom() 480-483: no buffers (never begun, or ended) returns 0.
    if (!inited_) {
        rx_buffer_.clear();
        return 0;
    }
    rx_buffer_.assign(size, 0);
    rx_index_ = 0;
    size_t got = 0;
    if (non_stop_) {
        // Repeated start: i2cWriteReadNonStop with the pending tx buffer (Wire.cpp).
        non_stop_ = false;
        uint8_t wr = do_write(static_cast<uint8_t>(address), tx_buffer_.data(), tx_buffer_.size(), false);
        tx_buffer_.clear();
        if (wr != 0) {
            rx_buffer_.clear();
            return 0;
        }
        got = do_read(static_cast<uint8_t>(address), rx_buffer_.data(), size);
    } else {
        got = do_read(static_cast<uint8_t>(address), rx_buffer_.data(), size);
    }
    rx_buffer_.resize(got);
    return got;
}

uint8_t TwoWire::requestFrom(uint8_t address, uint8_t size, uint8_t sendStop) {
    return static_cast<uint8_t>(requestFrom(static_cast<uint16_t>(address), static_cast<size_t>(size), sendStop != 0));
}
uint8_t TwoWire::requestFrom(uint8_t address, uint8_t size) { return requestFrom(address, size, static_cast<uint8_t>(1)); }
uint8_t TwoWire::requestFrom(int address, int size) {
    return requestFrom(static_cast<uint8_t>(address), static_cast<uint8_t>(size));
}
uint8_t TwoWire::requestFrom(int address, int size, int sendStop) {
    return requestFrom(static_cast<uint8_t>(address), static_cast<uint8_t>(size), static_cast<uint8_t>(sendStop));
}

size_t TwoWire::write(uint8_t data) {
    if (!inited_) return 0;  // Wire.cpp 2.0.17 write() 525-528: NULL TX buffer pointer
    if (tx_buffer_.size() >= I2C_BUFFER_LENGTH) return 0;
    tx_buffer_.push_back(data);
    return 1;
}

size_t TwoWire::write(const uint8_t *data, size_t quantity) {
    size_t n = 0;
    for (; n < quantity; ++n) {
        if (!write(data[n])) break;
    }
    return n;
}

int TwoWire::available() { return static_cast<int>(rx_buffer_.size() - rx_index_); }

int TwoWire::read() {
    if (rx_index_ >= rx_buffer_.size()) return -1;
    return rx_buffer_[rx_index_++];
}

int TwoWire::peek() {
    if (rx_index_ >= rx_buffer_.size()) return -1;
    return rx_buffer_[rx_index_];
}

void TwoWire::flush() {
    rx_index_ = 0;
    rx_buffer_.clear();
    tx_buffer_.clear();
}
